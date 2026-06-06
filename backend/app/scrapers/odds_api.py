"""Odds fetcher - The Odds API integration (v2: h2h + spreads + totals + btts)"""
import math
import logging
from datetime import datetime
from typing import Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.odds import MatchOdds, Bookmaker, OddsHistory
from app.models.match import Match

logger = logging.getLogger(__name__)
settings = get_settings()

# The Odds API - FIFA World Cup 2026
SPORT_KEY = "soccer_fifa_world_cup"
BASE_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"


async def fetch_odds_from_api() -> list[dict]:
    """Fetch raw odds from The Odds API (h2h + spreads + totals)"""
    if not settings.odds_api_key:
        logger.warning("ODDS_API_KEY not set, skipping odds fetch")
        return []

    logger.info(f"Fetching odds from The Odds API (sport={SPORT_KEY})...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(BASE_URL, params={
            "apiKey": settings.odds_api_key,
            "regions": "eu,uk,us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "decimal",
        })
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Odds API returned {len(data)} events")
        return data


def _derive_market_xg(over25: float | None, under25: float | None,
                       home_prob: float, away_prob: float) -> tuple[float, float]:
    """Derive market expected goals from over/under and 1X2 odds.

    Uses Newton's method on the Poisson CDF to invert over25 odds into total xG,
    then splits by home/away probability ratio.
    """
    total_xg = 2.5  # default fallback

    if over25 and under25 and over25 > 1 and under25 > 1:
        # Implied probabilities
        p_over = 1.0 / over25
        p_under = 1.0 / under25
        # Remove margin
        total_raw = p_over + p_under
        p_over_norm = p_over / total_raw
        p_under_norm = p_under / total_raw

        # Poisson P(goals <= 2) = sum_{k=0}^{2} e^{-lam} * lam^k / k!
        # Find lambda where P(goals <= 2) = p_under_norm
        # Use simple binary search
        lo, hi = 0.5, 5.0
        for _ in range(30):
            mid = (lo + hi) / 2
            p_under_mid = math.exp(-mid) * (1 + mid + mid * mid / 2)
            if p_under_mid > p_under_norm:
                lo = mid
            else:
                hi = mid
        total_xg = (lo + hi) / 2

    # Split total xG by home/away probability
    if home_prob + away_prob > 0:
        home_ratio = home_prob / (home_prob + away_prob)
    else:
        home_ratio = 0.5

    home_xg = total_xg * home_ratio * 1.08  # slight home advantage
    away_xg = total_xg * (1 - home_ratio) * 0.92
    return round(home_xg, 2), round(away_xg, 2)


async def store_odds(db: AsyncSession, events: list[dict]):
    """Parse and store odds into database (h2h + spreads + totals + btts)"""
    stored = 0
    unmatched = 0
    for event in events:
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")

        match = await _find_match_by_teams(db, home_team, away_team)
        if not match:
            unmatched += 1
            logger.debug(f"No match found for '{home_team}' vs '{away_team}'")
            continue

        for bookmaker_data in event.get("bookmakers", []):
            bk_name = bookmaker_data["title"]
            bk_slug = bookmaker_data.get("key", bk_name.lower().replace(" ", ""))

            bk = await _get_or_create_bookmaker(db, bk_name, bk_slug)

            # Initialize all odds
            home_odds = draw_odds = away_odds = None
            over25 = under25 = over15 = under15 = None
            btts_yes = btts_no = None
            spread_home = spread_line = spread_away = None

            for market in bookmaker_data.get("markets", []):
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}

                if market["key"] == "h2h":
                    home_odds = outcomes.get(home_team)
                    away_odds = outcomes.get(away_team)
                    draw_odds = outcomes.get("Draw")

                elif market["key"] == "spreads":
                    # Find the -1 or -0.5 spread line (most common for football)
                    for o in market.get("outcomes", []):
                        point = o.get("point", 0)
                        if o["name"] == home_team:
                            # Home team handicap (negative = giving goals)
                            if point in (-1, -0.5, -0.75, -1.5, 0.5):
                                spread_home = o["price"]
                                spread_line = point
                        elif o["name"] == away_team:
                            if spread_home and spread_line is not None:
                                # Away side is the opposite line
                                if abs(o.get("point", 0) + spread_line) < 0.01:
                                    spread_away = o["price"]
                    # If we found home side but not away, try again
                    if spread_home and not spread_away:
                        for o in market.get("outcomes", []):
                            if o["name"] == away_team and o.get("point") == -spread_line:
                                spread_away = o["price"]

                elif market["key"] == "totals":
                    for o in market.get("outcomes", []):
                        pt = o.get("point")
                        if pt == 2.5:
                            if o["name"] == "Over":
                                over25 = o["price"]
                            elif o["name"] == "Under":
                                under25 = o["price"]
                        elif pt == 1.5:
                            if o["name"] == "Over":
                                over15 = o["price"]
                            elif o["name"] == "Under":
                                under15 = o["price"]

                elif market["key"] == "btts":
                    for o in market.get("outcomes", []):
                        if o["name"] == "Yes":
                            btts_yes = o["price"]
                        elif o["name"] == "No":
                            btts_no = o["price"]

            if not all([home_odds, draw_odds, away_odds]):
                continue

            # De-margin 1X2 probabilities
            margin = (1 / home_odds + 1 / draw_odds + 1 / away_odds) - 1
            raw_probs = [1 / home_odds, 1 / draw_odds, 1 / away_odds]
            total_raw = sum(raw_probs)
            hp = raw_probs[0] / total_raw
            dp = raw_probs[1] / total_raw
            ap = raw_probs[2] / total_raw

            # Derive market expected goals
            market_hg, market_ag = _derive_market_xg(over25, under25, hp, ap)

            odds_record = MatchOdds(
                match_id=match.id,
                bookmaker_id=bk.id,
                home_odds=home_odds,
                draw_odds=draw_odds,
                away_odds=away_odds,
                over25_odds=over25,
                under25_odds=under25,
                over15_odds=over15,
                under15_odds=under15,
                btts_yes_odds=btts_yes,
                btts_no_odds=btts_no,
                spread_home_odds=spread_home,
                spread_line=spread_line,
                spread_away_odds=spread_away,
                market_home_goals=market_hg,
                market_away_goals=market_ag,
                home_prob=round(hp, 4),
                draw_prob=round(dp, 4),
                away_prob=round(ap, 4),
                margin=round(margin, 4),
                fetched_at=datetime.utcnow(),
            )
            db.add(odds_record)

            # Store in history for trend charts
            for sel, odds_val in [("home", home_odds), ("draw", draw_odds), ("away", away_odds)]:
                db.add(OddsHistory(
                    match_id=match.id, bookmaker_id=bk.id,
                    market="h2h", selection=sel, odds=odds_val,
                ))
            if over25:
                db.add(OddsHistory(
                    match_id=match.id, bookmaker_id=bk.id,
                    market="totals", selection="over25", odds=over25,
                ))
            if under25:
                db.add(OddsHistory(
                    match_id=match.id, bookmaker_id=bk.id,
                    market="totals", selection="under25", odds=under25,
                ))
            if btts_yes:
                db.add(OddsHistory(
                    match_id=match.id, bookmaker_id=bk.id,
                    market="btts", selection="yes", odds=btts_yes,
                ))
            stored += 1

    await db.commit()
    logger.info(f"Stored odds: {stored} bookmaker-match entries from {len(events)} events ({unmatched} unmatched)")


