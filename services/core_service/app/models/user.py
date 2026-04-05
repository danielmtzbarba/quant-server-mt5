from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Float
from core.base import Base
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .watchlist import WatchlistItem
    from .trading import BrokerAccount
    from .alert import Alert
    from .auth import LoginToken


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    has_stock_portfolio: Mapped[bool] = mapped_column(Boolean, default=True)
    has_fx_portfolio: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_capital: Mapped[float] = mapped_column(Float, default=0.0)
    fx_capital: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    watchlist_items: Mapped[List["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    broker_accounts: Mapped[List["BrokerAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    login_tokens: Mapped[List["LoginToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
