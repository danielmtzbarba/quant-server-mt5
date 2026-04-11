from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session):
        super().__init__(User, session)

    async def get_by_phone(self, phone_number: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, phone_number: str, name: str | None = None) -> User:
        user = await self.get_by_phone(phone_number)
        if user:
            if name and user.name != name:
                user.name = name
                await self.session.commit()
                await self.session.refresh(user)
            return user

        return await self.create(phone_number=phone_number, name=name)

    async def get_with_relations(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.alerts), selectinload(User.watchlist_items))
        )
        return result.scalar_one_or_none()
