# SDK I/O Design Review (Reader/Writer)

Date: 2025-12-29  
Scope: `sdk/tradingcz/io/*` (Reader/Writer + Kafka reader/writer)

## Executive summary

Your current `Reader`/`Writer` abstractions are a good start for provider-agnostic I/O, but they will become painful as soon as you integrate **async-first sources** (Alpaca stream, IB stream) and want multiple sinks (Kafka, REST, files) without bespoke glue classes.

The biggest issues today are:

- **Async mismatch**: The base interfaces are sync-only, but real-time market feeds are typically async.
- **Kafka performance semantics**: `KafkaWriter.write()` currently flushes on every call (kills batching and throughput).
- **Transport couples serialization**: Kafka classes hardcode JSON and hardcode `KafkaKey` in the reader.
- **Readers can’t stop cleanly**: `KafkaReader.read()` loops forever with no cancellation/stop mechanism.

The recommended “clean but not over-engineered” approach is:

- Keep your **existing sync** interfaces for simple scripts.
- Add **async-first** equivalents (`AsyncReader`/`AsyncWriter`) + a tiny **adapter** (`AsyncWriterFromSync`) so Alpaca can `await writer.write(...)` even when the sink is sync.
- Separate **transport** (Kafka/HTTP/etc) from **serialization** (JSON/Pydantic/etc) via a small `Serde` abstraction.

This keeps strategies/risk-management code stable: they only depend on `Reader/Writer` contracts and domain models.

---

## Current state (what exists)

- `tradingcz.io.reader.Reader[KeyT, ValueT]`: sync `read(callback)`.
- `tradingcz.io.writer.Writer[KeyT, ValueT]`: sync `write(key, value, callback=None)`.
- `tradingcz.io.kafka_writer.KafkaWriter`: uses `confluent_kafka.Producer` and JSON-serializes key/value.
  - **Note**: it calls `flush()` for each message (inside `finally`).
- `tradingcz.io.kafka_reader.KafkaReader`: uses `confluent_kafka.Consumer`.
  - Hardcodes key to `KafkaKey` and value as JSON.

---

## Weakness analysis (practical impact)

### 1) Async mismatch

**Problem**: Alpaca/IB style streaming code is usually `async` and expects `await` for downstream I/O.

**Impact**:
- You create “glue classes” per combination (Alpaca→Kafka, Alpaca→REST, IB→Kafka, etc.).
- Call sites become inconsistent (some `await`, some not).

### 2) Unclear delivery semantics

**Problem**: A `write()` can mean many things:
- queued in client buffer
- acknowledged by broker
- durably written

Today, `KafkaWriter.write()` triggers `flush()` per call, which tries to make “write means delivered”. That’s expensive and still not a perfect guarantee.

**Impact**:
- Throughput and latency degrade.
- Strategy/risk code can’t choose semantics (fire-and-forget vs wait-for-ack).

### 3) Serialization is coupled to Kafka

**Problem**: Kafka writer always does `json.dumps` and reader always `json.loads`; reader hardcodes `KafkaKey`.

**Impact**:
- Can’t reuse Kafka transport for non-JSON payloads (Avro/Protobuf) or other key types.
- Harder to support multiple event types in the same topic or to evolve schema.

### 4) Reader shutdown/cancellation is missing

**Problem**: `KafkaReader.read()` loops forever.

**Impact**:
- Hard to stop strategies cleanly.
- Deployments (Kubernetes) need graceful shutdown to avoid rebalances / inconsistent offsets.

---

## Design goals (keep it simple)

1. **Strategies and services depend on stable contracts**, not vendor libraries.
2. Support **sync and async** without duplicate business logic.
3. **Transport-agnostic** (Kafka, REST, files, in-memory) and **provider-agnostic** (Alpaca, IB).
4. Don’t over-engineer: avoid massive frameworks; keep interfaces small and explicit.

---

## Options

### Option A — Sync-only core + thread boundary (minimal changes)

- Keep sync `Reader/Writer` only.
- For async feeds, use `asyncio.to_thread(...)` to call sync writers.

Pros:
- Minimal API.

Cons:
- Async readers become awkward.
- You still end up with glue code everywhere.

### Option B — Dual sync + async interfaces + adapters (recommended)

- Keep current sync `Reader/Writer`.
- Add `AsyncReader/AsyncWriter`.
- Provide adapters so components can be mixed.

Pros:
- Clean boundary: async feeds can `await`.
- Existing sync code remains usable.

Cons:
- Slightly more surface area (4 interfaces instead of 2).

### Option C — Async-only SDK I/O

Pros:
- Consistent for streaming.

Cons:
- Makes simple tooling harder.
- Would be a breaking change for existing sync callers.

