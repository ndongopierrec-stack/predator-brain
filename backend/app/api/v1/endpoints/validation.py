"""
API Validation — Predator Brain
Expose les résultats walk-forward, statut de validation et règles de prudence.

Endpoints:
  GET  /api/v1/validation/status        Statut global de validation du modèle
  GET  /api/v1/validation/walk-forward  Résultats walk-forward par ligue/saison
  GET  /api/v1/validation/sensitivity   Tableau de sensibilité conf × edge
  POST /api/v1/validation/prudence      Calcule la règle de prudence pour une stratégie
"""

import json
import logging
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("predator.api.validation")
router = APIRouter(prefix="/validation", tags=["Validation"])

# Chemin vers les résultats walk-forward générés par le script
_DATA_DIR = Path(__file__).resolve().parents[4] / "data"
_WF_FILE  = _DATA_DIR / "walk_forward_results.json"


def _load_wf_results() -> dict:
    if not _WF_FILE.exists():
        return {}
    with open(_WF_FILE, encoding="utf-8") as f:
        return json.load(f)


def _prudence_verdict(bets: int, roi: float, max_dd: float,
                      n_pos: int, n_total: int) -> dict:
    """Règles de prudence standardisées."""
    status = "OK"
    issues = []
    real_money = False

    if bets < 200:
        status = "A_CONFIRMER"
        issues.append(f"Seulement {bets} paris (objectif: 500+)")
    elif bets < 500:
        status = "A_CONFIRMER"
        issues.append(f"{bets} paris — significativité limitée (objectif: 500+)")

    if roi < 0:
        status = "A_EVITER"
        issues.append(f"ROI négatif ({roi:+.1f}%)")

    if max_dd > 50:
        if status in ("OK", "A_CONFIRMER"):
            status = "RISQUE_ELEVE"
        issues.append(f"Drawdown max trop élevé ({max_dd:.0f}%) — risque de ruine")

    if n_total >= 3 and n_pos < n_total // 2:
        if status == "OK": status = "A_CONFIRMER"
        issues.append(f"Moins de 50% des saisons profitables ({n_pos}/{n_total})")

    if n_pos >= 3 and roi > 0 and bets >= 500 and max_dd < 40:
        status = "PROMETTEUR"

    if bets >= 1000 and n_pos >= 4 and max_dd < 40 and roi > 3:
        status = "VALIDE"
        real_money = True

    # Mise max recommandée
    if bets < 500:
        max_stake = 0.5
    elif bets < 1000:
        max_stake = 1.0
    elif status == "VALIDE":
        max_stake = 2.0
    else:
        max_stake = 0.0  # paper trading uniquement si A_EVITER

    return {
        "status":       status,
        "issues":       issues,
        "max_stake_pct": max_stake,
        "real_money":   real_money,
        "paper_only":   not real_money,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
def get_validation_status():
    """
    Statut global de validation du modèle Predator Brain.
    Lit les résultats walk-forward et calcule le statut pour chaque ligue.
    """
    from app.core.model_registry import registry

    data = _load_wf_results()
    wf   = data.get("walk_forward", [])

    league_stats = {}
    for row in wf:
        lg = row.get("league", "?")
        if lg not in league_stats:
            league_stats[lg] = {"rois": [], "bets": 0, "dds": [], "n_pos": 0, "n_seasons": 0}
        league_stats[lg]["rois"].append(row["roi"])
        league_stats[lg]["bets"] += row["bets"]
        league_stats[lg]["dds"].append(row["max_dd"])
        league_stats[lg]["n_seasons"] += 1
        if row["roi"] > 0:
            league_stats[lg]["n_pos"] += 1

    import numpy as np
    leagues = {}
    for lg, s in league_stats.items():
        avg_roi = float(np.mean(s["rois"])) if s["rois"] else 0.0
        avg_dd  = float(np.mean(s["dds"]))  if s["dds"]  else 100.0
        verdict = _prudence_verdict(s["bets"], avg_roi, avg_dd, s["n_pos"], s["n_seasons"])
        leagues[lg] = {
            "avg_roi":    round(avg_roi, 2),
            "avg_dd":     round(avg_dd, 1),
            "n_seasons":  s["n_seasons"],
            "n_positive": s["n_pos"],
            "total_bets": s["bets"],
            **verdict,
        }

    # Statut global = le pire statut de toutes les ligues
    all_statuses = [v["status"] for v in leagues.values()]
    priority = ["VALIDE", "PROMETTEUR", "OK", "RISQUE_ELEVE", "A_CONFIRMER", "A_EVITER"]
    global_status = "INCONNU"
    for s in priority[::-1]:
        if s in all_statuses:
            global_status = s
            break

    return {
        "global_status":    global_status,
        "no_money_mode":    global_status not in ("VALIDE",),
        "model_ready":      registry.is_trained,
        "n_matches_trained": registry.n_matches,
        "walk_forward_available": bool(wf),
        "generated_at":     data.get("generated_at", "N/A"),
        "leagues":          leagues,
        "global_rules": {
            "max_stake_global": 0.5,  # jamais plus que 0.5% tant que status != VALIDE
            "paper_only":       global_status not in ("VALIDE",),
            "message": (
                "MODELE EN VALIDATION — paper trading uniquement. "
                "Aucune stratégie n'a encore atteint le statut VALIDE "
                "(500+ paris, 4+ saisons positives, drawdown <40%)."
            ) if global_status not in ("VALIDE",) else "Modèle validé — trading réel autorisé avec précautions."
        },
    }


@router.get("/walk-forward")
def get_walk_forward(league: Optional[str] = None, config: Optional[str] = None):
    """Résultats walk-forward saison par saison."""
    data = _load_wf_results()
    rows = data.get("walk_forward", [])
    if league:
        rows = [r for r in rows if r.get("league", "").lower() == league.lower()]
    if config:
        rows = [r for r in rows if r.get("config", "") == config]
    return {
        "count": len(rows),
        "results": rows,
        "generated_at": data.get("generated_at", "N/A"),
    }


@router.get("/sensitivity")
def get_sensitivity(league: Optional[str] = None):
    """Tableau de sensibilité conf × edge."""
    data = _load_wf_results()
    rows = data.get("sensitivity", [])
    if league:
        rows = [r for r in rows if r.get("league", "").lower() == league.lower()]
    # Trier par ROI décroissant
    rows = sorted(rows, key=lambda r: r.get("roi", -999), reverse=True)
    return {
        "count": len(rows),
        "best_roi": rows[0] if rows else None,
        "table": rows,
    }


class PrudenceRequest(BaseModel):
    bets:          int   = Field(..., ge=0, description="Nombre total de paris")
    roi_pct:       float = Field(..., description="ROI en % (peut être négatif)")
    max_drawdown:  float = Field(..., ge=0, le=100, description="Drawdown max en %")
    n_seasons_pos: int   = Field(..., ge=0, description="Nombre de saisons positives")
    n_seasons_tot: int   = Field(..., ge=1, description="Nombre de saisons testées")
    bankroll:      float = Field(10_000.0, gt=0, description="Capital disponible en EUR")


@router.post("/prudence")
def compute_prudence(req: PrudenceRequest):
    """Calcule la règle de prudence pour une stratégie donnée."""
    verdict = _prudence_verdict(
        req.bets, req.roi_pct, req.max_drawdown,
        req.n_seasons_pos, req.n_seasons_tot,
    )
    max_eur = (verdict["max_stake_pct"] / 100) * req.bankroll
    return {
        **verdict,
        "max_stake_eur": round(max_eur, 2),
        "bankroll":      req.bankroll,
        "interpretation": _interpret(verdict["status"], verdict["issues"]),
    }


def _interpret(status: str, issues: list) -> str:
    msgs = {
        "VALIDE":        "Stratégie validée statistiquement. Trading réel autorisé avec gestion stricte.",
        "PROMETTEUR":    "Signal prometteur. Continuer en paper trading avant d'engager du capital réel.",
        "OK":            "Résultats neutres. Pas d'edge statistiquement prouvé.",
        "A_CONFIRMER":   "Données insuffisantes pour conclure. Paper trading obligatoire.",
        "RISQUE_ELEVE":  "ROI positif mais drawdown dangereux. Ne pas risquer de capital réel.",
        "A_EVITER":      "Stratégie non profitable sur les données historiques. Ne pas jouer.",
        "INCONNU":       "Aucune donnée de validation disponible. Paper trading uniquement.",
    }
    base = msgs.get(status, "Statut inconnu.")
    if issues:
        return base + " Problèmes : " + " | ".join(issues)
    return base
