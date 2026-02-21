"""API routes for the dashboard and health checks."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.api.models import (
    ConversationDetail,
    ConversationListItem,
    HealthResponse,
    MetricsResponse,
)
from src.database.database import get_session
from src.services.analytics_service import AnalyticsService

router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")


# --- Health ---


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version="0.1.0")


# --- API endpoints (JSON) ---


@router.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics(session: AsyncSession = Depends(get_session)):
    logger.debug("API: fetching metrics")
    analytics = AnalyticsService(session)
    metrics = await analytics.get_dashboard_metrics()
    return MetricsResponse(**metrics)


@router.get("/api/conversations", response_model=list[ConversationListItem])
async def get_conversations(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    logger.debug(f"API: fetching conversations (limit={limit}, offset={offset})")
    analytics = AnalyticsService(session)
    items = await analytics.get_conversations_list(limit=limit, offset=offset)
    return [ConversationListItem(**item) for item in items]


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    logger.debug(f"API: fetching conversation {conversation_id}")
    analytics = AnalyticsService(session)
    detail = await analytics.get_conversation_detail(conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail(**detail)


# --- Dashboard (HTML) ---


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
