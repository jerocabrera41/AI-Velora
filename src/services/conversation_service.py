"""Service for managing conversations and messages."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from src.database.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    Platform,
    ResolutionType,
)
from src.config import settings


class ConversationService:
    """Handles conversation lifecycle and message persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_conversation(
        self,
        guest_phone: str,
        hotel_id: uuid.UUID,
        platform: Platform = Platform.TELEGRAM,
        booking_id: uuid.UUID | None = None,
    ) -> Conversation:
        """Get an active conversation for the guest, or create a new one."""
        # Look for an existing active conversation
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.guest_phone == guest_phone,
                Conversation.hotel_id == hotel_id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()

        if conversation is not None:
            # Check if conversation has timed out
            timeout = timedelta(hours=settings.conversation_timeout_hours)
            if (
                conversation.last_message_at
                and datetime.now(timezone.utc) - conversation.last_message_at.replace(
                    tzinfo=timezone.utc
                )
                > timeout
            ):
                logger.info(
                    f"Conversation {conversation.id} timed out, closing and creating new one"
                )
                conversation.status = ConversationStatus.RESOLVED
                conversation.resolution_type = ResolutionType.AUTOMATED
                await self.session.commit()
            else:
                logger.debug(f"Resuming conversation {conversation.id}")
                return conversation

        # Create new conversation
        conversation = Conversation(
            hotel_id=hotel_id,
            guest_phone=guest_phone,
            booking_id=booking_id,
            platform=platform,
            status=ConversationStatus.ACTIVE,
        )
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)

        logger.info(f"New conversation created: {conversation.id} for {guest_phone}")
        return conversation

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        intent: str | None = None,
        metadata: dict | None = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            intent=intent,
            metadata_json=metadata or {},
        )
        self.session.add(message)

        # Update conversation last_message_at
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_message_at=datetime.now(timezone.utc))
        )

        await self.session.commit()
        await self.session.refresh(message)

        logger.debug(
            f"Message added to conversation {conversation_id}: "
            f"role={role.value}, intent={intent}"
        )
        return message

    async def get_conversation_history(
        self,
        conversation_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[dict]:
        """Get message history for a conversation."""
        limit = limit or settings.max_conversation_history

        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))

        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "intent": msg.intent,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]

    async def escalate_conversation(
        self, conversation_id: uuid.UUID, reason: str
    ) -> None:
        """Mark a conversation as escalated (handoff to human)."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                status=ConversationStatus.ESCALATED,
                resolution_type=ResolutionType.HUMAN_HANDOFF,
            )
        )
        await self.session.commit()
        logger.info(f"Conversation {conversation_id} escalated: {reason}")

    async def resolve_conversation(self, conversation_id: uuid.UUID) -> None:
        """Mark a conversation as resolved automatically."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                status=ConversationStatus.RESOLVED,
                resolution_type=ResolutionType.AUTOMATED,
            )
        )
        await self.session.commit()
        logger.info(f"Conversation {conversation_id} resolved automatically")

    async def get_conversation_by_id(
        self, conversation_id: uuid.UUID
    ) -> Conversation | None:
        """Get a conversation with its messages."""
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def link_booking(
        self, conversation_id: uuid.UUID, booking_id: uuid.UUID
    ) -> None:
        """Associate a booking with a conversation."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(booking_id=booking_id)
        )
        await self.session.commit()
        logger.info(
            f"Linked booking {booking_id} to conversation {conversation_id}"
        )

    async def reset_conversation(self, guest_phone: str, hotel_id: uuid.UUID) -> None:
        """Close all active conversations for a guest (used by /reset command)."""
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.guest_phone == guest_phone,
                Conversation.hotel_id == hotel_id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
            .values(
                status=ConversationStatus.RESOLVED,
                resolution_type=ResolutionType.AUTOMATED,
            )
        )
        await self.session.commit()
        logger.info(f"Reset conversations for {guest_phone}")
