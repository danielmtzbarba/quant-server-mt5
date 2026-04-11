from sqlalchemy import select, delete
from ..models.alert import Alert
from .base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    def __init__(self, session):
        super().__init__(Alert, session)

    async def get_by_user(self, user_id: int):
        result = await self.session.execute(
            select(Alert).where(Alert.user_id == user_id)
        )
        return result.scalars().all()

    async def delete_by_id_and_user(self, alert_id: int, user_id: int):
        result = await self.session.execute(
            delete(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount > 0
