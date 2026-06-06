"""Match & Team models"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class MatchStage(str, enum.Enum):
    GROUP = "group"
    R32 = "R32"
    R16 = "R16"
    QF = "QF"
    SF = "SF"
    THIRD = "3RD"
    FINAL = "FINAL"


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(8), unique=True, nullable=False, index=True)  # FIFA code: USA, ARG...
    name = Column(String(100), nullable=False)        # 中文名
    name_en = Column(String(100))                      # English name
    flag = Column(String(10))                          # emoji flag
    confederation = Column(String(20))                 # UEFA, CONMEBOL...
    fifa_rank = Column(Integer)
    strength = Column(Float, default=50.0)             # 0-100 rating

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(50), unique=True)      # API external ID
    stage = Column(String(10), nullable=False, default="group")
    group_name = Column(String(5))                     # A, B, C... (null for knockout)
    round_num = Column(Integer)                        # 1, 2, 3 for group stage

    home_team_code = Column(String(8), ForeignKey("teams.code"), nullable=True)
    away_team_code = Column(String(8), ForeignKey("teams.code"), nullable=True)

    home_score = Column(Integer, nullable=True)        # null = not played yet
    away_score = Column(Integer, nullable=True)

    venue = Column(String(200))
    city = Column(String(100))
    match_date = Column(DateTime)
    status = Column(String(20), default="scheduled")

    # Relations
    home_team = relationship("Team", foreign_keys=[home_team_code])
    away_team = relationship("Team", foreign_keys=[away_team_code])
    odds = relationship("MatchOdds", back_populates="match", cascade="all, delete-orphan")
    news_impact = relationship("NewsImpact", back_populates="match", cascade="all, delete-orphan")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
