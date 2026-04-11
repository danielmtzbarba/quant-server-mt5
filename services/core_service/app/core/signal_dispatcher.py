import httpx
import asyncio
import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.trading import Strategy, Order, BrokerAccount
from ..models.user import User
from ..models.auth import SignupSession
from .config import settings

logger = structlog.get_logger(__name__)

MESSAGING_SERVICE_URL = settings.MESSAGING_SERVICE_URL
MT5_ENGINE_URL = settings.MT5_SERVICE_URL
MAX_POSITIONS = 10  # Standardized default


class SignalDispatcher:
    """Manages the distribution of trading signals and account synchronization."""

    async def broadcast_signal(self, db: AsyncSession, signal_data: dict):
        """Dispatches a signal to all subscribed and qualified users."""
        symbol = signal_data.get("symbol", "UNK").upper()
        action = signal_data.get("action", "HOLD").upper()
        price = signal_data.get("price", 0.0)
        strategy_name = signal_data.get("strategy", "SR_50").upper()

        if action == "HOLD":
            return {"status": "ignored", "reason": "HOLD action"}

        logger.info(
            "command_received",
            type="signal",
            strategy=strategy_name,
            symbol=symbol,
            action=action,
        )

        # 1. Fetch Strategy and Subscribers
        result = await db.execute(
            select(User)
            .join(User.subscribed_strategies)
            .join(Strategy)
            .join(SignupSession, User.phone_number == SignupSession.phone_number)
            .where(Strategy.name == strategy_name)
            .where(SignupSession.completed.is_(True))
            .options(selectinload(User.broker_accounts))
        )
        subscribers = result.scalars().all()

        if not subscribers:
            logger.info(f"No active subscribers for {strategy_name}")
            return {"status": "no_subscribers"}

        async with httpx.AsyncClient() as client:
            tasks = []
            for user in subscribers:
                tasks.append(
                    self._process_user_signal(
                        client, db, user, symbol, action, price, strategy_name
                    )
                )

            await asyncio.gather(*tasks)

        try:
            await db.commit()
            logger.info("command_validated", status="success", count=len(subscribers))
        except Exception as e:
            logger.error("db_write_failed", error=str(e), action="broadcast_signal")
            await db.rollback()
            return {"status": "failed", "error": str(e)}

        return {"status": "broadcasted", "count": len(subscribers)}

    async def _process_user_signal(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        user: User,
        symbol: str,
        action: str,
        price: float,
        strategy_name: str,
    ):
        """Handles notification and execution for a single user."""
        # 1. Notify via Messaging Service (Decoupled)
        try:
            await client.post(
                f"{MESSAGING_SERVICE_URL}/notifications",
                json={
                    "phone": user.phone_number,
                    "event": "SIGNAL",
                    "data": {"action": action, "symbol": symbol, "price": price},
                },
                timeout=5.0,
            )
        except Exception as e:
            logger.error(f"Failed to notify {user.phone_number}: {e}")

        # 2. Execute on Broker Accounts
        for acc in user.broker_accounts:
            # Create PENDING order in DB
            from datetime import datetime, timezone
            import time

            order_id = int(time.time() * 1000)
            new_order = Order(
                id=order_id,
                broker_account_id=acc.id,
                symbol=symbol,
                action=action,
                quantity=0.01,  # Default volume
                price=price,
                status="PENDING",
                created_at=datetime.now(timezone.utc),
            )
            db.add(new_order)
            logger.info(
                "trade_intent_created",
                user_id=user.id,
                account=acc.account_number,
                symbol=symbol,
                action=action,
            )

            # Dispatch to MT5 Engine
            try:
                # Note: MT5_ENGINE_URL should point to the Azure IP/Domain if external
                resp = await client.post(
                    f"{MT5_ENGINE_URL}/api/order",
                    json={
                        "action": action,
                        "symbol": symbol,
                        "volume": 0.01,
                        "price": price,
                        "comment": f"Auto:{strategy_name}",
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    logger.info(
                        f"Execution success for {user.name} ({acc.account_number})"
                    )
                else:
                    logger.error(f"Execution rejected for {user.name}: {resp.text}")
            except Exception as e:
                logger.error(f"Network error reaching MT5 for {user.name}: {e}")

    async def handle_position_event(
        self, db: AsyncSession, event_type: str, mt5_login: str, data: dict
    ):
        """Handles real-time position events (OPENED/CLOSED/ERROR)."""
        logger.info(f"Position Event: {event_type} for {mt5_login}")

        # 1. Resolve Account & User
        from sqlalchemy import select

        result = await db.execute(
            select(User)
            .join(BrokerAccount)
            .where(BrokerAccount.account_number == str(mt5_login))
            .options(selectinload(User.broker_accounts))
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"Event for unknown mt5_login: {mt5_login}")
            return

        # 2. Notify User via Messaging Service
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{MESSAGING_SERVICE_URL}/notifications",
                    json={
                        "phone": user.phone_number,
                        "event": event_type,
                        "data": data,
                    },
                    timeout=5.0,
                )
            except Exception as e:
                logger.error(f"Failed to notify event for {user.phone_number}: {e}")

        # 3. Update Database (Implementation depends on event_type)
        # Note: Position sync endpoints already exist in main.py,
        # but we consolidate the 'trigger' here if needed.
        pass


signal_dispatcher = SignalDispatcher()
