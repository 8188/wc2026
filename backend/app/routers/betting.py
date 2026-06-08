"""Betting routes - simulated betting system"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.bet import Bet, BettingSession
from app.models.match import Match, Team

router = APIRouter(prefix="/bet", tags=["betting"])


class PlaceBetRequest(BaseModel):
    session_id: str
    match_id: int
    match_label: str = ""
    selection: str  # home, draw, away, over, under, btts_yes, btts_no
    selection_label: str = ""
    bookmaker: str = ""
    odds: float
    stake: float
    # Multi-market fields
    bet_type: str = "1x2"  # 1x2, spread, over_under, btts
    spread_line: Optional[float] = None
    total_line: Optional[float] = None


class SettleBetRequest(BaseModel):
    bet_id: int
    result: str  # won, lost


class CancelBetRequest(BaseModel):
    bet_id: int


@router.post("")
async def place_bet(req: PlaceBetRequest, db: AsyncSession = Depends(get_db)):
    """Place a simulated bet"""
    # Get or create session
    session_stmt = select(BettingSession).where(BettingSession.id == req.session_id)
    session = (await db.execute(session_stmt)).scalar_one_or_none()

    if not session:
        session = BettingSession(id=req.session_id, bankroll=10000, start_bankroll=10000)
        db.add(session)
        await db.flush()

    if req.stake > session.bankroll:
        raise HTTPException(status_code=400, detail=f"余额不足 (当前: {session.bankroll:.2f})")
    if req.stake < 10:
        raise HTTPException(status_code=400, detail="最小投注 10 元")

    # Auto-fill match_label and selection_label if empty
    if not req.match_label or not req.selection_label:
        match_stmt = (
            select(Match)
            .where(Match.id == req.match_id)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
        )
        match = (await db.execute(match_stmt)).scalar_one_or_none()
        if match:
            home_name = match.home_team.name if match.home_team else (match.home_team_code or "TBD")
            away_name = match.away_team.name if match.away_team else (match.away_team_code or "TBD")
            if not req.match_label:
                req.match_label = f"{home_name} vs {away_name}"
            if not req.selection_label:
                label_map = {
                    "home": f"{home_name}胜", "away": f"{away_name}胜", "draw": "平局",
                    "over": "大球", "under": "小球", "btts_yes": "双方进球", "btts_no": "双方不进球",
                }
                label = label_map.get(req.selection, req.selection)
                if req.bet_type == "over_under" and req.total_line:
                    label = f"{'大' if req.selection == 'over' else '小'}{req.total_line}球"
                elif req.bet_type == "spread" and req.spread_line is not None:
                    side = home_name if req.selection == "home" else away_name
                    sign = "+" if req.spread_line > 0 else ""
                    label = f"{side} {sign}{req.spread_line}"
                req.selection_label = label

    potential_return = round(req.stake * req.odds, 2)
    potential_profit = round(potential_return - req.stake, 2)

    bet = Bet(
        session_id=req.session_id,
        match_id=req.match_id,
        match_label=req.match_label,
        selection=req.selection,
        selection_label=req.selection_label,
        bet_type=req.bet_type,
        spread_line=req.spread_line,
        total_line=req.total_line,
        bookmaker=req.bookmaker,
        odds=req.odds,
        stake=req.stake,
        potential_return=potential_return,
        potential_profit=potential_profit,
        status="pending",
    )
    session.bankroll -= req.stake
    session.total_bets += 1

    db.add(bet)
    await db.commit()
    await db.refresh(bet)

    return {
        "id": bet.id,
        "matchId": bet.match_id,
        "matchLabel": bet.match_label,
        "selection": bet.selection,
        "selectionLabel": bet.selection_label,
        "betType": bet.bet_type,
        "spreadLine": bet.spread_line,
        "totalLine": bet.total_line,
        "odds": bet.odds,
        "stake": bet.stake,
        "potentialReturn": bet.potential_return,
        "potentialProfit": bet.potential_profit,
        "status": bet.status,
        "placedAt": bet.placed_at.isoformat(),
        "bankroll": session.bankroll,
    }


@router.post("/{bet_id}/settle")
async def settle_bet(bet_id: int, req: SettleBetRequest, db: AsyncSession = Depends(get_db)):
    """Settle a bet (won or lost)"""
    stmt = select(Bet).where(Bet.id == bet_id)
    bet = (await db.execute(stmt)).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status != "pending":
        raise HTTPException(status_code=400, detail="Bet already settled")

    session_stmt = select(BettingSession).where(BettingSession.id == bet.session_id)
    session = (await db.execute(session_stmt)).scalar_one_or_none()

    bet.status = "settled"
    bet.result = req.result
    bet.settled_at = datetime.utcnow()

    if req.result == "won":
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

    await db.commit()
    await db.refresh(bet)

    return {
        "id": bet.id,
        "result": req.result,
        "profit": bet.profit,
        "bankroll": session.bankroll if session else 0,
        "settledAt": bet.settled_at.isoformat(),
    }


@router.post("/{bet_id}/cancel")
async def cancel_bet(bet_id: int, req: CancelBetRequest, db: AsyncSession = Depends(get_db)):
    """Cancel a pending bet and refund stake"""
    stmt = select(Bet).where(Bet.id == bet_id)
    bet = (await db.execute(stmt)).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status != "pending":
        raise HTTPException(status_code=400, detail="Bet already settled or cancelled")

    session_stmt = select(BettingSession).where(BettingSession.id == bet.session_id)
    session = (await db.execute(session_stmt)).scalar_one_or_none()

    bet.status = "cancelled"
    bet.settled_at = datetime.utcnow()

    # Refund stake
    if session:
        session.bankroll += bet.stake

    await db.commit()
    await db.refresh(bet)

    return {
        "id": bet.id,
        "status": "cancelled",
        "bankroll": session.bankroll if session else 0,
    }


@router.get("/pending")
async def get_pending_bets(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get pending bets for a session"""
    stmt = select(Bet).where(Bet.session_id == session_id, Bet.status == "pending").order_by(Bet.placed_at.desc())
    result = await db.execute(stmt)
    bets = result.scalars().all()

    return [
        {
            "id": b.id,
            "matchId": b.match_id,
            "matchLabel": b.match_label,
            "selection": b.selection,
            "selectionLabel": b.selection_label,
            "odds": b.odds,
            "stake": b.stake,
            "potentialReturn": b.potential_return,
            "betType": b.bet_type,
            "spreadLine": b.spread_line,
            "totalLine": b.total_line,
            "placedAt": b.placed_at.isoformat(),
        }
        for b in bets
    ]


