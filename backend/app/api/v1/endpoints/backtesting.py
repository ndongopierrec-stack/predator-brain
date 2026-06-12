"""
API Backtesting — Predator Brain

Endpoints:
  POST /api/v1/backtest/run          Lance un backtest sur données historiques
  POST /api/v1/backtest/walk-forward Walk-Forward validation
  GET  /api/v1/backtest/strategies   Stratégies prédéfinies disponibles
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("predator.api.backtest")
router = APIRouter(prefix="/backtest", tags=["Backtesting"])

# Ajouter le chemin du projet parent
_BASE = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(_BASE))


class BacktestRequest(BaseModel):
    from_date: str = Field("2022-01-01", description="Date de début YYYY-MM-DD")
    to_date:   str = Field("2024-12-31", description="Date de fin YYYY-MM-DD")
    leagues:   Optional[List[str]] = Field(None, description='["E0","F1","D1"]')
    min_confidence: float = Field(0.55, ge=0.40, le=0.85)
    min_edge:   float = Field(0.03, ge=0.00, le=0.20)
    kelly_fraction: float = Field(0.25, ge=0.05, le=1.0)
    max_stake_pct: float = Field(0.05, ge=0.01, le=0.20)
    initial_bankroll: float = Field(10_000.0, gt=0)
    home_only: bool = Field(False, description="Parier uniquement sur les victoires à domicile")
    strategy_name: str = Field("default", description="Nom de la stratégie (pour le rapport)")


class WalkForwardRequest(BacktestRequest):
    n_splits: int = Field(5, ge=2, le=10, description="Nombre de splits walk-forward")


PREDEFINED_STRATEGIES = {
    "conservative": {
        "name": "Stratégie Conservatrice",
        "description": "Paris à fort edge seulement. Faible ROI mais drawdown minimal.",
        "min_confidence": 0.65,
        "min_edge": 0.08,
        "kelly_fraction": 0.10,
        "max_stake_pct": 0.02,
    },
    "moderate": {
        "name": "Stratégie Modérée (Recommandée)",
        "description": "Équilibre entre ROI et risque. Quart-Kelly. Standard professionnel.",
        "min_confidence": 0.55,
        "min_edge": 0.04,
        "kelly_fraction": 0.25,
        "max_stake_pct": 0.05,
    },
    "aggressive": {
        "name": "Stratégie Agressive",
        "description": "ROI élevé potentiel mais drawdown significatif.",
        "min_confidence": 0.50,
        "min_edge": 0.02,
        "kelly_fraction": 0.50,
        "max_stake_pct": 0.08,
    },
    "home_value": {
        "name": "Value Bets Domicile",
        "description": "Spécialisé sur les favoris à domicile avec edge > 5%.",
        "min_confidence": 0.58,
        "min_edge": 0.05,
        "kelly_fraction": 0.25,
        "max_stake_pct": 0.04,
        "home_only": True,
    },
}


@router.get("/strategies")
def list_strategies():
    """Retourne les stratégies de backtesting prédéfinies."""
    return {
        "strategies": PREDEFINED_STRATEGIES,
        "note": "Vous pouvez utiliser ces paramètres dans POST /run ou personnaliser"
    }


@router.post("/run")
def run_backtest(req: BacktestRequest):
    """
    Lance un backtest sur les données historiques CSV.

    Utilise le modèle Dixon-Coles entraîné et les données football-data.co.uk.
    """
    from app.core.model_registry import registry

    try:
        from backtesting.real_backtest import RealBacktest
        from data.real_data_loader import RealDataLoader
    except ImportError as e:
        raise HTTPException(500, f"Module de backtesting non disponible: {e}")

    if not registry.is_trained or registry._df_cache is None:
        raise HTTPException(400, "Modèle non entraîné. Lancez POST /predictions/retrain d'abord.")

    # Modèle wrappé pour le backtest
    def predict_fn(match: dict) -> dict:
        return registry.predict(
            match.get("team_home", ""),
            match.get("team_away", ""),
        )

    bt = RealBacktest(initial_bankroll=req.initial_bankroll)
    results = bt.run(
        from_date=req.from_date,
        to_date=req.to_date,
        model=predict_fn,
        leagues=req.leagues,
        min_confidence=req.min_confidence,
        kelly_fraction=req.kelly_fraction,
        max_stake_pct=req.max_stake_pct,
        min_edge=req.min_edge,
        df=registry._df_cache,
        home_only=req.home_only,
    )

    # Limiter l'equity curve à 500 points pour le frontend
    curve = results.equity_curve
    if len(curve) > 500:
        step = len(curve) // 500
        curve = curve[::step]

    return {
        "strategy_name": req.strategy_name,
        "period": {"from": req.from_date, "to": req.to_date},
        "parameters": {
            "min_confidence": req.min_confidence,
            "min_edge": req.min_edge,
            "kelly_fraction": req.kelly_fraction,
            "max_stake_pct": req.max_stake_pct,
        },
        "results": {
            "total_matches":  results.total_matches,
            "total_bets":     results.total_bets,
            "bets_won":       results.bets_won,
            "win_rate":       round(results.win_rate * 100, 2),
            "accuracy":       round(results.accuracy * 100, 2),
            "roi_pct":        round(results.roi_pct, 2),
            "total_profit":   round(results.total_profit, 2),
            "total_staked":   round(results.total_staked, 2),
            "final_bankroll": round(results.final_bankroll, 2),
            "max_drawdown":   round(results.max_drawdown * 100, 2),
            "sharpe_ratio":   round(results.sharpe_ratio, 2),
            "avg_odds":       round(results.avg_odds, 2),
            "avg_confidence": round(results.avg_confidence * 100, 2),
        },
        "by_league": {
            lg: {
                "bets":     s["bets"],
                "win_rate": round(s["win_rate"] * 100, 2),
                "roi_pct":  round(s["roi_pct"], 2),
                "profit":   round(s["profit"], 2),
            }
            for lg, s in results.by_league.items()
        },
        "by_result_type": {
            outcome: {
                "bets":     s["bets"],
                "win_rate": round(s["win_rate"] * 100, 2),
                "roi_pct":  round(s["roi_pct"], 2),
            }
            for outcome, s in results.by_result_type.items()
        },
        "equity_curve":    curve,
        "interpretation": _interpret_backtest(results),
    }


@router.post("/walk-forward")
def walk_forward_validation(req: WalkForwardRequest):
    """
    Walk-Forward Validation — évite le data snooping.
    Entraîne sur le passé, teste sur le futur. N splits.
    """
    from app.core.model_registry import registry

    try:
        from backtesting.real_backtest import RealBacktest
    except ImportError as e:
        raise HTTPException(500, f"Module de backtesting non disponible: {e}")

    if not registry.is_trained or registry._df_cache is None:
        raise HTTPException(400, "Modèle non entraîné.")

    def model_factory(train_df):
        """Entraîne un modèle sur les données train et retourne une fn de prédiction."""
        from app.services.models.dixon_coles import DixonColesModel
        dc = DixonColesModel()
        dc.fit(train_df, time_decay=True)

        def predict_fn(match: dict) -> dict:
            pred = dc.predict(match.get("team_home", ""), match.get("team_away", ""))
            return {"prob_home": pred.prob_home, "prob_draw": pred.prob_draw, "prob_away": pred.prob_away}

        return predict_fn

    bt = RealBacktest(initial_bankroll=req.initial_bankroll)
    splits = bt.walk_forward_validation(
        model_factory=model_factory,
        df=registry._df_cache,
        n_splits=req.n_splits,
        min_confidence=req.min_confidence,
        min_edge=req.min_edge,
        kelly_fraction=req.kelly_fraction,
        max_stake_pct=req.max_stake_pct,
    )

    import numpy as np
    return {
        "n_splits": len(splits),
        "summary": {
            "avg_roi":      round(float(np.mean([s.roi_pct for s in splits])), 2),
            "avg_accuracy": round(float(np.mean([s.accuracy for s in splits])) * 100, 2),
            "avg_drawdown": round(float(np.mean([s.max_drawdown for s in splits])) * 100, 2),
            "avg_sharpe":   round(float(np.mean([s.sharpe_ratio for s in splits])), 2),
        },
        "splits": [
            {
                "split":         i + 1,
                "total_bets":    s.total_bets,
                "win_rate":      round(s.win_rate * 100, 2),
                "roi_pct":       round(s.roi_pct, 2),
                "max_drawdown":  round(s.max_drawdown * 100, 2),
                "sharpe":        round(s.sharpe_ratio, 2),
                "final_bankroll":round(s.final_bankroll, 2),
            }
            for i, s in enumerate(splits)
        ],
    }


def _interpret_backtest(r) -> str:
    lines = []

    if r.total_bets == 0:
        return "Aucun pari déclenché avec ces paramètres — assouplissez les filtres."

    if r.roi_pct > 5:
        lines.append(f"✅ ROI excellent ({r.roi_pct:+.1f}%) — stratégie potentiellement profitable.")
    elif r.roi_pct > 0:
        lines.append(f"🟡 ROI positif ({r.roi_pct:+.1f}%) — continuez avec plus de données.")
    else:
        lines.append(f"🔴 ROI négatif ({r.roi_pct:+.1f}%) — revoir les paramètres.")

    lines.append(f"Sur {r.total_bets} paris : {r.win_rate:.0%} de réussite, "
                 f"drawdown max {r.max_drawdown:.0%}, Sharpe {r.sharpe_ratio:.2f}.")

    if r.max_drawdown > 0.25:
        lines.append("⚠️ Drawdown élevé — réduire la fraction Kelly ou augmenter le seuil d'edge.")

    return " ".join(lines)
