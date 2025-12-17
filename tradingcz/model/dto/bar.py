"""Bar (OHLCV candlestick) data model and converters.

Centralized conversion logic for all providers, enabling seamless provider
swapping and multi-transport support (REST, Kafka, etc).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from alpaca.data.models import Bar as AlpacaBar


@dataclass(slots=True)
class Bar:
    """OHLCV bar (candlestick) - the core unit for backtesting.

    Domain model used everywhere: strategies, backtesting, storage, Kafka.
    Provider-agnostic; no dependency on Alpaca SDK or other vendor types.
    """
    symbol: str
    timestamp: datetime       # Opening time, tz-aware UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int | None = None   # Number of trades in bar
    vwap: float | None = None        # Volume-weighted average price
    raw: object | None = None        # Provider's original object (for debugging)

    def to_dict(self) -> dict:
        """Serialize Bar to dict for Kafka, caching, etc.

        Returns a pure dict representation suitable for JSON serialization.
        """
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'trade_count': self.trade_count,
            'vwap': self.vwap,
        }


class BarResponse(BaseModel):
    """HTTP response model for a single bar.

    Validates JSON schema and provides Swagger documentation.
    Used by FastAPI to serialize Bar to JSON automatically.
    """
    timestamp: str          # ISO format
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_count: Optional[int] = None
    vwap: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T09:30:00+00:00",
                "open": 150.0,
                "high": 152.5,
                "low": 149.8,
                "close": 151.2,
                "volume": 2500000,
                "trade_count": 45000,
                "vwap": 151.05
            }
        }
    )


class BarConverter:
    """Centralized converter for Bar domain model.

    Handles all conversions:
    - from_alpaca() - Alpaca SDK Bar -> our Bar
    - from_interactive_brokers() - IB Bar -> our Bar (future)
    - from_polygon() - Polygon Bar -> our Bar (future)
    - to_response() - Bar -> HTTP response (FastAPI)
    - to_dict() - Bar -> dict (Kafka, caching)

    New providers can be added by adding a new from_*() method without
    changing the Bar model or any consumer code.
    """

    @staticmethod
    def from_alpaca(alpaca_bar: AlpacaBar, symbol: str | None = None) -> Bar:
        """Convert Alpaca SDK Bar to our Bar.

        Alpaca SDK returns loose types (e.g., trade_count is float, not int).
        This converter normalizes to our stricter domain model.

        Args:
            alpaca_bar: alpaca.data.models.Bar object
            symbol: Optional symbol override (if alpaca_bar.symbol is not available)

        Returns:
            Bar domain model
        """
        # Use symbol from parameter if provided, otherwise try to get from object
        bar_symbol = symbol or getattr(alpaca_bar, 'symbol', None)
        if not bar_symbol:
            raise ValueError("Symbol must be provided or present in alpaca_bar")

        return Bar(
            symbol=bar_symbol,
            timestamp=alpaca_bar.timestamp,
            open=float(alpaca_bar.open),
            high=float(alpaca_bar.high),
            low=float(alpaca_bar.low),
            close=float(alpaca_bar.close),
            volume=float(alpaca_bar.volume),
            trade_count=alpaca_bar.trade_count,
            vwap=float(alpaca_bar.vwap) if alpaca_bar.vwap else None,
            raw=alpaca_bar,
        )

    @staticmethod
    def from_interactive_brokers(ib_bar: Any) -> Bar:  # pragma: no cover
        """Convert Interactive Brokers Bar to our Bar (placeholder).

        Future implementation: Maps IB Bar -> our Bar.
        IB may not provide all fields (e.g., VWAP); those stay None.
        """
        # Placeholder for future IB support
        raise NotImplementedError("Interactive Brokers support not yet implemented")

    @staticmethod
    def from_polygon(polygon_bar: Any) -> Bar:  # pragma: no cover
        """Convert Polygon Bar to our Bar (placeholder).

        Future implementation: Maps Polygon Bar -> our Bar.
        """
        # Placeholder for future Polygon support
        raise NotImplementedError("Polygon support not yet implemented")

    @staticmethod
    def to_response(bar: Bar) -> BarResponse:
        """Convert Bar domain model to HTTP response.

        Args:
            bar: Bar domain model

        Returns:
            BarResponse (Pydantic model) ready for JSON serialization
        """
        return BarResponse(
            timestamp=bar.timestamp.isoformat(),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=int(bar.volume),
            trade_count=bar.trade_count,
            vwap=bar.vwap,
        )

    @staticmethod
    def to_dict(bar: Bar) -> dict:
        """Convert Bar to dict (delegates to Bar.to_dict()).

        Provided for consistency with other converters.
        """
        return bar.to_dict()
