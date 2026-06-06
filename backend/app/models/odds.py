"""Odds models - bookmaker odds storage"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)  # Bet365, Pinnacle...
    slug = Column(String(100), unique=True)                   # bet365, pinnacle...
    logo_url = Column(String(500))
    region = Column(String(20))  # eu, uk, us

    created_at = Column(DateTime, default=datetime.utcnow)


class MatchOdds(Base):
    __tablename__ = "match_odds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)

    # 1X2 (Match Result)
    home_odds = Column(Float)
    draw_odds = Column(Float)
    away_odds = Column(Float)

    # Over/Under 2.5
    over25_odds = Column(Float, nullable=True)
    under25_odds = Column(Float, nullable=True)

    # Both Teams To Score
    btts_yes_odds = Column(Float, nullable=True)
    btts_no_odds = Column(Float, nullable=True)

    # Spread / Handicap
    spread_home_odds = Column(Float, nullable=True)
    spread_line = Column(Float, nullable=True)    # e.g. -0.5, -1, +0.5
    spread_away_odds = Column(Float, nullable=True)

    # Totals (Over/Under) - multiple lines
    over15_odds = Column(Float, nullable=True)
    under15_odds = Column(Float, nullable=True)

    # Market implied expected goals (derived from odds)
    market_home_goals = Column(Float, nullable=True)
    market_away_goals = Column(Float, nullable=True)

    # Implied probabilities (after removing margin)
    home_prob = Column(Float)
    draw_prob = Column(Float)
    away_prob = Column(Float)
    margin = Column(Float)  # bookmaker margin %

    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    match = relationship("Match", back_populates="odds")
    bookmaker = relationship("Bookmaker")

    __table_args__ = (
        UniqueConstraint("match_id", "bookmaker_id", "fetched_at", name="uq_odds_snapshot"),
    )


class OddsHistory(Base):
    """Track odds movement over time for trend analysis"""
    __tablename__ = "odds_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    market = Column(String(20), nullable=False)  # h2h, totals, btts
    selection = Column(String(20), nullable=False)  # home, draw, away, over, under
    odds = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
