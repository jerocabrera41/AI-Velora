"""Analytics service for dashboard metrics."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.models import (
    Booking,
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    ResolutionType,
    RoomType,
    UpsellConversion,
    UpsellOffer,
)

DEFAULT_COST_PER_ESCALATION = 15.0


class AnalyticsService:
    """Computes metrics for the dashboard."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_dashboard_metrics(self) -> dict:
        """Get all dashboard metrics in a single call."""
        logger.debug("Computing dashboard metrics")

        total = await self._total_conversations_today()
        auto_resolved = await self._auto_resolved_today()
        avg_response = await self._avg_response_time_ms()
        top_intents = await self._top_intents(limit=8)
        upsell = await self._upsell_metrics()

        outcomes = await self._conversation_outcomes()
        financial = await self._financial_metrics()
        hourly = await self._hourly_distribution()
        upsell_by_offer = await self._upsell_by_offer()
        total_all_time = await self._total_conversations_all_time()
        auto_all_time_pct = await self._auto_resolved_all_time_pct()

        auto_pct = (auto_resolved / total * 100) if total > 0 else 0.0

        return {
            "total_conversations_today": total,
            "auto_resolved_today": auto_resolved,
            "auto_resolved_pct": round(auto_pct, 1),
            "avg_response_time_ms": avg_response,
            "top_intents": top_intents,
            "upsell_revenue": upsell["revenue"],
            "upsell_conversion_rate": upsell["conversion_rate"],
            "outcomes": outcomes,
            "financial": financial,
            "hourly_distribution": hourly,
            "upsell_by_offer": upsell_by_offer,
            "total_conversations_all_time": total_all_time,
            "auto_resolved_all_time_pct": auto_all_time_pct,
        }

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
            msg_count_result = await self.session.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id
                )
            )
            msg_count = msg_count_result.scalar_one()
            outcome = await self._classify_conversation_outcome(conv)

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
                    "outcome": outcome,
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

    # ------------------------------------------------------------------
    # Existing private methods
    # ------------------------------------------------------------------

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

    async def _upsell_metrics(self) -> dict:
        """Compute upsell revenue and conversion rate."""
        total_result = await self.session.execute(
            select(func.count(UpsellConversion.id))
        )
        total_offers = total_result.scalar_one()

        accepted_result = await self.session.execute(
            select(func.count(UpsellConversion.id)).where(
                UpsellConversion.status == "accepted"
            )
        )
        accepted = accepted_result.scalar_one()

        revenue_result = await self.session.execute(
            select(func.coalesce(func.sum(UpsellOffer.price), 0.0))
            .join(UpsellConversion, UpsellConversion.offer_id == UpsellOffer.id)
            .where(UpsellConversion.status == "accepted")
        )
        revenue = float(revenue_result.scalar_one())

        conversion_rate = (accepted / total_offers * 100) if total_offers > 0 else 0.0

        return {
            "revenue": round(revenue, 2),
            "conversion_rate": round(conversion_rate, 1),
        }

    # ------------------------------------------------------------------
    # New: Conversation outcomes
    # ------------------------------------------------------------------

    async def _conversation_outcomes(self) -> dict:
        """Classify all conversations by outcome."""
        now = datetime.now(timezone.utc)
        abandon_threshold = now - timedelta(hours=24)

        # Escalated
        escalated = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.ESCALATED
            )
        )
        escalada = escalated.scalar_one()

        # Abandoned (active + last_message > 24h ago)
        abandoned = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.last_message_at < abandon_threshold,
            )
        )
        abandonada = abandoned.scalar_one()

        # Active (not abandoned)
        active = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.last_message_at >= abandon_threshold,
            )
        )
        en_curso = active.scalar_one()

        # Venta: has booking_id + at least one new_booking intent message
        venta_subq = select(Message.id).where(
            Message.conversation_id == Conversation.id,
            Message.intent == "new_booking",
        ).exists()
        ventas = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.booking_id.isnot(None),
                venta_subq,
            )
        )
        venta = ventas.scalar_one()

        # Upsell exitoso: booking has accepted UpsellConversion
        upsell_subq = select(UpsellConversion.id).where(
            UpsellConversion.booking_id == Conversation.booking_id,
            UpsellConversion.status == "accepted",
        ).exists()
        upsells = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.booking_id.isnot(None),
                upsell_subq,
            )
        )
        upsell_exitoso = upsells.scalar_one()

        # Problema resuelto: resolved+automated with service_request intent
        problema_subq = select(Message.id).where(
            Message.conversation_id == Conversation.id,
            Message.intent == "service_request",
        ).exists()
        problemas = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.RESOLVED,
                Conversation.resolution_type == ResolutionType.AUTOMATED,
                problema_subq,
            )
        )
        problema_resuelto = problemas.scalar_one()

        # Consulta resuelta: resolved+automated without service_request/new_booking
        has_action_intent = select(Message.id).where(
            Message.conversation_id == Conversation.id,
            Message.intent.in_(["service_request", "new_booking"]),
        ).exists()
        consultas = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.RESOLVED,
                Conversation.resolution_type == ResolutionType.AUTOMATED,
                ~has_action_intent,
                Conversation.booking_id.is_(None),
            )
        )
        consulta_resuelta = consultas.scalar_one()

        return {
            "venta": venta,
            "upsell_exitoso": upsell_exitoso,
            "problema_resuelto": problema_resuelto,
            "consulta_resuelta": consulta_resuelta,
            "escalada": escalada,
            "abandonada": abandonada,
            "en_curso": en_curso,
        }

    async def _classify_conversation_outcome(self, conv) -> str:
        """Classify a single conversation's outcome for the list view."""
        now = datetime.now(timezone.utc)
        abandon_threshold = now - timedelta(hours=24)

        if conv.status == ConversationStatus.ESCALATED:
            return "escalada"

        if conv.status == ConversationStatus.ACTIVE:
            last = conv.last_message_at
            if last:
                # Ensure timezone-aware comparison
                last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
                if last_aware < abandon_threshold:
                    return "abandonada"
            return "en_curso"

        # Resolved conversation -- check for upsell first (higher value)
        if conv.booking_id:
            upsell_result = await self.session.execute(
                select(func.count(UpsellConversion.id)).where(
                    UpsellConversion.booking_id == conv.booking_id,
                    UpsellConversion.status == "accepted",
                )
            )
            if upsell_result.scalar_one() > 0:
                return "upsell_exitoso"

            # Check for new_booking intent
            intent_result = await self.session.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id,
                    Message.intent == "new_booking",
                )
            )
            if intent_result.scalar_one() > 0:
                return "venta"

        # Check for service_request intent
        sr_result = await self.session.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conv.id,
                Message.intent == "service_request",
            )
        )
        if sr_result.scalar_one() > 0:
            return "problema_resuelto"

        return "consulta_resuelta"

    # ------------------------------------------------------------------
    # New: Financial metrics
    # ------------------------------------------------------------------

    async def _financial_metrics(self) -> dict:
        """Compute financial metrics from bookings and upsells."""
        # Booking revenue: only bookings linked to conversations
        result = await self.session.execute(
            select(Booking, RoomType)
            .join(Conversation, Conversation.booking_id == Booking.id)
            .join(
                RoomType,
                (RoomType.hotel_id == Booking.hotel_id)
                & (RoomType.name == Booking.room_type),
            )
        )
        rows = result.all()

        booking_revenue = 0.0
        for booking, room_type in rows:
            try:
                checkin = date.fromisoformat(booking.checkin_date)
                checkout = date.fromisoformat(booking.checkout_date)
                nights = (checkout - checkin).days
                if nights > 0:
                    booking_revenue += room_type.price_per_night * nights
            except (ValueError, TypeError):
                continue

        # Upsell revenue (reuse existing)
        upsell = await self._upsell_metrics()
        upsell_revenue = upsell["revenue"]

        # Estimated savings: all auto-resolved conversations * cost per escalation
        auto_resolved_result = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.RESOLVED,
                Conversation.resolution_type == ResolutionType.AUTOMATED,
            )
        )
        auto_resolved_count = auto_resolved_result.scalar_one()
        estimated_savings = auto_resolved_count * DEFAULT_COST_PER_ESCALATION

        total_agent_revenue = booking_revenue + upsell_revenue

        return {
            "booking_revenue": round(booking_revenue, 2),
            "upsell_revenue": round(upsell_revenue, 2),
            "estimated_savings": round(estimated_savings, 2),
            "total_agent_revenue": round(total_agent_revenue, 2),
            "cost_per_escalation": DEFAULT_COST_PER_ESCALATION,
        }

    # ------------------------------------------------------------------
    # New: Hourly distribution
    # ------------------------------------------------------------------

    async def _hourly_distribution(self) -> list[dict]:
        """Count conversations started per hour of day (all time)."""
        result = await self.session.execute(
            select(
                func.cast(
                    func.strftime("%H", Conversation.started_at), Integer
                ).label("hour"),
                func.count(Conversation.id).label("count"),
            )
            .group_by("hour")
            .order_by("hour")
        )
        rows = result.all()

        hour_counts = {row[0]: row[1] for row in rows}
        return [
            {"hour": h, "count": hour_counts.get(h, 0)} for h in range(24)
        ]

    # ------------------------------------------------------------------
    # New: Upsell by offer
    # ------------------------------------------------------------------

    async def _upsell_by_offer(self) -> list[dict]:
        """Break down upsell performance by individual offer."""
        result = await self.session.execute(
            select(
                UpsellOffer.name,
                UpsellOffer.offer_type,
                UpsellOffer.price,
                func.count(UpsellConversion.id).label("offered_count"),
                func.sum(
                    case(
                        (UpsellConversion.status == "accepted", 1),
                        else_=0,
                    )
                ).label("accepted_count"),
            )
            .join(UpsellConversion, UpsellConversion.offer_id == UpsellOffer.id)
            .group_by(
                UpsellOffer.id,
                UpsellOffer.name,
                UpsellOffer.offer_type,
                UpsellOffer.price,
            )
            .order_by(func.count(UpsellConversion.id).desc())
        )
        rows = result.all()

        return [
            {
                "offer_name": row[0],
                "offer_type": row[1],
                "offered_count": row[3],
                "accepted_count": row[4] or 0,
                "revenue": round(row[2] * (row[4] or 0), 2),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # New: All-time totals
    # ------------------------------------------------------------------

    async def _total_conversations_all_time(self) -> int:
        result = await self.session.execute(
            select(func.count(Conversation.id))
        )
        return result.scalar_one()

    async def _auto_resolved_all_time_pct(self) -> float:
        total = await self._total_conversations_all_time()
        if total == 0:
            return 0.0
        resolved = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.resolution_type == ResolutionType.AUTOMATED,
            )
        )
        auto = resolved.scalar_one()
        return round(auto / total * 100, 1)
