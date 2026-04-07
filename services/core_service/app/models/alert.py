from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Float, DateTime
from core.base import Base
from typing import TYPE_CHECKING, List
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .user import User


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[str] = mapped_column(String(20))
    target_price: Mapped[float] = mapped_column(Float)
    condition: Mapped[str] = mapped_column(String(10))  # ABOVE, BELOW
    market: Mapped[str] = mapped_column(String(10))  # FX, STOCK
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="alerts")
    deliveries: Mapped[List["NotificationDelivery"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(20), default="SENT")

    alert: Mapped["Alert"] = relationship(back_populates="deliveries")
