"""Tests for the PMS service."""

import pytest
import pytest_asyncio

from src.database.seed import HOTEL_ID
from src.services.pms_service import PMSService


@pytest_asyncio.fixture
async def pms(db_session):
    return PMSService(db_session)


@pytest.mark.asyncio
async def test_get_booking_by_confirmation(pms):
    """Verify that a booking can be found by confirmation number."""
    result = await pms.get_booking_by_confirmation("PLR-2024-001")
    assert result is not None
    assert result["guest_name"] == "Juan Perez"
    assert result["room_type"] == "Deluxe"
    assert result["confirmation_number"] == "PLR-2024-001"


@pytest.mark.asyncio
async def test_get_booking_by_confirmation_not_found(pms):
    """Verify that a non-existent booking returns None."""
    result = await pms.get_booking_by_confirmation("FAKE-999")
    assert result is None


@pytest.mark.asyncio
async def test_get_booking_by_phone(pms):
    """Verify that a booking can be found by phone number."""
    result = await pms.get_booking_by_phone("+5491112345678")
    assert result is not None
    assert result["guest_name"] == "Juan Perez"


@pytest.mark.asyncio
async def test_get_hotel(pms):
    """Verify hotel info is returned correctly."""
    result = await pms.get_hotel(HOTEL_ID)
    assert result is not None
    assert result["name"] == "Hotel Palermo Soho"
    assert "wifi" in result["amenities"]


@pytest.mark.asyncio
async def test_get_hotel_amenities(pms):
    """Verify hotel amenities are returned."""
    result = await pms.get_hotel_amenities(HOTEL_ID)
    assert result is not None
    assert result["wifi"]["available"] is True
    assert result["breakfast"]["included"] is True
    assert result["pool"]["available"] is True


@pytest.mark.asyncio
async def test_create_service_request(pms):
    """Verify a service request can be created."""
    from src.database.seed import BOOKING_1_ID

    result = await pms.create_service_request(
        booking_id=BOOKING_1_ID,
        request_type="towels",
        details="2 toallas extra para habitacion 305",
    )
    assert result["status"] == "pending"
    assert result["request_type"] == "towels"
