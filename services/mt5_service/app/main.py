import sys
import os

# Ensure the parent directory is in sys.path so 'app' can be found as a package
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from fastapi import FastAPI  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from app.core.logging import logger  # noqa: E402
from app.services.mt5_service import mt5_service  # noqa: E402
from app.api.trading import router as trading_router  # noqa: E402
from app.api.monitoring import router as monitoring_router  # noqa: E402


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
