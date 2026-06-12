"""Test rapide du walk-forward ML (1 ligue, 2 modèles)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from data.real_data_loader import RealDataLoader
from app.services.features.feature_engineering import FeatureEngineer
from app.services.models.ml_models import MultiModelEngine, compute_bookmaker_baseline

# Charger données
data_dir = str(Path(__file__).resolve().parents[2] / "data" / "raw")
df = RealDataLoader.load_multiple_csvs(data_dir)
print(f"Données: {len(df):,} matchs")

# Features
fe = FeatureEngineer()
df = fe.build(df)
print(f"Features: {len(df.columns)} colonnes")

# Tester sur Ligue 1 uniquement (F1) pour la rapidité
print(f"Valeurs league: {df['league'].value_counts().head(10).to_dict()}")
# Ligue 1 peut être "Ligue 1" (nom lisible) ou "F1" (code)
ligue1_mask = df["league"].str.contains("Ligue 1|F1", na=False)
df_f1 = df[ligue1_mask].copy()
print(f"\nLigue 1: {len(df_f1):,} matchs | saisons: {sorted(df_f1['season'].unique())}")

# Baseline bookmaker
bm = compute_bookmaker_baseline(df_f1)
print("\n📊 Baseline bookmaker (Brier à battre):")
for market, b in bm.items():
    print(f"  {market:12s}: Brier={b['brier']:.4f} | LogLoss={b['log_loss']:.4f}")

# Walk-forward ML (2 saisons min train, test saisons suivantes)
print("\n🤖 Walk-forward ML (LogReg + LightGBM)...")
t0 = time.time()
engine = MultiModelEngine(min_train_seasons=2, conf_threshold=0.56, edge_min=0.04)
result = engine.walk_forward(df_f1)

if "error" in result:
    print(f"Erreur: {result['error']}")
    sys.exit(1)

rows = result["walk_forward_rows"]
print(f"Walk-forward terminé en {time.time()-t0:.1f}s — {len(rows)} évaluations")

# Agréger
agg = engine.aggregate(rows)
print("\n📋 Résultats agrégés par modèle/marché:")
for key in sorted(agg.keys(), key=lambda k: agg[k].get("roi_mean") or -99, reverse=True):
    s = agg[key]
    roi = s.get("roi_mean")
    brier = s.get("brier_mean")
    n = s.get("n_bets_total", 0)
    sp = s.get("n_seasons_pos", 0)
    st = s.get("n_seasons", 0)
    status_icon = "✓" if (roi and roi > 0) else "✗"
    print(f"  {status_icon} [{key:25}] ROI={roi:+.1f}% | Brier={brier:.4f} | N={n} | {sp}/{st} sais+")

print("\n✓ ML Walk-forward OK")
