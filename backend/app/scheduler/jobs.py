"""Scheduler jobs - periodic data updates"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import async_session
from app.config import get_settings
from app.scrapers.odds_api import fetch_odds_from_api, store_odds
from app.scrapers.rss import fetch_rss_news, analyze_sentiment_batch
from app.scrapers.football_api import job_update_football

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler()


async def job_update_odds():
    """Fetch and store latest odds"""
    logger.info("⏰ Running odds update job...")
    try:
        events = await fetch_odds_from_api()
        if events:
            async with async_session() as db:
                await store_odds(db, events)
        logger.info(f"✅ Odds update complete: {len(events)} events")
    except Exception as e:
        logger.error(f"❌ Odds update failed: {e}")


async def job_update_news():
    """Fetch RSS news and run sentiment analysis"""
    logger.info("⏰ Running news update job...")
    try:
        async with async_session() as db:
            await fetch_rss_news(db)
            await analyze_sentiment_batch(db)
        logger.info("✅ News update complete")
    except Exception as e:
        logger.error(f"❌ News update failed: {e}")


async def job_update_football_job():
    """Fetch injuries and news from API-Football"""
    logger.info("⏰ Running API-Football update job...")
    try:
        async with async_session() as db:
            await job_update_football(db)
        logger.info("✅ API-Football update complete")
    except Exception as e:
        logger.error(f"❌ API-Football update failed: {e}")


def start_scheduler():
    """Start all scheduled jobs with staggered first runs"""
    scheduler.start()

    now = datetime.now()  # use local time to match APScheduler's internal clock
    # Odds: run in 10s (core data, highest priority)
    scheduler.add_job(
        job_update_odds, "interval",
        minutes=settings.odds_update_interval,
        id="odds_update",
        misfire_grace_time=300,
        next_run_time=now + timedelta(seconds=10),
    )
    # News: wait for first interval (RSS is free, no rush)
    scheduler.add_job(
        job_update_news, "interval",
        minutes=settings.news_update_interval,
        id="news_update",
        misfire_grace_time=300,
    )
    # Football: delayed 3min after odds (avoid concurrent API calls)
    scheduler.add_job(
        job_update_football_job, "interval",
        minutes=settings.injury_update_interval,
        id="football_update",
        misfire_grace_time=300,
        next_run_time=now + timedelta(minutes=3),
    )

    logger.info(
        f"📅 Scheduler started: odds every {settings.odds_update_interval}min, "
        f"news every {settings.news_update_interval}min, "
        f"football every {settings.injury_update_interval}min"
    )


def stop_scheduler():
    """Stop all scheduled jobs"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("📅 Scheduler stopped")
