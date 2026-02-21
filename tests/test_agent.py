"""Tests for the hotel agent (integration-level, using mocked LLM)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.agent.core import HotelAgent
from src.database.models import Platform
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

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response("greeting")
    )

    with patch("src.agent.core.anthropic.AsyncAnthropic", return_value=mock_client):
        agent = HotelAgent(pms, conv_service, HOTEL_ID)
        result = await agent.process_message(
            user_message="Hola, buenas tardes!",
            guest_phone="+5491112345678",
            conversation_id=conversation.id,
        )

    assert result["response"] != ""
    assert result["intent"] == "greeting"
    assert "Palermo Soho" in result["response"] or "Velora" in result["response"]


@pytest.mark.asyncio
async def test_booking_info_intent_detected(services, conversation):
    """Verify that booking_info intent is correctly detected."""
    pms, conv_service = services

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_anthropic_response("booking_info"),
            _mock_anthropic_response("Tu check-in es a las 15:00hs, Juan!"),
        ]
    )

    with patch("src.agent.core.anthropic.AsyncAnthropic", return_value=mock_client):
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

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_anthropic_response("out_of_scope"),
            _mock_anthropic_response(
                "Esa consulta excede lo que puedo resolver. Te comunico con recepcion."
            ),
        ]
    )

    with patch("src.agent.core.anthropic.AsyncAnthropic", return_value=mock_client):
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

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_anthropic_response("amenities_query"),
            _mock_anthropic_response(
                "Si! Tenemos WiFi gratuito. La clave es palermo2024."
            ),
        ]
    )

    with patch("src.agent.core.anthropic.AsyncAnthropic", return_value=mock_client):
        agent = HotelAgent(pms, conv_service, HOTEL_ID)
        result = await agent.process_message(
            user_message="Tienen WiFi?",
            guest_phone="+5491112345678",
            conversation_id=conversation.id,
        )

    assert result["intent"] == "amenities_query"
    assert result["response"] != ""
