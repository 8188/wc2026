"""Predictions routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.match import Match, Team
from app.models.odds import MatchOdds, Bookmaker
from app.models.news import NewsImpact
from app.services.predictor import PredictionEngine

router = APIRouter(prefix="/predictions", tags=["predictions"])
engine = PredictionEngine()


@router.get("/")
async def list_predictions(db: AsyncSession = Depends(get_db)):
    """Get predictions for all matches with defined teams"""
    # Load all matches with teams
    stmt = (
        select(Match)
        .where(Match.home_team_code.isnot(None))
        .where(Match.away_team_code.isnot(None))
        .order_by(Match.match_date.asc())
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()

    # Batch load all teams
    team_codes = set()
    for m in matches:
        if m.home_team_code:
            team_codes.add(m.home_team_code)
        if m.away_team_code:
            team_codes.add(m.away_team_code)
    teams_stmt = select(Team).where(Team.code.in_(team_codes))
    teams_result = await db.execute(teams_stmt)
    teams_map = {t.code: t for t in teams_result.scalars().all()}

    # Batch load all bookmaker odds
    if matches:
        match_ids = [m.id for m in matches]
        odds_stmt = (
            select(MatchOdds, Bookmaker)
            .join(Bookmaker, MatchOdds.bookmaker_id == Bookmaker.id)
            .where(MatchOdds.match_id.in_(match_ids))
        )
        odds_result = await db.execute(odds_stmt)
        odds_map: dict[int, dict] = {}
        for odds, bk in odds_result.all():
            odds_map.setdefault(odds.match_id, {})[bk.slug] = {
                "name": bk.name,
                "outcome": {"home": odds.home_odds, "draw": odds.draw_odds, "away": odds.away_odds},
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
            }

        # Batch load news impact
        impact_stmt = select(NewsImpact).where(NewsImpact.match_id.in_(match_ids))
        impact_result = await db.execute(impact_stmt)
        impact_map: dict[int, dict] = {}
        impact_form_map: dict[int, dict] = {}
        for imp in impact_result.scalars().all():
            impact_map.setdefault(imp.match_id, {})[imp.team_code] = {
                "score": imp.total_impact,
                "news": [],
            }
            impact_form_map.setdefault(imp.match_id, {})[imp.team_code] = imp.recent_form or ""
    else:
        odds_map = {}
        impact_map = {}
        impact_form_map = {}

    predictions = []
    for match in matches:
        home = teams_map.get(match.home_team_code)
        away = teams_map.get(match.away_team_code)
        if not home or not away:
            continue

        bookmaker_odds = odds_map.get(match.id, {})
        news_impact = impact_map.get(match.id, {})
        form_data = impact_form_map.get(match.id, {})

        pred = engine.predict_match(match, home, away, bookmaker_odds, news_impact, form_data)
        if pred:
            predictions.append(pred.to_dict())

    return predictions


@router.get("/{match_id}")
async def get_prediction(match_id: int, db: AsyncSession = Depends(get_db)):
    """Get prediction for a specific match"""
    stmt = select(Match).where(Match.id == match_id)
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if not match.home_team_code or not match.away_team_code:
        raise HTTPException(status_code=400, detail="Teams not yet determined")

    home = (await db.execute(select(Team).where(Team.code == match.home_team_code))).scalar_one_or_none()
    away = (await db.execute(select(Team).where(Team.code == match.away_team_code))).scalar_one_or_none()

    pred = engine.predict_match(match, home, away)
    if not pred:
        raise HTTPException(status_code=500, detail="Prediction failed")

    # Also fetch odds for this match to include in response
    odds_stmt = (
        select(MatchOdds, Bookmaker)
        .join(Bookmaker, MatchOdds.bookmaker_id == Bookmaker.id)
        .where(MatchOdds.match_id == match_id)
    )
    odds_result = await db.execute(odds_stmt)
    bookmaker_odds = {}
    for odds, bk in odds_result.all():
        bookmaker_odds[bk.slug] = {
            "name": bk.name,
            "outcome": {"home": odds.home_odds, "draw": odds.draw_odds, "away": odds.away_odds},
            "over25": odds.over25_odds,
            "under25": odds.under25_odds,
            "bttsYes": odds.btts_yes_odds,
            "bttsNo": odds.btts_no_odds,
            "spread": {
                "home": odds.spread_home_odds,
                "line": odds.spread_line,
                "away": odds.spread_away_odds,
            } if odds.spread_line is not None else None,
        }

    # Re-predict with odds if available
    if bookmaker_odds:
        pred = engine.predict_match(match, home, away, bookmaker_odds)

    return pred.to_dict()
