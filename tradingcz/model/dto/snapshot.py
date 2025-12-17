"""Snapshot (aggregated market state) data model and converters.

Combines latest trade, quote, and bars into a single view for real-time decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from alpaca.data.models import Snapshot as AlpacaSnapshot
    from tradingcz.model.dto.bar import Bar
    from tradingcz.model.dto.quote import Quote
    from tradingcz.model.dto.trade import Trade


@dataclass(slots=True)
class Snapshot:
    """Current market state - aggregated view for real-time decisions.

    Combines the latest trade, quote, minute bar, and daily bar in one call.
    More efficient than calling individual methods separately.
    """
    symbol: str
    latest_trade: Trade | None = None
    latest_quote: Quote | None = None
    minute_bar: Bar | None = None
    daily_bar: Bar | None = None
    previous_daily_bar: Bar | None = None
    raw: object | None = None

    def to_dict(self) -> dict:
        """Serialize Snapshot to dict for Kafka, caching, etc."""
        from tradingcz.model.dto.bar import Bar
        from tradingcz.model.dto.quote import Quote
        from tradingcz.model.dto.trade import Trade

        return {
            'symbol': self.symbol,
            'latest_trade': self.latest_trade.to_dict() if self.latest_trade else None,
            'latest_quote': self.latest_quote.to_dict() if self.latest_quote else None,
            'minute_bar': self.minute_bar.to_dict() if self.minute_bar else None,
            'daily_bar': self.daily_bar.to_dict() if self.daily_bar else None,
            'previous_daily_bar': self.previous_daily_bar.to_dict() if self.previous_daily_bar else None,
        }


class SnapshotResponse(BaseModel):
    """HTTP response model for a market snapshot."""
    latest_trade: Optional[dict] = None
    latest_quote: Optional[dict] = None
    minute_bar: Optional[dict] = None
    daily_bar: Optional[dict] = None
    previous_daily_bar: Optional[dict] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "latest_trade": {
                    "timestamp": "2024-01-15T14:30:00+00:00",
                    "price": 150.50,
                    "size": 1000,
                    "exchange": "XNAS"
                },
                "latest_quote": {
                    "timestamp": "2024-01-15T14:30:00+00:00",
                    "bid_price": 150.49,
                    "ask_price": 150.51,
                    "bid_size": 500,
                    "ask_size": 600
                },
                "minute_bar": {
                    "timestamp": "2024-01-15T14:30:00+00:00",
                    "open": 150.45,
                    "high": 150.60,
                    "low": 150.40,
                    "close": 150.50,
                    "volume": 50000
                },
                "daily_bar": {
                    "timestamp": "2024-01-15T00:00:00+00:00",
                    "open": 149.50,
                    "high": 151.00,
                    "low": 149.40,
                    "close": 150.50,
                    "volume": 5000000
                }
            }
        }
    )


class SnapshotConverter:
    """Centralized converter for Snapshot domain model."""

    @staticmethod
    def from_alpaca(alpaca_snapshot: AlpacaSnapshot, symbol: str | None = None) -> Snapshot:
        """Convert Alpaca SDK Snapshot to our Snapshot.

        Alpaca SDK returns loose types. This converter recursively normalizes
        all nested objects to our stricter domain models.

        Args:
            alpaca_snapshot: alpaca.data.models.Snapshot object
            symbol: Optional symbol override (if alpaca_snapshot.symbol is not available)

        Returns:
            Snapshot domain model
        """
        from tradingcz.model.dto.bar import BarConverter  # pylint: disable=import-outside-toplevel
        from tradingcz.model.dto.quote import QuoteConverter  # pylint: disable=import-outside-toplevel
        from tradingcz.model.dto.trade import TradeConverter  # pylint: disable=import-outside-toplevel

        # Use symbol from parameter if provided, otherwise try to get from object
        snap_symbol = symbol or getattr(alpaca_snapshot, 'symbol', None)
        if not snap_symbol:
            raise ValueError("Symbol must be provided or present in alpaca_snapshot")

        return Snapshot(
            symbol=snap_symbol,
            latest_trade=TradeConverter.from_alpaca(alpaca_snapshot.latest_trade, symbol=snap_symbol)
            if alpaca_snapshot.latest_trade else None,
            latest_quote=QuoteConverter.from_alpaca(alpaca_snapshot.latest_quote, symbol=snap_symbol)
            if alpaca_snapshot.latest_quote else None,
            minute_bar=BarConverter.from_alpaca(alpaca_snapshot.minute_bar, symbol=snap_symbol)
            if alpaca_snapshot.minute_bar else None,
            daily_bar=BarConverter.from_alpaca(alpaca_snapshot.daily_bar, symbol=snap_symbol)
            if alpaca_snapshot.daily_bar else None,
            previous_daily_bar=BarConverter.from_alpaca(alpaca_snapshot.previous_daily_bar, symbol=snap_symbol)
            if alpaca_snapshot.previous_daily_bar else None,
            raw=alpaca_snapshot,
        )

    @staticmethod
    def to_response(snapshot: Snapshot) -> SnapshotResponse:
        """Convert Snapshot domain model to HTTP response.

        Args:
            snapshot: Snapshot domain model

        Returns:
            SnapshotResponse (Pydantic model) ready for JSON serialization
        """
        from tradingcz.model.dto.bar import BarConverter
        from tradingcz.model.dto.quote import QuoteConverter
        from tradingcz.model.dto.trade import TradeConverter

        return SnapshotResponse(
            latest_trade=TradeConverter.to_dict(snapshot.latest_trade) if snapshot.latest_trade else None,
            latest_quote=QuoteConverter.to_dict(snapshot.latest_quote) if snapshot.latest_quote else None,
            minute_bar=BarConverter.to_dict(snapshot.minute_bar) if snapshot.minute_bar else None,
            daily_bar=BarConverter.to_dict(snapshot.daily_bar) if snapshot.daily_bar else None,
            previous_daily_bar=BarConverter.to_dict(snapshot.previous_daily_bar)
            if snapshot.previous_daily_bar else None,
        )

    @staticmethod
    def to_dict(snapshot: Snapshot) -> dict:
        """Convert Snapshot to dict (delegates to Snapshot.to_dict())."""
        return snapshot.to_dict()
