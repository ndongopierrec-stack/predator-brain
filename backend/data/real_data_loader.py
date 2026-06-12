"""
RealDataLoader — Chargement et normalisation des CSV football-data.co.uk

Format source (football-data.co.uk) :
    Div, Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR,
    B365H, B365D, B365A,  (cotes Bet365 ouverture)
    PSH, PSD, PSA,        (cotes Pinnacle — les plus sharpes)
    Avg>2.5, Avg<2.5,     (over/under)

Colonnes de sortie standardisées :
    team_home, team_away, score_home, score_away, match_date,
    league, season,
    odds_home, odds_draw, odds_away,      (Bet365)
    odds_home_ps, odds_draw_ps, odds_away_ps,  (Pinnacle)
    odds_over25, odds_under25,
    ftr (H/D/A)
"""

import os
import logging
import warnings
from pathlib import Path
from typing import Optional
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger("predator.data_loader")

# ── Mapping colonnes football-data.co.uk → standard Predator Brain ───────────
COLUMN_MAP = {
    "HomeTeam":  "team_home",
    "AwayTeam":  "team_away",
    "FTHG":      "score_home",
    "FTAG":      "score_away",
    "Date":      "match_date",
    "Div":       "league_raw",
    "FTR":       "ftr",
    # Cotes Bet365 (ouverture)
    "B365H":     "odds_home",
    "B365D":     "odds_draw",
    "B365A":     "odds_away",
    # Cotes Pinnacle (closing — les plus efficientes)
    "PSH":       "odds_home_ps",
    "PSD":       "odds_draw_ps",
    "PSA":       "odds_away_ps",
    # Over/Under (Bet365)
    "B365>2.5":  "odds_over25",
    "B365<2.5":  "odds_under25",
    # Closing Over/Under Bet365
    "B365C>2.5": "odds_over25_c",
    "B365C<2.5": "odds_under25_c",
    # Stats de match
    "HS":  "shots_home",
    "AS":  "shots_away",
    "HST": "shots_target_home",
    "AST": "shots_target_away",
}

# ── Code ligue → nom lisible ──────────────────────────────────────────────────
LEAGUE_NAMES = {
    "E0": "Premier League",
    "E1": "Championship",
    "F1": "Ligue 1",
    "D1": "Bundesliga",
    "D2": "2. Bundesliga",
    "SP1": "La Liga",
    "SP2": "La Liga 2",
    "I1": "Serie A",
    "I2": "Serie B",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "B1": "Jupiler Pro League",
    "SC0": "Scottish Premiership",
    "G1": "Super League Greece",
    "T1": "Super Lig Turkey",
}


