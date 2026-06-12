"""
Feature Engineering — Predator Brain V2

Calcule toutes les features avancées avant chaque match :
  - Elo global / domicile / extérieur  (mise à jour match par match)
  - Forme récente (buts, points, CS, BTTS, O2.5 sur N derniers matchs)
  - Contexte calendrier (jours de repos, période saison, streak)
  - Features marché (probabilité implicite, marge bookmaker, mouvement cote)

Usage:
    from app.services.features.feature_engineering import FeatureEngineer
    fe = FeatureEngineer()
    df = fe.build(df_raw)          # enrichit avec toutes les features
    X, y = fe.to_matrix(df, target="home_win")
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple
import logging

logger = logging.getLogger("predator.features")

# ── Elo ───────────────────────────────────────────────────────────────────────

DEFAULT_ELO  = 1500.0
K_FACTOR     = 20.0     # vitesse d'adaptation
HOME_ADVANCE = 100.0    # avantage domicile en points Elo (avant le match)


def _expected_elo(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def _outcome_score(ftr: str) -> Tuple[float, float]:
    if ftr == "H": return 1.0, 0.0
    if ftr == "A": return 0.0, 1.0
    return 0.5, 0.5


def add_elo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les ratings Elo pour chaque équipe AVANT chaque match.
    Mise à jour chronologique stricte — pas de look-ahead.

    Ajoute : elo_home, elo_away, elo_home_home, elo_away_away,
             elo_diff, elo_prob_home
    """
    df = df.sort_values("match_date").reset_index(drop=True)

    elo: Dict[str, float]      = {}   # Elo global
    elo_h: Dict[str, float]    = {}   # Elo domicile
    elo_a: Dict[str, float]    = {}   # Elo extérieur
    n_matches: Dict[str, int]  = {}   # matchs joués

    elo_home_col   = np.zeros(len(df))
    elo_away_col   = np.zeros(len(df))
    elo_hh_col     = np.zeros(len(df))  # Elo domicile quand à domicile
    elo_aa_col     = np.zeros(len(df))  # Elo extérieur quand à l'extérieur
    elo_diff_col   = np.zeros(len(df))
    elo_prob_col   = np.zeros(len(df))

    for idx, row in df.iterrows():
        h = row["team_home"]
        a = row["team_away"]

        eh  = elo.get(h, DEFAULT_ELO)
        ea  = elo.get(a, DEFAULT_ELO)
        ehh = elo_h.get(h, DEFAULT_ELO)
        eaa = elo_a.get(a, DEFAULT_ELO)

        # Enregistrer AVANT la mise à jour (anti look-ahead)
        elo_home_col[idx]  = eh
        elo_away_col[idx]  = ea
        elo_hh_col[idx]    = ehh
        elo_aa_col[idx]    = eaa
        elo_diff_col[idx]  = (eh + HOME_ADVANCE) - ea
        elo_prob_col[idx]  = _expected_elo(eh + HOME_ADVANCE, ea)

        # Mise à jour post-match
        ftr = str(row.get("ftr", "D")).upper().strip()
        if ftr not in ("H", "D", "A"):
            continue

        exp_h = _expected_elo(eh + HOME_ADVANCE, ea)
        exp_a = 1.0 - exp_h
        s_h, s_a = _outcome_score(ftr)

        elo[h]   = eh  + K_FACTOR * (s_h - exp_h)
        elo[a]   = ea  + K_FACTOR * (s_a - exp_a)
        elo_h[h] = ehh + K_FACTOR * (s_h - exp_h)
        elo_a[a] = eaa + K_FACTOR * (s_a - exp_a)
        n_matches[h] = n_matches.get(h, 0) + 1
        n_matches[a] = n_matches.get(a, 0) + 1

    df["elo_home"]      = elo_home_col
    df["elo_away"]      = elo_away_col
    df["elo_home_home"] = elo_hh_col
    df["elo_away_away"] = elo_aa_col
    df["elo_diff"]      = elo_diff_col
    df["elo_prob_home"] = elo_prob_col
    return df


# ── Forme récente ─────────────────────────────────────────────────────────────

