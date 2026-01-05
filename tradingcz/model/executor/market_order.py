"""Simple market order with a possibility of OTO bracket order
"""
from pydantic import BaseModel, ConfigDict

from tradingcz.model.enum.order import TimeInForce


class MarketOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    qty: float
    side: str
    time_in_force: TimeInForce
    type: str | None
    order_class: str | None
    stop_loss: dict[str, float] | None
