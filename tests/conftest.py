import sys
import os
import pytest

# Ensure all service 'app' directories are in sys.path for relative imports
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_PATHS = [
    ROOT_DIR,
    os.path.join(ROOT_DIR, "services/core_service/app"),
    os.path.join(ROOT_DIR, "services/messaging_service/app"),
    os.path.join(ROOT_DIR, "services/mt5_service/app"),
    os.path.join(ROOT_DIR, "services/sync_service/app"),
]

for path in PROJECT_PATHS:
    if path not in sys.path:
        sys.path.insert(0, path)

from typing import AsyncGenerator  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# Force pytest-asyncio
pytest_plugins = ["pytest_asyncio"]

# Import apps for testing
try:
    import services.core_service.app.main as core_main

    core_app = core_main.app
except (ImportError, ModuleNotFoundError):
    core_main = None
    core_app = None

try:
    import services.messaging_service.app.main as msg_main

    msg_app = msg_main.app
except (ImportError, ModuleNotFoundError):
    msg_main = None
    msg_app = None

# 2. Setup In-Memory SQLite for fast testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

# --- Dependency Overrides ---


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


if core_app and core_main and hasattr(core_main, "get_db"):
    core_app.dependency_overrides[core_main.get_db] = override_get_db

if msg_app and msg_main and hasattr(msg_main, "get_db"):
    msg_app.dependency_overrides[msg_main.get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_db():
    """Initialize a CLEAN test database for EVERY test case."""
    try:
        # Import models EXPLICITLY to ensure they register with the correct Base
        from services.core_service.app.infra.base import Base
        import services.core_service.app.models.user  # noqa: F401
        import services.core_service.app.models.alert  # noqa: F401
        import services.core_service.app.models.watchlist  # noqa: F401
        import services.core_service.app.models.trading  # noqa: F401
        import services.core_service.app.models.auth  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception as e:
        print(f"FAILED TO SETUP DB: {e}")
        yield


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean DB session for each test case."""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


# Test Clients
@pytest.fixture
async def core_client() -> AsyncGenerator[AsyncClient, None]:
    if core_app:
        async with AsyncClient(
            transport=ASGITransport(app=core_app), base_url="http://core"
        ) as client:
            yield client
    else:
        pytest.skip("Core app not available")


@pytest.fixture
async def msg_client() -> AsyncGenerator[AsyncClient, None]:
    if msg_app:
        async with AsyncClient(
            transport=ASGITransport(app=msg_app), base_url="http://msg"
        ) as client:
            yield client
    else:
        pytest.skip("Messaging app not available")


# Global Mocks
@pytest.fixture(autouse=True)
def mock_external_apis(mocker):
    mocker.patch(
        "services.messaging_service.app.infra.whatsapp.utils.send_message",
        return_value={"status": "sent"},
    )
    mocker.patch(
        "openai.resources.chat.Completions.create",
        return_value=mocker.Mock(
            choices=[
                mocker.Mock(
                    message=mocker.Mock(content='{"symbol": "EURUSD", "action": "BUY"}')
                )
            ]
        ),
    )
    mocker.patch(
        "services.sync_service.app.core.sync_service.SyncService.verify_history",
        return_value={"status": "success", "mismatched_bars": 0},
    )
    mocker.patch(
        "services.sync_service.app.core.sync_service.SyncService.evaluate_strategy",
        return_value=(None, None),
    )

    # Safe env mock
    def safe_env(key, default=None):
        num_keys = ["MAX_POSITIONS", "PORT", "GMT_OFFSET", "SWAP_SIZE_GB"]
        if key in num_keys:
            return "5"
        return "mock_value"

    mocker.patch("common_config.get_env_var", side_effect=safe_env)
    yield