def add_form(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    Calcule les features de forme pour chaque équipe AVANT chaque match.
    Strictement causal : n'utilise que les matchs passés.

    Features ajoutées (suffixe _h = domicile, _a = extérieur) :
      form_pts, form_gf, form_ga, form_gd, form_cs, form_btts, form_o25,
      form_h_pts, form_a_pts  (forme à domicile vs à l'extérieur)
    """
    df = df.sort_values("match_date").reset_index(drop=True)

    # Historique glissant par équipe
    history: Dict[str, List[dict]] = {}

    cols = {
        "form_pts_h": [], "form_gf_h": [], "form_ga_h": [], "form_gd_h": [],
        "form_cs_h": [], "form_btts_h": [], "form_o25_h": [], "form_home_pts_h": [],
        "form_pts_a": [], "form_gf_a": [], "form_ga_a": [], "form_gd_a": [],
        "form_cs_a": [], "form_btts_a": [], "form_o25_a": [], "form_away_pts_a": [],
    }

    def _form_stats(records: List[dict], is_home_role: Optional[bool] = None) -> dict:
        """Calcule les stats de forme sur les N derniers matchs."""
        recs = records[-window:]
        if is_home_role is not None:
            recs_venue = [r for r in records if r["home_role"] == is_home_role][-window:]
            venue_pts = np.mean([r["pts"] for r in recs_venue]) if recs_venue else 1.5
        else:
            venue_pts = 1.5

        if not recs:
            return {"pts": 1.5, "gf": 1.2, "ga": 1.2, "gd": 0.0,
                    "cs": 0.25, "btts": 0.45, "o25": 0.50, "venue_pts": 1.5}
        return {
            "pts":      np.mean([r["pts"]  for r in recs]),
            "gf":       np.mean([r["gf"]   for r in recs]),
            "ga":       np.mean([r["ga"]   for r in recs]),
            "gd":       np.mean([r["gd"]   for r in recs]),
            "cs":       np.mean([r["cs"]   for r in recs]),
            "btts":     np.mean([r["btts"] for r in recs]),
            "o25":      np.mean([r["o25"]  for r in recs]),
            "venue_pts": venue_pts,
        }

    for idx, row in df.iterrows():
        h = row["team_home"]
        a = row["team_away"]
        sh = float(row.get("score_home", 0) or 0)
        sa = float(row.get("score_away", 0) or 0)
        ftr = str(row.get("ftr", "D")).upper().strip()
        total = sh + sa

        # Lire la forme AVANT mise à jour
        fh = _form_stats(history.get(h, []), is_home_role=True)
        fa = _form_stats(history.get(a, []), is_home_role=False)

        cols["form_pts_h"].append(fh["pts"])
        cols["form_gf_h"].append(fh["gf"])
        cols["form_ga_h"].append(fh["ga"])
        cols["form_gd_h"].append(fh["gd"])
        cols["form_cs_h"].append(fh["cs"])
        cols["form_btts_h"].append(fh["btts"])
        cols["form_o25_h"].append(fh["o25"])
        cols["form_home_pts_h"].append(fh["venue_pts"])

        cols["form_pts_a"].append(fa["pts"])
        cols["form_gf_a"].append(fa["gf"])
        cols["form_ga_a"].append(fa["ga"])
        cols["form_gd_a"].append(fa["gd"])
        cols["form_cs_a"].append(fa["cs"])
        cols["form_btts_a"].append(fa["btts"])
        cols["form_o25_a"].append(fa["o25"])
        cols["form_away_pts_a"].append(fa["venue_pts"])

        # Mise à jour historique post-match
        if ftr not in ("H", "D", "A"):
            continue

        pts_h = 3 if ftr == "H" else (1 if ftr == "D" else 0)
        pts_a = 3 if ftr == "A" else (1 if ftr == "D" else 0)
        btts  = 1.0 if (sh > 0 and sa > 0) else 0.0
        o25   = 1.0 if total > 2.5 else 0.0

        if h not in history: history[h] = []
        if a not in history: history[a] = []

        history[h].append({"pts": pts_h, "gf": sh, "ga": sa, "gd": sh - sa,
                            "cs": 1.0 if sa == 0 else 0.0, "btts": btts, "o25": o25,
                            "home_role": True})
        history[a].append({"pts": pts_a, "gf": sa, "ga": sh, "gd": sa - sh,
                            "cs": 1.0 if sh == 0 else 0.0, "btts": btts, "o25": o25,
                            "home_role": False})

    for col, values in cols.items():
        df[col] = values

    # Features dérivées
    df["form_pts_diff"]  = df["form_pts_h"]  - df["form_pts_a"]
    df["form_gd_diff"]   = df["form_gd_h"]   - df["form_gd_a"]
    df["form_o25_avg"]   = (df["form_o25_h"] + df["form_o25_a"]) / 2
    df["form_btts_avg"]  = (df["form_btts_h"] + df["form_btts_a"]) / 2
    return df


# ── Features marché ───────────────────────────────────────────────────────────

def add_market_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrait les probabilités implicites et la marge bookmaker depuis les cotes.
    Utilise Bet365 (B365) et Pinnacle (PS) si disponibles.

    Features :
      implied_h, implied_d, implied_a   — probabilités implicites B365
      bm_margin                         — surmarge bookmaker (vig)
      ps_implied_h, ps_implied_a        — Pinnacle implied probs
      ps_margin                         — marge Pinnacle (référence efficience)
      clv_proxy                         — proxy CLV si Pinnacle dispo
    """

    def safe_div(a, b, default=0.5):
        try:
            return float(a) / float(b) if float(b) > 0 else default
        except (TypeError, ValueError, ZeroDivisionError):
            return default

    def to_f(x, default=0.0):
        try: return float(x)
        except: return default

    # Bet365 1X2
    if all(c in df.columns for c in ["odds_home", "odds_draw", "odds_away"]):
        oh = df["odds_home"].apply(lambda x: to_f(x, 0))
        od = df["odds_draw"].apply(lambda x: to_f(x, 0))
        oa = df["odds_away"].apply(lambda x: to_f(x, 0))
        ih = oh.apply(lambda x: 1/x if x > 1 else 0)
        id_ = od.apply(lambda x: 1/x if x > 1 else 0)
        ia = oa.apply(lambda x: 1/x if x > 1 else 0)
        total = ih + id_ + ia
        total = total.replace(0, np.nan)
        df["implied_h"]  = ih / total
        df["implied_d"]  = id_ / total
        df["implied_a"]  = ia / total
        df["bm_margin"]  = (total - 1.0).fillna(0.05)
    else:
        df["implied_h"]  = 0.46
        df["implied_d"]  = 0.26
        df["implied_a"]  = 0.28
        df["bm_margin"]  = 0.05

    # Pinnacle (proxy closing line)
    if all(c in df.columns for c in ["odds_home_ps", "odds_draw_ps", "odds_away_ps"]):
        psh = df["odds_home_ps"].apply(lambda x: to_f(x, 0))
        psd = df["odds_draw_ps"].apply(lambda x: to_f(x, 0))
        psa = df["odds_away_ps"].apply(lambda x: to_f(x, 0))
        pi_h = psh.apply(lambda x: 1/x if x > 1 else 0)
        pi_d = psd.apply(lambda x: 1/x if x > 1 else 0)
        pi_a = psa.apply(lambda x: 1/x if x > 1 else 0)
        ptot = pi_h + pi_d + pi_a
        ptot = ptot.replace(0, np.nan)
        df["ps_implied_h"] = (pi_h / ptot).fillna(df["implied_h"])
        df["ps_implied_a"] = (pi_a / ptot).fillna(df["implied_a"])
        df["ps_margin"]    = (ptot - 1.0).fillna(0.02)
        df["has_pinnacle"] = True
    else:
        df["ps_implied_h"] = df["implied_h"]
        df["ps_implied_a"] = df["implied_a"]
        df["ps_margin"]    = 0.02
        df["has_pinnacle"] = False

    # Over/Under implied prob
    if "odds_over25" in df.columns:
        o_odds = df["odds_over25"].apply(lambda x: to_f(x, 0))
        df["implied_over25"] = o_odds.apply(lambda x: 1/x if x > 1 else 0.5)
    else:
        df["implied_over25"] = 0.50

    # Features dérivées
    df["bm_vs_equal"]   = df["implied_h"] - 0.333  # favori domicile vs neutre
    df["margin_ratio"]  = df["bm_margin"] / 0.05    # ratio vs marge typique

    return df


# ── Features calendrier ───────────────────────────────────────────────────────

def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Contexte calendrier : repos, période de saison, etc.
    """
    df = df.sort_values("match_date").reset_index(drop=True)
    df["match_date"] = pd.to_datetime(df["match_date"])

    # Période de saison (0=début, 0.5=milieu, 1=fin)
    df["season_month"]  = df["match_date"].dt.month
    df["season_phase"]  = df["match_date"].apply(lambda d:
        (d.month - 8) % 12 / 11.0  # août=0, juin=1
    )
    df["is_weekday"]    = (df["match_date"].dt.dayofweek < 5).astype(int)

    # Jours de repos depuis le dernier match (approximation)
    last_match: Dict[str, pd.Timestamp] = {}
    rest_h = []
    rest_a = []

    for _, row in df.iterrows():
        h = row["team_home"]
        a = row["team_away"]
        d = row["match_date"]

        lh = last_match.get(h)
        la = last_match.get(a)

        rest_h.append((d - lh).days if lh is not None else 14)
        rest_a.append((d - la).days if la is not None else 14)

        last_match[h] = d
        last_match[a] = d

    df["rest_days_h"] = np.clip(rest_h, 3, 30)
    df["rest_days_a"] = np.clip(rest_a, 3, 30)
    df["rest_diff"]   = df["rest_days_h"] - df["rest_days_a"]

    return df


# ── FeatureEngineer ───────────────────────────────────────────────────────────

FEATURE_COLS = [
    # Elo
    "elo_home", "elo_away", "elo_home_home", "elo_away_away",
    "elo_diff", "elo_prob_home",
    # Forme
    "form_pts_h", "form_gf_h", "form_ga_h", "form_gd_h",
    "form_cs_h", "form_btts_h", "form_o25_h", "form_home_pts_h",
    "form_pts_a", "form_gf_a", "form_ga_a", "form_gd_a",
    "form_cs_a", "form_btts_a", "form_o25_a", "form_away_pts_a",
    "form_pts_diff", "form_gd_diff", "form_o25_avg", "form_btts_avg",
    # Marché
    "implied_h", "implied_d", "implied_a", "bm_margin",
    "ps_implied_h", "ps_implied_a", "implied_over25",
    "bm_vs_equal", "margin_ratio",
    # Calendrier
    "rest_days_h", "rest_days_a", "rest_diff",
    "season_phase", "is_weekday",
]

TARGETS = {
    "home_win":  lambda df: (df["ftr"] == "H").astype(int),
    "draw":      lambda df: (df["ftr"] == "D").astype(int),
    "away_win":  lambda df: (df["ftr"] == "A").astype(int),
    "over_25":   lambda df: df.get("over_25", (df.get("total_goals", 0) > 2.5)).astype(int),
    "btts":      lambda df: df.get("btts", ((df.get("score_home", 0) > 0) & (df.get("score_away", 0) > 0))).astype(int),
}


class FeatureEngineer:
    """
    Pipeline de feature engineering complet pour Predator Brain V2.

    Usage:
        fe = FeatureEngineer()
        df_rich = fe.build(df_raw)
        X, y = fe.to_matrix(df_rich, target="home_win")
    """

    def __init__(self, form_window: int = 5):
        self.form_window = form_window

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrichit le DataFrame avec toutes les features (ordre chronologique)."""
        logger.info(f"[FE] Construction features sur {len(df):,} matchs...")
        df = df.copy()
        df = df.sort_values("match_date").reset_index(drop=True)

        # Normaliser FTR
        if "ftr" in df.columns:
            df["ftr"] = df["ftr"].astype(str).str.upper().str.strip()

        # Targets de base
        df["home_win"] = (df["ftr"] == "H").astype(int)
        df["draw"]     = (df["ftr"] == "D").astype(int)
        df["away_win"] = (df["ftr"] == "A").astype(int)
        if "total_goals" not in df.columns:
            df["total_goals"] = (
                pd.to_numeric(df.get("score_home", 0), errors="coerce").fillna(0) +
                pd.to_numeric(df.get("score_away", 0), errors="coerce").fillna(0)
            )
        df["over_25"] = (df["total_goals"] > 2.5).astype(int)
        if "score_home" in df.columns and "score_away" in df.columns:
            sh = pd.to_numeric(df["score_home"], errors="coerce").fillna(0)
            sa = pd.to_numeric(df["score_away"], errors="coerce").fillna(0)
            df["btts"] = ((sh > 0) & (sa > 0)).astype(int)

        df = add_elo(df)
        logger.info("[FE] Elo OK")
        df = add_form(df, window=self.form_window)
        logger.info("[FE] Forme OK")
        df = add_market_features(df)
        logger.info("[FE] Marché OK")
        df = add_calendar_features(df)
        logger.info("[FE] Calendrier OK")

        logger.info(f"[FE] {len(FEATURE_COLS)} features disponibles | "
                    f"{df[FEATURE_COLS].isna().sum().sum()} NaN")
        return df

    def to_matrix(self, df: pd.DataFrame, target: str = "home_win",
                  extra_cols: Optional[List[str]] = None) -> Tuple[pd.DataFrame, pd.Series]:
        """Retourne X (features) et y (target) prêts pour sklearn."""
        cols = [c for c in FEATURE_COLS if c in df.columns]
        if extra_cols:
            cols += [c for c in extra_cols if c in df.columns and c not in cols]

        df_clean = df[cols + [target]].dropna()
        X = df_clean[cols].fillna(0)
        y = df_clean[target]
        return X, y

    def feature_names(self) -> List[str]:
        return [c for c in FEATURE_COLS]
