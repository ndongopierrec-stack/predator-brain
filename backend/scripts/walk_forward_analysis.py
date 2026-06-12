"""
Walk-Forward Analysis — Predator Brain
Validation saison par saison STRICTE : train sur N saisons, test sur N+1

Méthodologie anti-overfitting :
- Jamais de look-ahead : les données de test ne sont jamais vues à l'entraînement
- Les paramètres (conf, edge) sont testés SUR TOUTES LES SAISONS, pas juste 2023-24
- Rapport de stabilité : un signal est fiable seulement s'il est consistant

Usage: cd backend && python scripts/walk_forward_analysis.py
"""

import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, r"D:\predator_project\predator_brain\backend")

import numpy as np
import pandas as pd
from pathlib import Path
from data.real_data_loader import RealDataLoader
from app.services.models.dixon_coles import DixonColesModel
from backtesting.real_backtest import RealBacktest

DATA_DIR = r"D:\predator_project\predator_brain\data\raw"

# ── Paramètres à tester (anti-overfitting) ──────────────────────────────────

CONFIGS = [
    {"name": "Ref (0.55/4%)",  "conf": 0.55, "edge": 0.04, "kf": 0.25},
    {"name": "Med (0.58/5%)",  "conf": 0.58, "edge": 0.05, "kf": 0.20},
    {"name": "Str (0.60/6%)",  "conf": 0.60, "edge": 0.06, "kf": 0.20},
    {"name": "HiE (0.60/8%)",  "conf": 0.60, "edge": 0.08, "kf": 0.15},
    {"name": "TrS (0.62/7%)",  "conf": 0.62, "edge": 0.07, "kf": 0.15},
]

# ── Chargement de toutes les données ────────────────────────────────────────

def load_all_data(league_filter=None):
    loader = RealDataLoader()
    df = RealDataLoader.load_multiple_csvs(DATA_DIR)
    df = loader.enrich_with_form(df)
    if league_filter:
        df = df[df["league"].isin(league_filter)].copy()
    # Ajouter colonne saison (ex: "2021-22" → "2122")
    df["season"] = df["match_date"].apply(lambda d: _season_label(pd.Timestamp(d)))
    return df

def _season_label(d: pd.Timestamp) -> str:
    """Transforme une date en code saison ex. '1415' '2324'."""
    if d.month >= 7:
        y1, y2 = d.year, d.year + 1
    else:
        y1, y2 = d.year - 1, d.year
    return f"{str(y1)[-2:]}{str(y2)[-2:]}"

# ── Walk-forward ─────────────────────────────────────────────────────────────

def walk_forward(df: pd.DataFrame, league: str, configs: list) -> list:
    """
    Walk-forward saison par saison.
    Pour chaque saison de test disponible, entraîne sur TOUTES les saisons précédentes.
    """
    seasons = sorted(df["season"].unique())
    results = []

    # Il faut au minimum 2 saisons pour train+test
    if len(seasons) < 2:
        return results

    print(f"  Walk-forward {league}: {len(seasons)} saisons disponibles : {seasons}")

    for test_idx in range(1, len(seasons)):
        train_seasons = seasons[:test_idx]
        test_season   = seasons[test_idx]

        train = df[df["season"].isin(train_seasons)].copy()
        test  = df[df["season"] == test_season].copy()

        if len(train) < 200 or len(test) < 50:
            continue

        # Entraîner le modèle
        try:
            dc = DixonColesModel(max_goals=6)
            dc.fit(train, time_decay=True, min_matches_per_team=5)
        except Exception as e:
            print(f"    [!] Erreur entraînement saison {test_season}: {e}")
            continue

        def pred_fn(m):
            try:
                p = dc.predict(m["team_home"], m["team_away"])
                return {
                    "prob_home": p.prob_home, "prob_draw": p.prob_draw,
                    "prob_away": p.prob_away, "prob_over_25": p.prob_over_25,
                    "dc_known": p.dc_known,
                }
            except Exception:
                return {"prob_home": 0.46, "prob_draw": 0.26, "prob_away": 0.28}

        # Tester chaque config
        for cfg in configs:
            bt = RealBacktest(initial_bankroll=10_000.0)
            r = bt.run(
                test["match_date"].min().strftime("%Y-%m-%d"),
                test["match_date"].max().strftime("%Y-%m-%d"),
                pred_fn, test.copy(),
                min_confidence=cfg["conf"],
                min_edge=cfg["edge"],
                kelly_fraction=cfg["kf"],
                max_stake_pct=0.05,
            )
            results.append({
                "league":        league,
                "train_seasons": "+".join(train_seasons),
                "test_season":   test_season,
                "config":        cfg["name"],
                "n_train":       len(train),
                "n_test":        len(test),
                "bets":          r.total_bets,
                "win_rate":      round(r.win_rate * 100, 1),
                "roi":           round(r.roi_pct, 2),
                "max_dd":        round(r.max_drawdown * 100, 1),
                "sharpe":        round(r.sharpe_ratio, 2),
                "profit":        round(r.total_profit, 2),
            })

        # Affichage rapide
        best = max([r2 for r2 in results if r2["test_season"] == test_season],
                   key=lambda x: x["roi"], default=None)
        if best:
            print(f"    Saison {test_season}: train={len(train)} matchs | "
                  f"test={len(test)} matchs | "
                  f"meilleur ROI={best['roi']:+.1f}% ({best['bets']} paris, {best['config']})")

    return results


