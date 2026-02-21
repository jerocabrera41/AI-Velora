"""Pydantic schemas for API responses."""

from datetime import datetime

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_conversations_today: int
    auto_resolved_today: int
    auto_resolved_pct: float
    avg_response_time_ms: int
    top_intents: list[dict]
    upsell_revenue: float = 0.0
    upsell_conversion_rate: float = 0.0


class ConversationListItem(BaseModel):
    id: str
    guest_phone: str
    platform: str
    status: str
    resolution_type: str | None
    started_at: str | None
    last_message_at: str | None
    message_count: int


class MessageDetail(BaseModel):
    id: str
    role: str
    content: str
    intent: str | None
    metadata: dict | None
    created_at: str | None


class ConversationDetail(BaseModel):
    id: str
    guest_phone: str
    platform: str
    status: str
    resolution_type: str | None
    started_at: str | None
    last_message_at: str | None
    messages: list[MessageDetail]


class HealthResponse(BaseModel):
    status: str
    version: str
