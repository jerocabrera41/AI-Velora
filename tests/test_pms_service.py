"""Tests for the PMS service."""

from datetime import date, timedelta

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


@pytest.mark.asyncio
async def test_get_room_types(pms):
    """Verify room types are returned for the hotel."""
    result = await pms.get_room_types(HOTEL_ID)
    assert len(result) == 3
    names = {rt["name"] for rt in result}
    assert names == {"Standard", "Deluxe", "Suite"}
    standard = next(rt for rt in result if rt["name"] == "Standard")
    assert standard["price_per_night"] == 120.0
    assert standard["max_guests"] == 2
    assert standard["total_rooms"] == 10


@pytest.mark.asyncio
async def test_check_availability(pms):
    """Verify availability check returns available rooms."""
    # Use future dates to avoid overlap with seeded bookings
    future = date.today() + timedelta(days=60)
    checkin = future.isoformat()
    checkout = (future + timedelta(days=3)).isoformat()

    result = await pms.check_availability(HOTEL_ID, checkin, checkout, num_guests=2)
    assert len(result) > 0
    # All 3 types should accommodate 2 guests
    names = {r["name"] for r in result}
    assert "Standard" in names
    assert "Deluxe" in names
    assert "Suite" in names
    # Verify price calculation
    standard = next(r for r in result if r["name"] == "Standard")
    assert standard["nights"] == 3
    assert standard["total_price"] == 120.0 * 3


@pytest.mark.asyncio
async def test_check_availability_filters_by_guests(pms):
    """Verify availability filters out room types with insufficient capacity."""
    future = date.today() + timedelta(days=60)
    checkin = future.isoformat()
    checkout = (future + timedelta(days=2)).isoformat()

    # 4 guests: only Suite (max 4) should be available
    result = await pms.check_availability(HOTEL_ID, checkin, checkout, num_guests=4)
    assert len(result) == 1
    assert result[0]["name"] == "Suite"


@pytest.mark.asyncio
async def test_create_booking(pms):
    """Verify a new booking can be created."""
    future = date.today() + timedelta(days=90)
    checkin = future.isoformat()
    checkout = (future + timedelta(days=2)).isoformat()

    result = await pms.create_booking(
        hotel_id=HOTEL_ID,
        guest_name="Test Guest",
        guest_phone="+5491100001111",
        guest_email="test@example.com",
        checkin_date=checkin,
        checkout_date=checkout,
        room_type="Standard",
        num_guests=2,
    )
    assert result["success"] is True
    assert result["booking"]["guest_name"] == "Test Guest"
    assert result["booking"]["room_type"] == "Standard"
    assert result["booking"]["confirmation_number"].startswith("PLR-2025-")
    assert result["nights"] == 2
    assert result["total_price"] == 240.0


@pytest.mark.asyncio
async def test_create_booking_no_availability(pms):
    """Verify booking creation fails when no rooms available."""
    future = date.today() + timedelta(days=90)
    checkin = future.isoformat()
    checkout = (future + timedelta(days=2)).isoformat()

    # 5 guests: no room type supports this
    result = await pms.create_booking(
        hotel_id=HOTEL_ID,
        guest_name="Too Many Guests",
        guest_phone="+5491100009999",
        guest_email=None,
        checkin_date=checkin,
        checkout_date=checkout,
        room_type="Standard",
        num_guests=5,
    )
    assert result["success"] is False
    assert "error" in result
