from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Float, BigInteger, Integer, DateTime
from ..infra.base import Base
from typing import TYPE_CHECKING, List
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .user import User


class UserStrategy(Base):
    __tablename__ = "user_strategies"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True
    )
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(200))

    users: Mapped[List["User"]] = relationship(
        secondary="user_strategies", back_populates="subscribed_strategies"
    )
    orders: Mapped[List["Order"]] = relationship(back_populates="strategy")


class BrokerAccount(Base):
    __tablename__ = "broker_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_number: Mapped[str] = mapped_column(String(50))
    broker_name: Mapped[str] = mapped_column(String(100))
    account_type: Mapped[str] = mapped_column(String(20))  # e.g., 'MT5', 'IBKR'

    user: Mapped["User"] = relationship(back_populates="broker_accounts")
    orders: Mapped[List["Order"]] = relationship(
        back_populates="broker_account", cascade="all, delete-orphan"
    )
    positions: Mapped[List["Position"]] = relationship(
        back_populates="broker_account", cascade="all, delete-orphan"
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(20))  # BUY, SELL
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    broker_account: Mapped["BrokerAccount"] = relationship(back_populates="orders")
    strategy: Mapped["Strategy"] = relationship(back_populates="orders")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(Float)
    type: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Buy, 1=Sell
    average_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float, nullable=True)
    active_status: Mapped[bool] = mapped_column(default=True)

    broker_account: Mapped["BrokerAccount"] = relationship(back_populates="positions")
