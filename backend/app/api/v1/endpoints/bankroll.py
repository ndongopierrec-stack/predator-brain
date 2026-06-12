"""API Bankroll — Predator Brain"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("predator.api.bankroll")
router = APIRouter(prefix="/bankroll", tags=["Bankroll"])


class StakeCalcRequest(BaseModel):
    edge_pct: float = Field(..., ge=0, le=50, description="Edge en %")
    odds: float = Field(..., gt=1.0, description="Cote décimale")
    prob_model: float = Field(..., ge=0, le=1, description="Probabilité modèle")
    bankroll: float = Field(10_000.0, gt=0)
    strategy: str = Field("kelly_quarter", description="flat_pct / kelly_quarter / kelly_half")
    league: str = Field("unknown")
    market: str = Field("1X2")
    n_legs: int = Field(1, ge=1, le=8, description="Sélections dans le ticket")


class BetSettleRequest(BaseModel):
    bet_id: str
    won: bool
    bankroll_after: Optional[float] = None


@router.post("/calculate-stake")
def calculate_stake(req: StakeCalcRequest):
    """
    Calcule la mise optimale selon la stratégie sélectionnée.
    Retourne aussi les comparaisons Kelly full / half / quarter.
    """
    from app.services.engines.bankroll_engine import (
        BankrollEngine, StakeStrategy
    )

    strategy_map = {
        "flat":           StakeStrategy.FLAT_PCT,
        "flat_pct":       StakeStrategy.FLAT_PCT,
        "kelly_full":     StakeStrategy.KELLY_FULL,
        "kelly_half":     StakeStrategy.KELLY_HALF,
        "kelly_quarter":  StakeStrategy.KELLY_QUARTER,
        "kelly_tenth":    StakeStrategy.KELLY_TENTH,
    }
    strat = strategy_map.get(req.strategy, StakeStrategy.KELLY_QUARTER)

    engine = BankrollEngine(
        initial_bankroll=req.bankroll,
        strategy=strat,
    )

    rec = engine.recommend_stake(
        edge_pct=req.edge_pct,
        odds=req.odds,
        prob_model=req.prob_model,
        league=req.league,
        market=req.market,
        n_legs=req.n_legs,
    )

    # Calculer toutes les stratégies pour comparaison
    b = req.odds - 1
    p = req.prob_model
    q = 1 - p
    kelly_full_pct = max(0.0, (b * p - q) / b) * 100 if b > 0 else 0.0

    return {
        "recommended": {
            "strategy":    rec.strategy.value,
            "stake_pct":   rec.stake_pct,
            "stake_abs":   rec.stake_amount,
            "risk_level":  rec.risk_level.value,
            "is_recommended": rec.is_recommended,
            "message":     rec.message,
            "warnings":    rec.warnings,
        },
        "kelly_comparison": {
            "kelly_full":    {"pct": round(kelly_full_pct, 2), "abs": round(kelly_full_pct / 100 * req.bankroll, 2)},
            "kelly_half":    {"pct": round(kelly_full_pct / 2, 2), "abs": round(kelly_full_pct / 200 * req.bankroll, 2)},
            "kelly_quarter": {"pct": round(kelly_full_pct / 4, 2), "abs": round(kelly_full_pct / 400 * req.bankroll, 2)},
            "kelly_tenth":   {"pct": round(kelly_full_pct / 10, 2), "abs": round(kelly_full_pct / 1000 * req.bankroll, 2)},
        },
        "math": {
            "edge_pct":      req.edge_pct,
            "odds":          req.odds,
            "prob_model":    req.prob_model,
            "fair_odds":     round(1 / p, 3) if p > 0 else 0,
            "expected_value": round((p * (req.odds - 1) - q) * 100, 2),
        },
    }


@router.get("/snapshot")
def get_bankroll_snapshot():
    """État actuel de la bankroll."""
    from app.core.model_registry import registry
    snap = registry.bankroll_engine.get_snapshot()
    return {
        "total":           snap.total,
        "available":       snap.available,
        "reserved":        snap.reserved,
        "daily_profit":    snap.daily_profit,
        "weekly_profit":   snap.weekly_profit,
        "monthly_profit":  snap.monthly_profit,
        "drawdown_current": round(snap.drawdown_current * 100, 2),
        "drawdown_max":     round(snap.drawdown_max * 100, 2),
        "peak":            snap.peak,
        "open_bets":       len(registry.bankroll_engine._open_bets),
    }


@router.get("/performance")
def get_performance():
    """Rapport de performance complet."""
    from app.core.model_registry import registry
    perf = registry.bankroll_engine.performance_report()
    curve = registry.bankroll_engine.get_equity_curve()
    # Limiter à 200 points
    if len(curve) > 200:
        step = len(curve) // 200
        curve = curve[::step]
    return {**perf, "equity_curve": curve}


@router.get("/alerts")
def get_alerts():
    """Alertes de risque actives."""
    from app.core.model_registry import registry
    alerts = registry.bankroll_engine.get_alerts(unread_only=False)
    return {
        "count": len(alerts),
        "alerts": [
            {"severity": a.severity, "message": a.message, "action": a.action,
             "timestamp": a.timestamp.isoformat()}
            for a in alerts[-10:]
        ],
    }
