"""
Télécharge les données historiques étendues depuis football-data.co.uk
Saisons 2014-15 à 2024-25 pour 6 ligues (E0, F1, D1, SP1, I1, F2)

Usage:
    cd backend && python scripts/download_extended_data.py

Sources légales uniquement — football-data.co.uk (données historiques publiques)
"""

import sys, os, time, requests, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

# ── Configuration ────────────────────────────────────────────────────────────

LEAGUES = {
    "E0":  "Premier League",
    "F1":  "Ligue 1",
    "D1":  "Bundesliga",
    "SP1": "La Liga",
    "I1":  "Serie A",
    "F2":  "Ligue 2",
}

# Saisons au format YY/ZZ → préfixe URL "YYZZ"
# football-data.co.uk supporte généralement depuis ~1993 pour E0
SEASONS = [
    ("1415", "2014-15"),
    ("1516", "2015-16"),
    ("1617", "2016-17"),
    ("1718", "2017-18"),
    ("1819", "2018-19"),
    ("1920", "2019-20"),
    ("2021", "2020-21"),
    ("2122", "2021-22"),
    ("2223", "2022-23"),
    ("2324", "2023-24"),
    ("2425", "2024-25"),   # saison en cours
]

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Colonnes qu'on attend ────────────────────────────────────────────────────

REQUIRED_COLS = {"HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"}
ODDS_COLS = {
    "B365H", "B365D", "B365A",       # Bet365
    "PSH", "PSD", "PSA",             # Pinnacle
    "WHH", "WHD", "WHA",             # William Hill
    "B365>2.5", "B365<2.5",          # Over/Under Bet365
    "P>2.5", "P<2.5",                # Over/Under Pinnacle
}

# ── Téléchargement ───────────────────────────────────────────────────────────

def download(season_code: str, season_name: str, league: str, league_name: str) -> dict:
    url = BASE_URL.format(season=season_code, league=league)
    dest = OUT_DIR / f"{league}_{season_code}.csv"

    # Déjà téléchargé ?
    if dest.exists() and dest.stat().st_size > 500:
        return {"status": "cached", "rows": None, "path": str(dest)}

    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 404:
            return {"status": "not_found"}
        r.raise_for_status()

        content = r.text
        if len(content) < 200 or "HomeTeam" not in content:
            return {"status": "empty"}

        dest.write_text(content, encoding="utf-8-sig")

        # Compter les lignes
        rows = len([l for l in content.split("\n") if l.strip()]) - 1
        return {"status": "ok", "rows": rows, "path": str(dest)}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_columns(filepath: str) -> dict:
    """Vérifie les colonnes disponibles dans un CSV."""
    import csv
    try:
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            cols = set(reader.fieldnames or [])
        missing_required = REQUIRED_COLS - cols
        odds_present = ODDS_COLS & cols
        return {
            "cols_total": len(cols),
            "missing_required": list(missing_required),
            "odds_present": sorted(odds_present),
            "has_pinnacle": bool({"PSH", "PSD", "PSA"} & cols),
            "has_bet365_ou": bool({"B365>2.5", "B365<2.5"} & cols),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  DOWNLOAD DONNÉES ÉTENDUES — football-data.co.uk")
    print(f"  Destination : {OUT_DIR}")
    print("=" * 70)

    results = {}
    total_ok = 0
    total_cached = 0
    total_not_found = 0
    total_errors = 0

    for league, league_name in LEAGUES.items():
        results[league] = {}
        print(f"\n{'─'*40}")
        print(f"  {league_name} ({league})")
        print(f"{'─'*40}")

        for season_code, season_name in SEASONS:
            r = download(season_code, season_name, league, league_name)
            results[league][season_code] = r

            if r["status"] == "ok":
                print(f"  ✓ {season_name} : {r['rows']:4d} matchs téléchargés")
                total_ok += 1
                time.sleep(0.3)   # être gentil avec le serveur
            elif r["status"] == "cached":
                print(f"  = {season_name} : déjà présent")
                total_cached += 1
            elif r["status"] == "not_found":
                print(f"  ✗ {season_name} : non disponible (404)")
                total_not_found += 1
            elif r["status"] == "empty":
                print(f"  ✗ {season_name} : fichier vide")
                total_errors += 1
            else:
                print(f"  ✗ {season_name} : erreur — {r.get('error', '?')}")
                total_errors += 1

    print()
    print("=" * 70)
    print("  RAPPORT DE TÉLÉCHARGEMENT")
    print("=" * 70)
    print(f"  Nouveaux fichiers  : {total_ok}")
    print(f"  Déjà présents      : {total_cached}")
    print(f"  Non disponibles    : {total_not_found}")
    print(f"  Erreurs            : {total_errors}")

    # Audit qualité des fichiers présents
    print()
    print("  AUDIT QUALITÉ DES DONNÉES")
    print("─" * 70)

    all_csvs = sorted(OUT_DIR.glob("*.csv"))
    total_rows = 0
    col_warnings = []

    for csv_path in all_csvs:
        info = check_columns(str(csv_path))
        if "error" in info:
            continue
        # Compter les lignes
        try:
            with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
                n = sum(1 for l in f if l.strip()) - 1
            total_rows += max(n, 0)
        except:
            n = 0

        odds = "B365+Pinn" if info["has_pinnacle"] else ("B365" if info.get("odds_present") else "NO ODDS")
        ou   = "B365>2.5" if info["has_bet365_ou"] else "NO O/U"
        warn = f"⚠ MANQUE: {info['missing_required']}" if info["missing_required"] else ""
        print(f"  {csv_path.stem:<22} : {n:4d} matchs | {odds:<10} | {ou:<9} {warn}")
        if info["missing_required"]:
            col_warnings.append(csv_path.name)

    print()
    print(f"  Total matchs disponibles : {total_rows:,}")
    if col_warnings:
        print(f"  ⚠ Fichiers avec colonnes manquantes : {col_warnings}")
    else:
        print(f"  ✓ Tous les fichiers ont les colonnes requises")

    print("=" * 70)
    print(f"  Prêt pour l'analyse walk-forward.")
    print(f"  Lancer : python scripts/walk_forward_analysis.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
