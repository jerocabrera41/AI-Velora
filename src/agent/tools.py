"""Tools that the LLM agent can call to interact with hotel systems."""

import uuid
from typing import Any

from loguru import logger

from src.services.pms_service import PMSService
from src.services.conversation_service import ConversationService


class AgentTools:
    """Wraps PMS and conversation services as callable tools for the agent."""

    def __init__(
        self,
        pms: PMSService,
        conversation_service: ConversationService,
        hotel_id: uuid.UUID,
    ) -> None:
        self.pms = pms
        self.conversation_service = conversation_service
        self.hotel_id = hotel_id

    async def get_booking_details(self, confirmation_number: str) -> dict[str, Any]:
        """Look up a booking by confirmation number.

        Args:
            confirmation_number: The booking confirmation code (e.g. PLR-2024-001)

        Returns:
            Booking details or error message.
        """
        logger.info(f"Tool call: get_booking_details({confirmation_number})")
        booking = await self.pms.get_booking_by_confirmation(confirmation_number)
        if booking is None:
            return {
                "found": False,
                "message": f"No se encontro reserva con confirmacion {confirmation_number}",
            }
        return {"found": True, "booking": booking}

    async def get_booking_by_phone(self, phone: str) -> dict[str, Any]:
        """Look up a booking by guest phone number.

        Args:
            phone: Guest phone number.

        Returns:
            Booking details or error message.
        """
        logger.info(f"Tool call: get_booking_by_phone({phone})")
        booking = await self.pms.get_booking_by_phone(phone)
        if booking is None:
            return {
                "found": False,
                "message": f"No se encontro reserva para el telefono {phone}",
            }
        return {"found": True, "booking": booking}

    async def get_hotel_amenities(self) -> dict[str, Any]:
        """Get all amenities of the hotel.

        Returns:
            Dictionary with all hotel amenities and their details.
        """
        logger.info("Tool call: get_hotel_amenities()")
        amenities = await self.pms.get_hotel_amenities(self.hotel_id)
        if amenities is None:
            return {"error": "No se pudo obtener la informacion de amenities"}
        return amenities

    async def get_hotel_policies(self) -> dict[str, Any]:
        """Get hotel policies (check-in/out times, cancellation, etc).

        Returns:
            Dictionary with hotel policies.
        """
        logger.info("Tool call: get_hotel_policies()")
        policies = await self.pms.get_hotel_policies(self.hotel_id)
        if policies is None:
            return {"error": "No se pudo obtener las politicas del hotel"}
        return policies

    async def search_faq(self, query: str) -> list[dict[str, str]]:
        """Search the hotel FAQ for answers to the guest's question.

        Args:
            query: The guest's question or search terms.

        Returns:
            List of matching FAQ entries.
        """
        logger.info(f"Tool call: search_faq({query})")
        faqs = await self.pms.get_hotel_faq(self.hotel_id)
        if faqs is None:
            return []

        # Simple keyword matching (good enough for MVP)
        query_lower = query.lower()
        matches = []
        for faq in faqs:
            question = faq.get("question", "").lower()
            answer = faq.get("answer", "").lower()
            if any(
                word in question or word in answer
                for word in query_lower.split()
                if len(word) > 2
            ):
                matches.append(faq)

        logger.debug(f"FAQ search '{query}' returned {len(matches)} matches")
        return matches

    async def create_service_request(
        self, booking_id: str, request_type: str, details: str
    ) -> dict[str, Any]:
        """Register a service request from a guest.

        Args:
            booking_id: UUID of the guest's booking.
            request_type: Type of request (e.g. 'towels', 'late_checkout', 'wake_up_call').
            details: Free-text details of the request.

        Returns:
            Confirmation of the created request.
        """
        logger.info(
            f"Tool call: create_service_request({booking_id}, {request_type}, {details})"
        )
        try:
            result = await self.pms.create_service_request(
                booking_id=uuid.UUID(booking_id),
                request_type=request_type,
                details=details,
            )
            return {"success": True, "request": result}
        except Exception as e:
            logger.error(f"Failed to create service request: {e}")
            return {"success": False, "error": str(e)}

    async def get_room_types(self) -> dict[str, Any]:
        """Get all room types with prices and capacity.

        Returns:
            List of room types with details.
        """
        logger.info("Tool call: get_room_types()")
        room_types = await self.pms.get_room_types(self.hotel_id)
        if not room_types:
            return {"error": "No se encontraron tipos de habitacion"}
        return {"room_types": room_types}

    async def check_availability(
        self, checkin: str, checkout: str, num_guests: int
    ) -> dict[str, Any]:
        """Check room availability for given dates and guest count.

        Args:
            checkin: Check-in date (YYYY-MM-DD).
            checkout: Check-out date (YYYY-MM-DD).
            num_guests: Number of guests.

        Returns:
            Available room types with prices.
        """
        logger.info(f"Tool call: check_availability({checkin}, {checkout}, {num_guests})")
        available = await self.pms.check_availability(
            self.hotel_id, checkin, checkout, num_guests
        )
        if not available:
            return {
                "available": False,
                "message": "No hay habitaciones disponibles para las fechas y cantidad de huespedes indicados.",
            }
        return {"available": True, "rooms": available}

    async def create_booking(
        self,
        guest_name: str,
        guest_phone: str,
        guest_email: str | None,
        checkin_date: str,
        checkout_date: str,
        room_type: str,
        num_guests: int,
        special_requests: str | None = None,
    ) -> dict[str, Any]:
        """Create a new booking.

        Args:
            guest_name: Full name of the guest.
            guest_phone: Guest phone number.
            guest_email: Guest email (optional).
            checkin_date: Check-in date (YYYY-MM-DD).
            checkout_date: Check-out date (YYYY-MM-DD).
            room_type: Room type name (Standard, Deluxe, Suite).
            num_guests: Number of guests.
            special_requests: Special requests (optional).

        Returns:
            Created booking details or error.
        """
        logger.info(
            f"Tool call: create_booking({guest_name}, {room_type}, "
            f"{checkin_date}-{checkout_date})"
        )
        result = await self.pms.create_booking(
            hotel_id=self.hotel_id,
            guest_name=guest_name,
            guest_phone=guest_phone,
            guest_email=guest_email,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            room_type=room_type,
            num_guests=num_guests,
            special_requests=special_requests,
        )
        return result

    async def get_upsell_offers(self, booking_id: str | None = None) -> dict[str, Any]:
        """Get available upsell offers for the current guest.

        Args:
            booking_id: UUID of the guest's booking (optional, filters applicable offers).

        Returns:
            List of available upsell offers.
        """
        logger.info(f"Tool call: get_upsell_offers(booking_id={booking_id})")
        if booking_id:
            try:
                offers = await self.pms.get_applicable_offers(
                    self.hotel_id, uuid.UUID(booking_id)
                )
            except Exception as e:
                logger.error(f"Failed to get applicable offers: {e}")
                offers = await self.pms.get_upsell_offers(self.hotel_id)
        else:
            offers = await self.pms.get_upsell_offers(self.hotel_id)

        if not offers:
            return {"available": False, "message": "No hay ofertas disponibles en este momento."}
        return {"available": True, "offers": offers}

    async def respond_to_upsell(
        self, booking_id: str, offer_id: str, accepted: bool
    ) -> dict[str, Any]:
        """Record the guest's response to an upsell offer.

        Args:
            booking_id: UUID of the guest's booking.
            offer_id: UUID of the upsell offer.
            accepted: Whether the guest accepted the offer.

        Returns:
            Confirmation of the recorded response.
        """
        logger.info(
            f"Tool call: respond_to_upsell({booking_id}, {offer_id}, {accepted})"
        )
        try:
            result = await self.pms.record_upsell_response(
                booking_id=uuid.UUID(booking_id),
                offer_id=uuid.UUID(offer_id),
                accepted=accepted,
            )
            return {"success": True, "conversion": result}
        except Exception as e:
            logger.error(f"Failed to record upsell response: {e}")
            return {"success": False, "error": str(e)}

    async def escalate_to_human(
        self, conversation_id: str, reason: str
    ) -> dict[str, Any]:
        """Escalate the conversation to a human agent.

        Args:
            conversation_id: UUID of the conversation to escalate.
            reason: Reason for escalation.

        Returns:
            Confirmation of escalation.
        """
        logger.info(f"Tool call: escalate_to_human({conversation_id}, {reason})")
        try:
            await self.conversation_service.escalate_conversation(
                conversation_id=uuid.UUID(conversation_id),
                reason=reason,
            )
            return {
                "success": True,
                "message": "Conversacion escalada a recepcion",
            }
        except Exception as e:
            logger.error(f"Failed to escalate: {e}")
            return {"success": False, "error": str(e)}


