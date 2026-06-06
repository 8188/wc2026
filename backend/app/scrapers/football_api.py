"""API-Football scraper - injuries, news, and match data from api-football.com"""
import logging
from datetime import datetime, timedelta
from typing import Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.news import TeamNews, Injury
from app.models.match import Match, Team

logger = logging.getLogger(__name__)
settings = get_settings()

# API-Football base URL (v3)
API_BASE = "https://v3.football.api-sports.io"
WC_SEASON = 2026
WC_LEAGUE_ID = 1  # FIFA World Cup

# Mapping: our team codes -> API-Football team IDs (common IDs)
TEAM_API_IDS: dict[str, int] = {
    "USA": 845, "MEX": 28, "CAN": 2743, "ESP": 541, "ARG": 34,
    "FRA": 549, "ENG": 528, "BRA": 544, "POR": 547, "NED": 546,
    "BEL": 542, "GER": 545, "CRO": 558, "MAR": 606, "COL": 565,
    "URU": 562, "SUI": 561, "JPN": 600, "SEN": 605, "IRN": 599,
    "KOR": 608, "ECU": 564, "AUT": 554, "SWE": 560, "AUS": 603,
    "NOR": 553, "TUR": 570, "PAN": 2731, "EGY": 595, "ALG": 593,
    "SCO": 563, "PAR": 573, "TUN": 597, "BIH": 566, "CZE": 555,
    "CIV": 592, "GHA": 598, "UZB": 2678, "QAT": 615, "KSA": 611,
    "RSA": 596, "JOR": 609, "CPV": 3578, "CUW": 2729, "HAI": 2751,
    "NZL": 614, "IRQ": 610, "COD": 594,
}


def _headers() -> dict:
    """Build API headers with key"""
    key = settings.football_api_key
    if not key:
        return {}
    return {"x-apisports-key": key}


async def fetch_fixtures(db: AsyncSession) -> list[dict]:
    """Fetch World Cup 2026 fixtures from API-Football"""
    if not settings.football_api_key:
        logger.warning("FOOTBALL_API_KEY not set, skipping fixtures fetch")
        return []

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{API_BASE}/fixtures",
            headers=_headers(),
            params={"season": WC_SEASON, "league": WC_LEAGUE_ID},
        )
        if resp.status_code != 200:
            logger.error(f"API-Football fixtures error: {resp.status_code}")
            return []
        data = resp.json()
        return data.get("response", [])


async def fetch_injuries(fixture_id: int) -> list[dict]:
    """Fetch injuries for a specific fixture"""
    if not settings.football_api_key:
        return []

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{API_BASE}/injuries",
            headers=_headers(),
            params={"fixture": fixture_id},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("response", [])


async def fetch_team_news(team_api_id: int) -> list[dict]:
    """Fetch news for a specific team"""
    if not settings.football_api_key:
        return []

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{API_BASE}/news",
            headers=_headers(),
            params={"team": team_api_id, "limit": 10},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("response", [])


def _classify_news(text: str) -> tuple[str, str]:
    """Classify news into category and importance"""
    text_lower = text.lower()
    if any(w in text_lower for w in ["injur", "hurt", "surgery", "sidelin", "out for"]):
        return "injury", "high"
    if any(w in text_lower for w in ["transfer", "sign", "move to", "deal"]):
        return "transfer", "medium"
    if any(w in text_lower for w in ["form", "streak", "win", "lose", "defeat"]):
        return "form", "medium"
    if any(w in text_lower for w in ["tactic", "formation", "lineup", "strateg"]):
        return "tactical", "low"
    return "general", "low"


