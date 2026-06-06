"""WC2026 Betting Predictor - FastAPI Backend"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, async_session
from app.routers import matches, predictions, odds, news, betting
from app.services.seed import seed_database
from app.scheduler.jobs import start_scheduler, stop_scheduler

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting WC2026 Betting Predictor API...")
    await init_db()

    async with async_session() as db:
        await seed_database(db)

    start_scheduler()
    logger.info("✅ Startup complete")

    yield

    # Shutdown
    stop_scheduler()
    logger.info("👋 Shutdown complete")


app = FastAPI(
    title="WC2026 Betting Predictor API",
    description="2026 FIFA World Cup prediction engine with real odds and news",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(matches.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(odds.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(betting.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "wc2026-betting-predictor"}


@app.get("/api/data-status")
async def data_status():
    """Check when data was last updated"""
    from app.models.odds import MatchOdds
    from app.models.news import TeamNews
    from sqlalchemy import select, func

    async with async_session() as db:
        last_odds = (await db.execute(
            select(func.max(MatchOdds.fetched_at))
        )).scalar()
        last_news = (await db.execute(
            select(func.max(TeamNews.fetched_at))
        )).scalar()

    return {
        "lastOddsUpdate": last_odds.isoformat() if last_odds else None,
        "lastNewsUpdate": last_news.isoformat() if last_news else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
