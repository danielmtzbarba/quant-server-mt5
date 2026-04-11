from fastapi import APIRouter
import structlog
from ..models.schemas import TradeRequest, OrderResponse
from ..core.mt5_service import mt5_service
from ..core.metrics import EXECUTION_SUCCESS, EXECUTION_FAILED

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/order", tags=["Trading"])


@router.post("", response_model=OrderResponse)
def place_order(trade: TradeRequest):
    logger.info(
        "execution_request_received",
        action=trade.action,
        symbol=trade.symbol or trade.ticket,
    )
    result = mt5_service.place_order(trade)
    if result.status == "failed":
        logger.error("order_rejected", reason=result.comment)
        EXECUTION_FAILED.inc()
    else:
        logger.info("order_submitted", ticket=result.ticket)
        EXECUTION_SUCCESS.inc()
    return result
