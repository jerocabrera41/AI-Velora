"""Mock PMS (Property Management System) service.

Simulates a Cloudbeds-like PMS by querying the local SQLite database.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.models import (
    Booking,
    BookingStatus,
    Hotel,
    RoomType,
    ServiceRequest,
    UpsellConversion,
    UpsellOffer,
)


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

    async def get_room_types(self, hotel_id: uuid.UUID) -> list[dict]:
        """Get all room types for a hotel."""
        logger.info(f"PMS lookup: room_types for hotel_id={hotel_id}")

        result = await self.session.execute(
            select(RoomType).where(RoomType.hotel_id == hotel_id)
        )
        room_types = result.scalars().all()

        return [
            {
                "id": str(rt.id),
                "name": rt.name,
                "description": rt.description,
                "price_per_night": rt.price_per_night,
                "max_guests": rt.max_guests,
                "total_rooms": rt.total_rooms,
            }
            for rt in room_types
        ]

    async def check_availability(
        self,
        hotel_id: uuid.UUID,
        checkin: str,
        checkout: str,
        num_guests: int,
    ) -> list[dict]:
        """Check room availability for the given dates and guest count.

        For each room type that fits the guest count, counts overlapping
        bookings per night and returns the minimum available rooms.
        """
        logger.info(
            f"Checking availability: hotel={hotel_id}, "
            f"checkin={checkin}, checkout={checkout}, guests={num_guests}"
        )

        # Get room types that can accommodate the guests
        result = await self.session.execute(
            select(RoomType).where(
                and_(
                    RoomType.hotel_id == hotel_id,
                    RoomType.max_guests >= num_guests,
                )
            )
        )
        room_types = result.scalars().all()

        available = []
        for rt in room_types:
            # Count overlapping bookings (active ones only) for this room type
            result = await self.session.execute(
                select(func.count(Booking.id)).where(
                    and_(
                        Booking.hotel_id == hotel_id,
                        Booking.room_type == rt.name,
                        Booking.status.in_([
                            BookingStatus.CONFIRMED,
                            BookingStatus.CHECKED_IN,
                        ]),
                        Booking.checkin_date < checkout,
                        Booking.checkout_date > checkin,
                    )
                )
            )
            booked_count = result.scalar() or 0
            rooms_available = rt.total_rooms - booked_count

            if rooms_available > 0:
                # Calculate total nights and price
                checkin_date = date.fromisoformat(checkin)
                checkout_date = date.fromisoformat(checkout)
                nights = (checkout_date - checkin_date).days

                available.append({
                    "room_type_id": str(rt.id),
                    "name": rt.name,
                    "description": rt.description,
                    "price_per_night": rt.price_per_night,
                    "total_price": rt.price_per_night * nights,
                    "nights": nights,
                    "max_guests": rt.max_guests,
                    "rooms_available": rooms_available,
                })

        logger.info(f"Availability result: {len(available)} room types available")
        return available

    async def create_booking(
        self,
        hotel_id: uuid.UUID,
        guest_name: str,
        guest_phone: str,
        guest_email: str | None,
        checkin_date: str,
        checkout_date: str,
        room_type: str,
        num_guests: int,
        special_requests: str | None = None,
    ) -> dict:
        """Create a new booking after verifying availability.

        Returns the created booking dict or an error dict.
        """
        logger.info(
            f"Creating booking: hotel={hotel_id}, guest={guest_name}, "
            f"room={room_type}, {checkin_date} to {checkout_date}"
        )

        # Verify availability first
        available = await self.check_availability(
            hotel_id, checkin_date, checkout_date, num_guests
        )
        room_available = next(
            (r for r in available if r["name"] == room_type), None
        )

        if room_available is None:
            logger.warning(f"No availability for {room_type} on requested dates")
            return {
                "success": False,
                "error": f"No hay disponibilidad para {room_type} en las fechas solicitadas.",
            }

        # Generate confirmation number
        count_result = await self.session.execute(
            select(func.count(Booking.id)).where(Booking.hotel_id == hotel_id)
        )
        total_bookings = count_result.scalar() or 0
        confirmation_number = f"PLR-2025-{total_bookings + 1:03d}"

        booking = Booking(
            hotel_id=hotel_id,
            confirmation_number=confirmation_number,
            guest_name=guest_name,
            guest_phone=guest_phone,
            guest_email=guest_email,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            room_type=room_type,
            num_guests=num_guests,
            special_requests=special_requests,
            status=BookingStatus.CONFIRMED,
        )
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        logger.info(f"Booking created: {confirmation_number}")
        return {
            "success": True,
            "booking": self._booking_to_dict(booking),
            "total_price": room_available["total_price"],
            "nights": room_available["nights"],
        }

    async def get_upsell_offers(self, hotel_id: uuid.UUID) -> list[dict]:
        """Get all active upsell offers for a hotel."""
        logger.info(f"PMS lookup: upsell_offers for hotel_id={hotel_id}")

        result = await self.session.execute(
            select(UpsellOffer).where(
                and_(
                    UpsellOffer.hotel_id == hotel_id,
                    UpsellOffer.is_active == True,
                )
            )
        )
        offers = result.scalars().all()

        return [
            {
                "id": str(o.id),
                "name": o.name,
                "description": o.description,
                "price": o.price,
                "offer_type": o.offer_type,
            }
            for o in offers
        ]

    async def get_applicable_offers(
        self, hotel_id: uuid.UUID, booking_id: uuid.UUID
    ) -> list[dict]:
        """Get upsell offers applicable to a specific booking.

        Filters out upgrades that don't apply (e.g., no upgrade offer
        if guest already has a Suite).
        """
        logger.info(
            f"PMS lookup: applicable offers for booking={booking_id}"
        )

        # Get the booking to know the room type
        result = await self.session.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if booking is None:
            return []

        all_offers = await self.get_upsell_offers(hotel_id)

        applicable = []
        for offer in all_offers:
            # Skip upgrade to Deluxe if guest already has Deluxe or Suite
            if offer["offer_type"] == "upgrade" and "Deluxe" in offer["name"]:
                if booking.room_type in ("Deluxe", "Suite"):
                    continue
            # Skip upgrade to Suite if guest already has Suite
            if offer["offer_type"] == "upgrade" and "Suite" in offer["name"]:
                if booking.room_type == "Suite":
                    continue
            applicable.append(offer)

        logger.info(f"Applicable offers: {len(applicable)} for {booking.room_type}")
        return applicable

    async def record_upsell_response(
        self,
        booking_id: uuid.UUID,
        offer_id: uuid.UUID,
        accepted: bool,
    ) -> dict:
        """Record a guest's response to an upsell offer."""
        logger.info(
            f"Recording upsell response: booking={booking_id}, "
            f"offer={offer_id}, accepted={accepted}"
        )

        status = "accepted" if accepted else "declined"
        conversion = UpsellConversion(
            booking_id=booking_id,
            offer_id=offer_id,
            status=status,
            responded_at=datetime.utcnow(),
        )
        self.session.add(conversion)
        await self.session.commit()
        await self.session.refresh(conversion)

        return {
            "id": str(conversion.id),
            "booking_id": str(conversion.booking_id),
            "offer_id": str(conversion.offer_id),
            "status": conversion.status,
            "responded_at": conversion.responded_at.isoformat(),
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
