"""
Script de backtest rapide — Predator Brain
Usage: cd backend && python scripts/run_backtest.py
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.real_data_loader import RealDataLoader
from app.services.models.dixon_coles import DixonColesModel
from backtesting.real_backtest import RealBacktest
import numpy as np

print("=" * 60)
print("  BACKTEST REEL PREDATOR BRAIN (Dixon-Coles)")
print("=" * 60)

# 1. Charger les donnees
print("\n[1/4] Chargement des donnees...")
loader = RealDataLoader()
df = RealDataLoader.load_multiple_csvs("../data/raw")
if df.empty:
    print("ERREUR: Aucune donnee trouvee dans data/raw/")
    sys.exit(1)
df = loader.enrich_with_form(df)
print(f"  {len(df):,} matchs | {df['league'].nunique()} ligues | {df['team_home'].nunique()} equipes")

# 2. Split train/test (out-of-sample)
train = df[df["match_date"] < "2023-08-01"].copy()
test  = df[df["match_date"] >= "2023-08-01"].copy()
print(f"  Train: {len(train):,} matchs (2021-22 + 2022-23)")
print(f"  Test:  {len(test):,} matchs (2023-24 — hors-echantillon)")

# 3. Entrainer Dixon-Coles sur train seulement
print("\n[2/4] Entrainement Dixon-Coles sur donnees train...")
dc = DixonColesModel(max_goals=8)
dc.fit(train, time_decay=True)
print(f"  Modele: {len(dc.teams_)} equipes | gamma={dc.gamma_:.3f} | rho={dc.rho_:.4f}")
top_att = sorted(dc.attack_.items(), key=lambda x: x[1], reverse=True)[:3]
print(f"  Top attaques: {', '.join(f'{t}({s:+.2f})' for t,s in top_att)}")

# 4. Backtest sur donnees test (hors-echantillon — pas de look-ahead)
print("\n[3/4] Simulation backtest saison 2023-24...")

def predict_fn(match):
    try:
        p = dc.predict(match["team_home"], match["team_away"])
        return {
            "prob_home": p.prob_home, "prob_draw": p.prob_draw,
            "prob_away": p.prob_away, "prob_over_25": p.prob_over_25,
            "dc_known": p.dc_known,
        }
    except Exception:
        return {"prob_home": 0.46, "prob_draw": 0.26, "prob_away": 0.28}

bt = RealBacktest(initial_bankroll=10_000.0)
result = bt.run(
    from_date="2023-08-01",
    to_date="2024-06-30",
    model=predict_fn,
    df=test,
    min_confidence=0.55,
    min_edge=0.04,       # edge minimum 4%
    kelly_fraction=0.25, # Kelly quart
    max_stake_pct=0.05,  # max 5% du bankroll par pari
)

# 5. Rapport
print("\n[4/4] RESULTATS BACKTEST (hors-echantillon 2023-24)")
print("-" * 60)
print(f"  Matchs analyses     : {result.total_matches:,}")
print(f"  Paris places        : {result.total_bets:,}")
print(f"  Paris gagnes        : {result.bets_won:,}")
print(f"  Win rate            : {result.win_rate:.1%}")
print(f"  Mise totale         : {result.total_staked:,.0f} EUR")
print(f"  Profit net          : {result.total_profit:+,.0f} EUR")
print(f"  ROI                 : {result.roi_pct:+.1f}%")
print(f"  Bankroll finale     : {result.final_bankroll:,.0f} EUR (init: 10,000)")
print(f"  Drawdown maximum    : {result.max_drawdown:.1%}")
print(f"  Sharpe ratio        : {result.sharpe_ratio:.2f}")
print(f"  Cote moyenne        : {result.avg_odds:.2f}")

if result.total_bets > 0:
    print("\n  Par championnat:")
    for lg, s in sorted(result.by_league.items(), key=lambda x: x[1]["roi_pct"], reverse=True):
        wr = f"{s['win_rate']:.0%}"
        roi = f"{s['roi_pct']:+.1f}%"
        print(f"    {lg:<22}: {s['bets']:3d} paris | WR={wr} | ROI={roi}")

    print("\n  Par marche:")
    for mk, s in sorted(result.by_result_type.items(), key=lambda x: x[1]["roi_pct"], reverse=True):
        wr = f"{s['win_rate']:.0%}"
        roi = f"{s['roi_pct']:+.1f}%"
        print(f"    {mk:<12}: {s['bets']:3d} paris | WR={wr} | ROI={roi}")

print("\n" + "=" * 60)
if result.roi_pct > 3:
    verdict = "ROI POSITIF - Potentiel prometteur (a valider sur plus de donnees)"
elif result.roi_pct > 0:
    verdict = "ROI LEGEREMENT POSITIF - En limite de significativite statistique"
elif result.roi_pct > -3:
    verdict = "ROI NEUTRE - Aucun avantage statistiquement significatif"
else:
    verdict = "ROI NEGATIF - Strategie non profitable sur cette periode"
print(f"  VERDICT: {verdict}")
print("=" * 60)
