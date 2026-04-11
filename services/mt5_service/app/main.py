from fastapi import FastAPI
from contextlib import asynccontextmanager

from common_logging import setup_logging
from .core.mt5_service import mt5_service
from .api.trading import router as trading_router
from .api.monitoring import router as monitoring_router

# Setup standardized logging
logger = setup_logging("mt5-service", tag="MT5", color="green")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MT5
    if not mt5_service.initialize():
        logger.critical("Failed to initialize MT5 Service.")

    yield

    # Shutdown
    mt5_service.shutdown()


app = FastAPI(title="MT5 Minimal Wrapper API", lifespan=lifespan)

# Include core Routers
app.include_router(trading_router)
app.include_router(monitoring_router)

if __name__ == "__main__":
    import uvicorn

    # Use standard uvicorn run
    uvicorn.run(app, host="0.0.0.0", port=8000)
