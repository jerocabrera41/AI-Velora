"""Telegram bot entry point."""

import uuid

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from loguru import logger

from src.agent.core import HotelAgent
from src.config import settings
from src.database.database import async_session
from src.database.models import MessageRole, Platform
from src.database.seed import HOTEL_ID
from src.services.conversation_service import ConversationService
from src.services.pms_service import PMSService


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    logger.info(f"/start from user {update.effective_user.id}")
    await update.message.reply_text(
        "Hola! Bienvenido/a a Hotel Palermo Soho.\n\n"
        "Soy Sofia, tu asistente virtual. Puedo ayudarte con:\n"
        "- Informacion de tu reserva\n"
        "- Amenities del hotel (WiFi, desayuno, piscina...)\n"
        "- Pedidos de servicio (toallas, late checkout...)\n"
        "- Preguntas frecuentes\n\n"
        "Si tenes una reserva, compartime tu numero de confirmacion "
        "para brindarte atencion personalizada.\n\n"
        "Comandos:\n"
        "/help - Ver que puedo hacer\n"
        "/reset - Reiniciar conversacion"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    logger.info(f"/help from user {update.effective_user.id}")
    await update.message.reply_text(
        "Soy Sofia, el asistente virtual de Hotel Palermo Soho.\n\n"
        "Puedo ayudarte con:\n"
        "1. Informacion de reserva - check-in/out, confirmacion, habitacion\n"
        "2. Amenities - WiFi, desayuno, piscina, gym, parking\n"
        "3. Pedidos - toallas extra, late checkout, wake-up call\n"
        "4. Preguntas generales - como llegar, mascotas, lavanderia\n\n"
        "Simplemente escribime tu consulta y te respondo al toque!\n\n"
        "Si no puedo resolver algo, te conecto con recepcion."
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command - clears conversation context."""
    logger.info(f"/reset from user {update.effective_user.id}")
    guest_phone = str(update.effective_user.id)

    async with async_session() as session:
        conv_service = ConversationService(session)
        await conv_service.reset_conversation(guest_phone, HOTEL_ID)

    await update.message.reply_text(
        "Listo, reinicie la conversacion. Empecemos de nuevo!\n"
        "En que puedo ayudarte?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user_message = update.message.text
    guest_phone = str(update.effective_user.id)

    logger.info(
        f"Message from {guest_phone}: '{user_message[:80]}...'"
        if len(user_message) > 80
        else f"Message from {guest_phone}: '{user_message}'"
    )

    async with async_session() as session:
        pms = PMSService(session)
        conv_service = ConversationService(session)

        # Get or create conversation
        conversation = await conv_service.get_or_create_conversation(
            guest_phone=guest_phone,
            hotel_id=HOTEL_ID,
            platform=Platform.TELEGRAM,
        )

        # Try to link booking by phone if not already linked
        if conversation.booking_id is None:
            booking = await pms.get_booking_by_phone(guest_phone)
            if booking:
                await conv_service.link_booking(
                    conversation.id, uuid.UUID(booking["id"])
                )

        # Save user message
        await conv_service.add_message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message,
        )

        # Process with agent
        agent = HotelAgent(
            pms=pms,
            conversation_service=conv_service,
            hotel_id=HOTEL_ID,
        )

        try:
            result = await agent.process_message(
                user_message=user_message,
                guest_phone=guest_phone,
                conversation_id=conversation.id,
            )

            response_text = result["response"]
            intent = result.get("intent", "")
            metadata = result.get("metadata", {})

        except Exception as e:
            logger.error(f"Agent error: {e}")
            response_text = (
                "Disculpa, tuve un problema tecnico. "
                "Por favor intenta de nuevo o contacta a recepcion "
                "al +54 11 4833-1234."
            )
            intent = "error"
            metadata = {"error": str(e)}

        # Save assistant response
        await conv_service.add_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            intent=intent,
            metadata=metadata,
        )

    # Send response to user
    await update.message.reply_text(response_text)
    logger.info(f"Response sent to {guest_phone} (intent={intent})")


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    if not settings.telegram_bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set. Get one from @BotFather on Telegram."
        )

    application = Application.builder().token(settings.telegram_bot_token).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Telegram bot application created")
    return application
