import sys
import os

# Ensure the parent directory is in sys.path so 'app' can be found as a package
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import asyncio  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from app.core.logging import logger  # noqa: E402
from app.services.influx_service import influx_service  # noqa: E402
from app.workers.monitoring import position_monitor_task  # noqa: E402
from app.workers.publishing import candle_publisher_task  # noqa: E402
from app.workers.health import health_monitor_loop  # noqa: E402

from app.api.sync import router as sync_router  # noqa: E402

# Setup Templates
# In production (Docker), these are at /app/templates. In local dev, they are at the root.
templates = Jinja2Templates(
    directory="/app/templates"
    if os.path.exists("/app/templates")
    else "../../templates"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Services
    influx_service.connect()

    # Wait for MT5 Service to be ready before starting workers
    from app.services.mt5_client import mt5_client

    await mt5_client.wait_until_ready()

    # Start Background Workers
    task_p = asyncio.create_task(position_monitor_task())
    task_c = asyncio.create_task(candle_publisher_task())
    task_h = asyncio.create_task(health_monitor_loop())

    logger.info("Sync Service initialized and workers started.")

    yield

    # Shutdown
    task_p.cancel()
    task_c.cancel()
    task_h.cancel()

    influx_service.close()
    logger.info("Sync Service shutdown complete.")


app = FastAPI(title="Sync & Dashboard Service", lifespan=lifespan)

# Mount static files for dashboard (if any)
# Note: In the container, static is at /app/static but we want it relative to this file's execution dir if running locally
static_dir = "/app/static" if os.path.exists("/app/static") else "../../../static"
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def get_dashboard_redirect(request: Request):
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/dashboard")


# Include Routers
app.include_router(sync_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
