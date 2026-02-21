"""Seed data for development: Hotel Palermo Soho + 3 sample bookings."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from src.database.models import Booking, BookingStatus, Hotel, RoomType, UpsellOffer

# Fixed UUIDs for reproducibility
HOTEL_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
BOOKING_1_ID = uuid.UUID("b1000001-0000-0000-0000-000000000001")
BOOKING_2_ID = uuid.UUID("b1000002-0000-0000-0000-000000000002")
BOOKING_3_ID = uuid.UUID("b1000003-0000-0000-0000-000000000003")
ROOM_TYPE_STANDARD_ID = uuid.UUID("c1000001-0000-0000-0000-000000000001")
ROOM_TYPE_DELUXE_ID = uuid.UUID("c1000002-0000-0000-0000-000000000002")
ROOM_TYPE_SUITE_ID = uuid.UUID("c1000003-0000-0000-0000-000000000003")
UPSELL_OFFER_IDS = [
    uuid.UUID("d1000001-0000-0000-0000-000000000001"),
    uuid.UUID("d1000002-0000-0000-0000-000000000002"),
    uuid.UUID("d1000003-0000-0000-0000-000000000003"),
    uuid.UUID("d1000004-0000-0000-0000-000000000004"),
    uuid.UUID("d1000005-0000-0000-0000-000000000005"),
    uuid.UUID("d1000006-0000-0000-0000-000000000006"),
]


def get_hotel_data() -> dict:
    today = date.today()
    return {
        "id": HOTEL_ID,
        "name": "Hotel Palermo Soho",
        "description": (
            "Hotel boutique de 4 estrellas en el corazon de Palermo, Buenos Aires. "
            "Ubicado a pasos de las mejores tiendas, restaurantes y bares de la zona."
        ),
        "amenities": {
            "wifi": {
                "available": True,
                "cost": "free",
                "password": "palermo2024",
            },
            "breakfast": {
                "included": True,
                "hours": "07:00-11:00",
                "location": "Restaurant Nivel 1",
            },
            "pool": {
                "available": True,
                "hours": "08:00-20:00",
                "location": "Rooftop",
            },
            "gym": {
                "available": True,
                "hours": "24/7",
                "location": "Nivel -1",
            },
            "parking": {
                "available": True,
                "cost": "$15/day",
                "spots": "limited",
            },
            "spa": {
                "available": True,
                "hours": "10:00-20:00",
                "location": "Nivel -1",
                "cost": "Extra charge",
            },
        },
        "policies": {
            "checkin": "15:00",
            "checkout": "11:00",
            "late_checkout": {
                "available": True,
                "cost": "$30",
                "subject_to": "availability",
            },
            "early_checkin": {
                "available": True,
                "cost": "$20",
                "subject_to": "availability",
            },
            "cancellation": "Cancelacion gratuita hasta 48 horas antes del arribo",
        },
        "faq": [
            {
                "question": "Como llego desde el aeropuerto?",
                "answer": (
                    "Desde Ezeiza: taxi (~$35 USD, 45min) o transfer privado. "
                    "Desde Aeroparque: taxi (~$15 USD, 20min). "
                    "Tambien ofrecemos servicio de transfer por $40 USD."
                ),
            },
            {
                "question": "Aceptan mascotas?",
                "answer": (
                    "Si, aceptamos mascotas de hasta 10kg "
                    "con un cargo adicional de $20 USD por noche."
                ),
            },
            {
                "question": "Tienen servicio de lavanderia?",
                "answer": (
                    "Si, ofrecemos servicio de lavanderia con entrega en 24hs. "
                    "Podes dejar la ropa en la bolsa de lavanderia del placard."
                ),
            },
            {
                "question": "A que distancia estan las atracciones principales?",
                "answer": (
                    "Plaza Serrano: 2 cuadras. MALBA: 10 min caminando. "
                    "Jardin Botanico: 5 min caminando. Bosques de Palermo: 15 min caminando."
                ),
            },
            {
                "question": "Tienen room service?",
                "answer": (
                    "Si, room service disponible de 07:00 a 23:00. "
                    "Menu disponible en la tablet de la habitacion."
                ),
            },
            {
                "question": "Ofrecen caja de seguridad?",
                "answer": (
                    "Si, cada habitacion cuenta con caja de seguridad digital. "
                    "Las instrucciones estan en la carpeta de bienvenida."
                ),
            },
        ],
        "contact_phone": "+54 11 4833-1234",
        "address": "Honduras 4742, Palermo Soho, Buenos Aires, Argentina",
    }


def get_room_types_data() -> list[dict]:
    return [
        {
            "id": ROOM_TYPE_STANDARD_ID,
            "hotel_id": HOTEL_ID,
            "name": "Standard",
            "description": "Habitacion confortable con cama doble, bano privado, TV y escritorio de trabajo.",
            "price_per_night": 120.0,
            "max_guests": 2,
            "total_rooms": 10,
        },
        {
            "id": ROOM_TYPE_DELUXE_ID,
            "hotel_id": HOTEL_ID,
            "name": "Deluxe",
            "description": "Habitacion superior con cama king, sala de estar, minibar y vista a la ciudad.",
            "price_per_night": 200.0,
            "max_guests": 3,
            "total_rooms": 6,
        },
        {
            "id": ROOM_TYPE_SUITE_ID,
            "hotel_id": HOTEL_ID,
            "name": "Suite",
            "description": "Suite premium con sala independiente, jacuzzi privado, terraza y servicio VIP.",
            "price_per_night": 350.0,
            "max_guests": 4,
            "total_rooms": 3,
        },
    ]


def get_bookings_data() -> list[dict]:
    today = date.today()
    return [
        {
            "id": BOOKING_1_ID,
            "confirmation_number": "PLR-2024-001",
            "hotel_id": HOTEL_ID,
            "guest_name": "Juan Perez",
            "guest_phone": "+5491112345678",
            "guest_email": "juan.perez@email.com",
            "checkin_date": today.isoformat(),
            "checkout_date": (today + timedelta(days=2)).isoformat(),
            "room_type": "Deluxe",
            "num_guests": 2,
            "special_requests": "Habitacion alta con vista a la calle",
            "status": BookingStatus.CONFIRMED,
        },
        {
            "id": BOOKING_2_ID,
            "confirmation_number": "PLR-2024-002",
            "hotel_id": HOTEL_ID,
            "guest_name": "Maria Gonzalez",
            "guest_phone": "+5491198765432",
            "guest_email": "maria.gonzalez@email.com",
            "checkin_date": (today + timedelta(days=1)).isoformat(),
            "checkout_date": (today + timedelta(days=6)).isoformat(),
            "room_type": "Suite",
            "num_guests": 1,
            "special_requests": None,
            "status": BookingStatus.CONFIRMED,
        },
        {
            "id": BOOKING_3_ID,
            "confirmation_number": "PLR-2024-003",
            "hotel_id": HOTEL_ID,
            "guest_name": "Carlos Rodriguez",
            "guest_phone": "+5491155551234",
            "guest_email": "carlos.r@email.com",
            "checkin_date": (today - timedelta(days=1)).isoformat(),
            "checkout_date": (today + timedelta(days=1)).isoformat(),
            "room_type": "Standard",
            "num_guests": 1,
            "special_requests": "Almohada extra",
            "status": BookingStatus.CHECKED_IN,
        },
    ]


def get_upsell_offers_data() -> list[dict]:
    return [
        {
            "id": UPSELL_OFFER_IDS[0],
            "hotel_id": HOTEL_ID,
            "name": "Upgrade a Deluxe",
            "description": (
                "Mejora tu habitacion a Deluxe con cama king, "
                "sala de estar, minibar y vista a la ciudad."
            ),
            "price": 80.0,
            "offer_type": "upgrade",
            "is_active": True,
        },
        {
            "id": UPSELL_OFFER_IDS[1],
            "hotel_id": HOTEL_ID,
            "name": "Upgrade a Suite",
            "description": (
                "Mejora tu habitacion a Suite premium con jacuzzi privado, "
                "terraza y servicio VIP."
            ),
            "price": 150.0,
            "offer_type": "upgrade",
            "is_active": True,
        },
        {
            "id": UPSELL_OFFER_IDS[2],
            "hotel_id": HOTEL_ID,
            "name": "Paquete Desayuno Premium",
            "description": (
                "Desayuno premium con opciones gourmet, jugos naturales "
                "y servicio de barista en mesa."
            ),
            "price": 18.0,
            "offer_type": "breakfast",
            "is_active": True,
        },
        {
            "id": UPSELL_OFFER_IDS[3],
            "hotel_id": HOTEL_ID,
            "name": "Late Checkout",
            "description": (
                "Extiende tu estadía hasta las 14:00hs "
                "(sujeto a disponibilidad)."
            ),
            "price": 30.0,
            "offer_type": "late_checkout",
            "is_active": True,
        },
        {
            "id": UPSELL_OFFER_IDS[4],
            "hotel_id": HOTEL_ID,
            "name": "Tratamiento Spa Relax",
            "description": (
                "Masaje relajante de 60 minutos en nuestro spa "
                "con aromaterapia incluida."
            ),
            "price": 50.0,
            "offer_type": "spa",
            "is_active": True,
        },
        {
            "id": UPSELL_OFFER_IDS[5],
            "hotel_id": HOTEL_ID,
            "name": "Early Check-in",
            "description": (
                "Ingreso anticipado a partir de las 12:00hs "
                "(sujeto a disponibilidad)."
            ),
            "price": 20.0,
            "offer_type": "early_checkin",
            "is_active": True,
        },
    ]


async def seed_database(session: AsyncSession) -> None:
    """Populate the database with sample data if empty."""

    result = await session.execute(select(Hotel).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Database already seeded, skipping")
        return

    logger.info("Seeding database with sample data...")

    hotel = Hotel(**get_hotel_data())
    session.add(hotel)

    for room_type_data in get_room_types_data():
        session.add(RoomType(**room_type_data))

    for booking_data in get_bookings_data():
        booking = Booking(**booking_data)
        session.add(booking)

    for offer_data in get_upsell_offers_data():
        session.add(UpsellOffer(**offer_data))

    await session.commit()
    logger.info(
        "Seeded: 1 hotel (Hotel Palermo Soho) + 3 room types "
        "(Standard, Deluxe, Suite) + 3 bookings "
        "(Juan Perez, Maria Gonzalez, Carlos Rodriguez) + 6 upsell offers"
    )
