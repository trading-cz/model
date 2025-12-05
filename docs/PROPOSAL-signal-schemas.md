# Kafka Trading Workflow - Schema Proposal

## Analysis Questions

### 1. Should RAW_SIGNALS and CLEAN_SIGNALS be separate topics?

**Recommendation: YES - Keep separate topics**

| Aspect | Separate Topics | Single Topic with Flag |
|--------|-----------------|------------------------|
| **Consumer isolation** | ✅ Portfolio Manager only consumes CLEAN_SIGNALS | ❌ Must filter in every consumer |
| **Retention policies** | ✅ Can retain CLEAN longer, purge RAW faster | ❌ Same retention for all |
| **Replay/debugging** | ✅ Can replay RAW through Gatekeeper again | ❌ Mixed data |
| **Scaling** | ✅ Independent partition counts | ❌ Shared partitioning |
| **Schema evolution** | ✅ Can evolve independently | ❌ Coupled |

**However**, the schemas should be nearly identical - CLEAN_SIGNALS just adds validation metadata.

---

## 2. Proposed Topic Structure

```
Topics:
├── signal.raw              # Strategy → Signal Gatekeeper
├── signal.clean            # Signal Gatekeeper → Portfolio Manager  
├── order.request           # Portfolio Manager → Executor
└── order.execution         # Executor → Portfolio Manager, DB
```

**Naming convention**: `<domain>.<stage>` (lowercase, dot-separated)

---

## 3. Proposed Schemas

### Common Key Schema (reuse across all topics)

All trading messages share the same key structure for correlation:

```
schemas/kafka/common/key.avsc  (already exists)
```

### RAW_SIGNAL Value Schema

Two options:

#### Option A: Polymorphic with `type` field (your current approach)

```json
{
  "type": "record",
  "name": "RawSignalValue",
  "namespace": "cz.trading.model.kafka.signal.raw",
  "doc": "Raw trading signal from strategy",
  "fields": [
    {
      "name": "signal_type",
      "type": {
        "type": "enum",
        "name": "SignalType",
        "symbols": ["EQUITY", "FUTURE", "OPTION", "CRYPTO", "FX"]
      },
      "doc": "Asset class of the signal"
    },
    {
      "name": "instrument",
      "type": {
        "type": "record",
        "name": "Instrument",
        "fields": [
          {"name": "symbol", "type": "string", "doc": "Ticker symbol (e.g., NVDA, ES, BTC)"},
          {"name": "exchange", "type": ["null", "string"], "default": null, "doc": "Exchange code (e.g., NASDAQ, CME)"},
          {"name": "currency", "type": "string", "default": "USD", "doc": "Currency code"},
          {"name": "figi", "type": ["null", "string"], "default": null, "doc": "OpenFIGI identifier"},
          {"name": "expiry_month", "type": ["null", "string"], "default": null, "doc": "Futures: expiry month code (F,G,H,J,K,M,N,Q,U,V,X,Z)"},
          {"name": "expiry_year", "type": ["null", "int"], "default": null, "doc": "Futures: expiry year"},
          {"name": "multiplier", "type": ["null", "double"], "default": null, "doc": "Futures: contract multiplier"},
          {"name": "option_type", "type": ["null", {"type": "enum", "name": "OptionType", "symbols": ["CALL", "PUT"]}], "default": null},
          {"name": "strike", "type": ["null", "double"], "default": null, "doc": "Options: strike price"},
          {"name": "expiry_date", "type": ["null", {"type": "string", "logicalType": "date"}], "default": null, "doc": "Options: expiry date"},
          {"name": "style", "type": ["null", {"type": "enum", "name": "OptionStyle", "symbols": ["AMERICAN", "EUROPEAN"]}], "default": null}
        ]
      }
    },
    {
      "name": "signal_logic",
      "type": {
        "type": "record",
        "name": "SignalLogic",
        "fields": [
          {
            "name": "action",
            "type": {"type": "enum", "name": "SignalAction", "symbols": ["LONG", "SHORT", "FLAT", "CLOSE"]},
            "doc": "Signal direction"
          },
          {
            "name": "strength",
            "type": "double",
            "doc": "Conviction level 0.0 to 1.0"
          },
          {
            "name": "horizon",
            "type": {"type": "enum", "name": "SignalHorizon", "symbols": ["INTRA_1M", "INTRA_5M", "INTRA_15M", "SWING_D", "TREND_W"]},
            "doc": "Expected holding period"
          }
        ]
      }
    },
    {
      "name": "metadata",
      "type": ["null", {"type": "map", "values": "string"}],
      "default": null,
      "doc": "Optional key-value metadata for debugging (current_price, ref_indicator, regime_detected)"
    }
  ]
}
```

#### Option B: Separate topics per asset class

```
signal.raw.equity
signal.raw.future
signal.raw.option
```

Each with a simpler, dedicated schema. **Pros**: Cleaner schemas, easier evolution. **Cons**: More topics to manage.

**Recommendation**: Start with **Option A** (single topic, polymorphic) - you can split later if needed.

---

### CLEAN_SIGNAL Value Schema

Extends RAW_SIGNAL with validation results:

```json
{
  "type": "record",
  "name": "CleanSignalValue",
  "namespace": "cz.trading.model.kafka.signal.clean",
  "doc": "Validated trading signal after gatekeeper checks",
  "fields": [
    {
      "name": "raw_signal",
      "type": "cz.trading.model.kafka.signal.raw.RawSignalValue",
      "doc": "Original raw signal (embedded)"
    },
    {
      "name": "validation",
      "type": {
        "type": "record",
        "name": "ValidationResult",
        "fields": [
          {"name": "validated_at", "type": {"type": "long", "logicalType": "timestamp-millis"}},
          {"name": "gatekeeper_id", "type": "string", "doc": "Which gatekeeper instance validated"},
          {"name": "checks_passed", "type": {"type": "array", "items": "string"}, "doc": "List of passed checks"},
          {"name": "market_open", "type": "boolean"},
          {"name": "data_freshness_ms", "type": "long", "doc": "Age of data at validation time"}
        ]
      }
    }
  ]
}
```

---

## 4. File Structure

```
schemas/
└── kafka/
    ├── common/
    │   └── key.avsc                    # Shared key (existing)
    ├── signal/
    │   ├── raw/
    │   │   └── value.avsc              # RawSignalValue
    │   └── clean/
    │       └── value.avsc              # CleanSignalValue
    ├── order/
    │   ├── request/
    │   │   └── value.avsc              # OrderRequestValue
    │   └── execution/
    │       └── value.avsc              # ExecutionReportValue
    └── enums/
        └── common.avsc                 # Shared enums (optional)
```

---

## 5. Key Questions for You

1. **Metadata field**: Keep as `map<string, string>` (flexible) or define explicit fields?
   - Flexible: easier to add debug info
   - Explicit: better type safety, schema evolution

2. **FIGI vs Symbol**: Is FIGI lookup done at signal time or later?

3. **Price in signal**: Should `current_price` be a proper field or stay in metadata?
   - If Portfolio Manager uses it → make it explicit
   - If just for logging → keep in metadata

4. **Rejected signals**: Should Signal Gatekeeper produce to a `signal.rejected` topic for debugging?

---

## 6. Next Steps

1. Review this proposal
2. Decide on Option A vs B (polymorphic vs separate topics)
3. I'll create the `.avsc` files in `schemas/kafka/`
4. Test generation with `dc-avro generate-model --path ... --model-type pydantic`
