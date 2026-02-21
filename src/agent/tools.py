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
