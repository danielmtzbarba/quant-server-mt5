import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Force pytest-asyncio
pytest_plugins = ["pytest_asyncio"]

# Import apps for testing
import services.core_service.app.main as core_main  # noqa: E402

core_app = core_main.app

import services.execution_service.app.main as exec_main  # noqa: E402

exec_app = exec_main.app

import services.messaging_service.app.main as msg_main  # noqa: E402

msg_app = msg_main.app

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


# To ensure object identity matches, we pull get_db from the imported modules
if hasattr(core_main, "get_db"):
    core_app.dependency_overrides[core_main.get_db] = override_get_db

if hasattr(exec_main, "get_db"):
    exec_app.dependency_overrides[exec_main.get_db] = override_get_db

if hasattr(msg_main, "get_db"):
    msg_app.dependency_overrides[msg_main.get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_db():
    """Initialize a CLEAN test database for EVERY test case."""
    # Use the SINGLE Base that all models are registered to
    # We must be careful to use the correct Base object identity too
    # core.base should be findable via sys.path now.
    try:
        from core.base import Base

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
    async with AsyncClient(
        transport=ASGITransport(app=core_app), base_url="http://core"
    ) as client:
        yield client


@pytest.fixture
async def exec_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=exec_app), base_url="http://exec"
    ) as client:
        yield client


@pytest.fixture
async def msg_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=msg_app), base_url="http://msg"
    ) as client:
        yield client


# Global Mocks
@pytest.fixture(autouse=True)
def mock_external_apis(mocker):
    mocker.patch("whatsapp.utils.send_message", return_value={"status": "sent"})
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
        "services.sync_db_service.sync_db_service.log_candle",
        return_value={"status": "success"},
    )
    mocker.patch(
        "services.sync_db_service.sync_db_service.evaluate_strategy",
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