# ── Tableau de sensibilité ────────────────────────────────────────────────────

def sensitivity_table(df: pd.DataFrame, league: str) -> list:
    """
    Teste une grille de (confidence × edge) sur toutes les données disponibles.
    Utilise la 1ère moitié comme train, la 2ème comme test.
    But : identifier le seuil LE PLUS ROBUSTE, pas le plus performant.
    """
    seasons = sorted(df["season"].unique())
    mid = len(seasons) // 2
    train = df[df["season"].isin(seasons[:mid])].copy()
    test  = df[df["season"].isin(seasons[mid:])].copy()

    if len(train) < 200 or len(test) < 50:
        return []

    dc = DixonColesModel(max_goals=6)
    dc.fit(train, time_decay=True, min_matches_per_team=5)

    def pred_fn(m):
        try:
            p = dc.predict(m["team_home"], m["team_away"])
            return {"prob_home": p.prob_home, "prob_draw": p.prob_draw,
                    "prob_away": p.prob_away, "prob_over_25": p.prob_over_25}
        except:
            return {"prob_home": 0.46, "prob_draw": 0.26, "prob_away": 0.28}

    conf_values = [0.55, 0.57, 0.58, 0.60, 0.62, 0.65]
    edge_values = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10]

    rows = []
    for conf in conf_values:
        for edge in edge_values:
            bt = RealBacktest(initial_bankroll=10_000.0)
            r = bt.run(
                test["match_date"].min().strftime("%Y-%m-%d"),
                test["match_date"].max().strftime("%Y-%m-%d"),
                pred_fn, test.copy(),
                min_confidence=conf,
                min_edge=edge,
                kelly_fraction=0.20,
                max_stake_pct=0.05,
            )
            rows.append({
                "league": league,
                "conf":   conf,
                "edge":   edge,
                "bets":   r.total_bets,
                "roi":    round(r.roi_pct, 2),
                "win_rate": round(r.win_rate * 100, 1),
                "sharpe": round(r.sharpe_ratio, 2),
                "max_dd": round(r.max_drawdown * 100, 1),
            })
    return rows


# ── Audit qualité données ─────────────────────────────────────────────────────

def data_quality_audit(df: pd.DataFrame) -> dict:
    """Vérifie doublons, matchs annulés, cotes manquantes, noms incohérents."""
    report = {}

    # Doublons
    dup_mask = df.duplicated(subset=["match_date","team_home","team_away"], keep=False)
    report["duplicates"] = int(dup_mask.sum())

    # Scores nuls/anormaux (possible annulation)
    bad_scores = df[(df["score_home"] < 0) | (df["score_away"] < 0) |
                    (df["score_home"] > 15) | (df["score_away"] > 15)]
    report["bad_scores"] = len(bad_scores)

    # Cotes manquantes
    if "odds_home" in df.columns:
        no_odds = df["odds_home"].isna().sum()
        report["matches_no_odds"] = int(no_odds)
        report["pct_no_odds"] = round(no_odds / len(df) * 100, 1)

    # Par ligue et saison
    by_league_season = df.groupby(["league","season"]).size().reset_index(name="n")
    report["by_league_season"] = by_league_season.to_dict("records")

    # Noms d'équipes uniques par ligue (pour détecter les incohérences)
    team_counts = {}
    for league in df["league"].unique():
        teams = set(df[df["league"]==league]["team_home"].unique())
        team_counts[league] = len(teams)
    report["teams_per_league"] = team_counts

    # COVID flag (saisons avec matchs manquants)
    expected = {"E0":380,"F1":380,"D1":306,"SP1":380,"I1":380}
    incomplete = []
    for _, row in by_league_season.iterrows():
        lg_raw = df[(df["league"]==row["league"]) & (df["season"]==row["season"])]["league_raw"].iloc[0] \
                 if "league_raw" in df.columns else ""
        exp = expected.get(lg_raw, 340)
        if row["n"] < exp * 0.85:
            incomplete.append(f"{row['league']} {row['season']} ({row['n']}/{exp})")
    report["incomplete_seasons"] = incomplete

    return report


