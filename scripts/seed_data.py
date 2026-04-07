import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os
from dotenv import load_dotenv
import sys

# Add the app directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../services/core_service/app"))

from models.trading import Strategy
from core.database import DATABASE_URL


async def seed():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        # 1. Seed Strategies
        strategies = [
            {
                "name": "SR_BOUNCE_REJECTION",
                "description": "Trading based on support/resistance rejection and ATR bounce zones.",
            },
        ]

        for s_data in strategies:
            result = await session.execute(
                select(Strategy).where(Strategy.name == s_data["name"])
            )
            if not result.scalar_one_or_none():
                print(f"Seeding strategy: {s_data['name']}")
                session.add(Strategy(**s_data))

        await session.commit()

    print("Seeding completed.")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(seed())
