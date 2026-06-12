"""
CLV Auto-Closer — Predator Brain V2

Récupère automatiquement les cotes de fermeture via The Odds API
pour tous les paris en attente, puis calcule le CLV final.

Usage:
    from app.services.engines.clv_auto_closer import CLVAutoCloser
    closer = CLVAutoCloser()
    updated = closer.run()  # met à jour tous les paris pending

Planning recommandé :
    - Lancer 1h avant le coup d'envoi de chaque match
    - Lancer juste après la fermeture des cotes (10 min avant KO)
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("predator.clv_auto_closer")

# Pinnacle sportId / bookmakers de référence pour la cote de fermeture
CLOSING_LINE_BOOKMAKERS = [
    "pinnacle",
    "betfair_ex_eu",
    "pinnacle_live",
]

MARKET_TO_ODDSAPI = {
    "1X2_H":    ("h2h",   "home"),
    "1X2_D":    ("h2h",   "draw"),
    "1X2_A":    ("h2h",   "away"),
    "OU25_O":   ("totals", "Over"),
    "OU25_U":   ("totals", "Under"),
    "BTTS_Y":   ("h2h",   None),   # BTTS non standard sur The Odds API
    "BTTS_N":   ("h2h",   None),
}

SPORT_KEYS = {
    "Premier League":  "soccer_epl",
    "Ligue 1":         "soccer_france_ligue1",
    "La Liga":         "soccer_spain_la_liga",
    "Bundesliga":      "soccer_germany_bundesliga",
    "Serie A":         "soccer_italy_serie_a",
}


class CLVAutoCloser:
    """
    Fermeture automatique du CLV via The Odds API.

    Flux :
    1. Lire les paris enregistrés (CLV engine) sans cote de fermeture
    2. Pour chaque pari, requêter The Odds API avec le bon sport_key
    3. Trouver la cote de fermeture Pinnacle (ou la meilleure disponible)
    4. Mettre à jour le pari avec la cote de fermeture et le CLV calculé
    5. Sauvegarder dans clv_closing_history.json
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")
        self.base_url = "https://api.the-odds-api.com/v4"
        self._history_file = Path(__file__).resolve().parents[4] / "data" / "clv_closing_history.json"
        self._history: Dict[str, dict] = self._load_history()

    def _load_history(self) -> Dict[str, dict]:
        if self._history_file.exists():
            with open(self._history_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_history(self):
        self._history_file.parent.mkdir(exist_ok=True)
        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump(self._history, f, indent=2, ensure_ascii=False, default=str)

    def _get_sport_key(self, league: str) -> str:
        return SPORT_KEYS.get(league, "soccer_epl")

    def _fetch_odds(self, sport_key: str, event_id: Optional[str] = None) -> List[dict]:
        """Récupère les cotes depuis The Odds API."""
        if not self.api_key:
            logger.warning("[CLV-Closer] Pas de ODDS_API_KEY — skip fetch")
            return []

        params = {
            "apiKey":   self.api_key,
            "regions":  "eu",
            "markets":  "h2h,totals",
            "oddsFormat": "decimal",
            "bookmakers": ",".join(CLOSING_LINE_BOOKMAKERS),
        }
        try:
            if event_id:
                url = f"{self.base_url}/sports/{sport_key}/events/{event_id}/odds"
            else:
                url = f"{self.base_url}/sports/{sport_key}/odds"

            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json() if isinstance(resp.json(), list) else [resp.json()]
        except Exception as e:
            logger.warning(f"[CLV-Closer] Erreur fetch odds ({sport_key}): {e}")
            return []

    def _find_closing_odd(self, events: List[dict], home: str, away: str,
                          market_key: str, selection: str) -> Optional[float]:
        """
        Cherche la cote de fermeture d'une sélection dans les events.
        Priorité : Pinnacle > betfair_ex_eu > première source disponible.
        """
        for event in events:
            ev_home = event.get("home_team", "").lower()
            ev_away = event.get("away_team", "").lower()
            if home.lower() not in ev_home and away.lower() not in ev_away:
                continue

            # Trier les bookmakers par priorité
            bookmakers = event.get("bookmakers", [])
            bm_sorted = sorted(
                bookmakers,
                key=lambda b: CLOSING_LINE_BOOKMAKERS.index(b["key"])
                if b["key"] in CLOSING_LINE_BOOKMAKERS else 99
            )

            for bm in bm_sorted:
                for market in bm.get("markets", []):
                    if market.get("key") != market_key:
                        continue
                    for outcome in market.get("outcomes", []):
                        if outcome.get("name", "").lower() == selection.lower():
                            return float(outcome["price"])
        return None

    def fetch_closing_for_bet(self, home: str, away: str, league: str,
                               market: str, match_date: Optional[str] = None) -> Optional[float]:
        """Récupère la cote de fermeture pour un pari spécifique."""
        sport_key = self._get_sport_key(league)
        oddsapi_market, selection = MARKET_TO_ODDSAPI.get(market, ("h2h", "home"))

        if not selection:
            logger.debug(f"[CLV-Closer] Marché {market} non supporté par The Odds API")
            return None

        events = self._fetch_odds(sport_key)
        if not events:
            return None

        closing = self._find_closing_odd(events, home, away, oddsapi_market, selection)
        if closing:
            logger.info(f"[CLV-Closer] {home} vs {away} | {market} | closing={closing:.3f}")
        return closing

    def update_single(self, bet_id: str, home: str, away: str, league: str,
                      market: str, odds_taken: float,
                      match_date: Optional[str] = None) -> dict:
        """
        Met à jour la cote de fermeture et calcule le CLV pour un pari.
        Retourne le résultat.
        """
        closing = self.fetch_closing_for_bet(home, away, league, market, match_date)

        if closing is None:
            return {
                "bet_id":       bet_id,
                "status":       "closing_not_found",
                "clv_pct":      None,
                "clv_signal":   None,
            }

        # CLV = (cote_prise / cote_fermeture - 1) × 100
        clv_pct = (odds_taken / closing - 1) * 100

        # Signal
        if clv_pct >= 8:     signal = "EXCELLENT"
        elif clv_pct >= 3:   signal = "GOOD"
        elif clv_pct >= -2:  signal = "NEUTRAL"
        elif clv_pct >= -8:  signal = "BAD"
        else:                signal = "TERRIBLE"

        result = {
            "bet_id":        bet_id,
            "status":        "updated",
            "odds_taken":    round(odds_taken, 3),
            "odds_closing":  round(closing, 3),
            "clv_pct":       round(clv_pct, 2),
            "clv_signal":    signal,
            "updated_at":    datetime.utcnow().isoformat(),
        }

        # Sauvegarder dans l'historique
        self._history[bet_id] = result
        self._save_history()

        return result

    def run(self) -> List[dict]:
        """
        Met à jour tous les paris en attente via le CLV engine.
        Appelé automatiquement avant chaque calcul de rapport.
        """
        try:
            from app.core.model_registry import registry
            pending = [
                r for r in registry.clv_engine.records.values()
                if r.odds_closing is None and r.result_actual is None
            ]
        except Exception as e:
            logger.warning(f"[CLV-Closer] Registry non disponible: {e}")
            return []

        if not pending:
            logger.info("[CLV-Closer] Aucun pari en attente de closing")
            return []

        updated = []
        logger.info(f"[CLV-Closer] {len(pending)} paris en attente de closing")

        for rec in pending:
            # Vérifier que le match est proche (±2h de l'heure courante ou passé)
            now = datetime.utcnow()
            match_dt = rec.match_date
            if match_dt > now + timedelta(hours=2):
                logger.debug(f"[CLV-Closer] {rec.bet_id}: match trop loin ({match_dt}), skip")
                continue

            result = self.update_single(
                bet_id=rec.bet_id,
                home=rec.home_team,
                away=rec.away_team,
                league=rec.league,
                market=rec.market,
                odds_taken=rec.odds_taken,
                match_date=match_dt.isoformat(),
            )

            if result["status"] == "updated":
                # Mettre à jour le CLV engine en mémoire
                try:
                    registry.clv_engine.update_closing_odds(rec.bet_id, result["odds_closing"])
                    updated.append(result)
                    logger.info(
                        f"[CLV-Closer] ✓ {rec.bet_id}: "
                        f"CLV={result['clv_pct']:+.1f}% ({result['clv_signal']})"
                    )
                except Exception as e:
                    logger.warning(f"[CLV-Closer] Erreur update engine pour {rec.bet_id}: {e}")

        logger.info(f"[CLV-Closer] {len(updated)}/{len(pending)} paris mis à jour")
        return updated

    def get_history(self) -> List[dict]:
        return list(self._history.values())

    def stats(self) -> dict:
        """Statistiques sur les CLV calculés."""
        records = list(self._history.values())
        if not records:
            return {"n": 0, "avg_clv": None, "pct_positive": None}

        clvs = [r["clv_pct"] for r in records if r.get("clv_pct") is not None]
        if not clvs:
            return {"n": len(records), "avg_clv": None, "pct_positive": None}

        pos = sum(1 for c in clvs if c > 0)
        return {
            "n":           len(clvs),
            "avg_clv_pct": round(sum(clvs) / len(clvs), 2),
            "median_clv":  round(sorted(clvs)[len(clvs) // 2], 2),
            "pct_positive": round(pos / len(clvs) * 100, 1),
            "signals": {
                "EXCELLENT": sum(1 for r in records if r.get("clv_signal") == "EXCELLENT"),
                "GOOD":      sum(1 for r in records if r.get("clv_signal") == "GOOD"),
                "NEUTRAL":   sum(1 for r in records if r.get("clv_signal") == "NEUTRAL"),
                "BAD":       sum(1 for r in records if r.get("clv_signal") == "BAD"),
                "TERRIBLE":  sum(1 for r in records if r.get("clv_signal") == "TERRIBLE"),
            }
        }


# Singleton
_closer = CLVAutoCloser()


def get_auto_closer() -> CLVAutoCloser:
    return _closer
