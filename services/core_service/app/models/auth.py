from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Float, Boolean, DateTime
from sqlalchemy.sql import func
from datetime import datetime
from core.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User


class LoginToken(Base):
    __tablename__ = "login_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    expires_at: Mapped[float] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="login_tokens")


class SignupSession(Base):
    __tablename__ = "signup_sessions"

    phone_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    step: Mapped[str] = mapped_column(String(50), default="ASK_NAME")
    name: Mapped[str | None] = mapped_column(String(100))
    interests: Mapped[str | None] = mapped_column(String(50))  # 'FX', 'STOCKS', 'BOTH'
    fx_capital: Mapped[float | None] = mapped_column(Float)
    stocks_capital: Mapped[float | None] = mapped_column(Float)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
