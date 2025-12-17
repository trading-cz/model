"""Trading Model - Shared data models for the trading platform.

This package provides:
- Enums: Timeframe, Adjustment, SortOrder, OrderSide, OrderType
- DTOs: Bar, Quote, Trade, Snapshot (for REST APIs and internal use)
- Converters: DTO ↔ Provider-specific conversions
- Response Models: HTTP response validation
- Kafka schemas: Generated from Avro (in generated/ folder)

Usage:
    from tradingcz.model import Timeframe, Bar, Quote, BarConverter
    from tradingcz.model.kafka.market_stock_quote import MarketStockQuoteValue
"""

from .enums import (
    Timeframe,
    Adjustment,
    SortOrder,
    OrderSide,
    OrderType,
)
from .dto import (
    Bar,
    Quote,
    Trade,
    Snapshot,
    BarResponse,
    QuoteResponse,
    TradeResponse,
    SnapshotResponse,
    BarConverter,
    QuoteConverter,
    TradeConverter,
    SnapshotConverter,
)

__all__ = [
    # Enums
    "Timeframe",
    "Adjustment",
    "SortOrder",
    "OrderSide",
    "OrderType",
    # DTOs
    "Bar",
    "Quote",
    "Trade",
    "Snapshot",
    # Response Models (HTTP)
    "BarResponse",
    "QuoteResponse",
    "TradeResponse",
    "SnapshotResponse",
    # Converters
    "BarConverter",
    "QuoteConverter",
    "TradeConverter",
    "SnapshotConverter",
]
