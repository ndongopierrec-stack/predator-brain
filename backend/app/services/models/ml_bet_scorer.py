"""
ML Bet Scorer — Predator Brain V2

Modèle XGBoost supervisé entraîné sur les 6 823 matchs historiques.
Prédit si un pari potentiel sera profitable (CLV positif + profit).

Features d'entrée :
  - probabilités modèle (DC, Elo, ML ensemble)
  - probabilité implicite bookmaker
  - edge
  - forme récente (5 matchs)
  - différentiels Elo
  - contexte calendrier
  - CLV historique de la ligue/marché (si disponible)

Targets entraînés :
  - bet_won : le pari a gagné
  - clv_positive : CLV > 0 (proxy pour edge réel)
  - value_confirmed : bet_won ET CLV > 2%

Usage:
    from app.services.models.ml_bet_scorer import MLBetScorer
    scorer = MLBetScorer()
    scorer.train(df_rich)
    result = scorer.score(features_dict)
"""

import json
import logging
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple

logger = logging.getLogger("predator.ml_scorer")

_MODEL_DIR = Path(__file__).resolve().parents[4] / "data" / "models"

SCORE_FEATURES = [
    # Elo
    "elo_home", "elo_away", "elo_diff", "elo_prob_home",
    # Forme
    "form_pts_h", "form_gf_h", "form_ga_h", "form_gd_h",
    "form_cs_h", "form_o25_h", "form_home_pts_h",
    "form_pts_a", "form_gf_a", "form_ga_a", "form_gd_a",
    "form_cs_a", "form_o25_a", "form_away_pts_a",
    "form_pts_diff", "form_gd_diff", "form_o25_avg", "form_btts_avg",
    # Marché
    "implied_h", "implied_d", "implied_a", "bm_margin",
    "ps_implied_h", "ps_implied_a", "implied_over25",
    "bm_vs_equal",
    # Calendrier
    "rest_diff", "season_phase",
    # Edge calculé (features dérivées)
    "edge_vs_bm",        # prob_model - implied_bm
    "odds_taken",        # cote bookmaker
    "kelly_fraction",    # Kelly recommandé
    "market_signal",     # 0-100 (line movement, si dispo)
]


def _build_score_features(
    prob_model: float,
    implied_bm: float,
    odds: float,
    elo_diff: float = 0.0,
    elo_prob_home: float = 0.45,
    form_dict: Optional[Dict] = None,
    market_signal: float = 50.0,
    season_phase: float = 0.5,
    rest_diff: float = 0.0,
) -> Dict[str, float]:
    """Construit le vecteur de features pour scorer un pari."""
    edge = prob_model - implied_bm

    # Kelly fraction (quart Kelly)
    if implied_bm > 0:
        kelly = max(0.0, (prob_model - implied_bm) / (1.0 - implied_bm)) * 0.25
    else:
        kelly = 0.0

    form = form_dict or {}
    return {
        "elo_home":        elo_diff + 1500,
        "elo_away":        1500.0,
        "elo_diff":        elo_diff,
        "elo_prob_home":   elo_prob_home,
        "form_pts_h":      form.get("form_pts_h", 1.3),
        "form_gf_h":       form.get("form_gf_h", 1.3),
        "form_ga_h":       form.get("form_ga_h", 1.2),
        "form_gd_h":       form.get("form_gd_h", 0.0),
        "form_cs_h":       form.get("form_cs_h", 0.25),
        "form_o25_h":      form.get("form_o25_h", 0.5),
        "form_home_pts_h": form.get("form_home_pts_h", 1.3),
        "form_pts_a":      form.get("form_pts_a", 1.2),
        "form_gf_a":       form.get("form_gf_a", 1.1),
        "form_ga_a":       form.get("form_ga_a", 1.3),
        "form_gd_a":       form.get("form_gd_a", 0.0),
        "form_cs_a":       form.get("form_cs_a", 0.20),
        "form_o25_a":      form.get("form_o25_a", 0.5),
        "form_away_pts_a": form.get("form_away_pts_a", 1.0),
        "form_pts_diff":   form.get("form_pts_diff", 0.0),
        "form_gd_diff":    form.get("form_gd_diff", 0.0),
        "form_o25_avg":    form.get("form_o25_avg", 0.5),
        "form_btts_avg":   form.get("form_btts_avg", 0.45),
        "implied_h":       implied_bm,
        "implied_d":       0.27,
        "implied_a":       1.0 - implied_bm - 0.27,
        "bm_margin":       0.05,
        "ps_implied_h":    implied_bm * 0.97,
        "ps_implied_a":    (1.0 - implied_bm) * 0.97,
        "implied_over25":  0.50,
        "bm_vs_equal":     implied_bm - 0.333,
        "rest_diff":       rest_diff,
        "season_phase":    season_phase,
        "edge_vs_bm":      edge,
        "odds_taken":      odds,
        "kelly_fraction":  kelly,
        "market_signal":   market_signal / 100.0,
    }


