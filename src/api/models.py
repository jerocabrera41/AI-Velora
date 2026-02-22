"""Pydantic schemas for API responses."""

from datetime import datetime

from pydantic import BaseModel


class ConversationOutcomes(BaseModel):
    venta: int = 0
    upsell_exitoso: int = 0
    problema_resuelto: int = 0
    consulta_resuelta: int = 0
    escalada: int = 0
    abandonada: int = 0
    en_curso: int = 0


class FinancialMetrics(BaseModel):
    booking_revenue: float = 0.0
    upsell_revenue: float = 0.0
    estimated_savings: float = 0.0
    total_agent_revenue: float = 0.0
    cost_per_escalation: float = 15.0


class HourlyDistribution(BaseModel):
    hour: int
    count: int


class UpsellOfferMetric(BaseModel):
    offer_name: str
    offer_type: str
    offered_count: int
    accepted_count: int
    revenue: float


class MetricsResponse(BaseModel):
    total_conversations_today: int
    auto_resolved_today: int
    auto_resolved_pct: float
    avg_response_time_ms: int
    top_intents: list[dict]
    upsell_revenue: float = 0.0
    upsell_conversion_rate: float = 0.0
    outcomes: ConversationOutcomes | None = None
    financial: FinancialMetrics | None = None
    hourly_distribution: list[HourlyDistribution] = []
    upsell_by_offer: list[UpsellOfferMetric] = []
    total_conversations_all_time: int = 0
    auto_resolved_all_time_pct: float = 0.0


class ConversationListItem(BaseModel):
    id: str
    guest_phone: str
    platform: str
    status: str
    resolution_type: str | None
    started_at: str | None
    last_message_at: str | None
    message_count: int
    outcome: str | None = None


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