# ── Règle de prudence ────────────────────────────────────────────────────────

def prudence_verdict(bets_total: int, roi: float, max_dd: float,
                     n_seasons_positive: int, n_seasons_total: int) -> dict:
    """
    Applique les règles de prudence pour déterminer le statut d'une stratégie.
    """
    issues = []
    status = "OK"

    if bets_total < 200:
        status = "A_CONFIRMER"
        issues.append(f"Seulement {bets_total} paris au total (objectif: 500+)")
    elif bets_total < 500:
        if status == "OK": status = "A_CONFIRMER"
        issues.append(f"{bets_total} paris — significativité limitée (objectif: 500+)")

    if roi < 0:
        status = "A_EVITER"
        issues.append(f"ROI négatif ({roi:+.1f}%)")

    if max_dd > 50:
        if status in ("OK", "A_CONFIRMER"): status = "RISQUE_ELEVE"
        issues.append(f"Drawdown max trop élevé ({max_dd:.0f}%)")

    if n_seasons_positive < 3 and n_seasons_total >= 3:
        if status == "OK": status = "A_CONFIRMER"
        issues.append(f"Seulement {n_seasons_positive}/{n_seasons_total} saisons positives")

    if n_seasons_positive >= 3 and roi > 0 and bets_total >= 500:
        status = "PROMETTEUR"

    return {
        "status": status,
        "issues": issues,
        "max_stake_pct": 0.5 if bets_total < 500 else (1.0 if bets_total < 1000 else 2.0),
        "real_money": bets_total >= 1000 and n_seasons_positive >= 4 and max_dd < 40,
    }


# ── Rapport final ────────────────────────────────────────────────────────────

