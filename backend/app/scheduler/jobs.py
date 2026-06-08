"""Scheduler jobs - periodic data updates"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.database import async_session
from app.config import get_settings
from app.scrapers.odds_api import fetch_odds_from_api, store_odds
from app.scrapers.rss import fetch_rss_news, analyze_sentiment_batch
from app.scrapers.football_api import job_update_football
from app.models.bet import Bet, BettingSession
from app.models.match import Match

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


async def job_auto_settle_bets():
    """Auto-settle bets for matches that have finished"""
    logger.info("⏰ Running auto-settle check...")
    try:
        async with async_session() as db:
            # Find all pending bets
            stmt = select(Bet).where(Bet.status == "pending")
            result = await db.execute(stmt)
            pending_bets = result.scalars().all()

            if not pending_bets:
                return

            # Collect unique match IDs
            match_ids = list({b.match_id for b in pending_bets})

            # Fetch matches with scores
            match_stmt = select(Match).where(
                Match.id.in_(match_ids),
                Match.home_score.isnot(None),
                Match.away_score.isnot(None),
            )
            match_result = await db.execute(match_stmt)
            finished_matches = {m.id: m for m in match_result.scalars().all()}

            settled_count = 0
            for bet in pending_bets:
                match = finished_matches.get(bet.match_id)
                if not match:
                    continue

                hs, aws = match.home_score, match.away_score
                won = _determine_bet_result(bet, hs, aws)

                # Settle the bet
                session_stmt = select(BettingSession).where(BettingSession.id == bet.session_id)
                session = (await db.execute(session_stmt)).scalar_one_or_none()

                bet.status = "settled"
                bet.result = "won" if won else "lost"
                bet.settled_at = datetime.utcnow()

                if won:
                    payout = bet.stake * bet.odds
                    bet.profit = round(payout - bet.stake, 2)
                    if session:
                        session.bankroll += payout
                        session.wins += 1
                else:
                    bet.profit = -bet.stake
                    if session:
                        session.losses += 1

                if session:
                    session.total_profit = round(session.bankroll - session.start_bankroll, 2)

                settled_count += 1
                logger.info(
                    f"  Auto-settled bet#{bet.id}: {bet.bet_type}/{bet.selection} "
                    f"on match#{bet.match_id} ({hs}:{aws}) -> {'WON' if won else 'LOST'}"
                )

            if settled_count > 0:
                await db.commit()
                logger.info(f"✅ Auto-settled {settled_count} bets")
    except Exception as e:
        logger.error(f"❌ Auto-settle failed: {e}")


def _determine_bet_result(bet: Bet, home_score: int, away_score: int) -> bool:
    """Determine if a bet won based on bet type and match score"""
    sel = bet.selection

    if bet.bet_type == "1x2":
        if sel == "home":
            return home_score > away_score
        elif sel == "away":
            return away_score > home_score
        elif sel == "draw":
            return home_score == away_score
        return False

    elif bet.bet_type == "spread":
        # spread_line is from home team's perspective
        # e.g. spread_line = -0.5 means home gives 0.5
        # Actual result: home_score + spread_line vs away_score
        line = bet.spread_line or 0
        if sel == "home":
            return (home_score + line) > away_score
        else:  # away
            return (home_score + line) < away_score

    elif bet.bet_type == "over_under":
        total_goals = home_score + away_score
        line = bet.total_line or 2.5
        if sel == "over":
            return total_goals > line
        else:  # under
            return total_goals < line

    return False


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
    # News: run 30s after startup, then every interval
    scheduler.add_job(
        job_update_news, "interval",
        minutes=settings.news_update_interval,
        id="news_update",
        misfire_grace_time=300,
        next_run_time=now + timedelta(seconds=30),
    )
    # Football: delayed 3min after odds (avoid concurrent API calls)
    scheduler.add_job(
        job_update_football_job, "interval",
        minutes=settings.injury_update_interval,
        id="football_update",
        misfire_grace_time=300,
        next_run_time=now + timedelta(minutes=3),
    )

    # Auto-settle: check every 5 minutes, first run after 2 minutes
    scheduler.add_job(
        job_auto_settle_bets, "interval",
        minutes=5,
        id="auto_settle",
        misfire_grace_time=300,
        next_run_time=now + timedelta(minutes=2),
    )

    logger.info(
        f"📅 Scheduler started: odds every {settings.odds_update_interval}min, "
        f"news every {settings.news_update_interval}min, "
        f"football every {settings.injury_update_interval}min, "
        f"auto-settle every 5min"
    )


def stop_scheduler():
    """Stop all scheduled jobs"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("📅 Scheduler stopped")