async def job_update_football(db: AsyncSession):
    """Main job: fetch injuries and news from API-Football"""
    if not settings.football_api_key:
        logger.warning("FOOTBALL_API_KEY not set, skipping API-Football update")
        return

    logger.info("Fetching fixtures from API-Football (league=1, season=2026)...")

    # 1. Fetch fixtures to get fixture IDs
    fixtures = await fetch_fixtures(db)
    if not fixtures:
        logger.warning("No fixtures returned from API-Football (check API key quota)")
        return

    logger.info(f"Got {len(fixtures)} fixtures from API-Football")

    # Build fixture ID -> match code mapping
    team_names_to_codes = {}
    teams = (await db.execute(select(Team))).scalars().all()
    for t in teams:
        if t.name_en:
            team_names_to_codes[t.name_en.lower()] = t.code

    fixture_count = 0
    injury_count = 0

    # 2. Fetch injuries per fixture (limit to conserve free API quota: 100 req/day)
    api_calls = 1  # already used 1 for fixtures
    max_api_calls = 15  # conserve daily quota
    for fix in fixtures[:max_api_calls - 1]:
        fixture_id = fix.get("fixture", {}).get("id")
        home_team_name = fix.get("teams", {}).get("home", {}).get("name", "")
        away_team_name = fix.get("teams", {}).get("away", {}).get("name", "")

        if not fixture_id:
            continue

        injuries = await fetch_injuries(fixture_id)
        if not injuries:
            continue

        fixture_count += 1

        # Determine which team each injury belongs to
        for inj_data in injuries:
            player_info = inj_data.get("player", {})
            team_info = inj_data.get("team", {})
            player_name = player_info.get("name", "Unknown")
            team_name = team_info.get("name", "")
            position = player_info.get("position", "")

            # Find team code
            team_code = None
            for t_name, t_code in team_names_to_codes.items():
                if t_name in team_name.lower() or team_name.lower() in t_name:
                    team_code = t_code
                    break

            if not team_code:
                continue

            # Check for duplicate
            existing = await db.execute(
                select(Injury).where(
                    Injury.team_code == team_code,
                    Injury.player_name == player_name,
                )
            )
            if existing.scalar_one_or_none():
                continue

            reason_text = inj_data.get("reason", "")
            status = "DOUBTFUL"
            reason_lower = reason_text.lower() if reason_text else ""
            if any(w in reason_lower for w in ["out", "sidelined", "surgery"]):
                status = "OUT"
            elif any(w in reason_lower for w in ["returning", "recovery"]):
                status = "RETURNING"

            injury = Injury(
                team_code=team_code,
                player_name=player_name,
                position=_map_position(position),
                status=status,
                reason=reason_text,
                reported_at=datetime.utcnow(),
            )
            db.add(injury)
            injury_count += 1

    # 3. Fetch team news for top teams
    news_count = 0
    top_teams = ["ESP", "ARG", "FRA", "ENG", "BRA", "POR", "GER", "NED", "USA", "JPN"]
    for code in top_teams:
        api_id = TEAM_API_IDS.get(code)
        if not api_id:
            continue

        news_items = await fetch_team_news(api_id)
        for item in news_items[:5]:  # limit per team
            headline = item.get("headline", "")
            if not headline:
                continue

            # Dedup
            existing = await db.execute(
                select(TeamNews).where(
                    TeamNews.team_code == code,
                    TeamNews.headline == headline,
                )
            )
            if existing.scalar_one_or_none():
                continue

            category, importance = _classify_news(headline)
            pub_date = None
            if item.get("published"):
                try:
                    pub_date = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
                except Exception:
                    pass

            news = TeamNews(
                team_code=code,
                headline=headline,
                source="api-football",
                url=item.get("link", ""),
                published_at=pub_date or datetime.utcnow(),
                sentiment="neutral",
                sentiment_score=0.0,
                impact_weight=0.8 if importance == "high" else 0.5,
                category=category,
                importance=importance,
            )
            db.add(news)
            news_count += 1

    await db.commit()
    logger.info(
        f"API-Football update: {fixture_count} fixtures, "
        f"{injury_count} injuries, {news_count} news items"
    )


def _map_position(pos: str) -> str:
    """Map API-Football position to short code"""
    pos_map = {
        "Goalkeeper": "GK", "Defender": "CB", "Midfielder": "CM",
        "Attacker": "ST", "Forward": "ST",
    }
    return pos_map.get(pos, pos[:2].upper() if pos else "??")