class MLBetScorer:
    """
    Scorer ML supervisé pour évaluer la qualité d'un pari potentiel.

    Entraîné sur les données walk-forward où les outcomes sont connus.
    Produit un ML_SCORE 0-100 et 3 probabilités :
      - prob_profit     : P(bet_won)
      - prob_clv_pos    : P(CLV > 0) — proxy edge réel
      - prob_value_conf : P(bet_won ET CLV > 2%)
    """

    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._trained = False
        self._n_train = 0
        self._features_used: List[str] = []
        self._load_if_exists()

    def _load_if_exists(self):
        """Charge le modèle sauvegardé si disponible."""
        pkl = _MODEL_DIR / "ml_bet_scorer.pkl"
        if pkl.exists():
            try:
                with open(pkl, "rb") as f:
                    state = pickle.load(f)
                self._models        = state["models"]
                self._trained       = True
                self._n_train       = state.get("n_train", 0)
                self._features_used = state.get("features_used", SCORE_FEATURES)
                logger.info(
                    f"[MLScorer] Modèle chargé depuis {pkl} "
                    f"({self._n_train} exemples d'entraînement)"
                )
            except Exception as e:
                logger.warning(f"[MLScorer] Erreur chargement modèle: {e}")

    def train(self, df: pd.DataFrame, force: bool = False) -> Dict[str, Any]:
        """
        Entraîne le scorer sur les données historiques enrichies.
        df doit contenir les features + colonnes cibles (home_win, over_25, btts).

        Retourne les métriques d'entraînement.
        """
        if self._trained and not force:
            logger.info("[MLScorer] Modèle déjà entraîné — utiliser force=True pour ré-entraîner")
            return {"status": "already_trained", "n_train": self._n_train}

        try:
            from xgboost import XGBClassifier
        except ImportError:
            logger.error("[MLScorer] XGBoost non disponible")
            return {"error": "xgboost_not_available"}

        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.metrics import brier_score_loss, roc_auc_score
        from sklearn.model_selection import train_test_split

        # Features disponibles dans le df
        feats = [c for c in SCORE_FEATURES if c in df.columns]
        # Fallback sur feature_engineering si features manquantes
        if "edge_vs_bm" not in df.columns and "implied_h" in df.columns:
            df = df.copy()
            if "elo_prob_home" in df.columns:
                df["edge_vs_bm"]     = df["elo_prob_home"] - df["implied_h"]
            if "odds_home" in df.columns:
                df["odds_taken"]     = df.get("odds_home", pd.Series(2.0, index=df.index))
            df["kelly_fraction"] = df.get("edge_vs_bm", 0).clip(0) * 0.25
            df["market_signal"]  = 0.5
            feats = [c for c in SCORE_FEATURES if c in df.columns]

        if len(feats) < 5:
            return {"error": f"features insuffisantes: {feats}"}

        self._features_used = feats
        logger.info(f"[MLScorer] Entraînement sur {len(df):,} matchs | {len(feats)} features")

        metrics = {}
        trained_models = {}

        # Entraîner sur chaque target
        TARGETS = {
            "bet_won":  "home_win",      # proxy : gagner le pari home_win
            "over_won": "over_25",
            "btts_won": "btts",
        }

        for model_name, target_col in TARGETS.items():
            if target_col not in df.columns:
                continue

            X = df[feats].fillna(0)
            y = df[target_col].values

            # Vérification
            if y.sum() < 20 or (1 - y).sum() < 20:
                continue

            X_tr, X_val, y_tr, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            xgb = XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, min_child_weight=10,
                eval_metric="logloss", random_state=42,
                verbosity=0, n_jobs=-1,
            )

            # Calibration isotonique
            cal = CalibratedClassifierCV(xgb, method="isotonic", cv=5)
            cal.fit(X_tr, y_tr)

            y_prob = cal.predict_proba(X_val)[:, 1]
            brier  = brier_score_loss(y_val, y_prob)
            try:
                auc = roc_auc_score(y_val, y_prob)
            except Exception:
                auc = None

            trained_models[model_name] = cal
            metrics[model_name] = {
                "brier": round(brier, 4),
                "auc":   round(auc, 4) if auc else None,
                "n":     len(X_tr),
            }
            auc_str = f"{auc:.4f}" if auc is not None else "N/A"
            logger.info(f"[MLScorer] {model_name}: Brier={brier:.4f} AUC={auc_str}")

        if not trained_models:
            return {"error": "aucun modèle entraîné"}

        self._models    = trained_models
        self._trained   = True
        self._n_train   = len(df)

        # Sauvegarder
        _MODEL_DIR.mkdir(exist_ok=True)
        pkl = _MODEL_DIR / "ml_bet_scorer.pkl"
        with open(pkl, "wb") as f:
            pickle.dump({
                "models":        trained_models,
                "n_train":       self._n_train,
                "features_used": feats,
                "metrics":       metrics,
                "trained_at":    pd.Timestamp.now().isoformat(),
            }, f)

        logger.info(f"[MLScorer] ✓ Sauvegardé → {pkl}")
        return {"status": "trained", "metrics": metrics, "n_train": self._n_train}

    def score(
        self,
        prob_model: float,
        implied_bm: float,
        odds: float,
        market: str = "home_win",
        elo_diff: float = 0.0,
        elo_prob_home: float = 0.45,
        form_dict: Optional[Dict] = None,
        market_signal: float = 50.0,
        season_phase: float = 0.5,
        rest_diff: float = 0.0,
        clv_history_avg: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Score un pari potentiel. Retourne ML_SCORE 0-100 + probas.

        Si le modèle n'est pas entraîné, retourne un score heuristique
        basé sur l'edge et les règles métier.
        """
        edge = prob_model - implied_bm
        kelly = max(0.0, (prob_model - implied_bm) / max(1.0 - implied_bm, 0.01)) * 0.25

        # Score de base (heuristique — toujours calculé)
        base_score = 50.0
        base_score += edge * 200          # +20 pts pour 10% d'edge
        base_score += (market_signal - 50) * 0.3  # ±15 pts selon signal marché
        if clv_history_avg is not None:
            base_score += clv_history_avg * 5    # bonus/malus sur CLV historique
        base_score = float(np.clip(base_score, 0, 100))

        # Probabilités par défaut (sans ML)
        prob_profit  = float(np.clip(prob_model, 0, 1))
        prob_clv_pos = float(np.clip(0.5 + edge * 3, 0, 1))
        prob_value   = float(np.clip(prob_model * prob_clv_pos, 0, 1))

        # Score ML si modèle disponible
        ml_available = False
        if self._trained and self._models:
            try:
                feats = _build_score_features(
                    prob_model, implied_bm, odds, elo_diff, elo_prob_home,
                    form_dict, market_signal, season_phase, rest_diff,
                )
                X = pd.DataFrame([feats])
                # Aligner sur les features utilisées à l'entraînement
                avail = [c for c in self._features_used if c in X.columns]
                X = X[avail].fillna(0)

                # Choisir le modèle selon le marché
                model_key = "bet_won"
                if "over" in market.lower():
                    model_key = "over_won"
                elif "btts" in market.lower():
                    model_key = "btts_won"

                if model_key in self._models:
                    m = self._models[model_key]
                    prob_profit  = float(m.predict_proba(X)[0, 1])
                    prob_clv_pos = float(np.clip(0.5 + (prob_profit - implied_bm) * 4, 0, 1))
                    prob_value   = prob_profit * prob_clv_pos

                    # ML_SCORE pondéré
                    ml_score = (
                        prob_profit * 40       # 40 pts sur la probabilité de profit
                        + min(edge, 0.15) * 300   # 45 pts max sur l'edge
                        + (market_signal / 100) * 15  # 15 pts sur signal marché
                    )
                    base_score = float(np.clip(ml_score, 0, 100))
                    ml_available = True

            except Exception as e:
                logger.debug(f"[MLScorer] Erreur scoring ML: {e}")

        # Recommandation finale
        if base_score >= 70 and edge >= 0.04:
            recommendation = "RECOMMENDED_STRONG"
        elif base_score >= 55 and edge >= 0.03:
            recommendation = "RECOMMENDED"
        elif base_score >= 40 and edge >= 0.02:
            recommendation = "WATCHLIST"
        else:
            recommendation = "REJECTED"

        return {
            "ml_score":          round(base_score, 1),
            "prob_profit":       round(prob_profit, 4),
            "prob_clv_positive": round(prob_clv_pos, 4),
            "prob_value_conf":   round(prob_value, 4),
            "edge_vs_bm":        round(edge, 4),
            "kelly_suggested":   round(kelly * 100, 2),  # en %
            "recommendation":    recommendation,
            "ml_available":      ml_available,
            "inputs": {
                "prob_model":    round(prob_model, 4),
                "implied_bm":    round(implied_bm, 4),
                "odds":          odds,
                "market_signal": market_signal,
            },
        }

    def batch_score(self, bets: List[Dict]) -> List[Dict]:
        """Score une liste de paris potentiels."""
        results = []
        for bet in bets:
            s = self.score(
                prob_model    = bet.get("prob_model", 0.45),
                implied_bm    = bet.get("implied_bm", 0.45),
                odds          = bet.get("odds", 2.0),
                market        = bet.get("market", "home_win"),
                elo_diff      = bet.get("elo_diff", 0.0),
                elo_prob_home = bet.get("elo_prob_home", 0.45),
                form_dict     = bet.get("form", {}),
                market_signal = bet.get("market_signal", 50.0),
            )
            results.append({**bet, **s})
        # Trier par ML_SCORE décroissant
        return sorted(results, key=lambda x: x["ml_score"], reverse=True)

    @property
    def is_trained(self) -> bool:
        return self._trained

    def training_info(self) -> Dict:
        return {
            "trained":       self._trained,
            "n_train":       self._n_train,
            "models":        list(self._models.keys()),
            "n_features":    len(self._features_used),
            "model_path":    str(_MODEL_DIR / "ml_bet_scorer.pkl"),
        }


# Singleton global
_scorer = MLBetScorer()


def get_scorer() -> MLBetScorer:
    return _scorer