# Tool definitions for Claude tool_use format
TOOL_DEFINITIONS = [
    {
        "name": "get_booking_details",
        "description": (
            "Busca una reserva por numero de confirmacion. "
            "Usalo cuando el huesped pregunte por su reserva, check-in/out, "
            "habitacion, o cualquier detalle de la reserva."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmation_number": {
                    "type": "string",
                    "description": "Numero de confirmacion de la reserva (ej: PLR-2024-001)",
                },
            },
            "required": ["confirmation_number"],
        },
    },
    {
        "name": "get_booking_by_phone",
        "description": (
            "Busca una reserva por numero de telefono del huesped. "
            "Usalo como alternativa cuando no se tiene numero de confirmacion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "Numero de telefono del huesped",
                },
            },
            "required": ["phone"],
        },
    },
    {
        "name": "get_hotel_amenities",
        "description": (
            "Obtiene informacion de todos los amenities del hotel "
            "(WiFi, desayuno, piscina, gym, parking, spa). "
            "Usalo cuando pregunten por servicios o instalaciones."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_hotel_policies",
        "description": (
            "Obtiene las politicas del hotel (horarios de check-in/out, "
            "cancelacion, late checkout, etc)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_faq",
        "description": (
            "Busca en las preguntas frecuentes del hotel. "
            "Usalo para preguntas generales como transporte, mascotas, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pregunta o terminos de busqueda",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_service_request",
        "description": (
            "Registra un pedido de servicio del huesped "
            "(toallas extra, late checkout, wake-up call, etc). "
            "Requiere booking_id del huesped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID de la reserva del huesped",
                },
                "request_type": {
                    "type": "string",
                    "description": "Tipo de pedido (towels, late_checkout, wake_up_call, room_service, cleaning, pillow, other)",
                },
                "details": {
                    "type": "string",
                    "description": "Detalles del pedido en texto libre",
                },
            },
            "required": ["booking_id", "request_type", "details"],
        },
    },
    {
        "name": "get_room_types",
        "description": (
            "Obtiene los tipos de habitacion disponibles con precios y capacidad. "
            "Usalo cuando el huesped pregunte por precios, tipos de habitacion o quiera reservar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Verifica la disponibilidad de habitaciones para fechas y cantidad de huespedes. "
            "Usalo cuando el huesped quiera saber si hay disponibilidad o quiera reservar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "checkin": {
                    "type": "string",
                    "description": "Fecha de check-in en formato YYYY-MM-DD",
                },
                "checkout": {
                    "type": "string",
                    "description": "Fecha de check-out en formato YYYY-MM-DD",
                },
                "num_guests": {
                    "type": "integer",
                    "description": "Cantidad de huespedes",
                },
            },
            "required": ["checkin", "checkout", "num_guests"],
        },
    },
    {
        "name": "create_booking",
        "description": (
            "Crea una nueva reserva para el huesped. "
            "Usalo cuando el huesped confirme que quiere realizar la reserva, "
            "despues de verificar disponibilidad."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "guest_name": {
                    "type": "string",
                    "description": "Nombre completo del huesped",
                },
                "guest_phone": {
                    "type": "string",
                    "description": "Numero de telefono del huesped",
                },
                "guest_email": {
                    "type": "string",
                    "description": "Email del huesped (opcional)",
                },
                "checkin_date": {
                    "type": "string",
                    "description": "Fecha de check-in en formato YYYY-MM-DD",
                },
                "checkout_date": {
                    "type": "string",
                    "description": "Fecha de check-out en formato YYYY-MM-DD",
                },
                "room_type": {
                    "type": "string",
                    "description": "Tipo de habitacion (Standard, Deluxe, Suite)",
                },
                "num_guests": {
                    "type": "integer",
                    "description": "Cantidad de huespedes",
                },
                "special_requests": {
                    "type": "string",
                    "description": "Pedidos especiales (opcional)",
                },
            },
            "required": [
                "guest_name", "guest_phone", "checkin_date",
                "checkout_date", "room_type", "num_guests",
            ],
        },
    },
    {
        "name": "get_upsell_offers",
        "description": (
            "Obtiene las ofertas de upselling disponibles para el huesped. "
            "Usalo cuando el huesped pregunte por upgrades, ofertas, promociones, "
            "o despues de confirmar una nueva reserva para sugerir mejoras."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID de la reserva del huesped (opcional, para filtrar ofertas aplicables)",
                },
            },
        },
    },
    {
        "name": "respond_to_upsell",
        "description": (
            "Registra la respuesta del huesped a una oferta de upselling. "
            "Usalo cuando el huesped acepte o rechace una oferta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID de la reserva del huesped",
                },
                "offer_id": {
                    "type": "string",
                    "description": "UUID de la oferta de upselling",
                },
                "accepted": {
                    "type": "boolean",
                    "description": "true si el huesped acepto, false si rechazo",
                },
            },
            "required": ["booking_id", "offer_id", "accepted"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escala la conversacion a un agente humano (recepcion). "
            "Usalo cuando no puedas resolver la consulta del huesped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "description": "UUID de la conversacion actual",
                },
                "reason": {
                    "type": "string",
                    "description": "Razon de la escalacion",
                },
            },
            "required": ["conversation_id", "reason"],
        },
    },
]