**Recommendation**: Option B.

---

## Recommended minimal contracts (Option B)

These are intentionally tiny.

### Message envelope

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


@dataclass(frozen=True, slots=True)
class Message(Generic[KeyT, ValueT]):
    key: KeyT
    value: ValueT
```

### Serde (serialization/deserialization)

Transport should not decide JSON vs Avro vs bytes.

```python
from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class Serde(Protocol, Generic[T]):
    def dumps(self, value: T) -> bytes: ...
    def loads(self, raw: bytes) -> T: ...
```

Example JSON serde (simple, adequate):

```python
import json
from typing import Any


class JsonSerde:
    def dumps(self, value: Any) -> bytes:
        return json.dumps(value).encode("utf-8")

    def loads(self, raw: bytes) -> Any:
        return json.loads(raw.decode("utf-8"))
```

Example Pydantic serde (for `KafkaKey`, `Quote`, etc.):

```python
from pydantic import BaseModel


class PydanticJsonSerde:
    def __init__(self, model_type: type[BaseModel]):
        self._model_type = model_type

    def dumps(self, value: BaseModel) -> bytes:
        return value.model_dump_json().encode("utf-8")

    def loads(self, raw: bytes) -> BaseModel:
        return self._model_type.model_validate_json(raw)
```

### Sync I/O

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


class Writer(ABC, Generic[KeyT, ValueT]):
    @abstractmethod
    def write(self, key: KeyT, value: ValueT) -> None:
        """Send/queue a message."""

    def close(self) -> None:
        """Release resources."""


class Reader(ABC, Generic[KeyT, ValueT]):
    @abstractmethod
    def read(self, on_message: Callable[[KeyT, ValueT], None]) -> None:
        """Blocking read loop."""

    def close(self) -> None:
        """Release resources."""
```

### Async I/O

Use async for real-time market feeds.

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Generic, TypeVar

KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


class AsyncWriter(ABC, Generic[KeyT, ValueT]):
    @abstractmethod
    async def write(self, key: KeyT, value: ValueT) -> None:
        """Send/queue a message."""

    async def aclose(self) -> None:
        """Release resources."""


class AsyncReader(ABC, Generic[KeyT, ValueT]):
    @abstractmethod
    def __aiter__(self) -> AsyncIterator[tuple[KeyT, ValueT]]:
        """Stream messages."""

    async def aclose(self) -> None:
        """Release resources."""
```

### Adapter: `AsyncWriterFromSync`

This is the key to “Alpaca requires async” but Kafka sink is sync.

```python
import asyncio


class AsyncWriterFromSync(AsyncWriter[KeyT, ValueT]):
    def __init__(self, writer: Writer[KeyT, ValueT]):
        self._writer = writer

    async def write(self, key: KeyT, value: ValueT) -> None:
        await asyncio.to_thread(self._writer.write, key, value)

    async def aclose(self) -> None:
        await asyncio.to_thread(self._writer.close)
```

This keeps your business logic async-first but lets you reuse sync transports.

---

## Kafka transport (implementation sketch)

### Kafka writer (transport + injected serdes)

**Key semantics**: `write()` should usually mean “queued locally” and `close()` should flush.

```python
from __future__ import annotations

import logging
from confluent_kafka import Producer

logger = logging.getLogger(__name__)


class KafkaWriter(Writer[KeyT, ValueT]):
    def __init__(
        self,
        producer_config: dict,
        topic: str,
        key_serde: Serde[KeyT],
        value_serde: Serde[ValueT],
    ) -> None:
        self._producer = Producer(producer_config)
        self._topic = topic
        self._key_serde = key_serde
        self._value_serde = value_serde

    def write(self, key: KeyT, value: ValueT) -> None:
        self._producer.produce(
            self._topic,
            key=self._key_serde.dumps(key),
            value=self._value_serde.dumps(value),
        )
        # Poll to serve delivery callbacks and internal events.
        self._producer.poll(0)

    def close(self) -> None:
        remaining = self._producer.flush(timeout=10.0)
        if remaining:
            logger.warning("%s messages not delivered (topic=%s)", remaining, self._topic)
```

### Kafka reader (transport + injected serdes + stop)

```python
from __future__ import annotations

from collections.abc import Callable
from confluent_kafka import Consumer, KafkaError


