"""Odds routes - real-time odds from multiple bookmakers"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional
from app.database import get_db
from app.models.odds import MatchOdds, Bookmaker, OddsHistory

router = APIRouter(prefix="/odds", tags=["odds"])


def _odds_to_dict(odds: MatchOdds, bookmaker: Bookmaker) -> dict:
    """Convert MatchOdds + Bookmaker to dict"""
    return {
        "name": bookmaker.name,
        "slug": bookmaker.slug,
        "outcome": {
            "home": odds.home_odds,
            "draw": odds.draw_odds,
            "away": odds.away_odds,
        },
        "over25": odds.over25_odds,
        "under25": odds.under25_odds,
        "over15": odds.over15_odds,
        "under15": odds.under15_odds,
        "bttsYes": odds.btts_yes_odds,
        "bttsNo": odds.btts_no_odds,
        "spread": {
            "home": odds.spread_home_odds,
            "line": odds.spread_line,
            "away": odds.spread_away_odds,
        } if odds.spread_line is not None else None,
        "marketHomeGoals": odds.market_home_goals,
        "marketAwayGoals": odds.market_away_goals,
        "margin": odds.margin,
        "fetchedAt": odds.fetched_at.isoformat() if odds.fetched_at else None,
    }


@router.get("/{match_id}")
async def get_match_odds(match_id: int, db: AsyncSession = Depends(get_db)):
    """Get latest odds for a match from all bookmakers"""
    # Get the latest odds per bookmaker
    subq = (
        select(
            MatchOdds.bookmaker_id,
            func.max(MatchOdds.fetched_at).label("max_fetched"),
        )
        .where(MatchOdds.match_id == match_id)
        .group_by(MatchOdds.bookmaker_id)
        .subquery()
    )

    stmt = (
        select(MatchOdds, Bookmaker)
        .join(subq, (MatchOdds.bookmaker_id == subq.c.bookmaker_id) & (MatchOdds.fetched_at == subq.c.max_fetched))
        .join(Bookmaker, MatchOdds.bookmaker_id == Bookmaker.id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return {"matchId": match_id, "bookmakerOdds": {}}

    bookmakers = {}
    for odds, bookmaker in rows:
        bookmakers[bookmaker.slug] = _odds_to_dict(odds, bookmaker)

    return {"matchId": match_id, "bookmakerOdds": bookmakers}


@router.get("/{match_id}/comparison")
async def get_odds_comparison(match_id: int, db: AsyncSession = Depends(get_db)):
    """Multi-bookmaker comparison table with all markets"""
    subq = (
        select(
            MatchOdds.bookmaker_id,
            func.max(MatchOdds.fetched_at).label("max_fetched"),
        )
        .where(MatchOdds.match_id == match_id)
        .group_by(MatchOdds.bookmaker_id)
        .subquery()
    )

    stmt = (
        select(MatchOdds, Bookmaker)
        .join(subq, (MatchOdds.bookmaker_id == subq.c.bookmaker_id) & (MatchOdds.fetched_at == subq.c.max_fetched))
        .join(Bookmaker, MatchOdds.bookmaker_id == Bookmaker.id)
        .order_by(MatchOdds.margin.asc())  # best odds first (lowest margin)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return {"matchId": match_id, "bookmakers": [], "bestOdds": {}}

    bookmakers_list = []
    best = {"home": None, "draw": None, "away": None, "over25": None, "under25": None, "bttsYes": None}

    for odds, bk in rows:
        entry = _odds_to_dict(odds, bk)
        bookmakers_list.append(entry)

        # Track best odds per market
        for key in ["home", "draw", "away"]:
            val = entry["outcome"].get(key)
            if val and (best[key] is None or val > best[key]["odds"]):
                best[key] = {"odds": val, "bookie": bk.name}
        for key, attr in [("over25", "over25"), ("under25", "under25"), ("bttsYes", "bttsYes")]:
            val = entry.get(attr)
            if val and (best[key] is None or val > best[key]["odds"]):
                best[key] = {"odds": val, "bookie": bk.name}

    return {
        "matchId": match_id,
        "bookmakers": bookmakers_list,
        "bestOdds": best,
        "lastUpdated": rows[0][0].fetched_at.isoformat() if rows else None,
    }


@router.get("/history/{match_id}")
async def get_odds_history(
    match_id: int,
    market: str = Query("h2h", description="Market: h2h, totals, btts"),
    days: int = Query(7, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
):
    """Get odds movement history for trend charts"""
    since = datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(OddsHistory, Bookmaker)
        .join(Bookmaker, OddsHistory.bookmaker_id == Bookmaker.id)
        .where(OddsHistory.match_id == match_id)
        .where(OddsHistory.market == market)
        .where(OddsHistory.recorded_at >= since)
        .order_by(OddsHistory.recorded_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "bookmaker": bk.slug,
            "bookmakerName": bk.name,
            "selection": h.selection,
            "odds": h.odds,
            "recordedAt": h.recorded_at.isoformat(),
        }
        for h, bk in rows
    ]
