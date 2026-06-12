"""
Script d'import des données football-data.co.uk

Usage :
    cd backend
    python scripts/import_data.py
    python scripts/import_data.py --dir D:/predator_project/data/raw
    python scripts/import_data.py --download  (télécharge aussi les CSV)

Ce script :
1. Charge tous les CSV depuis data/raw/
2. Valide et nettoie les données
3. Affiche un rapport statistique complet
4. Prépare le modèle à l'entraînement
"""

import sys
import argparse
import logging
from pathlib import Path

# Setup path
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("predator.import")


def download_csvs(raw_dir: str, seasons=None, leagues=None):
    """Télécharge les CSV depuis football-data.co.uk."""
    import urllib.request

    if seasons is None:
        seasons = ["2122", "2223", "2324"]
    if leagues is None:
        leagues = ["E0", "F1", "D1", "SP1", "I1"]

    league_names = {
        "E0": "Premier League", "F1": "Ligue 1", "D1": "Bundesliga",
        "SP1": "La Liga", "I1": "Serie A", "E1": "Championship",
        "D2": "2. Bundesliga", "SP2": "La Liga 2", "N1": "Eredivisie",
    }

    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    downloaded, failed = 0, 0

    for season in seasons:
        for league in leagues:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            dest = Path(raw_dir) / f"{league}_{season}.csv"

            if dest.exists():
                logger.info(f"✓ Déjà présent: {league_names.get(league, league)} {season}")
                downloaded += 1
                continue

            try:
                urllib.request.urlretrieve(url, str(dest))
                size = dest.stat().st_size // 1024
                logger.info(f"✓ Téléchargé: {league_names.get(league, league)} {season} ({size} KB)")
                downloaded += 1
            except Exception as e:
                logger.warning(f"✗ Échec: {league} {season} — {e}")
                failed += 1

    logger.info(f"Téléchargement: {downloaded} OK, {failed} échecs")


def run_import(raw_dir: str) -> dict:
    """Charge et analyse les données CSV."""
    from data.real_data_loader import RealDataLoader

    logger.info(f"=== Import données depuis: {raw_dir} ===")
    df = RealDataLoader.load_multiple_csvs(raw_dir)

    if df.empty:
        logger.error("Aucune donnée chargée. Vérifiez le répertoire et les CSV.")
        return {}

    summary = RealDataLoader.get_summary(df)

    print("\n" + "="*60)
    print("  RAPPORT D'IMPORT — Predator Brain")
    print("="*60)
    print(f"  Total matchs     : {summary['total_matches']:,}")
    print(f"  Période          : {summary['date_from']} → {summary['date_to']}")
    print(f"  Équipes uniques  : {summary['teams']}")
    print(f"  Championnats     : {', '.join(summary['leagues'])}")
    print(f"  Saisons          : {', '.join(summary['seasons'])}")
    print()
    print(f"  Victoire domicile: {summary['home_win_rate']}%")
    print(f"  Match nul        : {summary['draw_rate']}%")
    print(f"  Victoire extérn. : {summary['away_win_rate']}%")
    print(f"  Over 2.5         : {summary['over_25_rate']}%")
    print(f"  BTTS             : {summary['btts_rate']}%")
    print(f"  Moy. buts/match  : {summary['avg_goals']}")
    print(f"  Cotes Bet365     : {'✓ OUI' if summary['has_odds_b365'] else '✗ NON'}")
    print(f"  Cotes Pinnacle   : {'✓ OUI' if summary['has_odds_ps'] else '✗ NON'}")
    print("="*60)

    # Valider les données
    issues = []
    if summary['total_matches'] < 500:
        issues.append(f"⚠️  Seulement {summary['total_matches']} matchs — recommandé: 2000+")
    if not summary['has_odds_b365']:
        issues.append("⚠️  Pas de cotes Bet365 — le backtesting sera limité")
    if summary['home_win_rate'] and not (40 < summary['home_win_rate'] < 55):
        issues.append(f"⚠️  Taux de victoire domicile inhabituel: {summary['home_win_rate']}%")

    if issues:
        print("\nAvertissements :")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ Données valides et prêtes pour l'entraînement")

    print()
    return summary


def train_model(raw_dir: str):
    """Entraîne le modèle Dixon-Coles sur les données importées."""
    from app.core.model_registry import registry

    logger.info("=== Entraînement du modèle Dixon-Coles ===")
    result = registry.train_from_csv(raw_dir)

    if result["success"]:
        print(f"\n✅ Modèle entraîné avec succès !")
        print(f"   {result['n_matches']:,} matchs utilisés")
        print(f"   {result['n_teams']} équipes")
        print(f"   Championnats: {', '.join(result['leagues'][:5])}")

        # Tester une prédiction
        if result['n_teams'] > 0:
            dc = registry.dc
            teams = dc.teams_[:2]
            if len(teams) >= 2:
                pred = registry.predict(teams[0], teams[1])
                print(f"\n   Test: {teams[0]} vs {teams[1]}")
                print(f"   → {pred['prob_home']:.0%} / {pred['prob_draw']:.0%} / {pred['prob_away']:.0%}")
                print(f"   → dc_known: {pred['dc_known']}")
    else:
        print(f"\n❌ Entraînement échoué: {result.get('error')}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import données Predator Brain")
    parser.add_argument("--dir",      default=None,  help="Répertoire CSV (défaut: ../data/raw/)")
    parser.add_argument("--download", action="store_true", help="Télécharger les CSV d'abord")
    parser.add_argument("--train",    action="store_true", help="Entraîner le modèle après import")
    parser.add_argument("--seasons",  nargs="+", default=["2122", "2223", "2324"],
                        help="Saisons à télécharger ex. 2223 2324")
    parser.add_argument("--leagues",  nargs="+", default=["E0", "F1", "D1", "SP1", "I1"],
                        help="Ligues ex. E0 F1 D1 SP1 I1")
    args = parser.parse_args()

    raw_dir = args.dir or str(Path(_BACKEND).parent / "data" / "raw")

    if args.download:
        download_csvs(raw_dir, seasons=args.seasons, leagues=args.leagues)

    summary = run_import(raw_dir)

    if args.train and summary:
        train_model(raw_dir)
    elif summary:
        print("Lancez avec --train pour entraîner le modèle, ou utilisez l'endpoint /predictions/retrain")
