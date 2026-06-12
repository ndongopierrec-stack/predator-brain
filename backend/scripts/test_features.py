"""Test rapide du feature engineering."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from data.real_data_loader import RealDataLoader
from app.services.features.feature_engineering import FeatureEngineer

data_dir = str(Path(__file__).resolve().parents[2] / "data" / "raw")
df = RealDataLoader.load_multiple_csvs(data_dir)
print(f"Données brutes: {len(df):,} matchs, {len(df.columns)} colonnes")

# Le loader football-data.co.uk mappe déjà B365H→odds_home, PSH→odds_home_ps etc.
print(f"Colonnes dispo: {[c for c in df.columns if 'odds' in c or 'match_date' in c or 'season' in c or 'league' in c]}")

t0 = time.time()
fe = FeatureEngineer()
df_rich = fe.build(df)
elapsed = time.time() - t0

print(f"Feature engineering: {elapsed:.1f}s")
print(f"Matchs: {len(df_rich):,} | Colonnes: {len(df_rich.columns)}")
print(f"NaN total features: {df_rich[fe.feature_names()].isna().sum().sum()}")
print(f"elo_diff: min={df_rich['elo_diff'].min():.1f} max={df_rich['elo_diff'].max():.1f} mean={df_rich['elo_diff'].mean():.1f}")
print(f"form_pts_h mean: {df_rich['form_pts_h'].mean():.2f}")
print(f"implied_h mean: {df_rich['implied_h'].mean():.3f}")
print(f"over_25 rate: {df_rich['over_25'].mean():.3f}")
print(f"btts rate: {df_rich['btts'].mean():.3f}")
print("✓ Feature engineering OK")
