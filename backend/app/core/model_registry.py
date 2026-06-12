"""
Model Registry — Singleton du modèle Dixon-Coles et de ses dépendances.
Chargé une fois au démarrage, utilisé par tous les endpoints.
"""

import os
import logging
import pandas as pd
from pathlib import Path
from typing import Optional
from threading import Lock

logger = logging.getLogger("predator.registry")


from app.services.models.dixon_coles import (
    DixonColesModel, EnsemblePredictor
)
from app.services.engines.value_engine import ValueBettingEngine
from app.services.engines.clv_engine import CLVEngine
from app.services.engines.bankroll_engine import BankrollEngine, StakeStrategy
from app.services.engines.ticket_generator import TicketGenerator


class ModelRegistry:
    """Singleton thread-safe des modèles Predator Brain."""

    _instance: Optional["ModelRegistry"] = None
    _lock = Lock()

    def __init__(self):
        self.dc: Optional[DixonColesModel] = None
        self.ensemble: Optional[EnsemblePredictor] = None
        self.value_engine = ValueBettingEngine(
            min_edge=0.03,
            min_confidence=0.50,
            kelly_fraction=0.25,
            max_stake_pct=0.05,
        )
        self.clv_engine = CLVEngine()
        self.bankroll_engine = BankrollEngine(
            initial_bankroll=10_000.0,
            strategy=StakeStrategy.KELLY_QUARTER,
        )
        self.ticket_generator = TicketGenerator(bankroll=10_000.0)
        self.is_trained = False
        self.n_matches = 0
        self.training_leagues: list = []
        self._df_cache: Optional[pd.DataFrame] = None

    @classmethod
    def get(cls) -> "ModelRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def train_from_csv(
        self,
        csv_dir: str = None,
        min_matches: int = 200,
    ) -> dict:
        """
        Entraîne le modèle Dixon-Coles sur les CSV historiques.
        Peut prendre 10-60 secondes selon la quantité de données.
        """
        if csv_dir is None:
            # Chercher les données dans plusieurs emplacements possibles
            backend_dir = Path(__file__).resolve().parents[2]  # backend/
            candidates = [
                backend_dir.parent / "data" / "raw",    # predator_brain/data/raw (local dev)
                backend_dir / "data" / "raw",            # backend/data/raw
                Path("/app/data/raw"),                   # Railway /app/
                Path("data/raw"),                        # CWD relatif
            ]
            csv_dir = ""
            for candidate in candidates:
                if candidate.exists() and any(candidate.glob("*.csv")):
                    csv_dir = str(candidate)
                    logger.info(f"[REGISTRY] Données trouvées: {csv_dir}")
                    break
            if not csv_dir:
                logger.warning("[REGISTRY] Aucun répertoire de données trouvé — mode fallback")

        try:
            if not csv_dir or not Path(csv_dir).exists():
                return {"success": False, "error": f"Dossier CSV inexistant: {csv_dir}"}

            # Charger les CSV football-data.co.uk
            from data.real_data_loader import RealDataLoader

            logger.info(f"[REGISTRY] Chargement des CSV depuis {csv_dir}...")
            df = RealDataLoader.load_multiple_csvs(csv_dir)

            if df.empty or len(df) < min_matches:
                logger.warning(f"[REGISTRY] Pas assez de données ({len(df)} matchs, min {min_matches})")
                return {"success": False, "error": "Pas assez de données"}

            # Enrichir avec forme et H2H
            loader = RealDataLoader()
            df = loader.enrich_with_form(df)
            df = loader.enrich_with_h2h(df)

            self._df_cache = df
            self.n_matches = len(df)

            if "league" in df.columns:
                self.training_leagues = df["league"].dropna().unique().tolist()

            # Entraîner Dixon-Coles
            logger.info(f"[REGISTRY] Entraînement Dixon-Coles sur {len(df)} matchs...")
            self.dc = DixonColesModel(max_goals=8)
            self.dc.fit(df, time_decay=True)

            # Entraîner l'ensemble
            self.ensemble = EnsemblePredictor(dc_weight=0.55, form_weight=0.30, ml_weight=0.15)
            self.ensemble.dc = self.dc
            self.ensemble.dc.is_fitted = True

            self.is_trained = True
            logger.info(f"[REGISTRY] ✓ Modèle prêt | {len(self.dc.teams_)} équipes | "
                        f"{len(self.training_leagues)} ligues")

            return {
                "success": True,
                "n_matches": self.n_matches,
                "n_teams": len(self.dc.teams_),
                "leagues": self.training_leagues[:10],
            }

        except Exception as e:
            logger.error(f"[REGISTRY] Erreur entraînement: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def predict(
        self, home_team: str, away_team: str,
        form_home: float = 0.5, form_away: float = 0.5,
    ) -> dict:
        """Prédiction rapide. Fallback si modèle non entraîné."""
        if not self.is_trained or self.dc is None:
            # Retourner des probabilités par défaut
            return {
                "prob_home": 0.46, "prob_draw": 0.26, "prob_away": 0.28,
                "prob_over_25": 0.55, "prob_btts_yes": 0.52,
                "dc_known": False, "is_fallback": True,
            }

        pred = self.dc.predict(home_team, away_team)
        return {
            "prob_home":     pred.prob_home,
            "prob_draw":     pred.prob_draw,
            "prob_away":     pred.prob_away,
            "prob_over_15":  pred.prob_over_15,
            "prob_over_25":  pred.prob_over_25,
            "prob_over_35":  pred.prob_over_35,
            "prob_under_25": pred.prob_under_25,
            "prob_btts_yes": pred.prob_btts_yes,
            "prob_btts_no":  pred.prob_btts_no,
            "prob_1X":       pred.prob_home + pred.prob_draw,
            "prob_X2":       pred.prob_draw + pred.prob_away,
            "prob_12":       pred.prob_home + pred.prob_away,
            "lambda_home":   pred.lambda_home,
            "lambda_away":   pred.lambda_away,
            "score_matrix":  pred.score_matrix,
            "most_likely_score": pred.most_likely_score,
            "dc_known":      pred.dc_known,
            "is_fallback":   False,
        }


# ─── Singleton global ─────────────────────────────────────────────────────────
registry = ModelRegistry.get()
