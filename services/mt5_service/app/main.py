from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import sys

from common_logging import (
    setup_logging,
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
)
from .core.mt5_service import mt5_service
from .api.trading import router as trading_router
from .api.monitoring import router as monitoring_router

# --- FIX: Wine/Windows broken pipe noise ---
# Switching from Proactor (default) to Selector loop for improved stability in Wine
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def compact_exception_handler(loop, context):
    """Silences multi-line 'BrokenPipeError' stacks in Wine by condensing them into one line."""
    exception = context.get("exception")
    if isinstance(exception, BrokenPipeError) or (
        exception and "[WinError 10058]" in str(exception)
    ):
        logger.warning("MT5: Connection closed by peer (BrokenPipe 10058)")
    else:
        loop.default_exception_handler(context)


# Setup standardized logging
logger = setup_logging("mt5-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set compact exception handler to avoid emulation noise
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(compact_exception_handler)

    # Initialize MT5
    if not mt5_service.initialize():
        logger.critical("Failed to initialize MT5 Service.")

    yield

    # Shutdown
    mt5_service.shutdown()


app = FastAPI(title="MT5 Minimal Wrapper API", lifespan=lifespan)

# Add structured logging middlewares
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Include core Routers
app.include_router(trading_router)
app.include_router(monitoring_router)

if __name__ == "__main__":
    import uvicorn

    # Use standard uvicorn run
    uvicorn.run(app, host="0.0.0.0", port=8000)
