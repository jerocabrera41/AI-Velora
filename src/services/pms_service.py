"""Mock PMS (Property Management System) service.

Simulates a Cloudbeds-like PMS by querying the local SQLite database.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.models import Booking, Hotel, ServiceRequest


class PMSService:
    """Mock PMS that wraps database queries for hotel/booking operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_booking_by_confirmation(
        self, confirmation_number: str
    ) -> dict | None:
        """Look up a booking by its confirmation number."""
        logger.info(f"PMS lookup: confirmation_number={confirmation_number}")

        result = await self.session.execute(
            select(Booking).where(
                Booking.confirmation_number == confirmation_number.upper()
            )
        )
        booking = result.scalar_one_or_none()

        if booking is None:
            logger.warning(f"Booking not found: {confirmation_number}")
            return None

        return self._booking_to_dict(booking)

    async def get_booking_by_phone(self, phone: str) -> dict | None:
        """Look up a booking by guest phone number."""
        logger.info(f"PMS lookup: phone={phone}")

        # Try exact match first, then partial match (last 8 digits)
        result = await self.session.execute(
            select(Booking).where(Booking.guest_phone == phone)
        )
        booking = result.scalar_one_or_none()

        if booking is None and len(phone) >= 8:
            # Partial match on last 8 digits
            result = await self.session.execute(
                select(Booking).where(Booking.guest_phone.endswith(phone[-8:]))
            )
            booking = result.scalar_one_or_none()

        if booking is None:
            logger.warning(f"Booking not found for phone: {phone}")
            return None

        return self._booking_to_dict(booking)

    async def get_hotel(self, hotel_id: uuid.UUID) -> dict | None:
        """Get hotel details by ID."""
        logger.info(f"PMS lookup: hotel_id={hotel_id}")

        result = await self.session.execute(
            select(Hotel).where(Hotel.id == hotel_id)
        )
        hotel = result.scalar_one_or_none()

        if hotel is None:
            return None

        return {
            "id": str(hotel.id),
            "name": hotel.name,
            "description": hotel.description,
            "amenities": hotel.amenities,
            "policies": hotel.policies,
            "faq": hotel.faq,
            "contact_phone": hotel.contact_phone,
            "address": hotel.address,
        }

    async def get_hotel_amenities(self, hotel_id: uuid.UUID) -> dict | None:
        """Get just the amenities for a hotel."""
        hotel = await self.get_hotel(hotel_id)
        if hotel is None:
            return None
        return hotel["amenities"]

    async def get_hotel_faq(self, hotel_id: uuid.UUID) -> list[dict] | None:
        """Get FAQ entries for a hotel."""
        hotel = await self.get_hotel(hotel_id)
        if hotel is None:
            return None
        return hotel["faq"]

    async def get_hotel_policies(self, hotel_id: uuid.UUID) -> dict | None:
        """Get policies for a hotel."""
        hotel = await self.get_hotel(hotel_id)
        if hotel is None:
            return None
        return hotel["policies"]

    async def create_service_request(
        self,
        booking_id: uuid.UUID,
        request_type: str,
        details: str,
    ) -> dict:
        """Create a new service request for a guest."""
        logger.info(
            f"Creating service request: booking={booking_id}, "
            f"type={request_type}, details={details}"
        )

        service_request = ServiceRequest(
            booking_id=booking_id,
            request_type=request_type,
            details=details,
            status="pending",
        )
        self.session.add(service_request)
        await self.session.commit()
        await self.session.refresh(service_request)

        logger.info(f"Service request created: {service_request.id}")
        return {
            "id": str(service_request.id),
            "booking_id": str(service_request.booking_id),
            "request_type": service_request.request_type,
            "details": service_request.details,
            "status": service_request.status,
            "created_at": service_request.created_at.isoformat(),
        }

    async def get_default_hotel(self) -> dict | None:
        """Get the first (and only for MVP) hotel."""
        result = await self.session.execute(select(Hotel).limit(1))
        hotel = result.scalar_one_or_none()
        if hotel is None:
            return None
        return {
            "id": str(hotel.id),
            "name": hotel.name,
            "description": hotel.description,
            "amenities": hotel.amenities,
            "policies": hotel.policies,
            "faq": hotel.faq,
            "contact_phone": hotel.contact_phone,
            "address": hotel.address,
        }

    @staticmethod
    def _booking_to_dict(booking: Booking) -> dict:
        return {
            "id": str(booking.id),
            "confirmation_number": booking.confirmation_number,
            "hotel_id": str(booking.hotel_id),
            "guest_name": booking.guest_name,
            "guest_phone": booking.guest_phone,
            "guest_email": booking.guest_email,
            "checkin_date": booking.checkin_date,
            "checkout_date": booking.checkout_date,
            "room_type": booking.room_type,
            "num_guests": booking.num_guests,
            "special_requests": booking.special_requests,
            "status": booking.status.value if booking.status else None,
            "created_at": (
                booking.created_at.isoformat() if booking.created_at else None
            ),
        }
