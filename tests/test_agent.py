"""Tests for the hotel agent (integration-level, using mocked LLM)."""

import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from src.agent.core import HotelAgent
from src.database.models import MessageRole, Platform
from src.database.seed import HOTEL_ID
from src.services.conversation_service import ConversationService
from src.services.pms_service import PMSService


@pytest_asyncio.fixture
async def services(db_session):
    pms = PMSService(db_session)
    conv_service = ConversationService(db_session)
    return pms, conv_service


@pytest_asyncio.fixture
async def conversation(services, db_session):
    """Create a test conversation."""
    _, conv_service = services
    conv = await conv_service.get_or_create_conversation(
        guest_phone="+5491112345678",
        hotel_id=HOTEL_ID,
        platform=Platform.TELEGRAM,
    )
    return conv


def _mock_anthropic_response(text: str):
    """Create a mock Anthropic API response."""
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = text

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.stop_reason = "end_turn"
    return mock_response


@pytest.mark.asyncio
async def test_greeting_response(services, conversation):
    """Verify that the agent responds to greetings appropriately."""
    pms, conv_service = services

    with patch("src.agent.core.anthropic") as mock_anthropic:
        # Mock intent classification to return "greeting"
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("greeting")
        )

        agent = HotelAgent(pms, conv_service, HOTEL_ID)
        result = await agent.process_message(
            user_message="Hola, buenas tardes!",
            guest_phone="+5491112345678",
            conversation_id=conversation.id,
        )

        assert result["response"] != ""
        assert result["intent"] == "greeting"
        # Greeting handler doesn't call LLM for response, just builds it
        assert "Palermo Soho" in result["response"] or "Sofia" in result["response"]


@pytest.mark.asyncio
async def test_booking_info_intent_detected(services, conversation):
    """Verify that booking_info intent is correctly detected."""
    pms, conv_service = services

    with patch("src.agent.core.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        # First call = intent classification, second = response generation
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _mock_anthropic_response("booking_info"),
                _mock_anthropic_response(
                    "Tu check-in es a las 15:00hs, Juan!"
                ),
            ]
        )

        agent = HotelAgent(pms, conv_service, HOTEL_ID)
        result = await agent.process_message(
            user_message="A que hora es el check-in?",
            guest_phone="+5491112345678",
            conversation_id=conversation.id,
        )

        assert result["intent"] == "booking_info"
        assert result["response"] != ""


@pytest.mark.asyncio
async def test_out_of_scope_escalation(services, conversation):
    """Verify that out-of-scope queries are handled gracefully."""
    pms, conv_service = services

    with patch("src.agent.core.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        mock_client.messages.create = AsyncMock(
            side_effect=[
                _mock_anthropic_response("out_of_scope"),
                _mock_anthropic_response(
                    "Esa consulta excede lo que puedo resolver. "
                    "Te comunico con recepcion."
                ),
            ]
        )

        agent = HotelAgent(pms, conv_service, HOTEL_ID)
        result = await agent.process_message(
            user_message="Quiero reservar una mesa en un restaurante",
            guest_phone="+5491112345678",
            conversation_id=conversation.id,
        )

        assert result["intent"] == "out_of_scope"
        assert result["response"] != ""


@pytest.mark.asyncio
async def test_amenities_query_intent(services, conversation):
    """Verify that amenities queries are detected correctly."""
    pms, conv_service = services

    with patch("src.agent.core.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        mock_client.messages.create = AsyncMock(
            side_effect=[
                _mock_anthropic_response("amenities_query"),
                _mock_anthropic_response(
                    "Si! Tenemos WiFi gratuito. La clave es palermo2024."
                ),
            ]
        )

        agent = HotelAgent(pms, conv_service, HOTEL_ID)
        result = await agent.process_message(
            user_message="Tienen WiFi?",
            guest_phone="+5491112345678",
            conversation_id=conversation.id,
        )

        assert result["intent"] == "amenities_query"
        assert result["response"] != ""
