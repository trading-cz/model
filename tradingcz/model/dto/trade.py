"""Trade (tick) data model and converters.

Individual trade data (tick level) useful for tick-level analysis and volume profiling.
"""
# pylint: disable=duplicate-code
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from alpaca.data.models import Trade as AlpacaTrade


@dataclass(slots=True)
class Trade:  # pylint: disable=too-many-instance-attributes
    """Individual trade (tick) - for tick-level analysis.

    Represents a single executed trade at a point in time.
    """
    symbol: str
    timestamp: datetime       # tz-aware UTC
    price: float
    size: float
    exchange: str | None = None
    trade_id: str | None = None
    conditions: list[str] | None = None
    raw: object | None = None

    def to_dict(self) -> dict:
        """Serialize Trade to dict for Kafka, caching, etc."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'size': self.size,
            'exchange': self.exchange,
            'trade_id': self.trade_id,
            'conditions': self.conditions,
        }


class TradeResponse(BaseModel):
    """HTTP response model for a single trade."""
    timestamp: str
    price: float
    size: float
    exchange: Optional[str] = None
    trade_id: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T09:30:00+00:00",
                "price": 150.50,
                "size": 1000,
                "exchange": "XNAS",
                "trade_id": "1234567890"
            }
        }
    )


class TradeConverter:
    """Centralized converter for Trade domain model."""

    @staticmethod
    def from_alpaca(alpaca_trade: AlpacaTrade, symbol: str | None = None) -> Trade:
        """Convert Alpaca SDK Trade to our Trade.

        Alpaca SDK returns loose types. This converter normalizes to our
        stricter domain model with proper type conversions.

        Args:
            alpaca_trade: alpaca.data.models.Trade object
            symbol: Optional symbol override (if alpaca_trade.symbol is not available)

        Returns:
            Trade domain model
        """
        # Use symbol from parameter if provided, otherwise try to get from object
        trade_symbol = symbol or getattr(alpaca_trade, 'symbol', None)
        if not trade_symbol:
            raise ValueError("Symbol must be provided or present in alpaca_trade")

        return Trade(
            symbol=trade_symbol,
            timestamp=alpaca_trade.timestamp,
            price=float(alpaca_trade.price),
            size=float(alpaca_trade.size),
            exchange=alpaca_trade.exchange,
            trade_id=alpaca_trade.id,
            conditions=alpaca_trade.conditions,
            raw=alpaca_trade,
        )

    @staticmethod
    def to_response(trade: Trade) -> TradeResponse:
        """Convert Trade domain model to HTTP response.

        Args:
            trade: Trade domain model

        Returns:
            TradeResponse (Pydantic model) ready for JSON serialization
        """
        return TradeResponse(
            timestamp=trade.timestamp.isoformat(),
            price=trade.price,
            size=trade.size,
            exchange=trade.exchange,
            trade_id=trade.trade_id,
        )

    @staticmethod
    def to_dict(trade: Trade) -> dict:
        """Convert Trade to dict (delegates to Trade.to_dict())."""
        return trade.to_dict()