def print_report(wf_results: list, sens_results: list, quality: dict, league: str):
    from collections import defaultdict

    print()
    print("=" * 70)
    print(f"  RAPPORT WALK-FORWARD — {league.upper()}")
    print("=" * 70)

    if not wf_results:
        print("  Pas assez de données pour le walk-forward.")
        return

    # Filtrer config "Med (0.58/5%)" pour le rapport principal
    target_cfg = "Med (0.58/5%)"
    main_rows = [r for r in wf_results if r["config"] == target_cfg and r["league"] == league]

    print(f"\n  Configuration : {target_cfg}")
    print(f"  {'Saison test':<12} | {'Paris':>5} | {'WR':>5} | {'ROI':>7} | {'DD':>5} | {'Sharpe':>6}")
    print("  " + "-" * 50)

    total_bets = 0
    total_profit = 0.0
    n_positive = 0

    for r in main_rows:
        roi_str = f"{r['roi']:+.1f}%"
        mark = "+" if r["roi"] > 0 else " "
        print(f"  {r['test_season']:<12} | {r['bets']:>5} | {r['win_rate']:>4.0f}% | "
              f"{roi_str:>7} | {r['max_dd']:>4.0f}% | {r['sharpe']:>6.2f}  {mark}")
        total_bets += r["bets"]
        total_profit += r["profit"] * (r["bets"] / 10000.0)  # normalisé
        if r["roi"] > 0:
            n_positive += 1

    avg_roi = np.mean([r["roi"] for r in main_rows]) if main_rows else 0
    avg_dd  = np.mean([r["max_dd"] for r in main_rows]) if main_rows else 0
    avg_sh  = np.mean([r["sharpe"] for r in main_rows]) if main_rows else 0

    print()
    print(f"  Cumul : {total_bets:,} paris sur {len(main_rows)} saisons")
    print(f"  ROI moyen    : {avg_roi:+.1f}%")
    print(f"  Drawdown moy : {avg_dd:.0f}%")
    print(f"  Sharpe moyen : {avg_sh:.2f}")
    print(f"  Saisons positives : {n_positive}/{len(main_rows)}")

    # Verdict de prudence
    verdict = prudence_verdict(total_bets, avg_roi, avg_dd, n_positive, len(main_rows))
    print()
    print(f"  STATUT : {verdict['status']}")
    for issue in verdict["issues"]:
        print(f"    - {issue}")
    print(f"  Mise max recommandee : {verdict['max_stake_pct']:.1f}% de la bankroll")
    print(f"  Argent reel ? {'OUI (avec precautions)' if verdict['real_money'] else 'NON — paper trading uniquement'}")

    # Tableau de sensibilité
    if sens_results:
        print()
        print(f"  TABLEAU DE SENSIBILITE (conf x edge) — {league}")
        print(f"  {'Conf':>5} | {'Edge':>5} | {'Paris':>5} | {'WR':>5} | {'ROI':>7} | {'Sharpe':>6}")
        print("  " + "-" * 50)
        for r in sorted(sens_results, key=lambda x: x["roi"], reverse=True)[:10]:
            roi_str = f"{r['roi']:+.1f}%"
            print(f"  {r['conf']:>4.2f} | {r['edge']:>4.0%} | {r['bets']:>5} | "
                  f"{r['win_rate']:>4.0f}% | {roi_str:>7} | {r['sharpe']:>6.2f}")

    # Audit qualité
    print()
    print("  QUALITE DES DONNEES")
    print(f"    Doublons         : {quality.get('duplicates', 'N/A')}")
    print(f"    Scores anormaux  : {quality.get('bad_scores', 'N/A')}")
    print(f"    Saisons incompletes: {quality.get('incomplete_seasons', [])}")
    print(f"    Equipes par ligue  : {quality.get('teams_per_league', {})}")

    print()
    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  WALK-FORWARD ANALYSIS — PREDATOR BRAIN")
    print("  Anti-overfitting : chaque saison de test est strictement separee")
    print("=" * 70)

    print("\n[1/4] Chargement des donnees...")
    df_all = load_all_data()
    print(f"  Total : {len(df_all):,} matchs | {df_all['league'].nunique()} ligues | "
          f"{df_all['season'].nunique()} saisons")

    # Audit qualité global
    print("\n[2/4] Audit qualite des donnees...")
    quality = data_quality_audit(df_all)
    print(f"  Doublons: {quality['duplicates']} | Scores anormaux: {quality['bad_scores']}")
    if quality.get("incomplete_seasons"):
        print(f"  Saisons incompletes (COVID etc): {quality['incomplete_seasons']}")

    # Walk-forward Ligue 1 (le seul signal prometteur)
    print("\n[3/4] Walk-forward Ligue 1...")
    df_l1 = df_all[df_all["league"] == "Ligue 1"].copy()
    wf_l1 = walk_forward(df_l1, "Ligue 1", CONFIGS)
    sens_l1 = sensitivity_table(df_l1, "Ligue 1")

    # Walk-forward toutes ligues (pour comparer)
    print("\n[4/4] Walk-forward toutes ligues...")
    all_wf = []
    for league in sorted(df_all["league"].unique()):
        df_lg = df_all[df_all["league"] == league].copy()
        if len(df_lg["season"].unique()) >= 2:
            wf = walk_forward(df_lg, league, [CONFIGS[1]])  # config "Med" seulement
            all_wf.extend(wf)

    # Rapports
    print_report(wf_l1, sens_l1, quality, "Ligue 1")

    # Résumé toutes ligues
    print()
    print("=" * 70)
    print("  RESUME TOUTES LIGUES — config Med (0.58/5%)")
    print("=" * 70)
    print(f"  {'Ligue':<22} | {'Saisons':>7} | {'Paris':>6} | {'ROI moy':>8} | {'Sharpe moy':>10} | {'S+':>4}")
    print("  " + "-" * 65)

    for league in sorted(set(r["league"] for r in all_wf)):
        rows = [r for r in all_wf if r["league"] == league]
        if not rows:
            continue
        n_seasons = len(rows)
        total_bets = sum(r["bets"] for r in rows)
        avg_roi = np.mean([r["roi"] for r in rows])
        avg_sh  = np.mean([r["sharpe"] for r in rows])
        n_pos   = sum(1 for r in rows if r["roi"] > 0)
        verdict = prudence_verdict(total_bets, avg_roi,
                                   np.mean([r["max_dd"] for r in rows]),
                                   n_pos, n_seasons)
        status_short = {"OK":"OK","A_CONFIRMER":"CONF","RISQUE_ELEVE":"RISK",
                        "A_EVITER":"EVIT","PROMETTEUR":"PROM"}.get(verdict["status"],"?")
        print(f"  {league:<22} | {n_seasons:>7} | {total_bets:>6} | "
              f"{avg_roi:>+7.1f}% | {avg_sh:>10.2f} | {n_pos:>2}/{n_seasons} [{status_short}]")

    # Sauvegarder les résultats pour le frontend
    output = {
        "walk_forward": wf_l1 + all_wf,
        "sensitivity": sens_l1,
        "quality": quality,
        "generated_at": pd.Timestamp.now().isoformat(),
    }
    out_path = Path(DATA_DIR).parent / "walk_forward_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Resultats sauvegardes : {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
