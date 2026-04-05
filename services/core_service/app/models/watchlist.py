from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, UniqueConstraint
from core.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[str] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(10))  # FX, STOCK

    user: Mapped["User"] = relationship(back_populates="watchlist_items")

    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", "market", name="uq_user_stock_market"),
    )


class PortfolioItem(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(default=0.0)
    average_price: Mapped[float] = mapped_column(default=0.0)

    user: Mapped["User"] = relationship()
