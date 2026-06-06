"""Prediction Engine v2 - Multi-factor model with market fusion and Poisson score matrix"""
import math
from dataclasses import dataclass, field
from typing import Optional
from app.models.match import Team, Match


@dataclass
class FairOdds:
    home: float
    draw: float
    away: float


@dataclass
class ValueBet:
    type: str           # home, draw, away, over, under, btts_yes, btts_no
    bookie: str
    market_odds: float
    our_odds: float
    value: float        # (market - fair) / fair
    market: str = "1x2" # 1x2, totals, btts, spread


@dataclass
class ScorePred:
    """A predicted scoreline with probability"""
    score: str          # "2-1"
    home: int
    away: int
    probability: float  # 0.0 - 1.0


@dataclass
class Prediction:
    match_id: int
    match_label: str
    home_name: str
    away_name: str
    stage: str
    date: Optional[str]
    venue: Optional[str]

    # Probabilities
    home_prob: float
    draw_prob: float
    away_prob: float

    # Score prediction
    predicted_score: str
    confidence: str      # high, medium, low

    # Fair odds
    fair_odds: FairOdds

    # Bookmaker odds
    bookmaker_odds: dict = field(default_factory=dict)

    # Value bets
    value_bets: list = field(default_factory=list)

    # Recommendation
    recommendation: dict = field(default_factory=dict)

    # Factors breakdown
    factors: dict = field(default_factory=dict)

    # News & form
    news: dict = field(default_factory=dict)
    form: dict = field(default_factory=dict)
    model_factors: dict = field(default_factory=dict)

    # Market fusion
    top_scores: list = field(default_factory=list)  # List of ScorePred dicts
    market_expected_goals: dict = field(default_factory=dict)  # {home: x, away: y, total: z}
    handicap_rec: dict = field(default_factory=dict)  # recommended handicap line

    def to_dict(self) -> dict:
        return {
            "matchId": self.match_id,
            "match": self.match_label,
            "homeName": self.home_name,
            "awayName": self.away_name,
            "stage": self.stage,
            "date": self.date,
            "venue": self.venue,
            "prediction": {
                "home": round(self.home_prob, 3),
                "draw": round(self.draw_prob, 3),
                "away": round(self.away_prob, 3),
            },
            "predictedScore": self.predicted_score,
            "confidence": self.confidence,
            "fairOdds": {
                "home": self.fair_odds.home,
                "draw": self.fair_odds.draw,
                "away": self.fair_odds.away,
            },
            "bookmakerOdds": self.bookmaker_odds,
            "valueBets": [
                {
                    "type": v.type, "bookie": v.bookie,
                    "marketOdds": v.market_odds, "ourOdds": v.our_odds,
                    "value": round(v.value, 4), "market": v.market,
                }
                for v in self.value_bets
            ],
            "recommendation": self.recommendation,
            "factors": self.factors,
            "news": self.news,
            "form": self.form,
            "modelFactors": self.model_factors,
            "topScores": [
                {"score": s.score, "home": s.home, "away": s.away, "probability": round(s.probability, 4)}
                for s in self.top_scores
            ],
            "marketExpectedGoals": self.market_expected_goals,
            "handicapRec": self.handicap_rec,
        }


