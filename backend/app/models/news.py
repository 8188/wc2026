"""News & Injury models"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class TeamNews(Base):
    __tablename__ = "team_news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_code = Column(String(8), ForeignKey("teams.code"), nullable=False, index=True)
    headline = Column(String(500), nullable=False)
    source = Column(String(100))
    url = Column(String(500))
    published_at = Column(DateTime)

    # NLP sentiment
    sentiment = Column(String(20))      # positive, negative, neutral
    sentiment_score = Column(Float)     # -1.0 to 1.0
    impact_weight = Column(Float, default=0.5)  # how much this affects prediction

    # Classification
    category = Column(String(20), default="general")   # injury, transfer, form, tactical, general
    importance = Column(String(20), default="medium")  # high, medium, low

    fetched_at = Column(DateTime, default=datetime.utcnow)


class Injury(Base):
    __tablename__ = "injuries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_code = Column(String(8), ForeignKey("teams.code"), nullable=False, index=True)
    player_name = Column(String(200), nullable=False)
    position = Column(String(10))       # GK, CB, CM, LW, ST...
    status = Column(String(20))         # OUT, DOUBTFUL, RETURNING, READY
    reason = Column(Text)
    reported_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NewsImpact(Base):
    """Aggregated news impact score per match (computed by scheduler)"""
    __tablename__ = "news_impact"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    team_code = Column(String(8), ForeignKey("teams.code"), nullable=False)

    # Aggregated scores
    news_score = Column(Float, default=0.0)     # -5 to +5
    injury_score = Column(Float, default=0.0)   # -5 to +5
    form_score = Column(Float, default=0.0)     # -5 to +5 (recent 10 matches)
    total_impact = Column(Float, default=0.0)   # combined

    # Form string: WWDLWWDLWD
    recent_form = Column(String(20))

    computed_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="news_impact")
