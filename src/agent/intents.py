"""Intent classification for guest messages."""

from enum import Enum

from loguru import logger


class Intent(str, Enum):
    BOOKING_INFO = "booking_info"
    AMENITIES_QUERY = "amenities_query"
    SERVICE_REQUEST = "service_request"
    FAQ_GENERAL = "faq_general"
    GREETING = "greeting"
    OUT_OF_SCOPE = "out_of_scope"


# Keyword-based fallback classification (used if LLM classification fails)
INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.GREETING: [
        "hola", "buenos dias", "buenas tardes", "buenas noches",
        "hey", "hi", "hello", "buen dia", "que tal",
    ],
    Intent.BOOKING_INFO: [
        "reserva", "check-in", "checkin", "check-out", "checkout",
        "confirmacion", "habitacion", "room", "fecha", "noche",
        "llegada", "salida", "booking", "reservation",
    ],
    Intent.AMENITIES_QUERY: [
        "wifi", "internet", "desayuno", "breakfast", "piscina", "pileta",
        "pool", "gym", "gimnasio", "parking", "estacionamiento",
        "spa", "sauna",
    ],
    Intent.SERVICE_REQUEST: [
        "toalla", "towel", "late checkout", "wake up", "despertar",
        "room service", "almohada", "pillow", "limpieza", "cleaning",
        "necesito", "quiero", "podrian", "pueden",
    ],
    Intent.FAQ_GENERAL: [
        "aeropuerto", "airport", "taxi", "transfer", "mascota", "pet",
        "lavanderia", "laundry", "caja fuerte", "safe",
        "como llego", "direccion", "donde queda",
    ],
}


def classify_intent_fallback(message: str) -> Intent:
    """Keyword-based intent classification as a fallback.

    Used when the LLM is unavailable or returns an invalid response.
    """
    text = message.lower().strip()

    # Score each intent by keyword matches
    scores: dict[Intent, int] = {intent: 0 for intent in Intent}
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[intent] += 1

    best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]

    if scores[best_intent] == 0:
        logger.debug(f"No keyword match for: '{text}', defaulting to out_of_scope")
        return Intent.OUT_OF_SCOPE

    logger.debug(f"Fallback classification: '{text}' -> {best_intent.value}")
    return best_intent


def parse_llm_intent(raw: str) -> Intent:
    """Parse the LLM's intent classification response into an Intent enum."""
    cleaned = raw.strip().lower().replace(" ", "_")

    try:
        return Intent(cleaned)
    except ValueError:
        # Try partial matching
        for intent in Intent:
            if intent.value in cleaned or cleaned in intent.value:
                return intent

        logger.warning(f"Could not parse LLM intent: '{raw}', using fallback")
        return Intent.OUT_OF_SCOPE
