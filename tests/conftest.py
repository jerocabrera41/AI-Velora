"""Shared test fixtures."""

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.database import Base
from src.database.seed import get_bookings_data, get_hotel_data, HOTEL_ID
from src.database.models import Booking, Hotel


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
        for booking_data in get_bookings_data():
            session.add(Booking(**booking_data))
        await session.commit()

        yield session

    await engine.dispose()