class RealDataLoader:
    """Charge et normalise les données historiques football-data.co.uk."""

    @staticmethod
    def load_csv(filepath: str, season: str = None) -> pd.DataFrame:
        """
        Charge un fichier CSV football-data.co.uk et retourne un DataFrame normalisé.

        Args:
            filepath: Chemin vers le CSV
            season:   Identifiant saison ex. "2324" (auto-détecté depuis le nom de fichier)

        Returns:
            DataFrame avec colonnes standardisées
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"[LOADER] Fichier introuvable: {filepath}")
            return pd.DataFrame()

        try:
            # Essayer différents encodages (football-data.co.uk utilise parfois latin-1)
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(filepath, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                logger.error(f"[LOADER] Impossible de lire {filepath}")
                return pd.DataFrame()

            # Supprimer les lignes vides (souvent à la fin des fichiers football-data)
            df = df.dropna(how="all")

            # Renommer les colonnes connues
            rename_map = {col: COLUMN_MAP[col] for col in df.columns if col in COLUMN_MAP}
            df = df.rename(columns=rename_map)

            # Colonnes obligatoires
            required = ["team_home", "team_away", "score_home", "score_away"]
            if not all(c in df.columns for c in required):
                logger.warning(f"[LOADER] Colonnes manquantes dans {path.name}: {[c for c in required if c not in df.columns]}")
                return pd.DataFrame()

            # Nettoyer les scores
            df["score_home"] = pd.to_numeric(df["score_home"], errors="coerce")
            df["score_away"] = pd.to_numeric(df["score_away"], errors="coerce")
            df = df.dropna(subset=["score_home", "score_away"])
            df = df[(df["score_home"] >= 0) & (df["score_away"] >= 0)]
            df["score_home"] = df["score_home"].astype(int)
            df["score_away"] = df["score_away"].astype(int)

            # Date
            if "match_date" in df.columns:
                df["match_date"] = pd.to_datetime(df["match_date"], format="%d/%m/%Y", errors="coerce")
                # Essayer d'autres formats si nécessaire
                mask = df["match_date"].isna()
                if mask.any():
                    df.loc[mask, "match_date"] = pd.to_datetime(
                        df.loc[mask, "match_date_orig"] if "match_date_orig" in df.columns else df.loc[mask, "match_date"],
                        format="%d/%m/%y", errors="coerce"
                    )
                df = df.dropna(subset=["match_date"])

            # Saison
            if season is None:
                # Auto-détecter depuis le nom de fichier ex. "E0_2324.csv" → "2023-24"
                stem = path.stem  # "E0_2324"
                parts = stem.split("_")
                season = parts[1] if len(parts) > 1 else "unknown"

            df["season"] = season

            # Code ligue depuis le nom de fichier (ex. "E0" dans "E0_2324.csv")
            if "league_raw" not in df.columns:
                stem = path.stem
                league_code = stem.split("_")[0] if "_" in stem else stem
                df["league_raw"] = league_code

            # Nom lisible de la ligue
            df["league"] = df["league_raw"].map(LEAGUE_NAMES).fillna(df["league_raw"])

            # Nettoyer les noms d'équipes
            df["team_home"] = df["team_home"].str.strip()
            df["team_away"] = df["team_away"].str.strip()

            # Cotes numériques
            for col in ["odds_home", "odds_draw", "odds_away", "odds_home_ps", "odds_draw_ps",
                        "odds_away_ps", "odds_over25", "odds_under25"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Total buts
            df["total_goals"] = df["score_home"] + df["score_away"]
            df["over_25"] = (df["total_goals"] > 2.5).astype(int)
            df["btts"]    = ((df["score_home"] > 0) & (df["score_away"] > 0)).astype(int)

            # Résultat 1X2 (si FTR absent, calculer)
            if "ftr" not in df.columns or df["ftr"].isna().all():
                def result(row):
                    if row["score_home"] > row["score_away"]:  return "H"
                    if row["score_home"] < row["score_away"]:  return "A"
                    return "D"
                df["ftr"] = df.apply(result, axis=1)
            df["ftr"] = df["ftr"].str.upper().str.strip()

            logger.info(
                f"[LOADER] {path.name}: {len(df)} matchs | "
                f"ligue={df['league'].iloc[0]} | "
                f"saison={season} | "
                f"période={df['match_date'].min().date()} → {df['match_date'].max().date()}"
            )
            return df

        except Exception as e:
            logger.error(f"[LOADER] Erreur lors du chargement de {filepath}: {e}", exc_info=True)
            return pd.DataFrame()

    @staticmethod
    def load_multiple_csvs(csv_dir: str) -> pd.DataFrame:
        """
        Charge tous les CSV d'un répertoire et les concatène.

        Args:
            csv_dir: Répertoire contenant les fichiers *.csv

        Returns:
            DataFrame combiné de tous les matchs
        """
        dfs = []
        csv_dir_path = Path(csv_dir)

        if not csv_dir_path.exists():
            logger.warning(f"[LOADER] Répertoire introuvable: {csv_dir}")
            return pd.DataFrame()

        csv_files = sorted(csv_dir_path.glob("*.csv"))
        if not csv_files:
            logger.warning(f"[LOADER] Aucun CSV dans: {csv_dir}")
            return pd.DataFrame()

        logger.info(f"[LOADER] Chargement de {len(csv_files)} fichiers CSV depuis {csv_dir}")

        for csv_file in csv_files:
            df = RealDataLoader.load_csv(str(csv_file))
            if not df.empty:
                dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)

        # Supprimer les doublons (même match = même date + équipes)
        before = len(combined)
        combined = combined.drop_duplicates(
            subset=["team_home", "team_away", "match_date", "score_home", "score_away"],
            keep="first"
        )
        after = len(combined)
        if before > after:
            logger.info(f"[LOADER] {before - after} doublons supprimés")

        # Trier par date
        combined = combined.sort_values("match_date").reset_index(drop=True)

        logger.info(
            f"[LOADER] ✓ Total: {len(combined)} matchs | "
            f"{combined['team_home'].nunique() + combined['team_away'].nunique()} équipes uniques | "
            f"Ligues: {combined['league'].unique().tolist()} | "
            f"Période: {combined['match_date'].min().date()} → {combined['match_date'].max().date()}"
        )
        return combined

    def enrich_with_form(self, df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        """
        Calcule la forme récente de chaque équipe (ratio victoires sur 5 derniers matchs).

        Args:
            df:     DataFrame de matchs (doit avoir match_date, ftr, team_home, team_away)
            window: Nombre de matchs pour calculer la forme

        Returns:
            DataFrame enrichi avec form_home et form_away
        """
        df = df.sort_values("match_date").copy()
        df["form_home"] = 0.5
        df["form_away"] = 0.5

        # Calculer la forme par équipe
        team_history: dict = {}  # team → liste de résultats (1=win, 0.5=draw, 0=loss)

        for idx, row in df.iterrows():
            home = row["team_home"]
            away = row["team_away"]
            ftr  = row.get("ftr", "D")

            # Forme avant ce match
            hist_h = team_history.get(home, [])
            hist_a = team_history.get(away, [])
            form_h = np.mean(hist_h[-window:]) if hist_h else 0.5
            form_a = np.mean(hist_a[-window:]) if hist_a else 0.5
            df.at[idx, "form_home"] = round(form_h, 3)
            df.at[idx, "form_away"] = round(form_a, 3)

            # Mettre à jour l'historique après ce match
            if ftr == "H":
                team_history.setdefault(home, []).append(1.0)
                team_history.setdefault(away, []).append(0.0)
            elif ftr == "A":
                team_history.setdefault(home, []).append(0.0)
                team_history.setdefault(away, []).append(1.0)
            else:
                team_history.setdefault(home, []).append(0.5)
                team_history.setdefault(away, []).append(0.5)

        return df

    def enrich_with_h2h(self, df: pd.DataFrame, n_matches: int = 5) -> pd.DataFrame:
        """
        Ajoute les statistiques H2H (historique des confrontations directes).

        Args:
            df:       DataFrame de matchs
            n_matches: Nombre de confrontations directes à considérer

        Returns:
            DataFrame enrichi avec h2h_home_wins, h2h_draws, h2h_away_wins
        """
        df = df.sort_values("match_date").copy()
        df["h2h_home_wins"] = 0
        df["h2h_draws"]     = 0
        df["h2h_away_wins"] = 0

        h2h_history: dict = {}  # (team1, team2) → liste de résultats

        for idx, row in df.iterrows():
            home = row["team_home"]
            away = row["team_away"]
            ftr  = row.get("ftr", "D")

            # Chercher l'historique H2H (dans les deux sens)
            key   = (min(home, away), max(home, away))
            hist  = h2h_history.get(key, [])[-n_matches:]

            wins_h = sum(1 for h, r in hist if h == home and r == "win")
            wins_a = sum(1 for h, r in hist if h == away and r == "win")
            draws  = sum(1 for _, r in hist if r == "draw")

            df.at[idx, "h2h_home_wins"] = wins_h
            df.at[idx, "h2h_draws"]     = draws
            df.at[idx, "h2h_away_wins"] = wins_a

            # Mise à jour
            if ftr == "H":
                h2h_history.setdefault(key, []).append((home, "win"))
            elif ftr == "A":
                h2h_history.setdefault(key, []).append((away, "win"))
            else:
                h2h_history.setdefault(key, []).append((home, "draw"))

        return df

    @staticmethod
    def get_summary(df: pd.DataFrame) -> dict:
        """Retourne un résumé statistique du dataset."""
        if df.empty:
            return {"error": "Dataset vide"}

        total = len(df)
        return {
            "total_matches":   total,
            "leagues":         sorted(df["league"].unique().tolist()),
            "seasons":         sorted(df["season"].unique().tolist()),
            "teams":           len(set(df["team_home"].tolist() + df["team_away"].tolist())),
            "date_from":       str(df["match_date"].min().date()),
            "date_to":         str(df["match_date"].max().date()),
            "avg_goals":       round(df["total_goals"].mean(), 2) if "total_goals" in df.columns else None,
            "over_25_rate":    round(df["over_25"].mean() * 100, 1) if "over_25" in df.columns else None,
            "btts_rate":       round(df["btts"].mean() * 100, 1) if "btts" in df.columns else None,
            "home_win_rate":   round((df["ftr"] == "H").mean() * 100, 1) if "ftr" in df.columns else None,
            "draw_rate":       round((df["ftr"] == "D").mean() * 100, 1) if "ftr" in df.columns else None,
            "away_win_rate":   round((df["ftr"] == "A").mean() * 100, 1) if "ftr" in df.columns else None,
            "has_odds_b365":   "odds_home" in df.columns and df["odds_home"].notna().mean() > 0.5,
            "has_odds_ps":     "odds_home_ps" in df.columns and df["odds_home_ps"].notna().mean() > 0.5,
        }