@router.get("/history")
async def get_bet_history(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get settled bet history"""
    stmt = (
        select(Bet)
        .where(Bet.session_id == session_id, Bet.status.in_(["settled", "cancelled"]))
        .order_by(Bet.settled_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    bets = result.scalars().all()

    return [
        {
            "id": b.id,
            "matchLabel": b.match_label,
            "selectionLabel": b.selection_label,
            "odds": b.odds,
            "stake": b.stake,
            "result": b.result if b.status == "settled" else "cancelled",
            "profit": b.profit,
            "betType": b.bet_type,
            "settledAt": b.settled_at.isoformat() if b.settled_at else None,
        }
        for b in bets
    ]


@router.get("/stats")
async def get_betting_stats(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get betting statistics for a session"""
    stmt = select(BettingSession).where(BettingSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()

    if not session:
        return {
            "bankroll": 10000,
            "startBankroll": 10000,
            "totalBets": 0,
            "wins": 0,
            "losses": 0,
            "winRate": 0,
            "roi": 0,
            "totalProfit": 0,
            "profitPercent": 0,
            "pending": 0,
        }

    pending_stmt = select(func.count()).select_from(Bet).where(Bet.session_id == session_id, Bet.status == "pending")
    pending = (await db.execute(pending_stmt)).scalar()

    total = session.wins + session.losses
    win_rate = round(session.wins / total * 100, 1) if total > 0 else 0
    roi = round(session.total_profit / session.start_bankroll * 100, 1) if session.start_bankroll > 0 else 0

    return {
        "bankroll": round(session.bankroll, 2),
        "startBankroll": session.start_bankroll,
        "totalBets": total,
        "wins": session.wins,
        "losses": session.losses,
        "winRate": win_rate,
        "roi": roi,
        "totalProfit": round(session.total_profit, 2),
        "profitPercent": round(session.total_profit / session.start_bankroll * 100, 2),
        "pending": pending,
    }


@router.post("/reset")
async def reset_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Reset a betting session"""
    stmt = select(BettingSession).where(BettingSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session:
        session.bankroll = 10000
        session.start_bankroll = 10000
        session.total_bets = 0
        session.wins = 0
        session.losses = 0
        session.total_profit = 0
        await db.commit()

    return {"ok": True, "bankroll": 10000}