# Name aliases: API name -> our DB name_en
_NAME_ALIASES = {
    "Bosnia & Herzegovina": "Bosnia Herzegovina",
    "Bosnia and Herzegovina": "Bosnia Herzegovina",
    "Cura\u00e7ao": "Curacao",
    "Curacao": "Curacao",
    "Czech Rep.": "Czech Republic",
    "DR Congo": "DR Congo",
    "Dem. Rep. Congo": "DR Congo",
    "Ivory Coast": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "South Korea": "South Korea",
    "Korea Republic": "South Korea",
    "Saudi Arabia": "Saudi Arabia",
    "South Africa": "South Africa",
    "New Zealand": "New Zealand",
    "Cape Verde": "Cape Verde",
    "United States": "United States",
    "USA": "United States",
    "US": "United States",
}


def _normalize_team_name(name: str) -> str:
    """Normalize team name from API to match our DB"""
    return _NAME_ALIASES.get(name, name)


async def _find_match_by_teams(db: AsyncSession, home_name: str, away_name: str) -> Optional[Match]:
    """Find match by team English names (checks both home/away orderings)"""
    from app.models.match import Team
    home_name = _normalize_team_name(home_name)
    away_name = _normalize_team_name(away_name)
    home_team = (await db.execute(
        select(Team).where(Team.name_en.ilike(f"%{home_name}%"))
    )).scalar_one_or_none()
    away_team = (await db.execute(
        select(Team).where(Team.name_en.ilike(f"%{away_name}%"))
    )).scalar_one_or_none()

    if not home_team or not away_team:
        return None

    # Try exact home/away order
    result = await db.execute(select(Match).where(
        Match.home_team_code == home_team.code,
        Match.away_team_code == away_team.code,
    ))
    match = result.scalar_one_or_none()
    if match:
        return match

    # Try reversed order (API may swap home/away for group stage fixtures)
    result = await db.execute(select(Match).where(
        Match.home_team_code == away_team.code,
        Match.away_team_code == home_team.code,
    ))
    return result.scalar_one_or_none()


async def _get_or_create_bookmaker(db: AsyncSession, name: str, slug: str) -> Bookmaker:
    # Try by name first (same bookmaker may have regional slug variants)
    stmt = select(Bookmaker).where(Bookmaker.name == name)
    bk = (await db.execute(stmt)).scalar_one_or_none()
    if not bk:
        # Also try by slug
        stmt2 = select(Bookmaker).where(Bookmaker.slug == slug)
        bk = (await db.execute(stmt2)).scalar_one_or_none()
    if not bk:
        bk = Bookmaker(name=name, slug=slug)
        db.add(bk)
        await db.flush()
    return bk
