"""News & injury routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import Optional
from app.database import get_db
from app.models.news import TeamNews, Injury, NewsImpact
from app.models.match import Match

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/impact/{match_id}")
async def get_match_news_impact(match_id: int, db: AsyncSession = Depends(get_db)):
    """Get aggregated news impact for both teams in a match"""
    stmt = select(NewsImpact).where(NewsImpact.match_id == match_id)
    result = await db.execute(stmt)
    impacts = result.scalars().all()

    return {
        "matchId": match_id,
        "impacts": [
            {
                "teamCode": i.team_code,
                "newsScore": i.news_score,
                "injuryScore": i.injury_score,
                "formScore": i.form_score,
                "totalImpact": i.total_impact,
                "recentForm": i.recent_form,
                "computedAt": i.computed_at.isoformat() if i.computed_at else None,
            }
            for i in impacts
        ],
    }


@router.get("/{team_code}")
async def get_team_news(
    team_code: str,
    days: int = Query(30, description="Look back days"),
    db: AsyncSession = Depends(get_db),
):
    """Get news and injuries for a team"""
    since = datetime.utcnow() - timedelta(days=days)

    # News
    news_stmt = (
        select(TeamNews)
        .where(TeamNews.team_code == team_code)
        .where(TeamNews.fetched_at >= since)
        .order_by(TeamNews.published_at.desc())
    )
    news_result = await db.execute(news_stmt)
    news = news_result.scalars().all()

    # Injuries
    inj_stmt = (
        select(Injury)
        .where(Injury.team_code == team_code)
        .where(Injury.status.in_(["OUT", "DOUBTFUL", "RETURNING"]))
        .order_by(Injury.reported_at.desc())
    )
    inj_result = await db.execute(inj_stmt)
    injuries = inj_result.scalars().all()

    # Compute sentiment score
    total_score = sum((n.sentiment_score or 0) * (n.impact_weight or 0.5) for n in news)
    # Injury penalty
    for inj in injuries:
        if inj.status == "OUT":
            total_score -= 1.5
        elif inj.status == "DOUBTFUL":
            total_score -= 0.8
        elif inj.status == "RETURNING":
            total_score -= 0.3

    return {
        "teamCode": team_code,
        "score": round(total_score, 2),
        "news": [
            {
                "headline": n.headline,
                "source": n.source,
                "url": n.url or "#",
                "date": n.published_at.strftime("%Y-%m-%d") if n.published_at else None,
                "sentiment": n.sentiment,
                "sentimentScore": n.sentiment_score,
                "category": n.category or "general",
                "importance": n.importance or "medium",
            }
            for n in news
        ],
        "injuries": [
            {
                "player": i.player_name,
                "position": i.position,
                "status": i.status,
                "reason": i.reason,
            }
            for i in injuries
        ],
    }
