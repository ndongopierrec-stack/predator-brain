"""
Over/Under & BTTS API — Predator Brain

Endpoints:
  POST /api/v1/ou-btts/analyze      Analyse O/U et BTTS d'un match
  POST /api/v1/ou-btts/scan         Scanner plusieurs matchs
  POST /api/v1/ou-btts/value-bets   Détection de value bets O/U / BTTS
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger("predator.api.ou_btts")
router = APIRouter(prefix="/ou-btts", tags=["O/U & BTTS"])


# ─── Schémas ──────────────────────────────────────────────────────────────────

class OUBTTSAnalysisRequest(BaseModel):
    home_team: str = Field(..., min_length=2, example="Arsenal")
    away_team: str = Field(..., min_length=2, example="Chelsea")
    league: Optional[str] = None

    # Cotes disponibles (clés normalisées : OVER_25, UNDER_25, BTTS_Y, BTTS_N, etc.)
    market_odds: Optional[Dict[str, float]] = Field(
        None,
        description="Cotes par marché. Clés: OVER_15, UNDER_15, OVER_25, UNDER_25, OVER_35, BTTS_Y, BTTS_N",
        example={
            "OVER_25": 1.85,
            "UNDER_25": 1.98,
            "BTTS_Y": 1.72,
            "BTTS_N": 2.05,
            "OVER_15": 1.30,
            "OVER_35": 2.90,
        }
    )

    min_edge: float = Field(0.03, ge=0.01, le=0.30, description="Edge minimum pour value bet (0.03=3%)")


class OUBTTSScanRequest(BaseModel):
    matches: List[Dict] = Field(..., description="Liste de matchs avec market_odds")
    min_edge: float = Field(0.03, ge=0.01, le=0.30)
    top_n: int = Field(20, ge=1, le=100)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze")
def analyze_ou_btts(req: OUBTTSAnalysisRequest):
    """
    Analyse complète O/U et BTTS via le moteur Poisson bivariable.

    Utilise les lambdas DC quand disponibles (équipes connues).
    Retourne les probabilités pour O/U 1.5, 2.5, 3.5, 4.5, BTTS, Clean Sheet.
    """
    from app.core.model_registry import registry
    from app.services.engines.ou_btts_engine import OUBTTSEngine

    # Prédiction DC pour récupérer les lambdas
    probs = registry.predict(req.home_team, req.away_team)

    engine = OUBTTSEngine()
    lam_h = probs.get("lambda_home")
    lam_a = probs.get("lambda_away")
    dc_known = probs.get("dc_known", False)

    if lam_h and lam_a and lam_h > 0 and lam_a > 0:
        pred = engine.predict(
            lambda_home=lam_h,
            lambda_away=lam_a,
            home_team=req.home_team,
            away_team=req.away_team,
            dc_known=dc_known,
        )
    else:
        pred = engine.predict_from_1x2(
            prob_home=probs["prob_home"],
            prob_draw=probs["prob_draw"],
            prob_away=probs["prob_away"],
            home_team=req.home_team,
            away_team=req.away_team,
        )

    # Value bets si cotes fournies
    value_markets = []
    if req.market_odds:
        value_markets = engine.get_value_markets(pred, req.market_odds, min_edge=req.min_edge)

    return {
        "match": {
            "home_team": req.home_team,
            "away_team": req.away_team,
            "league": req.league,
        },
        "model": {
            "dc_known": pred.dc_known,
            "lambda_home": round(pred.lambda_home, 3),
            "lambda_away": round(pred.lambda_away, 3),
            "expected_total_goals": round(pred.expected_total_goals, 2),
            "most_likely_score": f"{pred.most_likely_goals_home}-{pred.most_likely_goals_away}",
            "model_confidence": round(pred.model_confidence, 2),
        },
        "over_under": {
            "over_15":  _fmt(pred.prob_over_15),
            "under_15": _fmt(pred.prob_under_15),
            "over_25":  _fmt(pred.prob_over_25),
            "under_25": _fmt(pred.prob_under_25),
            "over_35":  _fmt(pred.prob_over_35),
            "under_35": _fmt(pred.prob_under_35),
            "over_45":  _fmt(pred.prob_over_45),
            "under_45": _fmt(pred.prob_under_45),
        },
        "btts": {
            "yes":         _fmt(pred.prob_btts_yes),
            "no":          _fmt(pred.prob_btts_no),
            "btts_over25": _fmt(pred.prob_btts_over25),
            "no_btts_under25": _fmt(pred.prob_btts_under25),
        },
        "clean_sheet": {
            "home_clean": _fmt(pred.prob_cs_home),
            "away_clean": _fmt(pred.prob_cs_away),
        },
        "fair_odds": {
            "over_25":  round(1 / pred.prob_over_25, 2) if pred.prob_over_25 > 0 else None,
            "under_25": round(1 / pred.prob_under_25, 2) if pred.prob_under_25 > 0 else None,
            "btts_yes": round(1 / pred.prob_btts_yes, 2) if pred.prob_btts_yes > 0 else None,
            "btts_no":  round(1 / pred.prob_btts_no, 2) if pred.prob_btts_no > 0 else None,
        },
        "value_bets": value_markets,
        "warning": (
            None if pred.dc_known
            else "⚠️ Équipes non reconnues par le modèle — probabilités estimées depuis le marché, moins précises"
        ),
    }


@router.post("/scan")
def scan_ou_btts(req: OUBTTSScanRequest):
    """
    Scanne plusieurs matchs pour trouver les value bets O/U et BTTS.

    Chaque match doit avoir :
    - home_team, away_team
    - market_odds : {"OVER_25": 1.85, "BTTS_Y": 1.72, ...}
    """
    from app.core.model_registry import registry
    from app.services.engines.ou_btts_engine import OUBTTSEngine

    engine = OUBTTSEngine()
    all_value_bets = []
    total_analyzed = 0

    for match in req.matches:
        home = match.get("home_team", "")
        away = match.get("away_team", "")
        market_odds = match.get("market_odds", {})

        if not home or not away:
            continue

        probs = registry.predict(home, away)
        lam_h = probs.get("lambda_home")
        lam_a = probs.get("lambda_away")
        dc_known = probs.get("dc_known", False)

        if lam_h and lam_a:
            pred = engine.predict(lam_h, lam_a, home, away, dc_known)
        else:
            pred = engine.predict_from_1x2(
                probs["prob_home"], probs["prob_draw"], probs["prob_away"], home, away
            )

        total_analyzed += 1

        if market_odds:
            vbs = engine.get_value_markets(pred, market_odds, min_edge=req.min_edge)
            for vb in vbs:
                all_value_bets.append({
                    "match": f"{home} vs {away}",
                    "league": match.get("league", "?"),
                    "dc_known": pred.dc_known,
                    "lambda_home": round(pred.lambda_home, 2),
                    "lambda_away": round(pred.lambda_away, 2),
                    **vb,
                })

    # Trier par edge décroissant, limiter à top_n
    all_value_bets.sort(key=lambda x: x["edge_pct"], reverse=True)
    all_value_bets = all_value_bets[:req.top_n]

    return {
        "matches_analyzed": total_analyzed,
        "value_bets_found": len(all_value_bets),
        "min_edge_applied": req.min_edge,
        "value_bets": all_value_bets,
    }


# ─── Helper ───────────────────────────────────────────────────────────────────

def _fmt(p: float) -> dict:
    """Formate une probabilité avec sa cote juste."""
    p = max(0.001, min(0.999, p))
    return {
        "prob": round(p, 4),
        "pct":  f"{p:.1%}",
        "fair_odds": round(1 / p, 2),
    }