class PredictionEngine:
    """
    Multi-factor prediction model v2:
    - Strength rating 25% (FIFA rank + squad depth)
    - Recent form 15% (last 10 matches weighted)
    - News/Injury impact 15% (NLP sentiment)
    - Market implied prob 35% (bookmaker odds de-margined, highest weight)
    - Head-to-head 10% (historical matchups)

    Score prediction: Blend model xG (50%) + market xG (50%), then Poisson top-5.
    """

    WEIGHTS = {
        "strength": 0.25,
        "form": 0.15,
        "news": 0.15,
        "market": 0.35,
        "h2h": 0.10,
    }

    def predict_match(
        self,
        match: Match,
        home_team: Team,
        away_team: Team,
        bookmaker_odds: dict = None,
        news_impact: dict = None,
        form_data: dict = None,
    ) -> Optional[Prediction]:
        if not home_team or not away_team:
            return None

        home_str = (home_team.strength or 50) / 100
        away_str = (away_team.strength or 50) / 100

        # Factor: Form
        form_home = 0.5
        form_away = 0.5
        if form_data:
            form_home = self._parse_form(form_data.get("home", ""))
            form_away = self._parse_form(form_data.get("away", ""))

        # Factor: News impact
        news_home = 0.0
        news_away = 0.0
        if news_impact:
            news_home = news_impact.get("home", {}).get("total_impact", 0.0) / 10
            news_away = news_impact.get("away", {}).get("total_impact", 0.0) / 10

        # Factor: Market implied (from bookmaker consensus)
        market_home = 0.4
        market_away = 0.3
        has_real_odds = False
        if bookmaker_odds:
            avg_home = self._avg_bookmaker_prob(bookmaker_odds, "home")
            avg_away = self._avg_bookmaker_prob(bookmaker_odds, "away")
            if avg_home > 0:
                market_home = avg_home
                market_away = avg_away
                has_real_odds = True

        # Factor: H2H (simplified - use strength diff as proxy)
        h2h_home = 0.5 + (home_str - away_str) * 0.3
        h2h_away = 1 - h2h_home

        # Weighted score
        score_home = (
            home_str * self.WEIGHTS["strength"]
            + max(0, form_home) * self.WEIGHTS["form"]
            + max(0, 0.5 + news_home) * self.WEIGHTS["news"]
            + market_home * self.WEIGHTS["market"]
            + h2h_home * self.WEIGHTS["h2h"]
        )
        score_away = (
            away_str * self.WEIGHTS["strength"]
            + max(0, form_away) * self.WEIGHTS["form"]
            + max(0, 0.5 + news_away) * self.WEIGHTS["news"]
            + market_away * self.WEIGHTS["market"]
            + h2h_away * self.WEIGHTS["h2h"]
        )

        # Normalize to get probabilities
        draw_base = 0.22
        total = score_home + score_away
        raw_home = score_home / total
        raw_away = score_away / total

        home_prob = max(0.08, min(0.75, raw_home * (1 - draw_base)))
        away_prob = max(0.08, min(0.75, raw_away * (1 - draw_base)))
        draw_prob = 1 - home_prob - away_prob

        # Ensure normalization
        total_p = home_prob + draw_prob + away_prob
        home_prob /= total_p
        draw_prob /= total_p
        away_prob /= total_p

        # === Score prediction: blend model xG + market xG ===
        # Model xG (Poisson-style from probabilities)
        model_home_xg = max(0.2, home_prob * 3.8)
        model_away_xg = max(0.2, away_prob * 3.2)

        # Market xG (from bookmaker over/under + 1X2)
        market_xg_home, market_xg_away = self._extract_market_xg(bookmaker_odds)

        # Blend: 50% model + 50% market (if market available)
        if market_xg_home > 0 and market_xg_away > 0:
            home_xg = 0.5 * model_home_xg + 0.5 * market_xg_home
            away_xg = 0.5 * model_away_xg + 0.5 * market_xg_away
        else:
            home_xg = model_home_xg
            away_xg = model_away_xg

        home_goals = round(home_xg)
        away_goals = round(away_xg)

        # Top 5 most likely scorelines from Poisson
        top_scores = self._compute_top_scores(home_xg, away_xg, top_n=5)

        # Market expected goals for display
        total_xg = home_xg + away_xg
        market_xg_total = (market_xg_home + market_xg_away) if market_xg_home > 0 else None
        market_expected_goals = {
            "home": round(home_xg, 2),
            "away": round(away_xg, 2),
            "total": round(total_xg, 2),
            "marketHome": round(market_xg_home, 2) if market_xg_home > 0 else None,
            "marketAway": round(market_xg_away, 2) if market_xg_away > 0 else None,
            "marketTotal": round(market_xg_total, 2) if market_xg_total else None,
        }

        # Handicap recommendation
        handicap_rec = self._recommend_handicap(home_prob, away_prob, home_xg, away_xg)

        # Confidence
        edge = abs(home_prob - away_prob)
        if edge > 0.20:
            confidence = "high"
        elif edge > 0.10:
            confidence = "medium"
        else:
            confidence = "low"

        # Fair odds
        fair = FairOdds(
            home=round(1 / home_prob, 2),
            draw=round(1 / draw_prob, 2),
            away=round(1 / away_prob, 2),
        )

        # Find value bets (1X2 + totals + BTTS)
        value_bets = []
        if bookmaker_odds:
            value_bets = self._find_value_bets(bookmaker_odds, fair, total_xg)

        # Recommendation
        recommendation = self._make_recommendation(
            home_prob, draw_prob, away_prob, fair, value_bets,
            home_team.name, away_team.name, confidence
        )

        return Prediction(
            match_id=match.id,
            match_label=f"{home_team.name} vs {away_team.name}",
            home_name=home_team.name,
            away_name=away_team.name,
            stage=match.stage,
            date=match.match_date.strftime("%Y-%m-%d %H:%M") if match.match_date else None,
            venue=match.venue,
            home_prob=home_prob,
            draw_prob=draw_prob,
            away_prob=away_prob,
            predicted_score=f"{home_goals}-{away_goals}",
            confidence=confidence,
            fair_odds=fair,
            bookmaker_odds=bookmaker_odds or {},
            value_bets=value_bets,
            recommendation=recommendation,
            factors={
                "strength": round(home_str - away_str, 3),
                "form": round(form_home - form_away, 3),
                "news": round(news_home - news_away, 3),
            },
            news=news_impact or {},
            form=form_data or {},
            model_factors={
                "strength": home_team.strength,
                "awayStrength": away_team.strength,
                "hasRealOdds": has_real_odds,
            },
            top_scores=top_scores,
            market_expected_goals=market_expected_goals,
            handicap_rec=handicap_rec,
        )

    def _extract_market_xg(self, bookmaker_odds: dict) -> tuple[float, float]:
        """Extract average market xG from all bookmakers' odds data"""
        if not bookmaker_odds:
            return 0.0, 0.0

        home_xgs = []
        away_xgs = []

        for bk_name, bk_data in bookmaker_odds.items():
            # Check if bookmaker data has market xG (from our scraper)
            mhg = bk_data.get("marketHomeGoals")
            mag = bk_data.get("marketAwayGoals")
            if mhg and mag and mhg > 0 and mag > 0:
                home_xgs.append(mhg)
                away_xgs.append(mag)
                continue

            # Fallback: derive from over/under odds if available
            over25 = bk_data.get("over25")
            under25 = bk_data.get("under25")
            outcome = bk_data.get("outcome", {})
            if over25 and under25 and over25 > 1 and under25 > 1:
                hp = 1 / outcome.get("home", 2.0) if outcome.get("home") else 0.4
                ap = 1 / outcome.get("away", 3.0) if outcome.get("away") else 0.3

                # Binary search for total xG from over25
                p_under = (1 / under25) / ((1 / under25) + (1 / over25))
                lo, hi = 0.5, 5.0
                for _ in range(25):
                    mid = (lo + hi) / 2
                    p = math.exp(-mid) * (1 + mid + mid * mid / 2)
                    if p > p_under:
                        lo = mid
                    else:
                        hi = mid
                total_xg = (lo + hi) / 2

                ratio = hp / (hp + ap) if (hp + ap) > 0 else 0.5
                home_xgs.append(total_xg * ratio * 1.08)
                away_xgs.append(total_xg * (1 - ratio) * 0.92)

        if not home_xgs:
            return 0.0, 0.0

        return sum(home_xgs) / len(home_xgs), sum(away_xgs) / len(away_xgs)

    def _compute_top_scores(self, home_xg: float, away_xg: float, top_n: int = 5) -> list[ScorePred]:
        """Compute top N most likely scorelines using Poisson PMF"""
        scores = []
        max_goals = 6

        for h in range(max_goals):
            for a in range(max_goals):
                p_home = self._poisson_pmf(h, home_xg)
                p_away = self._poisson_pmf(a, away_xg)
                prob = p_home * p_away
                scores.append(ScorePred(
                    score=f"{h}-{a}",
                    home=h,
                    away=a,
                    probability=prob,
                ))

        scores.sort(key=lambda s: s.probability, reverse=True)
        return scores[:top_n]

    @staticmethod
    def _poisson_pmf(k: int, lam: float) -> float:
        """Poisson probability mass function: P(X=k) = e^-lam * lam^k / k!"""
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    def _recommend_handicap(self, home_p: float, away_p: float,
                             home_xg: float, away_xg: float) -> dict:
        """Recommend a handicap line based on the match prediction"""
        xg_diff = home_xg - away_xg
        prob_diff = home_p - away_p

        # Determine handicap line
        if xg_diff > 1.8:
            line = -2.0
            label = "主让2球"
        elif xg_diff > 1.2:
            line = -1.5
            label = "主让1.5球"
        elif xg_diff > 0.6:
            line = -1.0
            label = "主让1球"
        elif xg_diff > 0.2:
            line = -0.5
            label = "主让0.5球"
        elif xg_diff > -0.2:
            line = 0.0
            label = "平手盘"
        elif xg_diff > -0.6:
            line = 0.5
            label = "客让0.5球"
        elif xg_diff > -1.2:
            line = 1.0
            label = "客让1球"
        else:
            line = 1.5
            label = "客让1.5球"

        # Confidence in handicap
        if abs(prob_diff) > 0.25:
            h_conf = "high"
        elif abs(prob_diff) > 0.12:
            h_conf = "medium"
        else:
            h_conf = "low"

        return {
            "line": line,
            "label": label,
            "confidence": h_conf,
            "xgDiff": round(xg_diff, 2),
        }

    def _parse_form(self, form_str: str) -> float:
        """Parse WWDLWW form string to 0-1 score"""
        if not form_str:
            return 0.5
        weights = [1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6]
        total, score = 0, 0
        for i, c in enumerate(form_str[:10]):
            w = weights[i] if i < len(weights) else 0.5
            total += w
            if c == "W":
                score += w
            elif c == "D":
                score += w * 0.4
        return score / total if total > 0 else 0.5

    def _avg_bookmaker_prob(self, odds_dict: dict, selection: str) -> float:
        """Average implied probability across bookmakers"""
        probs = []
        for bk_name, bk_data in odds_dict.items():
            outcome = bk_data.get("outcome", {})
            odds_val = outcome.get(selection)
            if odds_val and odds_val > 1:
                probs.append(1 / odds_val)
        if not probs:
            return 0.0
        return sum(probs) / len(probs)

    def _find_value_bets(self, bookmaker_odds: dict, fair: FairOdds, total_xg: float) -> list:
        """Find value bets across 1X2, totals, and BTTS markets"""
        value_bets = []
        fair_map = {"home": fair.home, "draw": fair.draw, "away": fair.away}

        for bk_name, bk_data in bookmaker_odds.items():
            # 1X2 market
            outcome = bk_data.get("outcome", {})
            for sel in ["home", "draw", "away"]:
                market_odds = outcome.get(sel)
                our_odds = fair_map[sel]
                if market_odds and market_odds > our_odds:
                    value = (market_odds - our_odds) / our_odds
                    if value > 0.02:
                        value_bets.append(ValueBet(
                            type=sel, bookie=bk_name,
                            market_odds=market_odds, our_odds=our_odds,
                            value=value, market="1x2",
                        ))

            # Totals market (Over/Under 2.5)
            over25 = bk_data.get("over25")
            under25 = bk_data.get("under25")
            if over25 and over25 > 1:
                # Our fair odds for over 2.5
                p_under_25 = sum(
                    self._poisson_pmf(h, total_xg * 0.58) * self._poisson_pmf(a, total_xg * 0.42)
                    for h in range(6) for a in range(6) if h + a <= 2
                )
                p_over_25 = 1 - p_under_25
                if p_over_25 > 0.05:
                    our_over = round(1 / p_over_25, 2)
                    if over25 > our_over:
                        value = (over25 - our_over) / our_over
                        if value > 0.03:
                            value_bets.append(ValueBet(
                                type="over25", bookie=bk_name,
                                market_odds=over25, our_odds=our_over,
                                value=value, market="totals",
                            ))
            if under25 and under25 > 1:
                p_under_25 = sum(
                    self._poisson_pmf(h, total_xg * 0.58) * self._poisson_pmf(a, total_xg * 0.42)
                    for h in range(6) for a in range(6) if h + a <= 2
                )
                if p_under_25 > 0.05:
                    our_under = round(1 / p_under_25, 2)
                    if under25 > our_under:
                        value = (under25 - our_under) / our_under
                        if value > 0.03:
                            value_bets.append(ValueBet(
                                type="under25", bookie=bk_name,
                                market_odds=under25, our_odds=our_under,
                                value=value, market="totals",
                            ))

            # BTTS market
            btts_yes = bk_data.get("bttsYes")
            btts_no = bk_data.get("bttsNo")
            if btts_yes and btts_yes > 1:
                h_xg = total_xg * 0.58
                a_xg = total_xg * 0.42
                p_btts_yes = 1 - (self._poisson_pmf(0, h_xg) + self._poisson_pmf(0, a_xg) - self._poisson_pmf(0, h_xg) * self._poisson_pmf(0, a_xg))
                if p_btts_yes > 0.05:
                    our_btts = round(1 / p_btts_yes, 2)
                    if btts_yes > our_btts:
                        value = (btts_yes - our_btts) / our_btts
                        if value > 0.03:
                            value_bets.append(ValueBet(
                                type="btts_yes", bookie=bk_name,
                                market_odds=btts_yes, our_odds=our_btts,
                                value=value, market="btts",
                            ))

        value_bets.sort(key=lambda v: v.value, reverse=True)
        return value_bets

    def _make_recommendation(
        self, home_p, draw_p, away_p, fair, value_bets,
        home_name, away_name, confidence
    ) -> dict:
        """Generate betting recommendation"""
        if not value_bets:
            return {"action": "NO BET", "reason": "无明显价值机会", "stake": "none", "bet": None}

        best = value_bets[0]

        if best.value > 0.08 and confidence == "high":
            action = "STRONG VALUE"
            stake = "high"
        elif best.value > 0.05:
            action = "MODERATE VALUE"
            stake = "medium"
        elif best.value > 0.02:
            action = "SLIM VALUE"
            stake = "low"
        else:
            return {"action": "NO BET", "reason": "价值空间过小", "stake": "none", "bet": None}

        type_labels = {
            "home": f"{home_name}胜", "draw": "平局", "away": f"{away_name}胜",
            "over25": "大2.5球", "under25": "小2.5球",
            "btts_yes": "双方进球", "btts_no": "双方不进球",
        }
        sel_label = type_labels.get(best.type, best.type)
        reason = f"{sel_label} 市场赔率 {best.market_odds} 高于公平赔率 {best.our_odds}，存在 {(best.value*100):.1f}% 价值空间"

        return {
            "action": action,
            "reason": reason,
            "stake": stake,
            "bet": {
                "type": best.type,
                "bookie": best.bookie,
                "marketOdds": best.market_odds,
                "ourOdds": best.our_odds,
                "market": best.market,
            },
        }
