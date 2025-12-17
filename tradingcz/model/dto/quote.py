"""Quote (bid/ask level 1) data model and converters.

Level 1 market data (best bid/ask) useful for spread analysis and order routing.
"""
# pylint: disable=duplicate-code
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from alpaca.data.models import Quote as AlpacaQuote


@dataclass(slots=True)
class Quote:
    """Level 1 bid/ask quote - for spread analysis and order routing.

    Represents the best bid and ask prices (and sometimes sizes) at a point in time.
    """
    symbol: str
    timestamp: datetime       # tz-aware UTC
    bid_price: float
    ask_price: float
    bid_size: float | None = None
    ask_size: float | None = None
    bid_exchange: str | None = None
    ask_exchange: str | None = None
    conditions: list[str] | None = None
    raw: object | None = None

    def to_dict(self) -> dict:
        """Serialize Quote to dict for Kafka, caching, etc."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'bid_exchange': self.bid_exchange,
            'ask_exchange': self.ask_exchange,
            'conditions': self.conditions,
        }


class QuoteResponse(BaseModel):
    """HTTP response model for a single quote."""
    timestamp: str              # ISO format
    bid_price: float
    ask_price: float
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    spread: Optional[float] = None  # Calculated bid-ask spread

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T09:30:00+00:00",
                "bid_price": 150.50,
                "ask_price": 150.51,
                "bid_size": 1000,
                "ask_size": 1200,
                "spread": 0.01
            }
        }
    )


class QuoteConverter:
    """Centralized converter for Quote domain model."""

    @staticmethod
    def from_alpaca(alpaca_quote: AlpacaQuote, symbol: str | None = None) -> Quote:
        """Convert Alpaca SDK Quote to our Quote.

        Alpaca SDK returns loose types. This converter normalizes to our
        stricter domain model with proper type conversions.

        Args:
            alpaca_quote: alpaca.data.models.Quote object
            symbol: Optional symbol override (if alpaca_quote.symbol is not available)

        Returns:
            Quote domain model
        """
        # Use symbol from parameter if provided, otherwise try to get from object
        quote_symbol = symbol or getattr(alpaca_quote, 'symbol', None)
        if not quote_symbol:
            raise ValueError("Symbol must be provided or present in alpaca_quote")

        return Quote(
            symbol=quote_symbol,
            timestamp=alpaca_quote.timestamp,
            bid_price=float(alpaca_quote.bid_price),
            ask_price=float(alpaca_quote.ask_price),
            bid_size=float(alpaca_quote.bid_size) if alpaca_quote.bid_size else None,
            ask_size=float(alpaca_quote.ask_size) if alpaca_quote.ask_size else None,
            bid_exchange=alpaca_quote.bid_exchange,
            ask_exchange=alpaca_quote.ask_exchange,
            conditions=alpaca_quote.conditions,
            raw=alpaca_quote,
        )

    @staticmethod
    def to_response(quote: Quote) -> QuoteResponse:
        """Convert Quote domain model to HTTP response.

        Args:
            quote: Quote domain model

        Returns:
            QuoteResponse (Pydantic model) ready for JSON serialization
        """
        spread = round(quote.ask_price - quote.bid_price, 4)
        return QuoteResponse(
            timestamp=quote.timestamp.isoformat(),
            bid_price=quote.bid_price,
            ask_price=quote.ask_price,
            bid_size=quote.bid_size,
            ask_size=quote.ask_size,
            spread=spread if quote.ask_price and quote.bid_price else None,
        )

    @staticmethod
    def to_dict(quote: Quote) -> dict:
        """Convert Quote to dict (delegates to Quote.to_dict())."""
        return quote.to_dict()
