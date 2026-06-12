"""Backtest rapide pour audit — sans time_decay pour être plus rapide."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.real_data_loader import RealDataLoader
from app.services.models.dixon_coles import DixonColesModel
from backtesting.real_backtest import RealBacktest

loader = RealDataLoader()
print("Chargement des donnees...")
df = RealDataLoader.load_multiple_csvs("../data/raw")
df = loader.enrich_with_form(df)

train = df[df["match_date"] < "2023-08-01"]
test  = df[df["match_date"] >= "2023-08-01"]
print(f"Train: {len(train)} | Test: {len(test)}")

# Entrainer sans time_decay = plus rapide
print("Entrainement Dixon-Coles (rapide, sans time_decay)...")
dc = DixonColesModel(max_goals=6)
dc.fit(train, time_decay=False, min_matches_per_team=8)
print(f"DC: {len(dc.teams_)} equipes | gamma={dc.gamma_:.3f} | rho={dc.rho_:.4f}")

top_att = sorted(dc.attack_.items(), key=lambda x: x[1], reverse=True)[:5]
top_def = sorted(dc.defense_.items(), key=lambda x: x[1])[:5]
print("Top attaques:", [(t, round(s,3)) for t,s in top_att])
print("Top defenses:", [(t, round(s,3)) for t,s in top_def])

def pred(m):
    try:
        p = dc.predict(m["team_home"], m["team_away"])
        return {
            "prob_home": p.prob_home, "prob_draw": p.prob_draw,
            "prob_away": p.prob_away, "prob_over_25": p.prob_over_25,
            "dc_known": p.dc_known,
        }
    except Exception:
        return {"prob_home": 0.46, "prob_draw": 0.26, "prob_away": 0.28}

# Test: quelle proportion d'equipes est connue du modele?
known = sum(1 for _, row in test.iterrows()
            if row["team_home"] in dc.teams_ and row["team_away"] in dc.teams_)
print(f"Matchs avec equipes connues: {known}/{len(test)} ({known/len(test):.0%})")

print("\nBacktest (min_confidence=0.55, min_edge=4%, Kelly/4)...")
bt = RealBacktest(initial_bankroll=10_000.0)
r = bt.run(
    "2023-08-01", "2024-06-30", pred, test.copy(),
    min_confidence=0.55,
    min_edge=0.04,
    kelly_fraction=0.25,
    max_stake_pct=0.05,
)

print("\n" + "=" * 55)
print("  RESULTATS BACKTEST — SAISON 2023-24 (hors-echantillon)")
print("=" * 55)
print(f"  Matchs analyses  : {r.total_matches:,}")
print(f"  Paris places     : {r.total_bets:,}")
print(f"  Paris gagnes     : {r.bets_won:,}")
print(f"  Win rate         : {r.win_rate:.1%}")
print(f"  Mise totale      : {r.total_staked:,.0f} EUR")
print(f"  Profit net       : {r.total_profit:+,.0f} EUR")
print(f"  ROI              : {r.roi_pct:+.1f}%")
print(f"  Bankroll finale  : {r.final_bankroll:,.0f} EUR")
print(f"  Drawdown max     : {r.max_drawdown:.1%}")
print(f"  Sharpe ratio     : {r.sharpe_ratio:.2f}")
print(f"  Cote moyenne     : {r.avg_odds:.2f}")

if r.total_bets > 0:
    print("\n  Par championnat:")
    for lg, s in sorted(r.by_league.items(), key=lambda x: x[1]["roi_pct"], reverse=True):
        print(f"    {lg:<22}: {s['bets']:3d} paris | WR={s['win_rate']:.0%} | ROI={s['roi_pct']:+.1f}%")

    print("\n  Par marche:")
    for mk, s in sorted(r.by_result_type.items(), key=lambda x: x[1]["roi_pct"], reverse=True):
        print(f"    {mk:<12}: {s['bets']:3d} paris | WR={s['win_rate']:.0%} | ROI={s['roi_pct']:+.1f}%")

print("\n" + "=" * 55)
if r.roi_pct > 5:
    verdict = "EXCELLENT — ROI solide sur echantillon de test"
elif r.roi_pct > 2:
    verdict = "PROMETTEUR — ROI positif, a valider sur 1000+ paris"
elif r.roi_pct > 0:
    verdict = "NEUTRE/POSITIF — Faible edge, pas significatif (<500 paris)"
elif r.roi_pct > -3:
    verdict = "NEUTRE — Pas d'avantage statistiquement significatif"
else:
    verdict = "NEGATIF — Strategie non profitable sur cette periode"
print(f"  VERDICT: {verdict}")
print("=" * 55)
