"""RSS News fetcher for team news and injury updates"""
import logging
from datetime import datetime
from typing import Optional
import feedparser
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.news import TeamNews
from app.models.match import Team

logger = logging.getLogger(__name__)
settings = get_settings()

# RSS feeds for football news (verified working as of June 2026)
RSS_FEEDS = {
    "espn": "https://www.espn.com/espn/rss/soccer/news",
    "bbc": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky": "https://www.skysports.com/rss/12065",
    "guardian": "https://www.theguardian.com/football/rss.xml",
    "googlenews": "https://news.google.com/rss/search?q=FIFA+World+Cup+2026&hl=en-US&gl=US&ceid=US:en",
}

# Browser-like User-Agent to avoid datacenter IP blocking
_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Team name mapping for news matching (all 48 WC2026 teams)
TEAM_KEYWORDS = {
    # Group A
    "MEX": ["Mexico", "El Tri", "Chicharito"],
    "RSA": ["South Africa", "Bafana Bafana"],
    "KOR": ["South Korea", "Korea", "Son Heung-min", "Heung-min"],
    "CZE": ["Czech Republic", "Czech"],
    # Group B
    "CAN": ["Canada", "CanMNT", "Alphonso Davies", "Davies"],
    "BIH": ["Bosnia", "Herzegovina", "Bosnia and Herzegovina"],
    "QAT": ["Qatar"],
    "SUI": ["Switzerland", "Swiss", "Xhaka"],
    # Group C
    "BRA": ["Brazil", "Selecao", "Vinicius", "Endrick"],
    "MAR": ["Morocco", "Atlas Lions", "Hakimi"],
    "HAI": ["Haiti"],
    "SCO": ["Scotland", "Tartan Army"],
    # Group D
    "USA": ["USMNT", "USA", "United States", "Pulisic", "McKennie"],
    "PAR": ["Paraguay"],
    "AUS": ["Australia", "Socceroos"],
    "TUR": ["Turkey", "Türkiye"],
    # Group E
    "GER": ["Germany", "Die Mannschaft", "Musiala", "Wirtz"],
    "CUW": ["Curacao", "Cura\u00e7ao"],
    "CIV": ["Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"],
    "ECU": ["Ecuador", "La Tri", "Caicedo"],
    # Group F
    "NED": ["Netherlands", "Oranje", "Van Dijk", "Gakpo"],
    "JPN": ["Japan", "Samurai Blue", "Kubo", "Mitoma"],
    "SWE": ["Sweden"],
    "TUN": ["Tunisia", "Eagles of Carthage"],
    # Group G
    "BEL": ["Belgium", "Red Devils", "De Bruyne", "Doku"],
    "EGY": ["Egypt", "Pharaohs", "Salah"],
    "IRN": ["Iran", "Team Melli", "Taremi"],
    "NZL": ["New Zealand", "All Whites"],
    # Group H
    "ESP": ["Spain", "La Roja", "Yamal", "Pedri", "Rodri"],
    "CPV": ["Cape Verde", "Blue Sharks"],
    "KSA": ["Saudi Arabia", "Green Falcons"],
    "URU": ["Uruguay", "La Celeste", "Valverde", "Nunez"],
    # Group I
    "FRA": ["France", "Les Bleus", "Mbappe", "Griezmann"],
    "SEN": ["Senegal", "Lions of Teranga", "Mane"],
    "IRQ": ["Iraq", "Lions of Mesopotamia"],
    "NOR": ["Norway", "Haaland", "Odegaard"],
    # Group J
    "ARG": ["Argentina", "Albiceleste", "Messi", "Scaloni"],
    "ALG": ["Algeria", "Desert Foxes"],
    "AUT": ["Austria"],
    "JOR": ["Jordan"],
    # Group K
    "POR": ["Portugal", "Ronaldo", "Bruno Fernandes", "Leao"],
    "COD": ["DR Congo", "Congo", "Leopards"],
    "UZB": ["Uzbekistan"],
    "COL": ["Colombia", "Los Cafeteros", "Diaz"],
    # Group L
    "ENG": ["England", "Three Lions", "Bellingham", "Kane", "Foden"],
    "CRO": ["Croatia", "Vatreni", "Modric", "Gvardiol"],
    "GHA": ["Ghana", "Black Stars"],
    "PAN": ["Panama"],
}


async def fetch_rss_news(db: AsyncSession):
    """Fetch news from RSS feeds and match to teams"""
    all_entries = []

    for feed_name, url in RSS_FEEDS.items():
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=_RSS_HEADERS)
                resp.raise_for_status()

            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:20]:
                all_entries.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published_parsed"),
                    "source": feed_name,
                })
        except Exception as e:
            logger.error(f"Failed to fetch {feed_name}: {e}")

    # Match entries to teams
    for entry in all_entries:
        text = (entry["title"] + " " + entry.get("summary", "")).lower()
        for team_code, keywords in TEAM_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                # Check for duplicate
                existing = await db.execute(
                    select(TeamNews).where(
                        TeamNews.team_code == team_code,
                        TeamNews.headline == entry["title"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                pub_date = None
                if entry.get("published"):
                    try:
                        from time import mktime
                        pub_date = datetime.fromtimestamp(mktime(entry["published"]))
                    except Exception:
                        pass

                news = TeamNews(
                    team_code=team_code,
                    headline=entry["title"],
                    source=entry["source"],
                    url=entry.get("link"),
                    published_at=pub_date or datetime.utcnow(),
                    sentiment="neutral",  # Will be updated by NLP
                    sentiment_score=0.0,
                    impact_weight=0.5,
                )
                db.add(news)

    await db.commit()
    logger.info(f"Fetched {len(all_entries)} RSS entries")


async def analyze_sentiment_batch(db: AsyncSession):
    """Use OpenAI to analyze sentiment of unprocessed news"""
    if not settings.openai_api_key or settings.openai_api_key.startswith("your_"):
        logger.info("OpenAI API key not configured, skipping sentiment analysis")
        return

    # Get news without sentiment analysis
    stmt = select(TeamNews).where(TeamNews.sentiment_score == 0.0).limit(20)
    result = await db.execute(stmt)
    unprocessed = result.scalars().all()

    if not unprocessed:
        return

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        headlines = [n.headline for n in unprocessed]
        prompt = (
            "Analyze the sentiment of these football news headlines. "
            "For each, respond with JSON: [{\"index\": 0, \"sentiment\": \"positive/negative/neutral\", \"score\": 0.0 to 1.0 or -1.0}]\n\n"
            + "\n".join(f"{i}. {h}" for i, h in enumerate(headlines))
        )

        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        import json
        data = json.loads(response.choices[0].message.content)
        results = data if isinstance(data, list) else data.get("results", [])

        for r in results:
            idx = r.get("index", -1)
            if 0 <= idx < len(unprocessed):
                unprocessed[idx].sentiment = r.get("sentiment", "neutral")
                unprocessed[idx].sentiment_score = r.get("score", 0.0)

        await db.commit()
        logger.info(f"Analyzed sentiment for {len(results)} headlines")

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
