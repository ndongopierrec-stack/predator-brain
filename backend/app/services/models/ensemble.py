"""
Ensemble Model — Predator Brain V2

Combine Dixon-Coles + Elo + ML pour produire une probabilité finale.
Pondération dynamique par ligue et par marché basée sur les performances
walk-forward historiques.

Usage:
    from app.services.models.ensemble import EnsemblePredictor
    ens = EnsemblePredictor()
    prob = ens.predict(home_dc=0.50, home_ml=0.53, home_bm=0.46, market="home_win", league="F1")
"""

import numpy as np
import logging
from typing import Dict, Optional, Tuple, Any, List

logger = logging.getLogger("predator.ensemble")


# ── Poids par défaut (avant calibration walk-forward) ─────────────────────────
# Basés sur la littérature :
# - Bookmaker : référence marché
# - DC : meilleur modèle statistique classique
# - ML : meilleur si bien calibré
# - Elo : signal stable à long terme

DEFAULT_WEIGHTS = {
    "home_win": {
        "dc":   0.30,
        "elo":  0.15,
        "ml":   0.25,
        "bm":   0.30,  # implied probabilities
    },
    "over_25": {
        "dc":   0.20,
        "elo":  0.05,
        "ml":   0.40,
        "bm":   0.35,
    },
    "btts": {
        "dc":   0.15,
        "elo":  0.05,
        "ml":   0.45,
        "bm":   0.35,
    },
}

VALID_STATUS_HIERARCHY = ["VALIDE", "PROMETTEUR", "OK", "A_CONFIRMER", "RISQUE_ELEVE", "A_EVITER"]


def _softmax_weights(rois: Dict[str, float]) -> Dict[str, float]:
    """
    Calcule des poids softmax à partir des ROI walk-forward.
    Les modèles avec ROI négatif reçoivent un poids faible mais non nul.
    """
    keys = list(rois.keys())
    vals = np.array([rois[k] for k in keys], dtype=float)
    # Décaler pour éviter les exponentielles extrêmes
    vals = vals - vals.mean()
    exp_vals = np.exp(vals * 0.5)  # facteur 0.5 = softmax tempéré
    total = exp_vals.sum()
    if total == 0:
        w = np.ones(len(keys)) / len(keys)
    else:
        w = exp_vals / total
    return {k: float(v) for k, v in zip(keys, w)}


