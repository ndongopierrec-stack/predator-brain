"""
Model Comparison — Predator Brain V2

Lance le walk-forward ML sur toutes les ligues disponibles.
Génère data/model_comparison_results.json pour le frontend.

Usage:
    cd backend
    python scripts/model_comparison.py
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("comparison")


def load_and_enrich() -> pd.DataFrame:
    """Charge les CSV et applique tout le feature engineering."""
    from data.real_data_loader import RealDataLoader
    from app.services.features.feature_engineering import FeatureEngineer

    # Chemin données : ../data/raw/ depuis backend/
    data_dir = str(_ROOT.parent / "data" / "raw")
    df_raw = RealDataLoader.load_multiple_csvs(data_dir)
    if df_raw is None or df_raw.empty:
        raise ValueError("Aucune donnée chargée depuis " + data_dir)

    logger.info(f"Données brutes : {len(df_raw):,} matchs, {len(df_raw.columns)} colonnes")

    fe = FeatureEngineer(form_window=5)
    df_rich = fe.build(df_raw)
    logger.info(f"Features construites : {len(df_rich.columns)} colonnes")
    return df_rich


def run_dc_baseline(df: pd.DataFrame) -> dict:
    """
    Récupère les résultats DC walk-forward depuis le fichier existant.
    """
    wf_file = _ROOT.parent / "data" / "walk_forward_results.json"
    if not wf_file.exists():
        return {"error": "walk_forward_results.json not found"}
    with open(wf_file) as f:
        data = json.load(f)
    rows = data.get("walk_forward", [])

    # Agréger par ligue (config Ref par défaut)
    ref_rows = [r for r in rows if r.get("config") == "Ref"]
    if not ref_rows:
        ref_rows = rows[:20]

    by_league: dict = {}
    for r in ref_rows:
        lg = r.get("league", "?")
        if lg not in by_league:
            by_league[lg] = {"rois": [], "bets": 0, "briers": [], "n_pos": 0}
        by_league[lg]["rois"].append(r["roi"])
        by_league[lg]["bets"] += r["bets"]
        if r["roi"] > 0:
            by_league[lg]["n_pos"] += 1

    summary = {}
    for lg, s in by_league.items():
        rois = s["rois"]
        summary[lg] = {
            "model":         "dc",
            "league":        lg,
            "roi_mean":      round(float(np.mean(rois)), 2) if rois else None,
            "n_bets":        s["bets"],
            "n_seasons":     len(rois),
            "n_seasons_pos": s["n_pos"],
        }
    return summary


def run_ml_walkforward(df: pd.DataFrame) -> dict:
    """Lance le walk-forward ML sur toutes les ligues."""
    from app.services.models.ml_models import MultiModelEngine, compute_bookmaker_baseline

    results_by_league: dict = {}
    baselines_by_league: dict = {}

    # Utiliser les noms de ligues tels que retournés par le loader (ex: "Ligue 1", "Premier League")
    leagues = sorted(df["league"].dropna().unique().tolist()) if "league" in df.columns else ["all"]
    logger.info(f"Ligues disponibles: {leagues}")

    for league in leagues:
        df_lg = df[df["league"] == league].copy() if "league" in df.columns else df.copy()

        seasons = sorted(df_lg["season"].dropna().unique().tolist()) if "season" in df_lg.columns else []
        if len(seasons) < 3:
            logger.warning(f"[{league}] Seulement {len(seasons)} saisons — skip")
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"Ligue: {league} | {len(df_lg):,} matchs | {len(seasons)} saisons")

        # Baseline bookmaker
        bm_base = compute_bookmaker_baseline(df_lg)
        baselines_by_league[league] = bm_base

        # Walk-forward ML
        engine = MultiModelEngine(min_train_seasons=2, conf_threshold=0.56, edge_min=0.04)
        try:
            wf = engine.walk_forward(df_lg)
            if "error" in wf:
                logger.warning(f"[{league}] WF error: {wf['error']}")
                continue

            agg = engine.aggregate(wf["walk_forward_rows"])
            results_by_league[league] = {
                "summary":    agg,
                "wf_rows":    wf["walk_forward_rows"],
                "n_features": wf.get("n_features", 0),
                "seasons":    wf.get("seasons", []),
            }

            # Afficher résumé
            for key, s in sorted(agg.items(), key=lambda x: x[1].get("roi_mean") or -99, reverse=True):
                roi = s.get("roi_mean")
                brier = s.get("brier_mean")
                n = s.get("n_bets_total", 0)
                roi_str   = f"{roi:+.1f}%"   if roi   is not None else "N/A"
                brier_str = f"{brier:.4f}"   if brier is not None else "N/A"
                logger.info(f"  [{key:25}] ROI={roi_str} | Brier={brier_str} | N={n}")

        except Exception as e:
            logger.error(f"[{league}] Erreur: {e}", exc_info=True)

    return {
        "results":   results_by_league,
        "baselines": baselines_by_league,
    }


def build_comparison_table(ml_results: dict, dc_baseline: dict) -> list:
    """
    Construit la table de comparaison frontend :
    une ligne par (modèle, marché, ligue).
    """
    rows = []

    # Dixon-Coles
    for lg, dc in dc_baseline.items():
        rows.append({
            "model":         "dc",
            "league":        lg,
            "market":        "home_win",
            "roi_mean":      dc.get("roi_mean"),
            "n_bets":        dc.get("n_bets", 0),
            "n_seasons":     dc.get("n_seasons", 0),
            "n_seasons_pos": dc.get("n_seasons_pos", 0),
            "brier_mean":    None,
            "log_loss_mean": None,
            "sharpe_mean":   None,
            "max_dd_mean":   None,
            "auc_mean":      None,
            "status":        _status(dc.get("roi_mean"), dc.get("n_bets", 0), dc.get("n_seasons_pos", 0), dc.get("n_seasons", 0)),
        })

    # ML models
    for league, lg_data in ml_results.get("results", {}).items():
        summary = lg_data.get("summary", {})
        baseline = ml_results.get("baselines", {}).get(league, {})

        for key, s in summary.items():
            market = s.get("market", "?")
            bm_brier = baseline.get(market, {}).get("brier") if baseline else None
            brier = s.get("brier_mean")
            beats_bm = (brier < bm_brier) if (brier and bm_brier) else None

            rows.append({
                "model":          s["model"],
                "league":         league,
                "market":         market,
                "roi_mean":       s.get("roi_mean"),
                "n_bets":         s.get("n_bets_total", 0),
                "n_seasons":      s.get("n_seasons", 0),
                "n_seasons_pos":  s.get("n_seasons_pos", 0),
                "brier_mean":     brier,
                "bm_brier":       bm_brier,
                "beats_bm_brier": beats_bm,
                "log_loss_mean":  s.get("log_loss_mean"),
                "sharpe_mean":    s.get("sharpe_mean"),
                "max_dd_mean":    s.get("max_dd_mean"),
                "auc_mean":       s.get("auc_mean"),
                "status":         _status(s.get("roi_mean"), s.get("n_bets_total", 0),
                                          s.get("n_seasons_pos", 0), s.get("n_seasons", 0)),
            })

    return rows


def _status(roi: float | None, n_bets: int, n_pos: int, n_seasons: int) -> str:
    if roi is None:
        return "INCONNU"
    if roi < 0:
        return "A_EVITER"
    if n_bets < 200:
        return "A_CONFIRMER"
    if n_pos < max(1, n_seasons // 2):
        return "A_CONFIRMER"
    if roi >= 3 and n_bets >= 500 and n_pos >= 4:
        return "VALIDE"
    if roi > 0 and n_pos >= 3:
        return "PROMETTEUR"
    return "OK"


def generate_honest_report(table: list) -> dict:
    """
    Rapport honnête V2 :
    - Quel modèle bat DC ?
    - Meilleure calibration ?
    - Ligue la moins mauvaise ?
    - Meilleur marché ?
    - Still No Money Mode ?
    """
    df = pd.DataFrame(table)

    if df.empty:
        return {"error": "No data"}

    report = {}

    # Quel modèle bat DC ?
    dc_roi = df[df["model"] == "dc"]["roi_mean"].mean() if "dc" in df["model"].values else None

    best_models = []
    for model in ["logreg", "rf", "xgb", "lgbm"]:
        m_df = df[df["model"] == model]
        if m_df.empty:
            continue
        avg_roi = m_df["roi_mean"].dropna().mean()
        if dc_roi is not None and avg_roi > dc_roi:
            best_models.append({"model": model, "roi_mean": round(float(avg_roi), 2)})

    report["models_beating_dc"] = sorted(best_models, key=lambda x: x["roi_mean"], reverse=True)

    # Meilleure calibration (Brier le plus bas)
    brier_df = df.dropna(subset=["brier_mean"])
    if not brier_df.empty:
        best_brier = brier_df.loc[brier_df["brier_mean"].idxmin()]
        report["best_calibration"] = {
            "model":  best_brier["model"],
            "market": best_brier["market"],
            "league": best_brier["league"],
            "brier":  round(float(best_brier["brier_mean"]), 4),
        }
    else:
        report["best_calibration"] = None

    # Ligue la moins mauvaise (meilleur ROI moyen)
    league_roi = df.groupby("league")["roi_mean"].mean().sort_values(ascending=False)
    if not league_roi.empty:
        report["best_league"] = {
            "league": str(league_roi.index[0]),
            "avg_roi": round(float(league_roi.iloc[0]), 2),
        }
        report["worst_league"] = {
            "league": str(league_roi.index[-1]),
            "avg_roi": round(float(league_roi.iloc[-1]), 2),
        }
    else:
        report["best_league"]  = None
        report["worst_league"] = None

    # Meilleur marché
    market_roi = df.groupby("market")["roi_mean"].mean().sort_values(ascending=False)
    if not market_roi.empty:
        report["best_market"] = {
            "market": str(market_roi.index[0]),
            "avg_roi": round(float(market_roi.iloc[0]), 2),
        }
    else:
        report["best_market"] = None

    # Modèles VALIDES
    valide = df[df["status"] == "VALIDE"]
    report["n_valide"] = int(len(valide))
    report["still_no_money_mode"] = len(valide) == 0

    # Brier vs baseline
    beats_bm = df[df["beats_bm_brier"] == True] if "beats_bm_brier" in df.columns else pd.DataFrame()
    report["n_models_beating_bm_brier"] = int(len(beats_bm))

    # Conclusion
    if report["still_no_money_mode"]:
        report["verdict"] = (
            "MODÈLE EN VALIDATION — Aucun modèle n'atteint le statut VALIDE. "
            "Paper trading uniquement. "
            "Règle absolue : 0€ de vrai argent tant qu'un modèle n'a pas "
            "500+ paris, 4+ saisons positives, ROI >3%, Sharpe >1."
        )
    else:
        best = valide.nlargest(1, "roi_mean").iloc[0]
        report["verdict"] = (
            f"SIGNAL CONFIRMÉ — {best['model'].upper()} sur {best['market']} "
            f"en ligue {best['league']} atteint le statut VALIDE "
            f"(ROI={best['roi_mean']:+.1f}%). Procéder avec prudence."
        )

    return report


def main():
    logger.info("=" * 60)
    logger.info("  PREDATOR BRAIN V2 — Model Comparison")
    logger.info("=" * 60)

    try:
        df = load_and_enrich()
    except Exception as e:
        logger.error(f"Erreur chargement données: {e}", exc_info=True)
        sys.exit(1)

    logger.info("\n📊 Baseline Dixon-Coles...")
    dc_baseline = run_dc_baseline(df)

    logger.info("\n🤖 Walk-forward ML (tous modèles)...")
    ml_results = run_ml_walkforward(df)

    logger.info("\n🔬 Construction table de comparaison...")
    table = build_comparison_table(ml_results, dc_baseline)

    logger.info("\n📋 Rapport honnête V2...")
    report = generate_honest_report(table)

    # Afficher le verdict
    logger.info("\n" + "=" * 60)
    logger.info("  VERDICT FINAL")
    logger.info("=" * 60)
    logger.info(report.get("verdict", "?"))
    logger.info(f"  Modèles battant DC      : {len(report.get('models_beating_dc', []))}")
    logger.info(f"  Modèles VALIDES          : {report.get('n_valide', 0)}")
    logger.info(f"  Still No Money Mode      : {report.get('still_no_money_mode', True)}")
    logger.info(f"  Meilleure ligue          : {report.get('best_league')}")
    logger.info(f"  Meilleur marché          : {report.get('best_market')}")
    logger.info(f"  Meilleure calibration    : {report.get('best_calibration')}")

    # Sauvegarder
    out = {
        "generated_at":    datetime.now().isoformat(),
        "comparison_table": table,
        "ml_wf_rows":       [row for lg_data in ml_results["results"].values()
                             for row in lg_data.get("wf_rows", [])],
        "dc_baseline":      dc_baseline,
        "bookmaker_baselines": ml_results.get("baselines", {}),
        "honest_report":    report,
        "global_status":    "VALIDE" if not report["still_no_money_mode"] else "A_CONFIRMER",
        "no_money_mode":    report["still_no_money_mode"],
    }

    out_file = _ROOT.parent / "data" / "model_comparison_results.json"
    out_file.parent.mkdir(exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"\n✓ Résultats sauvegardés → {out_file}")
    logger.info(f"  {len(table)} lignes dans la table de comparaison")
    return out


if __name__ == "__main__":
    main()
