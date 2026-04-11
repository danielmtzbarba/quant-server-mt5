from typing import Generic, TypeVar, Type, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from ..infra.base import Base
from common_logging import setup_logging

logger = setup_logging("core-service")

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: Any) -> T | None:
        return await self.session.get(self.model, id)

    async def get_all(self) -> List[T]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        logger.info(f"DB: {self.model.__name__} CREATE")
        return instance

    async def update(self, id: Any, **kwargs) -> T | None:
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**kwargs)
        )
        await self.session.commit()
        logger.info(f"DB: {self.model.__name__} UPDATE")
        return await self.get(id)

    async def delete(self, id: Any) -> bool:
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.commit()
        if result.rowcount > 0:
            logger.info(f"DB: {self.model.__name__} DELETE")
        return result.rowcount > 0