class EnsemblePredictor:
    """
    Combine les signaux DC, Elo, ML et Bookmaker en une probabilité unifiée.

    Après walk-forward, `calibrate_weights()` met à jour les poids dynamiquement.
    """

    def __init__(self):
        self._weights: Dict[str, Dict[str, Dict[str, float]]] = {}
        # Structure : market → league → {dc, elo, ml, bm}

    def get_weights(self, market: str, league: Optional[str] = None) -> Dict[str, float]:
        """Retourne les poids pour un marché/ligue, avec fallback sur les défauts."""
        # Poids spécifiques à la ligue
        if league and market in self._weights:
            if league in self._weights[market]:
                return self._weights[market][league]

        # Poids globaux calibrés
        if market in self._weights and "__global__" in self._weights[market]:
            return self._weights[market]["__global__"]

        # Poids par défaut
        return DEFAULT_WEIGHTS.get(market, DEFAULT_WEIGHTS["home_win"])

    def calibrate_weights(self, wf_summary: Dict[str, Any]) -> None:
        """
        Met à jour les poids à partir des résultats walk-forward.

        wf_summary : dict issu de MultiModelEngine.aggregate()
        Format : { "lgbm_home_win": {roi_mean: ..., market: ..., model: ...}, ... }
        """
        # Regrouper par marché
        market_rois: Dict[str, Dict[str, float]] = {}

        for key, stats in wf_summary.items():
            market = stats.get("market", "home_win")
            model  = stats.get("model", "ml")
            roi    = stats.get("roi_mean")
            if roi is None:
                roi = -1.0

            if market not in market_rois:
                market_rois[market] = {}

            # Choisir le meilleur modèle ML (prend le meilleur ROI parmi logreg/rf/xgb/lgbm)
            ml_key = "ml"
            if market not in market_rois or ml_key not in market_rois[market]:
                market_rois[market][ml_key] = roi
            else:
                market_rois[market][ml_key] = max(market_rois[market][ml_key], roi)

        for market, rois in market_rois.items():
            # Ajouter DC et Elo avec leur ROI estimé (pas encore walkforwardé ici)
            base = DEFAULT_WEIGHTS.get(market, DEFAULT_WEIGHTS["home_win"])
            full_rois = {
                "dc":  0.0,   # référence neutre
                "elo": 1.0,   # signal stable
                "ml":  rois.get("ml", -3.0),
                "bm":  -0.5,  # bookmaker légèrement perdant après marge
            }
            weights = _softmax_weights(full_rois)

            # Normaliser
            total = sum(weights.values())
            if total > 0:
                weights = {k: v/total for k, v in weights.items()}

            if market not in self._weights:
                self._weights[market] = {}
            self._weights[market]["__global__"] = weights
            logger.info(f"[Ensemble] Poids {market}: {weights}")

    def predict(
        self,
        dc_probs: Optional[Dict[str, float]] = None,
        elo_prob_home: Optional[float] = None,
        ml_probs: Optional[Dict[str, float]] = None,
        bm_probs: Optional[Dict[str, float]] = None,
        market: str = "home_win",
        league: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calcule la probabilité ensemble pour un match.

        dc_probs   : {"home": 0.50, "draw": 0.27, "away": 0.23}
        elo_prob_home : 0.55 (prob home Elo)
        ml_probs   : {"home_win": 0.53, "over_25": 0.48, "btts": 0.42}
        bm_probs   : {"home_win": 0.46, "over_25": 0.52}
        """
        weights = self.get_weights(market, league)

        signals: Dict[str, float] = {}

        # Signal DC
        if dc_probs:
            if market == "home_win":
                signals["dc"] = dc_probs.get("home", 0.45)
            elif market == "over_25":
                signals["dc"] = dc_probs.get("over_25", 0.45)
            elif market == "btts":
                signals["dc"] = dc_probs.get("btts", 0.45)

        # Signal Elo
        if elo_prob_home is not None:
            if market == "home_win":
                signals["elo"] = float(elo_prob_home)
            else:
                signals["elo"] = 0.45  # Elo peu informatif pour O/U et BTTS

        # Signal ML
        if ml_probs:
            if market == "home_win":
                signals["ml"] = ml_probs.get("home_win", ml_probs.get("home", 0.45))
            elif market == "over_25":
                signals["ml"] = ml_probs.get("over_25", 0.45)
            elif market == "btts":
                signals["ml"] = ml_probs.get("btts", 0.45)

        # Signal Bookmaker (implied)
        if bm_probs:
            if market == "home_win":
                signals["bm"] = bm_probs.get("home_win", bm_probs.get("home", 0.45))
            elif market == "over_25":
                signals["bm"] = bm_probs.get("over_25", 0.45)
            elif market == "btts":
                signals["bm"] = 0.45

        # Combinaison pondérée
        total_w = 0.0
        prob = 0.0
        for source, p in signals.items():
            w = weights.get(source, 0.0)
            prob += w * p
            total_w += w

        if total_w > 0:
            prob /= total_w
        else:
            prob = 0.45  # fallback neutre

        prob = float(np.clip(prob, 0.01, 0.99))

        # Fair odds et edge
        fair_odds = round(1.0 / prob, 3) if prob > 0 else 99.0

        # CLV proxy
        bm_prob = signals.get("bm")
        bm_odds = round(1.0 / bm_prob, 3) if bm_prob and bm_prob > 0 else None
        edge_vs_bm = round(prob - bm_prob, 4) if bm_prob else None
        clv = round((fair_odds / bm_odds - 1) * 100, 2) if bm_odds else None

        return {
            "prob":       round(prob, 4),
            "fair_odds":  fair_odds,
            "signals":    signals,
            "weights":    weights,
            "edge_vs_bm": edge_vs_bm,
            "clv_pct":    clv,
            "market":     market,
            "n_signals":  len(signals),
        }

    def predict_all_markets(
        self,
        dc_probs: Optional[Dict] = None,
        elo_prob_home: Optional[float] = None,
        ml_probs: Optional[Dict] = None,
        bm_probs: Optional[Dict] = None,
        league: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calcule l'ensemble pour tous les marchés d'un coup."""
        results = {}
        for market in ["home_win", "over_25", "btts"]:
            results[market] = self.predict(
                dc_probs=dc_probs,
                elo_prob_home=elo_prob_home,
                ml_probs=ml_probs,
                bm_probs=bm_probs,
                market=market,
                league=league,
            )
        return results


# ── Instance globale ──────────────────────────────────────────────────────────

_ensemble = EnsemblePredictor()


def get_ensemble() -> EnsemblePredictor:
    return _ensemble
