"""Tests for intent classification (keyword fallback)."""

import pytest

from src.agent.intents import Intent, classify_intent_fallback, parse_llm_intent


class TestClassifyIntentFallback:
    def test_greeting(self):
        assert classify_intent_fallback("Hola, buenas tardes!") == Intent.GREETING

    def test_greeting_buenos_dias(self):
        assert classify_intent_fallback("Buenos dias") == Intent.GREETING

    def test_booking_info_checkin(self):
        assert classify_intent_fallback("A que hora es el check-in?") == Intent.BOOKING_INFO

    def test_booking_info_reserva(self):
        assert classify_intent_fallback("Quiero saber sobre mi reserva") == Intent.BOOKING_INFO

    def test_amenities_wifi(self):
        assert classify_intent_fallback("Tienen WiFi?") == Intent.AMENITIES_QUERY

    def test_amenities_breakfast(self):
        assert classify_intent_fallback("Hay desayuno incluido?") == Intent.AMENITIES_QUERY

    def test_amenities_pool(self):
        assert classify_intent_fallback("Donde esta la piscina?") == Intent.AMENITIES_QUERY

    def test_service_request_towels(self):
        assert classify_intent_fallback("Necesito toallas extra") == Intent.SERVICE_REQUEST

    def test_service_request_late_checkout(self):
        assert classify_intent_fallback("Quiero late checkout") == Intent.SERVICE_REQUEST

    def test_faq_airport(self):
        assert classify_intent_fallback("Como llego desde el aeropuerto?") == Intent.FAQ_GENERAL

    def test_faq_pets(self):
        assert classify_intent_fallback("Aceptan mascotas?") == Intent.FAQ_GENERAL

    def test_new_booking_reservar(self):
        assert classify_intent_fallback("Quiero reservar, hay disponibilidad?") == Intent.NEW_BOOKING

    def test_new_booking_disponibilidad(self):
        assert classify_intent_fallback("Hay disponibilidad para el proximo fin de semana?") == Intent.NEW_BOOKING

    def test_new_booking_precio(self):
        assert classify_intent_fallback("Cuanto cuesta una standard?") == Intent.NEW_BOOKING

    def test_new_booking_tarifas(self):
        assert classify_intent_fallback("Me pasan las tarifas?") == Intent.NEW_BOOKING

    def test_out_of_scope(self):
        assert classify_intent_fallback("Cual es el sentido de la vida?") == Intent.OUT_OF_SCOPE


class TestParseLlmIntent:
    def test_exact_match(self):
        assert parse_llm_intent("booking_info") == Intent.BOOKING_INFO

    def test_with_whitespace(self):
        assert parse_llm_intent("  amenities_query  ") == Intent.AMENITIES_QUERY

    def test_partial_match(self):
        assert parse_llm_intent("greeting response") == Intent.GREETING

    def test_new_booking(self):
        assert parse_llm_intent("new_booking") == Intent.NEW_BOOKING

    def test_invalid_returns_out_of_scope(self):
        assert parse_llm_intent("completely_invalid_thing") == Intent.OUT_OF_SCOPE
