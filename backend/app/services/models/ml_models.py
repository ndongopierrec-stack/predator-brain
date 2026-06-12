"""
ML Models — Predator Brain V2

LogReg · RandomForest · XGBoost · LightGBM
Walk-forward strict (pas de look-ahead)
Calibration : Brier, log loss, courbe de calibration
Markets : 1X2 (home_win), Over2.5, BTTS

Usage:
    from app.services.models.ml_models import MultiModelEngine
    engine = MultiModelEngine()
    results = engine.walk_forward(df, n_train_seasons=3)
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Any
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    brier_score_loss, log_loss, roc_auc_score,
    accuracy_score
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    logging.warning("XGBoost non disponible")

try:
    from lightgbm import LGBMClassifier
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    logging.warning("LightGBM non disponible")

logger = logging.getLogger("predator.ml")

MARKETS = ["home_win", "over_25", "btts"]

FEATURE_COLS = [
    "elo_home", "elo_away", "elo_home_home", "elo_away_away",
    "elo_diff", "elo_prob_home",
    "form_pts_h", "form_gf_h", "form_ga_h", "form_gd_h",
    "form_cs_h", "form_btts_h", "form_o25_h", "form_home_pts_h",
    "form_pts_a", "form_gf_a", "form_ga_a", "form_gd_a",
    "form_cs_a", "form_btts_a", "form_o25_a", "form_away_pts_a",
    "form_pts_diff", "form_gd_diff", "form_o25_avg", "form_btts_avg",
    "implied_h", "implied_d", "implied_a", "bm_margin",
    "ps_implied_h", "ps_implied_a", "implied_over25",
    "bm_vs_equal", "margin_ratio",
    "rest_days_h", "rest_days_a", "rest_diff",
    "season_phase", "is_weekday",
]


# ── Builders de modèles ────────────────────────────────────────────────────────

def _build_logreg() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            max_iter=1000, C=1.0, solver="lbfgs",
            random_state=42, class_weight="balanced"
        ))
    ])


def _build_rf() -> Pipeline:
    return Pipeline([
        ("clf", RandomForestClassifier(
            n_estimators=200, max_depth=6,
            min_samples_leaf=10, random_state=42,
            n_jobs=-1, class_weight="balanced"
        ))
    ])


def _build_xgb():
    if not HAS_XGB:
        return None
    return XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", random_state=42,
        verbosity=0, use_label_encoder=False,
        n_jobs=-1
    )


def _build_lgbm():
    if not HAS_LGB:
        return None
    return LGBMClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, verbose=-1, n_jobs=-1
    )


MODEL_BUILDERS = {
    "logreg": _build_logreg,
    "rf":     _build_rf,
    "xgb":    _build_xgb,
    "lgbm":   _build_lgbm,
}


# ── Métriques ─────────────────────────────────────────────────────────────────

def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray,
                    y_odds: Optional[np.ndarray] = None,
                    conf_threshold: float = 0.55,
                    edge_min: float = 0.04) -> Dict[str, Any]:
    """
    Calcule toutes les métriques de qualité + ROI simulé.
    y_odds : cotes bookmaker (1/implied) — pour simuler les paris
    """
    eps = 1e-9
    y_prob = np.clip(y_prob, eps, 1 - eps)

    metrics = {
        "brier":    round(float(brier_score_loss(y_true, y_prob)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        "n":        len(y_true),
    }

    try:
        metrics["auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)
    except Exception:
        metrics["auc"] = None

    # Calibration (10 bins)
    try:
        frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10)
        metrics["calibration_curve"] = {
            "mean_pred": mean_pred.tolist(),
            "frac_pos":  frac_pos.tolist(),
        }
        # Score de calibration : corrélation entre mean_pred et frac_pos
        if len(mean_pred) > 2:
            cal_corr = float(np.corrcoef(mean_pred, frac_pos)[0, 1])
            metrics["calibration_score"] = round(cal_corr, 4)
        else:
            metrics["calibration_score"] = None
    except Exception:
        metrics["calibration_curve"] = None
        metrics["calibration_score"] = None

    # ROI simulé (paris à conf > seuil et edge > min)
    if y_odds is not None:
        y_odds = np.array(y_odds)
        implied = 1.0 / np.maximum(y_odds, 1.01)
        edge = y_prob - implied
        mask = (y_prob >= conf_threshold) & (edge >= edge_min)

        if mask.sum() > 0:
            wins = y_true[mask].astype(float)
            odds_bet = y_odds[mask]
            pnl = np.where(wins, odds_bet - 1.0, -1.0)
            roi = float(np.mean(pnl)) * 100
            n_bets = int(mask.sum())
            metrics["roi_pct"]    = round(roi, 2)
            metrics["n_bets"]     = n_bets
            metrics["win_rate"]   = round(float(wins.mean()), 4)

            # Sharpe (approximation simple)
            if len(pnl) > 1:
                sharpe = float(np.mean(pnl) / (np.std(pnl) + 1e-9) * np.sqrt(n_bets))
                metrics["sharpe"] = round(sharpe, 3)
            else:
                metrics["sharpe"] = None

            # Max drawdown
            cumul = np.cumsum(pnl) / n_bets * 100
            peak  = np.maximum.accumulate(cumul)
            dd    = float(np.max(peak - cumul)) if len(cumul) > 0 else 0.0
            metrics["max_dd_pct"] = round(dd, 2)
        else:
            metrics["roi_pct"] = None
            metrics["n_bets"]  = 0
            metrics["sharpe"]  = None
            metrics["max_dd_pct"] = None
    return metrics


# ── Engine multi-modèles ───────────────────────────────────────────────────────

class MultiModelEngine:
    """
    Entraîne et évalue LogReg, RF, XGB, LGBM en walk-forward strict.

    df doit contenir :
      - "season"    (str : "2021-22")
      - "match_date"
      - FEATURE_COLS
      - "home_win", "over_25", "btts"
      - "implied_h", "implied_over25"  (pour ROI simulé)
      - "odds_home", "odds_over25"     (optionnel — cotes B365)
    """

    def __init__(self, min_train_seasons: int = 2,
                 conf_threshold: float = 0.56,
                 edge_min: float = 0.04):
        self.min_train_seasons = min_train_seasons
        self.conf_threshold    = conf_threshold
        self.edge_min          = edge_min

    def _get_features(self, df: pd.DataFrame) -> List[str]:
        return [c for c in FEATURE_COLS if c in df.columns]

    def _get_odds_col(self, df: pd.DataFrame, market: str) -> Optional[np.ndarray]:
        """Récupère les cotes bookmaker pour un marché."""
        mapping = {
            "home_win": ["odds_home", "implied_h"],
            "over_25":  ["odds_over25", "implied_over25"],
            "btts":     [],
        }
        for col in mapping.get(market, []):
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce").values
                if col.startswith("implied"):
                    # Convertir prob → cotes
                    with np.errstate(divide="ignore"):
                        odds = np.where(vals > 0, 1.0 / vals, 2.0)
                    return odds
                return vals
        return None

    def walk_forward(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Walk-forward strict par saison.
        Train sur saisons [0..N-1], test sur saison N.
        Répète pour N = min_train_seasons .. max_season.

        Retourne résultats agrégés par modèle et par marché.
        """
        df = df.sort_values("match_date").reset_index(drop=True)
        seasons = sorted(df["season"].unique().tolist())

        if len(seasons) < self.min_train_seasons + 1:
            logger.warning(f"[ML WF] Seulement {len(seasons)} saisons — "
                           f"besoin de {self.min_train_seasons + 1}+")
            return {"error": "not_enough_seasons", "seasons": seasons}

        feat_cols = self._get_features(df)
        if not feat_cols:
            return {"error": "no_features"}

        logger.info(f"[ML WF] {len(seasons)} saisons | {len(feat_cols)} features")

        all_results = []   # une entrée par (modèle, marché, saison test)

        for test_idx in range(self.min_train_seasons, len(seasons)):
            train_seasons = seasons[:test_idx]
            test_season   = seasons[test_idx]

            df_train = df[df["season"].isin(train_seasons)].copy()
            df_test  = df[df["season"] == test_season].copy()

            logger.info(f"[ML WF] Train {train_seasons[-3:]}..→ Test {test_season} "
                        f"({len(df_train)} train | {len(df_test)} test)")

            for market in MARKETS:
                if market not in df_train.columns:
                    continue

                X_tr = df_train[feat_cols].fillna(0).values
                y_tr = df_train[market].values
                X_te = df_test[feat_cols].fillna(0).values
                y_te = df_test[market].values

                # Ignorer si trop peu de positifs dans train
                if y_tr.sum() < 10 or (1 - y_tr).sum() < 10:
                    continue

                odds_te = self._get_odds_col(df_test, market)

                for model_name, builder in MODEL_BUILDERS.items():
                    model = builder()
                    if model is None:
                        continue
                    try:
                        # Calibration isotonique pour améliorer les probas
                        if model_name in ("xgb", "lgbm"):
                            cal = CalibratedClassifierCV(model, method="isotonic", cv=3)
                        else:
                            cal = model  # LogReg et RF déjà bien calibrés

                        cal.fit(X_tr, y_tr)
                        y_prob = cal.predict_proba(X_te)[:, 1]

                        mets = compute_metrics(
                            y_te, y_prob, odds_te,
                            conf_threshold=self.conf_threshold,
                            edge_min=self.edge_min,
                        )

                        all_results.append({
                            "model":       model_name,
                            "market":      market,
                            "test_season": test_season,
                            "n_train":     len(df_train),
                            "n_test":      len(df_test),
                            **mets,
                        })
                    except Exception as e:
                        logger.warning(f"[ML WF] {model_name}/{market}/{test_season}: {e}")

        return {
            "walk_forward_rows": all_results,
            "seasons":           seasons,
            "n_features":        len(feat_cols),
            "feature_names":     feat_cols,
        }

    def aggregate(self, wf_rows: List[dict]) -> Dict[str, Any]:
        """
        Agrège les résultats walk-forward par modèle et par marché.
        Calcule ROI moyen, Brier, Sharpe, n_seasons_positive.
        """
        if not wf_rows:
            return {}

        df = pd.DataFrame(wf_rows)

        summary = {}
        for (model, market), grp in df.groupby(["model", "market"]):
            key = f"{model}_{market}"
            rois = grp["roi_pct"].dropna().tolist()
            briers = grp["brier"].dropna().tolist()
            sharpes = grp["sharpe"].dropna().tolist()
            dds = grp["max_dd_pct"].dropna().tolist()
            n_bets = int(grp["n_bets"].sum())

            summary[key] = {
                "model":            model,
                "market":           market,
                "n_seasons":        len(grp),
                "n_seasons_pos":    int((grp["roi_pct"] > 0).sum()),
                "roi_mean":         round(float(np.mean(rois)), 2) if rois else None,
                "roi_std":          round(float(np.std(rois)), 2) if len(rois) > 1 else None,
                "brier_mean":       round(float(np.mean(briers)), 4) if briers else None,
                "sharpe_mean":      round(float(np.mean(sharpes)), 3) if sharpes else None,
                "max_dd_mean":      round(float(np.mean(dds)), 2) if dds else None,
                "n_bets_total":     n_bets,
                "log_loss_mean":    round(float(grp["log_loss"].mean()), 4),
                "auc_mean":         round(float(grp["auc"].dropna().mean()), 4) if not grp["auc"].dropna().empty else None,
            }

        return summary

    def train_final(self, df: pd.DataFrame, market: str = "home_win",
                    model_name: str = "lgbm") -> Optional[Any]:
        """
        Entraîne un modèle sur TOUT le dataset (pour prédictions futures).
        À utiliser après validation walk-forward.
        """
        feat_cols = self._get_features(df)
        X = df[feat_cols].fillna(0).values
        y = df[market].values

        if y.sum() < 10:
            return None

        builder = MODEL_BUILDERS.get(model_name)
        if builder is None or builder() is None:
            return None

        model = builder()
        cal = CalibratedClassifierCV(model, method="isotonic", cv=3) \
              if model_name in ("xgb", "lgbm") else model
        cal.fit(X, y)
        return cal


# ── Bookmaker baseline ─────────────────────────────────────────────────────────

def compute_bookmaker_baseline(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcule la performance du bookmaker comme baseline de comparaison.
    La cote implicite = probabilité prédite du bookmaker.
    Brier score < bookmaker = modèle meilleur que le marché.
    """
    results = {}

    market_map = {
        "home_win": ("implied_h",),
        "over_25":  ("implied_over25",),
        "btts":     (),
    }

    for market, implied_cols in market_map.items():
        if market not in df.columns:
            continue

        y_true = df[market].values
        for col in implied_cols:
            if col in df.columns:
                y_prob = pd.to_numeric(df[col], errors="coerce").fillna(0.45).values
                y_prob = np.clip(y_prob, 1e-9, 1 - 1e-9)
                results[market] = {
                    "brier":    round(float(brier_score_loss(y_true, y_prob)), 4),
                    "log_loss": round(float(log_loss(y_true, y_prob)), 4),
                    "n":        len(y_true),
                    "source":   col,
                }
                break

    return results
