from typing import List
from sqlalchemy import select, delete
from models.watchlist import WatchlistItem
from .base import BaseRepository


class WatchlistRepository(BaseRepository[WatchlistItem]):
    def __init__(self, session):
        super().__init__(WatchlistItem, session)

    async def get_by_user(self, user_id: int, market: str | None = None) -> List[str]:
        query = select(WatchlistItem.stock_id).where(WatchlistItem.user_id == user_id)
        if market:
            query = query.where(WatchlistItem.market == market.upper())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_full_watchlist(self, user_id: int) -> List[WatchlistItem]:
        result = await self.session.execute(
            select(WatchlistItem).where(WatchlistItem.user_id == user_id)
        )
        return list(result.scalars().all())

    async def add_symbol(self, user_id: int, symbol: str, market: str) -> bool:
        # Check if already exists in this market
        result = await self.session.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.stock_id == symbol.upper(),
                WatchlistItem.market == market.upper(),
            )
        )
        if result.scalar_one_or_none():
            return False

        await self.create(
            user_id=user_id, stock_id=symbol.upper(), market=market.upper()
        )
        return True

    async def remove_symbol(self, user_id: int, symbol: str) -> bool:
        result = await self.session.execute(
            delete(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.stock_id == symbol.upper(),
            )
        )
        await self.session.commit()
        return result.rowcount > 0
