"""
Model Comparison API — Predator Brain V2

GET  /api/v1/model-comparison/results     Table de comparaison complète
GET  /api/v1/model-comparison/report      Rapport honnête V2
GET  /api/v1/model-comparison/run         Lance le calcul en background
GET  /api/v1/model-comparison/status      Statut du calcul
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

logger = logging.getLogger("predator.api.comparison")
router = APIRouter(prefix="/model-comparison", tags=["Model Comparison V2"])

_DATA_DIR = Path(__file__).resolve().parents[5] / "data"
_CMP_FILE = _DATA_DIR / "model_comparison_results.json"

_run_state = {
    "running": False,
    "done":    False,
    "error":   None,
    "started": None,
    "finished": None,
}


def _load_results() -> dict:
    if not _CMP_FILE.exists():
        return {}
    with open(_CMP_FILE, encoding="utf-8") as f:
        return json.load(f)


def _run_comparison_background():
    """Lance le script model_comparison.py dans un thread."""
    import sys
    from pathlib import Path
    _backend = Path(__file__).resolve().parents[4]   # → backend/
    if str(_backend) not in sys.path:
        sys.path.insert(0, str(_backend))

    from datetime import datetime
    _run_state["running"] = True
    _run_state["error"]   = None
    _run_state["started"] = datetime.now().isoformat()

    try:
        from scripts.model_comparison import main as run_main
        run_main()
        _run_state["done"] = True
        _run_state["finished"] = datetime.now().isoformat()
        logger.info("[Comparison] ✓ Terminé")
    except Exception as e:
        _run_state["error"] = str(e)
        logger.error(f"[Comparison] Erreur: {e}", exc_info=True)
    finally:
        _run_state["running"] = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    """Statut du calcul model-comparison."""
    data = _load_results()
    return {
        **_run_state,
        "results_available": bool(data),
        "generated_at":      data.get("generated_at"),
        "no_money_mode":     data.get("no_money_mode", True),
        "global_status":     data.get("global_status", "INCONNU"),
    }


@router.post("/run")
def trigger_run():
    """Lance le calcul de comparaison en arrière-plan (~5-15 min)."""
    if _run_state["running"]:
        return {
            "message": "Calcul déjà en cours",
            "started": _run_state["started"],
        }

    t = threading.Thread(target=_run_comparison_background, daemon=True, name="comparison")
    t.start()

    return {
        "message": "Calcul lancé en arrière-plan. Vérifier /status dans 5-15 min.",
        "note":    "Le résultat sera disponible sur /results une fois terminé.",
    }


@router.get("/results")
def get_results(
    league: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    model:  Optional[str] = Query(None),
):
    """
    Table de comparaison complète.
    Filtrable par ligue, marché, modèle.
    """
    data = _load_results()
    if not data:
        return {
            "available": False,
            "message": "Aucun résultat disponible. Lancer POST /run pour démarrer le calcul.",
            "table": [],
        }

    table = data.get("comparison_table", [])

    if league:
        table = [r for r in table if r.get("league", "").lower() == league.lower()]
    if market:
        table = [r for r in table if r.get("market", "").lower() == market.lower()]
    if model:
        table = [r for r in table if r.get("model", "").lower() == model.lower()]

    # Trier par ROI décroissant
    table_sorted = sorted(
        table,
        key=lambda r: (r.get("roi_mean") or -999),
        reverse=True,
    )

    return {
        "available":     True,
        "generated_at":  data.get("generated_at"),
        "no_money_mode": data.get("no_money_mode", True),
        "global_status": data.get("global_status", "INCONNU"),
        "count":         len(table_sorted),
        "table":         table_sorted,
    }


@router.get("/report")
def get_report():
    """Rapport honnête V2 : verdict, meilleur modèle, meilleur marché..."""
    data = _load_results()
    if not data:
        return {
            "available": False,
            "message":   "Lancer POST /run pour générer le rapport.",
            "no_money_mode": True,
        }

    report = data.get("honest_report", {})
    return {
        "available":     True,
        "generated_at":  data.get("generated_at"),
        "no_money_mode": data.get("no_money_mode", True),
        "global_status": data.get("global_status", "INCONNU"),
        **report,
    }


@router.get("/wf-rows")
def get_wf_rows(
    league: Optional[str] = Query(None),
    model:  Optional[str] = Query(None),
    market: Optional[str] = Query(None),
):
    """Données brutes walk-forward par saison pour les graphiques."""
    data = _load_results()
    rows = data.get("ml_wf_rows", [])

    if league:
        rows = [r for r in rows if r.get("league", "").lower() == league.lower()]
    if model:
        rows = [r for r in rows if r.get("model", "").lower() == model.lower()]
    if market:
        rows = [r for r in rows if r.get("market", "").lower() == market.lower()]

    return {"count": len(rows), "rows": rows}


@router.get("/bookmaker-baselines")
def get_bookmaker_baselines(league: Optional[str] = Query(None)):
    """Scores Brier du bookmaker par ligue (référence de comparaison)."""
    data = _load_results()
    baselines = data.get("bookmaker_baselines", {})

    if league:
        baselines = {k: v for k, v in baselines.items() if k.lower() == league.lower()}

    return {
        "available":  bool(baselines),
        "baselines":  baselines,
        "note": "Brier score inférieur = meilleur. Battre le bookmaker = edge réel.",
    }
