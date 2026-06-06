"""Betting models - simulated betting system"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from app.database import Base


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)  # browser session ID

    match_id = Column(Integer, nullable=False, index=True)
    match_label = Column(String(200))  # "ESP vs CPV" for display

    selection = Column(String(20), nullable=False)  # home, draw, away, over, under, btts_yes, btts_no
    selection_label = Column(String(100))            # "西班牙胜"

    # Bet type
    bet_type = Column(String(20), default="1x2")     # 1x2, spread, over_under, btts
    spread_line = Column(Float, nullable=True)       # e.g. -0.5, -1
    total_line = Column(Float, nullable=True)        # e.g. 1.5, 2.5

    bookmaker = Column(String(100))     # which bookmaker odds used
    odds = Column(Float, nullable=False)
    stake = Column(Float, nullable=False)

    potential_return = Column(Float)
    potential_profit = Column(Float)

    status = Column(String(20), default="pending")  # pending, won, lost, cancelled
    result = Column(String(20), nullable=True)       # actual result
    profit = Column(Float, default=0.0)

    placed_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class BettingSession(Base):
    """Track per-session bankroll"""
    __tablename__ = "betting_sessions"

    id = Column(String(100), primary_key=True)  # session_id
    bankroll = Column(Float, default=10000.0)
    start_bankroll = Column(Float, default=10000.0)
    total_bets = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
