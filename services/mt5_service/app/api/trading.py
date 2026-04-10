from fastapi import APIRouter
from app.models.schemas import TradeRequest, OrderResponse
from app.services.mt5_service import mt5_service
from app.core.logging import logger

router = APIRouter(prefix="/api/order", tags=["Trading"])


@router.post("", response_model=OrderResponse)
def place_order(trade: TradeRequest):
    logger.info(f"Order Dispatch: {trade.action} on {trade.symbol or trade.ticket}")
    result = mt5_service.place_order(trade)
    if result.status == "failed":
        logger.error(f"Order Failed: {result.comment}")
    else:
        logger.info(f"Order Success: Ticket {result.ticket}")
    return result
