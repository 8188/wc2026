"""Match routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.match import Team, Match

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/teams")
async def list_teams(db: AsyncSession = Depends(get_db)):
    """Get all teams"""
    stmt = select(Team).order_by(Team.fifa_rank.asc())
    result = await db.execute(stmt)
    teams = result.scalars().all()

    return {
        t.code: {
            "name": t.name,
            "nameEn": t.name_en,
            "flag": t.flag,
            "confederation": t.confederation,
            "fifaRank": t.fifa_rank,
            "strength": t.strength,
        }
        for t in teams
    }


@router.get("/")
async def list_matches(
    stage: Optional[str] = Query(None, description="Filter by stage: group, R32, R16, QF, SF, 3RD, FINAL"),
    group: Optional[str] = Query(None, description="Filter by group: A, B, C..."),
    db: AsyncSession = Depends(get_db),
):
    """Get all matches with optional filters"""
    stmt = select(Match).order_by(Match.match_date.asc())
    if stage:
        stmt = stmt.where(Match.stage == stage)
    if group:
        stmt = stmt.where(Match.group_name == group)

    result = await db.execute(stmt)
    matches = result.scalars().all()

    return [
        {
            "id": m.id,
            "stage": m.stage,
            "group": m.group_name,
            "round": m.round_num,
            "home": m.home_team_code,
            "away": m.away_team_code,
            "homeScore": m.home_score,
            "awayScore": m.away_score,
            "venue": m.venue,
            "city": m.city,
            "date": m.match_date.isoformat() if m.match_date else None,
            "status": m.status,
        }
        for m in matches
    ]


@router.get("/{match_id}")
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    """Get single match details"""
    stmt = select(Match).where(Match.id == match_id)
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    return {
        "id": match.id,
        "stage": match.stage,
        "group": match.group_name,
        "round": match.round_num,
        "home": match.home_team_code,
        "away": match.away_team_code,
        "homeScore": match.home_score,
        "awayScore": match.away_score,
        "venue": match.venue,
        "city": match.city,
        "date": match.match_date.isoformat() if match.match_date else None,
        "status": match.status,
    }
