from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete
from typing import List
import uvicorn
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from repositories.user_repo import UserRepository
from repositories.watchlist_repo import WatchlistRepository
from repositories.alert_repo import AlertRepository
from models.user import User
from models.alert import Alert
from models.trading import Order, Position, BrokerAccount
from models.watchlist import WatchlistItem
from common_logging import setup_logging
from common_config import get_env_var
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Core Service...")
    # Definitive runtime silence for Uvicorn logs
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"]:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = False
        uv_logger.setLevel(logging.WARNING)
    yield
    logger.info("Shutting down Core Service...")


logger = setup_logging("core-service", tag="CORE", color="cyan")

app = FastAPI(title="Core Service", lifespan=lifespan)

# Setup templates and static files (Root-relative)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Root is 3 levels up from core_service/app/
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../../"))
templates = Jinja2Templates(directory=os.path.join(ROOT_DIR, "templates"))
app.mount(
    "/static", StaticFiles(directory=os.path.join(ROOT_DIR, "static")), name="static"
)


async def verify_admin_token(token: str | None = None):
    admin_token = get_env_var("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token not configured in .env",
        )
    if token != admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token"
        )
    return token


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# --- User Endpoints ---


@app.get("/users/{phone_number}")
async def get_user(phone_number: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: GET User {phone_number}")
    repo = UserRepository(db)
    user = await repo.get_by_phone(phone_number)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users/signup/init")
async def signup_init(phone_number: str, db: AsyncSession = Depends(get_db)):
    """Atomic initialization: creates both the User record and their Signup Session."""
    logger.info(f"DB: SIGNUP INIT {phone_number}")
    from models.auth import SignupSession
    from models.user import User

    # 1. Ensure User exists
    user_result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(phone_number=phone_number, name="User Pending")
        db.add(user)

    # 2. Ensure SignupSession exists (or reset it)
    session_result = await db.execute(
        select(SignupSession).where(SignupSession.phone_number == phone_number)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        session = SignupSession(
            phone_number=phone_number, step="ASK_NAME", completed=False
        )
        db.add(session)
    else:
        session.step = "ASK_NAME"
        session.completed = False

    try:
        await db.commit()
        logger.info(f"DB: Signup records for {phone_number} initialized.")
    except Exception as e:
        await db.rollback()
        logger.error(f"DB: Atomic signup failure for {phone_number}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to initialize user signup state."
        )

    return user


@app.get("/signup/session/{phone_number}")
async def get_signup_session(phone_number: str, db: AsyncSession = Depends(get_db)):
    from models.auth import SignupSession

    result = await db.execute(
        select(SignupSession).where(SignupSession.phone_number == phone_number)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Signup session not found")
    return session


@app.patch("/signup/session/{phone_number}")
async def update_signup_session(
    phone_number: str, updates: dict, db: AsyncSession = Depends(get_db)
):
    from models.auth import SignupSession

    result = await db.execute(
        select(SignupSession).where(SignupSession.phone_number == phone_number)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Signup session not found")

    for key, value in updates.items():
        if hasattr(session, key):
            setattr(session, key, value)

    await db.commit()
    return session


@app.patch("/users/{phone_number}")
async def update_user(
    phone_number: str, updates: dict, db: AsyncSession = Depends(get_db)
):
    logger.info(f"DB: PATCH User {phone_number}")
    repo = UserRepository(db)
    user = await repo.get_by_phone(phone_number)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for key, value in updates.items():
        if hasattr(user, key):
            setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user


@app.post("/users")
async def create_user(phone_number: str, name: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: CREATE User {phone_number} ({name})")
    repo = UserRepository(db)
    return await repo.create(phone_number=phone_number, name=name)


@app.get("/watchlist/users/{symbol}")
async def get_users_by_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: GET Observers -> {symbol}")
    from sqlalchemy import select
    from models.user import User
    from models.watchlist import WatchlistItem

    result = await db.execute(
        select(User)
        .join(User.watchlist_items)
        .where(WatchlistItem.stock_id == symbol.upper())
    )
    return result.scalars().all()


# --- Watchlist Endpoints ---


@app.get("/watchlist/{user_id}")
async def get_watchlist(user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: GET Watchlist (User {user_id})")
    repo = WatchlistRepository(db)
    return await repo.get_by_user(user_id)


@app.post("/watchlist")
async def add_to_watchlist(
    user_id: int, symbol: str, market: str, db: AsyncSession = Depends(get_db)
):
    logger.info(f"DB: ADD Watchlist (User {user_id} -> {symbol})")
    repo = WatchlistRepository(db)
    success = await repo.add_symbol(user_id, symbol, market)
    return {"success": success}


@app.delete("/watchlist")
async def remove_from_watchlist(
    user_id: int, symbol: str, db: AsyncSession = Depends(get_db)
):
    logger.info(f"DB: REMOVE Watchlist (User {user_id} -> {symbol})")
    repo = WatchlistRepository(db)
    success = await repo.remove_symbol(user_id, symbol)
    return {"success": success}


# --- Alert Endpoints ---


@app.get("/alerts/{user_id}")
async def get_alerts(user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: GET Alerts (User {user_id})")
    repo = AlertRepository(db)
    return await repo.get_by_user(user_id)


@app.post("/alerts")
async def create_alert(
    user_id: int,
    symbol: str,
    price: float,
    condition: str,
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"DB: CREATE Alert (User {user_id} -> {symbol} @ {price})")
    repo = AlertRepository(db)
    # Correct field names for the Alert model: stock_id, target_price
    return await repo.create(
        user_id=user_id,
        stock_id=symbol.upper(),
        target_price=price,
        condition=condition,
        market="FX",  # Default for testing
    )


@app.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: DELETE Alert {alert_id} (User {user_id})")
    repo = AlertRepository(db)
    success = await repo.delete_by_id_and_user(alert_id, user_id)
    return {"success": success}


# --- Account & User Mapping ---


@app.get("/accounts/verify/{account_number}")
async def verify_account(account_number: str, db: AsyncSession = Depends(get_db)):
    """Used by MT5 EA to verify if the current terminal is registered/authorized."""
    from models.trading import BrokerAccount
    from models.user import User

    result = await db.execute(
        select(BrokerAccount)
        .join(User)
        .where(BrokerAccount.account_number == account_number)
    )
    account = result.scalar_one_or_none()
    if not account:
        logger.warning(f"DB: Verification FAILED for account {account_number}")
        raise HTTPException(status_code=404, detail="Broker account not found")

    return account


@app.get("/accounts/{account_id}/user")
async def get_account_user(account_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from models.trading import BrokerAccount
    from models.user import User

    result = await db.execute(
        select(User)
        .join(BrokerAccount, User.id == BrokerAccount.user_id)
        .where(BrokerAccount.id == account_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Account or User not found")
    return user


@app.post("/broker_accounts")
async def create_broker_account(
    user_id: int,
    account_number: str,
    broker_name: str,
    account_type: str = "MT5",
    db: AsyncSession = Depends(get_db),
):
    from models.trading import BrokerAccount

    # Check if exists
    existing = await db.execute(
        select(BrokerAccount).where(BrokerAccount.account_number == account_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Account number already registered")

    account = BrokerAccount(
        user_id=user_id,
        account_number=account_number,
        broker_name=broker_name,
        account_type=account_type,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


# --- Strategy & Subscriptions ---


@app.get("/strategies")
async def list_strategies(db: AsyncSession = Depends(get_db)):
    from models.trading import Strategy

    result = await db.execute(select(Strategy))
    return result.scalars().all()


@app.post("/strategies/{strategy_name}/subscribe")
async def subscribe_to_strategy(
    strategy_name: str, user_id: int, db: AsyncSession = Depends(get_db)
):
    from models.trading import Strategy, UserStrategy

    # 1. Get Strategy
    s_result = await db.execute(
        select(Strategy).where(Strategy.name == strategy_name.upper())
    )
    strategy = s_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # 2. Check if already subscribed
    sub_result = await db.execute(
        select(UserStrategy).where(
            UserStrategy.user_id == user_id, UserStrategy.strategy_id == strategy.id
        )
    )
    if sub_result.scalar_one_or_none():
        return {"status": "already_subscribed"}

    # 3. Add subscription
    sub = UserStrategy(user_id=user_id, strategy_id=strategy.id)
    db.add(sub)
    await db.commit()
    return {"status": "success"}


@app.get("/strategies/{strategy_name}/subscribers")
async def get_strategy_subscribers(
    strategy_name: str, db: AsyncSession = Depends(get_db)
):
    from models.trading import Strategy
    from models.user import User
    from models.auth import SignupSession
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User)
        .join(User.subscribed_strategies)
        .join(SignupSession, User.phone_number == SignupSession.phone_number)
        .where(Strategy.name == strategy_name.upper())
        .where(SignupSession.completed.is_(True))
        .options(selectinload(User.broker_accounts))
    )
    return result.scalars().all()


# --- Order & Execution State ---


@app.post("/orders")
async def create_order(order_data: dict, db: AsyncSession = Depends(get_db)):
    # Standardize incoming payload keys for the Order model:
    # symbol -> symbol (OK), action -> action (OK), volume -> quantity
    if "volume" in order_data and "quantity" not in order_data:
        order_data["quantity"] = order_data.pop("volume")

    symbol = order_data.get("symbol", "UNK")
    logger.info(f"DB: CREATE Order ({symbol})")

    order = Order(**order_data)
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@app.get("/positions/{account_id}")
async def get_positions(account_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"DB: GET Positions (Acc {account_id})")
    from sqlalchemy import select

    result = await db.execute(
        select(Position).where(
            Position.broker_account_id == account_id, Position.active_status.is_(True)
        )
    )
    return result.scalars().all()


@app.post("/positions/sync")
async def sync_positions(
    account_id: int, positions_data: List[dict], db: AsyncSession = Depends(get_db)
):
    logger.info(
        f"DB: SYNC Positions for Acc {account_id} ({len(positions_data)} active)"
    )
    from sqlalchemy import update, select

    # 1. Mark all existing positions for this account as inactive
    await db.execute(
        update(Position)
        .where(Position.broker_account_id == account_id)
        .values(active_status=False)
    )

    # 2. Update or Create active positions
    for p_data in positions_data:
        ticket = p_data.get("ticket")
        if ticket is None:
            continue

        result = await db.execute(select(Position).where(Position.id == ticket))
        existing = result.scalar_one_or_none()

        if existing:
            existing.quantity = p_data.get("volume", existing.quantity)
            existing.average_price = p_data.get("price_open", existing.average_price)
            existing.current_price = p_data.get("profit", existing.current_price)
            existing.type = p_data.get("type", existing.type)
            existing.active_status = True
        else:
            new_pos = Position(
                id=ticket,
                broker_account_id=account_id,
                symbol=p_data.get("symbol"),
                quantity=p_data.get("volume"),
                type=p_data.get("type"),
                average_price=p_data.get("price_open"),
                current_price=p_data.get("profit"),
                active_status=True,
            )
            db.add(new_pos)

    await db.commit()
    return {"status": "success"}


@app.get("/positions/active/count")
async def get_active_positions_count(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, func
    from models.trading import Position

    result = await db.execute(
        select(func.count())
        .select_from(Position)
        .where(Position.active_status.is_(True))
    )
    return {"count": result.scalar() or 0}


@app.post("/positions/open")
async def open_position(pos_data: dict, db: AsyncSession = Depends(get_db)):
    from models.trading import Position, Order
    from sqlalchemy import update

    # 1. Create/Update Position
    new_pos = Position(
        id=pos_data["ticket"],
        broker_account_id=1,
        symbol=pos_data["symbol"],
        quantity=pos_data["volume"],
        average_price=pos_data["price"],
        type=pos_data.get("type"),
        active_status=True,
    )
    await db.merge(new_pos)

    # 2. Transition matching PENDING order to FILLED
    action = (
        "BUY"
        if pos_data.get("type") == 0
        else "SELL"
        if pos_data.get("type") == 1
        else None
    )
    if action:
        await db.execute(
            update(Order)
            .where(Order.symbol == pos_data["symbol"])
            .where(Order.action == action)
            .where(Order.status == "PENDING")
            .values(status="FILLED")
        )

    await db.commit()
    logger.info(f"DB: Position OPENED/SYNC {pos_data['ticket']}")
    return {"status": "success"}


@app.post("/positions/close")
async def close_position(
    ticket: int, profit: float, db: AsyncSession = Depends(get_db)
):
    logger.info(f"DB: CLOSE Position {ticket} (Profit: {profit})")
    from sqlalchemy import select

    result = await db.execute(select(Position).where(Position.id == ticket))
    position = result.scalar_one_or_none()
    if position:
        position.active_status = False
        position.current_price = profit
        await db.commit()
    return {"status": "success"}


# --- Admin Dashboard ---


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, token: str | None = None, db: AsyncSession = Depends(get_db)
):
    await verify_admin_token(token)

    # 1. Fetch Users
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    # 2. Fetch Alerts
    alerts_result = await db.execute(select(Alert).options(selectinload(Alert.user)))
    alerts = alerts_result.scalars().all()

    # 3. Fetch Positions
    pos_result = await db.execute(select(Position))
    positions = pos_result.scalars().all()

    # 4. Fetch Watchlist
    watch_result = await db.execute(
        select(WatchlistItem).options(selectinload(WatchlistItem.user))
    )
    watchlist = watch_result.scalars().all()

    # 5. Fetch Accounts
    acc_result = await db.execute(
        select(BrokerAccount).options(selectinload(BrokerAccount.user))
    )
    accounts = acc_result.scalars().all()

    # 6. Fetch Orders
    ord_result = await db.execute(select(Order))
    orders = ord_result.scalars().all()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "token": token,  # Pass token back for JS actions
            "users": users,
            "alerts": alerts,
            "positions": positions,
            "watchlist": watchlist,
            "accounts": accounts,
            "orders": orders,
            "stats": {
                "total_users": len(users),
                "total_alerts": len(alerts),
                "total_positions": len(positions),
            },
        },
    )


@app.delete("/admin/{type}/{id}")
async def admin_delete(
    type: str, id: int, token: str | None = None, db: AsyncSession = Depends(get_db)
):
    await verify_admin_token(token)

    table_map = {
        "user": User,
        "alert": Alert,
        "position": Position,
        "watchlist": WatchlistItem,
        "account": BrokerAccount,
        "order": Order,
    }

    model = table_map.get(type)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid type")

    await db.execute(delete(model).where(model.id == id))
    await db.commit()
    logger.info(f"DB: {type.upper()} DELETE (Admin)")
    return {"status": "success"}


if __name__ == "__main__":
    logger.info("Core Service Ready on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
