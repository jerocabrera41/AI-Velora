"""Application entry point: starts FastAPI server and Telegram bot concurrently."""

import asyncio
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src.api.routes import router
from src.config import settings
from src.database.database import async_session, close_db, init_db
from src.database.seed import seed_database


# --- Logging setup ---

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
)
logger.add(
    "logs/hotel_agent.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
)


# --- FastAPI app ---

app = FastAPI(
    title="AI Velora - Hotel Agent MVP",
    description="AI-powered hotel concierge agent for Telegram",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
app.include_router(router)


@app.on_event("startup")
async def startup():
    logger.info("Starting AI Velora Hotel Agent...")
    await init_db()
    async with async_session() as session:
        await seed_database(session)
    logger.info("Database initialized and seeded")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down AI Velora Hotel Agent...")
    await close_db()


# --- Main runner ---


async def run_bot():
    """Run the Telegram bot in polling mode."""
    from src.bot import create_bot_application

    if not settings.telegram_bot_token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set - Telegram bot will NOT start. "
            "Set the token in .env to enable the bot."
        )
        return

    application = create_bot_application()
    logger.info("Starting Telegram bot polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Keep running until cancelled
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Stopping Telegram bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


async def run_server():
    """Run the FastAPI server."""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Run both the web server and Telegram bot concurrently."""
    logger.info("=" * 60)
    logger.info("AI Velora - Hotel Agent MVP v0.1.0")
    logger.info("=" * 60)

    bot_task = asyncio.create_task(run_bot())
    server_task = asyncio.create_task(run_server())

    try:
        await asyncio.gather(server_task, bot_task)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received shutdown signal")
        bot_task.cancel()
        server_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