class KafkaReader(Reader[KeyT, ValueT]):
    def __init__(
        self,
        consumer_config: dict,
        topic: str,
        poll_seconds: float,
        key_serde: Serde[KeyT],
        value_serde: Serde[ValueT],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self._consumer = Consumer(consumer_config)
        self._topic = topic
        self._poll_seconds = poll_seconds
        self._key_serde = key_serde
        self._value_serde = value_serde
        self._should_stop = should_stop or (lambda: False)
        self._consumer.subscribe([topic])

    def read(self, on_message: Callable[[KeyT, ValueT], None]) -> None:
        try:
            while not self._should_stop():
                msg = self._consumer.poll(self._poll_seconds)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise RuntimeError(f"Kafka error: {msg.error()}")

                if msg.key() is None or msg.value() is None:
                    continue

                key = self._key_serde.loads(msg.key())
                value = self._value_serde.loads(msg.value())
                on_message(key, value)
        finally:
            self._consumer.close()

    def close(self) -> None:
        self._consumer.close()
```

---

## Example: Alpaca stream → Kafka (your original intent)

You want Alpaca to “read” quotes asynchronously, then publish to Kafka without the strategy code caring.

### Domain publisher (no Kafka, no Alpaca types leaked)

```python
from tradingcz.model.kafka_key import KafkaKey
from tradingcz.model.domain.quote import Quote


class QuotePublisher:
    def __init__(self, writer: AsyncWriter[KafkaKey, Quote], source_app: str) -> None:
        self._writer = writer
        self._source_app = source_app

    async def publish(self, quote: Quote) -> None:
        key = KafkaKey(source_app=self._source_app, event_type="quote", symbol=quote.symbol)
        await self._writer.write(key, quote)

    async def aclose(self) -> None:
        await self._writer.aclose()
```

### Wiring: sync Kafka writer + async adapter

```python
from tradingcz.io.adapters import AsyncWriterFromSync
from tradingcz.io.kafka_transport import KafkaWriter

key_serde = PydanticJsonSerde(KafkaKey)
quote_serde = PydanticJsonSerde(Quote)

sync_kafka = KafkaWriter(
    producer_config={"bootstrap.servers": "localhost:9092"},
    topic="quotes",
    key_serde=key_serde,
    value_serde=quote_serde,
)

async_writer = AsyncWriterFromSync(sync_kafka)

publisher = QuotePublisher(async_writer, source_app="alpaca")
```

### Alpaca-style stream reader (sketch)

You can implement an `AsyncReader` that yields `(key, value)` or yields domain events only.

```python
class AlpacaQuoteAsyncReader(AsyncReader[str, Quote]):
    def __init__(self, alpaca_client):
        self._client = alpaca_client

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        async for quote in self._client.stream_quotes():
            yield quote.symbol, quote

    async def aclose(self) -> None:
        await self._client.close()
```

Then compose:

```python
async for _symbol, quote in AlpacaQuoteAsyncReader(client):
    await publisher.publish(quote)
```

This avoids a bespoke `AlpacaQuoteKafka` class entirely.

---

## Example: Strategy reads from Kafka, writes to REST

The strategy depends only on the contracts.

```python
class MyStrategy:
    def __init__(self, quotes: Reader[KafkaKey, Quote], signal_sink: Writer[str, dict]):
        self._quotes = quotes
        self._signal_sink = signal_sink

    def run(self) -> None:
        def on_quote(key: KafkaKey, quote: Quote) -> None:
            # compute a signal
            payload = {"symbol": quote.symbol, "action": "BUY"}
            self._signal_sink.write("signal", payload)

        self._quotes.read(on_quote)
```

Wiring:

- `quotes` can be Kafka/IB/backtest file.
- `signal_sink` can be REST/Kafka/file.

---

## Migration path from today’s SDK

Keep compatibility and improve in small steps:

1. **Stop flushing per message** in the existing Kafka writer; flush in `close()`.
2. Add `Serde` and update Kafka reader/writer to accept serdes. Provide defaults to keep old behavior.
3. Add `AsyncWriter` and `AsyncWriterFromSync` adapter so Alpaca integrations can `await` without glue.
4. Add reader cancellation (`should_stop`) and/or an async reader interface for streaming sources.

---

## Quick checklist (what makes the SDK “solid”)

- Clear semantics:
  - `write()` queues; `close()` flushes; optional explicit `flush()` if needed.
- Separation of concerns:
  - transport != serialization
- Composition works:
  - reader -> domain logic -> writer (no combination classes)
- Shutdown:
  - readers can stop; writers close cleanly
- Typing:
  - generics are used consistently; avoid `Any` in public types

---

## What I would implement next (if you want)

- Add `tradingcz/io/serde.py`, `tradingcz/io/async_reader.py`, `tradingcz/io/async_writer.py`, `tradingcz/io/adapters.py`.
- Refactor Kafka reader/writer into transport+serde form while keeping old constructor defaults for backward compatibility.
- Add a couple of focused unit tests verifying:
  - serde round-trips
  - `AsyncWriterFromSync` calls sync writer
  - Kafka writer does not flush per message
