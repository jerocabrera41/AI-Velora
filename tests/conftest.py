"""Shared test fixtures."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.database import Base
from src.database.seed import get_bookings_data, get_hotel_data, get_room_types_data
from src.database.models import Booking, Hotel, RoomType


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory database session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Seed test data
        hotel = Hotel(**get_hotel_data())
        session.add(hotel)
        for room_type_data in get_room_types_data():
            session.add(RoomType(**room_type_data))
        for booking_data in get_bookings_data():
            session.add(Booking(**booking_data))
        await session.commit()

        yield session

    await engine.dispose()
