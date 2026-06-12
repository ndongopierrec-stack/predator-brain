"""
Profitability Audit API — Predator Brain V2

GET  /api/v1/profitability/report    Rapport complet de rentabilité
GET  /api/v1/profitability/verdict   Verdict simple : PROFITABLE / NOT PROFITABLE
POST /api/v1/profitability/train-ml  Entraîne le ML Bet Scorer
GET  /api/v1/profitability/ml-status Statut du ML Scorer
POST /api/v1/profitability/score-bet Score ML d'un pari potentiel
GET  /api/v1/profitability/clv-auto  Lance le CLV auto-closer
"""

import json
import logging
import threading
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("predator.api.profitability")
router = APIRouter(prefix="/profitability", tags=["Profitability Audit V2"])

_DATA_DIR = Path(__file__).resolve().parents[5] / "data"
_CMP_FILE = _DATA_DIR / "model_comparison_results.json"
_WF_FILE  = _DATA_DIR / "walk_forward_results.json"

_train_state = {
    "running": False,
    "done":    False,
    "error":   None,
    "metrics": None,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _compute_profitability_report() -> dict:
    """
    Construit le rapport de profitabilité depuis toutes les sources disponibles :
    - Walk-forward results (DC + ML)
    - CLV engine records
    - Model comparison results
    """
    cmp  = _load_json(_CMP_FILE)
    wf   = _load_json(_WF_FILE)

    # Données walk-forward ML
    ml_rows = cmp.get("ml_wf_rows", [])
    dc_wf   = wf.get("walk_forward", [])
    report_table = cmp.get("comparison_table", [])
    honest  = cmp.get("honest_report", {})

    # ── Métriques globales depuis le walk-forward ──────────────────────────────
    all_rois  = [r.get("roi_pct") for r in ml_rows if r.get("roi_pct") is not None]
    all_bets  = sum(r.get("n_bets", 0) for r in ml_rows)
    dc_rois   = [r.get("roi") for r in dc_wf if r.get("roi") is not None]
    dc_bets   = sum(r.get("bets", 0) for r in dc_wf)

    combined_rois = all_rois + dc_rois
    total_bets    = all_bets + dc_bets

    if combined_rois:
        avg_roi    = float(np.mean(combined_rois))
        best_roi   = float(np.max(combined_rois))
        worst_roi  = float(np.min(combined_rois))
        pct_pos    = float(np.mean([1 if r > 0 else 0 for r in combined_rois]) * 100)
    else:
        avg_roi = best_roi = worst_roi = pct_pos = None

    # Drawdown (DC walk-forward)
    dds = [r.get("max_dd") for r in dc_wf if r.get("max_dd") is not None]
    max_dd = float(np.max(dds)) if dds else None

    # ── Par ligue ─────────────────────────────────────────────────────────────
    by_league: Dict[str, dict] = {}
    for row in report_table:
        lg = row.get("league", "?")
        if lg not in by_league:
            by_league[lg] = {"rois": [], "bets": 0, "n_pos": 0, "briers": []}
        roi = row.get("roi_mean")
        if roi is not None:
            by_league[lg]["rois"].append(roi)
            if roi > 0: by_league[lg]["n_pos"] += 1
        by_league[lg]["bets"] += row.get("n_bets", 0)
        if row.get("brier_mean"): by_league[lg]["briers"].append(row["brier_mean"])

    leagues_out = {}
    for lg, d in by_league.items():
        rois = d["rois"]
        leagues_out[lg] = {
            "avg_roi":    round(float(np.mean(rois)), 2) if rois else None,
            "n_bets":     d["bets"],
            "n_pos_ratio": round(d["n_pos"] / max(len(rois), 1) * 100, 1),
            "avg_brier":  round(float(np.mean(d["briers"])), 4) if d["briers"] else None,
        }

    # ── Par marché ────────────────────────────────────────────────────────────
    by_market: Dict[str, dict] = {}
    for row in report_table:
        mkt = row.get("market", "?")
        if mkt not in by_market:
            by_market[mkt] = {"rois": [], "bets": 0}
        roi = row.get("roi_mean")
        if roi is not None: by_market[mkt]["rois"].append(roi)
        by_market[mkt]["bets"] += row.get("n_bets", 0)

    markets_out = {
        mkt: {
            "avg_roi": round(float(np.mean(d["rois"])), 2) if d["rois"] else None,
            "n_bets":  d["bets"],
        }
        for mkt, d in by_market.items()
    }

    # ── Par modèle ────────────────────────────────────────────────────────────
    by_model: Dict[str, dict] = {}
    for row in report_table:
        mdl = row.get("model", "?")
        if mdl not in by_model:
            by_model[mdl] = {"rois": [], "bets": 0, "n_valide": 0}
        roi = row.get("roi_mean")
        if roi is not None: by_model[mdl]["rois"].append(roi)
        by_model[mdl]["bets"] += row.get("n_bets", 0)
        if row.get("status") == "VALIDE":
            by_model[mdl]["n_valide"] += 1

    models_out = {
        mdl: {
            "avg_roi":  round(float(np.mean(d["rois"])), 2) if d["rois"] else None,
            "n_bets":   d["bets"],
            "n_valide": d["n_valide"],
        }
        for mdl, d in by_model.items()
    }

    # ── CLV engine (paris réels trackés) ──────────────────────────────────────
    clv_summary: dict = {}
    try:
        from app.core.model_registry import registry
        clv_summary = registry.clv_engine.summary_stats()
    except Exception:
        pass

    clv_auto_stats: dict = {}
    try:
        from app.services.engines.clv_auto_closer import get_auto_closer
        clv_auto_stats = get_auto_closer().stats()
    except Exception:
        pass

    # ── Verdict final ─────────────────────────────────────────────────────────
    verdict, verdict_color = _compute_verdict(
        avg_roi, total_bets, pct_pos, max_dd, clv_summary
    )

    # ── Bankroll curve (depuis DC WF) ─────────────────────────────────────────
    bankroll_curve = _build_bankroll_curve(dc_wf)

    # ── Corrélation CLV → ROI (si données dispo) ──────────────────────────────
    clv_roi_correlation = None
    if clv_summary.get("total_bets", 0) >= 10:
        clv_roi_correlation = "données CLV insuffisantes pour corrélation robuste"

    return {
        "generated_at":     pd.Timestamp.now().isoformat(),
        "data_source":      "walk_forward_strict + clv_engine",
        "n_matches_total":  6823,
        "n_seasons":        len(set(r.get("test_season") for r in ml_rows)),
        "n_leagues":        len(by_league),
        "n_models":         len(by_model),

        # Global
        "global": {
            "total_bets":   total_bets,
            "avg_roi_pct":  round(avg_roi, 2) if avg_roi else None,
            "best_roi_pct": round(best_roi, 2) if best_roi else None,
            "worst_roi_pct":round(worst_roi, 2) if worst_roi else None,
            "pct_seasons_positive": round(pct_pos, 1) if pct_pos else None,
            "max_drawdown_pct": round(max_dd, 1) if max_dd else None,
        },

        # Breakdowns
        "by_league":    leagues_out,
        "by_market":    markets_out,
        "by_model":     models_out,

        # CLV
        "clv_realtime": {
            "n_bets_tracked":   clv_summary.get("total_bets", 0),
            "avg_clv_pct":      clv_summary.get("avg_clv_pct"),
            "pct_clv_positive": clv_summary.get("clv_positive_rate"),
            "verdict":          clv_summary.get("verdict"),
            "auto_closer":      clv_auto_stats,
        },

        # Courbes
        "bankroll_curve": bankroll_curve,
        "clv_roi_correlation": clv_roi_correlation,

        # Rapport honnête V2
        "honest_report": honest,
        "no_money_mode": cmp.get("no_money_mode", True),

        # Verdict
        "verdict":          verdict,
        "verdict_color":    verdict_color,
        "verdict_details":  _verdict_details(avg_roi, total_bets, pct_pos, max_dd),
    }


def _compute_verdict(avg_roi, total_bets, pct_pos, max_dd, clv_summary) -> tuple:
    """Verdict de rentabilité 4 niveaux."""
    if total_bets < 50:
        return "INSUFFICIENT_DATA", "gray"

    clv_avg = clv_summary.get("avg_clv_pct") if clv_summary else None
    clv_pos_rate = clv_summary.get("clv_positive_rate", 50)

    if (avg_roi and avg_roi > 3
            and total_bets >= 500
            and pct_pos and pct_pos >= 60
            and (max_dd is None or max_dd < 40)
            and (clv_avg is None or clv_avg > 0)):
        return "PROFITABLE", "green"

    if (avg_roi and avg_roi > 0
            and total_bets >= 200
            and pct_pos and pct_pos >= 50):
        return "BREAK_EVEN", "yellow"

    if avg_roi and avg_roi < -5:
        return "NOT_PROFITABLE", "red"

    return "INSUFFICIENT_DATA", "gray"


def _verdict_details(avg_roi, total_bets, pct_pos, max_dd) -> list:
    details = []
    if total_bets < 500:
        details.append(f"⚠️ {total_bets} paris — objectif 500+ pour significativité statistique")
    if avg_roi is None:
        details.append("⚠️ Aucune donnée ROI disponible")
    elif avg_roi < 0:
        details.append(f"❌ ROI moyen {avg_roi:+.1f}% — stratégie perdante sur l'historique")
    elif avg_roi < 3:
        details.append(f"⚠️ ROI moyen {avg_roi:+.1f}% — positif mais pas assez solide")
    else:
        details.append(f"✅ ROI moyen {avg_roi:+.1f}% — signal positif")
    if pct_pos and pct_pos < 50:
        details.append(f"❌ Seulement {pct_pos:.0f}% des saisons positives")
    if max_dd and max_dd > 40:
        details.append(f"❌ Drawdown max {max_dd:.0f}% — risque de ruine élevé")
    return details


def _build_bankroll_curve(dc_wf: list) -> list:
    """Construit la courbe de bankroll simulée depuis le walk-forward DC."""
    bankroll = 10000.0
    points = [{"season": "start", "bankroll": bankroll, "roi": 0.0}]

    for row in sorted(dc_wf, key=lambda r: r.get("test_season", "")):
        roi = row.get("roi", 0) / 100
        bets = row.get("bets", 0)
        if bets == 0:
            continue
        # Simulation flat stake 2% par pari
        pnl = bankroll * 0.02 * bets * roi
        bankroll = max(0, bankroll + pnl)
        points.append({
            "season":    row.get("test_season", "?"),
            "league":    row.get("league", "?"),
            "bankroll":  round(bankroll, 2),
            "roi":       round(roi * 100, 2),
            "n_bets":    bets,
        })

    return points


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/report")
def get_report():
    """Rapport de profitabilité complet."""
    if not _CMP_FILE.exists() and not _WF_FILE.exists():
        return {
            "available": False,
            "message": "Lancer POST /api/v1/model-comparison/run d'abord",
        }
    try:
        rep = _compute_profitability_report()
        return {"available": True, **rep}
    except Exception as e:
        logger.error(f"Erreur rapport: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/verdict")
def get_verdict():
    """Verdict simple de rentabilité."""
    if not _CMP_FILE.exists():
        return {"verdict": "INSUFFICIENT_DATA", "message": "Aucune donnée de comparaison disponible"}
    try:
        rep = _compute_profitability_report()
        return {
            "verdict":        rep["verdict"],
            "verdict_color":  rep["verdict_color"],
            "details":        rep["verdict_details"],
            "avg_roi_pct":    rep["global"].get("avg_roi_pct"),
            "total_bets":     rep["global"]["total_bets"],
            "no_money_mode":  rep["no_money_mode"],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


class ScoreBetRequest(BaseModel):
    prob_model:    float = Field(..., ge=0, le=1)
    implied_bm:    float = Field(..., ge=0, le=1)
    odds:          float = Field(..., gt=1.0)
    market:        str   = "home_win"
    elo_diff:      float = 0.0
    elo_prob_home: float = 0.45
    market_signal: float = Field(50.0, ge=0, le=100)
    season_phase:  float = Field(0.5, ge=0, le=1)
    rest_diff:     float = 0.0


@router.post("/score-bet")
def score_bet(req: ScoreBetRequest):
    """Score ML d'un pari potentiel (0-100)."""
    from app.services.models.ml_bet_scorer import get_scorer
    scorer = get_scorer()
    return scorer.score(
        prob_model=req.prob_model,
        implied_bm=req.implied_bm,
        odds=req.odds,
        market=req.market,
        elo_diff=req.elo_diff,
        elo_prob_home=req.elo_prob_home,
        market_signal=req.market_signal,
        season_phase=req.season_phase,
        rest_diff=req.rest_diff,
    )


def _train_ml_background():
    _train_state["running"] = True
    _train_state["error"]   = None
    try:
        import sys
        _backend = Path(__file__).resolve().parents[4]
        if str(_backend) not in sys.path:
            sys.path.insert(0, str(_backend))

        from data.real_data_loader import RealDataLoader
        from app.services.features.feature_engineering import FeatureEngineer
        from app.services.models.ml_bet_scorer import get_scorer

        data_dir = str(_backend.parent / "data" / "raw")
        df = RealDataLoader.load_multiple_csvs(data_dir)
        fe = FeatureEngineer()
        df = fe.build(df)

        scorer = get_scorer()
        metrics = scorer.train(df, force=True)
        _train_state["done"]    = True
        _train_state["metrics"] = metrics
        logger.info(f"[Train] ✓ ML Bet Scorer entraîné: {metrics}")
    except Exception as e:
        _train_state["error"] = str(e)
        logger.error(f"[Train] Erreur: {e}", exc_info=True)
    finally:
        _train_state["running"] = False


@router.post("/train-ml")
def train_ml():
    """Lance l'entraînement du ML Bet Scorer en background."""
    if _train_state["running"]:
        return {"message": "Entraînement déjà en cours"}

    t = threading.Thread(target=_train_ml_background, daemon=True, name="ml-trainer")
    t.start()
    return {"message": "Entraînement lancé en background (~30s)", "state": _train_state}


@router.get("/ml-status")
def ml_status():
    """Statut du ML Bet Scorer."""
    from app.services.models.ml_bet_scorer import get_scorer
    scorer = get_scorer()
    return {
        "train_state": _train_state,
        "scorer_info": scorer.training_info(),
    }


@router.post("/clv-auto")
def run_clv_auto():
    """Lance le CLV auto-closer pour tous les paris pending."""
    from app.services.engines.clv_auto_closer import get_auto_closer
    closer = get_auto_closer()
    updated = closer.run()
    return {
        "updated": len(updated),
        "records": updated,
        "stats":   closer.stats(),
    }


@router.get("/clv-history")
def clv_history():
    """Historique des CLV calculés automatiquement."""
    from app.services.engines.clv_auto_closer import get_auto_closer
    closer = get_auto_closer()
    return {
        "history": closer.get_history(),
        "stats":   closer.stats(),
    }
