from sqlalchemy import select, update, delete
from models.auth import SignupSession
from .base import BaseRepository

class SignupRepository(BaseRepository[SignupSession]):
    def __init__(self, session):
        super().__init__(SignupSession, session)

    async def get_by_phone(self, phone_number: str) -> SignupSession | None:
        result = await self.session.execute(
            select(SignupSession).where(SignupSession.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def update_by_phone(self, phone_number: str, **kwargs) -> SignupSession | None:
        await self.session.execute(
            update(SignupSession)
            .where(SignupSession.phone_number == phone_number)
            .values(**kwargs)
        )
        await self.session.commit()
        return await self.get_by_phone(phone_number)
