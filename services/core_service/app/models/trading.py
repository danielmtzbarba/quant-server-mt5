from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Float, BigInteger, Integer
from core.base import Base
from typing import TYPE_CHECKING, List
from datetime import datetime

if TYPE_CHECKING:
    from .user import User


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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    broker_account: Mapped["BrokerAccount"] = relationship(back_populates="orders")


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
