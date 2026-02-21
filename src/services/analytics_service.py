"""Analytics service for dashboard metrics."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    ResolutionType,
)


class AnalyticsService:
    """Computes metrics for the dashboard."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_dashboard_metrics(self) -> dict:
        """Get all dashboard metrics in a single call."""
        logger.debug("Computing dashboard metrics")

        total = await self._total_conversations_today()
        auto_resolved = await self._auto_resolved_today()
        avg_response = await self._avg_response_time_ms()
        top_intents = await self._top_intents(limit=5)

        auto_pct = (auto_resolved / total * 100) if total > 0 else 0.0

        return {
            "total_conversations_today": total,
            "auto_resolved_today": auto_resolved,
            "auto_resolved_pct": round(auto_pct, 1),
            "avg_response_time_ms": avg_response,
            "top_intents": top_intents,
        }

    async def _total_conversations_today(self) -> int:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.started_at >= today_start
            )
        )
        return result.scalar_one()

    async def _auto_resolved_today(self) -> int:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.started_at >= today_start,
                Conversation.resolution_type == ResolutionType.AUTOMATED,
            )
        )
        return result.scalar_one()

    async def _avg_response_time_ms(self) -> int:
        """Average response time from metadata of assistant messages."""
        result = await self.session.execute(
            select(Message.metadata_json)
            .where(Message.role == MessageRole.ASSISTANT)
            .order_by(Message.created_at.desc())
            .limit(50)
        )
        rows = result.scalars().all()

        latencies = []
        for meta in rows:
            if meta and isinstance(meta, dict) and "latency_ms" in meta:
                latencies.append(meta["latency_ms"])

        if not latencies:
            return 0

        return int(sum(latencies) / len(latencies))

    async def _top_intents(self, limit: int = 5) -> list[dict]:
        """Most common intents across all messages."""
        result = await self.session.execute(
            select(
                Message.intent,
                func.count(Message.id).label("count"),
            )
            .where(Message.intent.isnot(None))
            .group_by(Message.intent)
            .order_by(func.count(Message.id).desc())
            .limit(limit)
        )
        rows = result.all()
        return [{"intent": row[0], "count": row[1]} for row in rows]

    async def get_conversations_list(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """Get conversations for the dashboard list view."""
        result = await self.session.execute(
            select(Conversation)
            .order_by(Conversation.last_message_at.desc())
            .limit(limit)
            .offset(offset)
        )
        conversations = result.scalars().all()

        items = []
        for conv in conversations:
            # Count messages
            msg_count_result = await self.session.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id
                )
            )
            msg_count = msg_count_result.scalar_one()

            items.append(
                {
                    "id": str(conv.id),
                    "guest_phone": conv.guest_phone,
                    "platform": conv.platform.value if conv.platform else "unknown",
                    "status": conv.status.value if conv.status else "unknown",
                    "resolution_type": (
                        conv.resolution_type.value if conv.resolution_type else None
                    ),
                    "started_at": (
                        conv.started_at.isoformat() if conv.started_at else None
                    ),
                    "last_message_at": (
                        conv.last_message_at.isoformat()
                        if conv.last_message_at
                        else None
                    ),
                    "message_count": msg_count,
                }
            )

        return items

    async def get_conversation_detail(self, conversation_id: str) -> dict | None:
        """Get full conversation with all messages."""
        import uuid

        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            return None

        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conv_uuid)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return None

        msg_result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()

        return {
            "id": str(conv.id),
            "guest_phone": conv.guest_phone,
            "platform": conv.platform.value if conv.platform else "unknown",
            "status": conv.status.value if conv.status else "unknown",
            "resolution_type": (
                conv.resolution_type.value if conv.resolution_type else None
            ),
            "started_at": conv.started_at.isoformat() if conv.started_at else None,
            "last_message_at": (
                conv.last_message_at.isoformat() if conv.last_message_at else None
            ),
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role.value,
                    "content": msg.content,
                    "intent": msg.intent,
                    "metadata": msg.metadata_json,
                    "created_at": (
                        msg.created_at.isoformat() if msg.created_at else None
                    ),
                }
                for msg in messages
            ],
        }
