"""
Value Betting Engine — Predator Brain

Moteur de détection des value bets inspiré de Trademate Sports / RebelBetting.
Analyse les cotes de plusieurs bookmakers, calcule l'edge contre le modèle
et filtre les paris mathématiquement rentables à long terme.

Logique:
  1. Charger les cotes (live ou historiques)
  2. Calculer la probabilité "sharp" du marché (cote Pinnacle sans marge)
  3. Calculer la probabilité du modèle Dixon-Coles + ensemble
  4. Comparer → Edge = prob_modèle × cote_bm - 1
  5. Filtrer edge > seuil + confiance > seuil + pas de signal adverse
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np

logger = logging.getLogger("predator.value_engine")


# ─── Structures de données ────────────────────────────────────────────────────

@dataclass
class OddsSnapshot:
    """Snapshot de cotes pour un marché et un bookmaker."""
    bookmaker: str
    market: str          # "1X2_H", "1X2_D", "1X2_A", "OU25_O", "OU25_U", "BTTS_Y", etc.
    odds: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MarketAnalysis:
    """Analyse d'un marché pour un match."""
    match_id: str
    home_team: str
    away_team: str
    market: str
    selection: str

    # Cotes
    best_bookmaker_odds: float
    best_bookmaker: str
    avg_market_odds: float
    pinnacle_odds: Optional[float]

    # Probabilités
    prob_model: float       # Probabilité du modèle Predator Brain
    prob_sharp: float       # Probabilité "vraie" du marché (Pinnacle sans marge)
    prob_bm_implied: float  # Probabilité implicite bookmaker (avec marge)

    # Edge
    edge_vs_model: float    # Edge contre le modèle (prob_model × cote - 1)
    edge_vs_sharp: float    # Edge contre Pinnacle (prob_sharp × cote - 1)

    # Qualité
    is_value: bool
    value_rating: str       # "FORT" / "BON" / "FAIBLE"
    confidence: float       # 0-1
    kelly_fraction: float   # Mise Kelly recommandée (fraction)
    recommended_stake_pct: float  # % bankroll recommandé

    # Explications
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Méta
    detected_at: datetime = field(default_factory=datetime.utcnow)
    match_date: Optional[datetime] = None


# ─── Calculs fondamentaux ─────────────────────────────────────────────────────

def remove_bookmaker_margin(
    odds_h: float, odds_d: float, odds_a: float
) -> Tuple[float, float, float]:
    """
    Retire la marge bookmaker des cotes 1X2 (normalisation).
    Retourne les probabilités "vraies" implicites.

    Formule: prob_true_i = (1/odds_i) / sum(1/odds_j)
    """
    if any(o <= 0 for o in [odds_h, odds_d, odds_a]):
        return 0.46, 0.26, 0.28  # fallback historique

    overround = 1/odds_h + 1/odds_d + 1/odds_a
    if overround <= 0:
        return 0.46, 0.26, 0.28

    p_h = (1/odds_h) / overround
    p_d = (1/odds_d) / overround
    p_a = (1/odds_a) / overround
    return p_h, p_d, p_a


def compute_edge(prob_model: float, bookmaker_odds: float) -> float:
    """
    Edge = prob_modèle × cote_bm - 1

    Si > 0 → expected value positive → value bet
    Si < 0 → pari défavorable mathématiquement
    """
    if bookmaker_odds <= 1.0 or prob_model <= 0:
        return -1.0
    return prob_model * bookmaker_odds - 1.0


def kelly_criterion(
    prob_win: float,
    odds: float,
    fraction: float = 0.25,
    max_pct: float = 0.05,
) -> float:
    """
    Mise optimale selon le critère de Kelly fractionné.

    K = (prob × odds - 1) / (odds - 1) × fraction
    Capped à max_pct de la bankroll.

    Args:
        prob_win: Probabilité estimée de gagner
        odds: Cote décimale
        fraction: Fraction Kelly (0.25 = quart-Kelly, conservateur)
        max_pct: Mise maximum en % de la bankroll (5%)
    """
    if odds <= 1.01 or prob_win <= 0:
        return 0.0

    b = odds - 1  # gain net par unité misée
    q = 1 - prob_win

    # Kelly complet
    kelly_full = (b * prob_win - q) / b if b > 0 else 0.0

    if kelly_full <= 0:
        return 0.0

    # Kelly fractionné
    stake = kelly_full * fraction
    return round(min(stake, max_pct), 4)


def classify_value(edge_pct: float, confidence: float) -> str:
    """Classifie la force d'une value bet."""
    if edge_pct >= 10 and confidence >= 0.65:
        return "FORT"
    elif edge_pct >= 5 and confidence >= 0.55:
        return "BON"
    elif edge_pct >= 3:
        return "FAIBLE"
    else:
        return "NONE"


# ─── Moteur principal ─────────────────────────────────────────────────────────

class ValueBettingEngine:
    """
    Moteur de détection de value bets.

    Intègre:
    - Calcul d'edge contre le modèle
    - Utilisation des cotes Pinnacle comme référence "sharp"
    - Calcul Kelly fractionné
    - Génération d'explications lisibles
    - Alertes sur risques cachés
    """

    # Bookmakers "sharp" reconnus (leurs cotes sont les plus efficientes)
    SHARP_BOOKS = {"pinnacle", "sbo", "betfair_exchange", "betfair", "matchbook"}

    # Bookmakers soft (marges élevées, limitent les gagnants)
    SOFT_BOOKS = {"bet365", "bwin", "unibet", "william_hill", "betway",
                  "1xbet", "parimatch", "betking"}

    def __init__(
        self,
        min_edge: float = 0.03,          # 3% edge minimum
        min_confidence: float = 0.50,    # 50% confiance minimum
        kelly_fraction: float = 0.25,    # Quart-Kelly (conservateur)
        max_stake_pct: float = 0.05,     # 5% bankroll max
        min_odds: float = 1.30,          # Cote min (éviter les "certitudes")
        max_odds: float = 15.0,          # Cote max (éviter l'aléatoire pur)
    ):
        self.min_edge        = min_edge
        self.min_confidence  = min_confidence
        self.kelly_fraction  = kelly_fraction
        self.max_stake_pct   = max_stake_pct
        self.min_odds        = min_odds
        self.max_odds        = max_odds

    def analyze_match(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        model_probs: Dict[str, float],       # {"home": 0.52, "draw": 0.24, "away": 0.24, "over_25": 0.58, ...}
        bookmaker_odds: Dict[str, Dict[str, float]],  # {"pinnacle": {"home": 2.10, ...}, "bet365": {...}}
        match_date: Optional[datetime] = None,
        recent_form_home: float = 0.5,
        recent_form_away: float = 0.5,
        n_injuries_home: int = 0,
        n_injuries_away: int = 0,
        is_important_match: bool = False,
    ) -> List[MarketAnalysis]:
        """
        Analyse complète d'un match — retourne toutes les value bets trouvées.

        Args:
            model_probs: Probabilités estimées par Predator Brain
                         Clés: "home", "draw", "away", "over_15", "under_15",
                               "over_25", "under_25", "over_35", "under_35",
                               "btts_yes", "btts_no", "1X", "X2", "12"
            bookmaker_odds: Dict bookmaker → {market → cote}
                            market format: "home", "draw", "away", "over_25", etc.
        """
        results = []

        # Consolider les cotes (best odds par marché)
        best_odds, avg_odds, sharp_odds = self._consolidate_odds(bookmaker_odds)

        # Probabilités sharp (Pinnacle sans marge si disponible)
        sharp_probs = self._compute_sharp_probs(sharp_odds)

        # Analyser chaque marché
        markets_to_check = list(model_probs.keys())

        for market in markets_to_check:
            prob_model = model_probs.get(market)
            if prob_model is None or prob_model <= 0.01:
                continue

            bm_odds_for_market = best_odds.get(market)
            if not bm_odds_for_market:
                continue

            bm_odds_val, best_bm_name = bm_odds_for_market

            # Vérifier les bornes de cotes
            if not (self.min_odds <= bm_odds_val <= self.max_odds):
                continue

            # Edge principal (contre notre modèle)
            edge = compute_edge(prob_model, bm_odds_val)

            # Edge contre Pinnacle (le plus fiable)
            sharp_prob = sharp_probs.get(market, prob_model)
            edge_sharp = compute_edge(sharp_prob, bm_odds_val)

            # Probabilité implicite bookmaker (avec marge)
            prob_bm_implied = 1 / bm_odds_val

            # Confiance
            confidence = self._compute_confidence(
                prob_model=prob_model,
                sharp_prob=sharp_prob,
                market=market,
                recent_form_home=recent_form_home,
                recent_form_away=recent_form_away,
                n_injuries_home=n_injuries_home,
                n_injuries_away=n_injuries_away,
            )

            # Value check
            is_value = (
                edge >= self.min_edge and
                confidence >= self.min_confidence
            )

            if not is_value:
                continue

            # Kelly
            kelly_pct = kelly_criterion(prob_model, bm_odds_val, self.kelly_fraction, self.max_stake_pct)

            # Rating
            rating = classify_value(edge * 100, confidence)
            if rating == "NONE":
                continue

            # Explications
            reasons, warnings = self._generate_explanation(
                market=market,
                home_team=home_team,
                away_team=away_team,
                prob_model=prob_model,
                sharp_prob=sharp_prob,
                bm_odds=bm_odds_val,
                edge=edge,
                recent_form_home=recent_form_home,
                recent_form_away=recent_form_away,
                n_injuries_home=n_injuries_home,
                n_injuries_away=n_injuries_away,
                is_important_match=is_important_match,
            )

            results.append(MarketAnalysis(
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
                market=self._market_label(market),
                selection=market,
                best_bookmaker_odds=round(bm_odds_val, 3),
                best_bookmaker=best_bm_name,
                avg_market_odds=round(avg_odds.get(market, bm_odds_val), 3),
                pinnacle_odds=sharp_odds.get(market),
                prob_model=round(prob_model, 4),
                prob_sharp=round(sharp_prob, 4),
                prob_bm_implied=round(prob_bm_implied, 4),
                edge_vs_model=round(edge * 100, 2),
                edge_vs_sharp=round(edge_sharp * 100, 2),
                is_value=is_value,
                value_rating=rating,
                confidence=round(confidence, 3),
                kelly_fraction=round(kelly_pct * 100, 2),
                recommended_stake_pct=round(kelly_pct * 100, 2),
                reasons=reasons,
                warnings=warnings,
                detected_at=datetime.utcnow(),
                match_date=match_date,
            ))

        return sorted(results, key=lambda x: -x.edge_vs_model)

    def _consolidate_odds(
        self, bookmaker_odds: Dict[str, Dict[str, float]]
    ) -> Tuple[Dict, Dict, Dict]:
        """
        Consolide les cotes de tous les bookmakers.
        Returns: (best_odds, avg_odds, sharp_odds)
        best_odds = {market: (best_odds_value, bookmaker_name)}
        """
        best: Dict[str, Tuple[float, str]] = {}
        sums: Dict[str, List[float]] = {}
        sharp: Dict[str, float] = {}

        for bm_name, odds_dict in bookmaker_odds.items():
            for market, odds_val in odds_dict.items():
                if not odds_val or odds_val <= 1.01:
                    continue

                # Best odds (la plus haute = la plus favorable au parieur)
                if market not in best or odds_val > best[market][0]:
                    best[market] = (odds_val, bm_name)

                # Pour la moyenne
                if market not in sums:
                    sums[market] = []
                sums[market].append(odds_val)

                # Sharp odds (Pinnacle en priorité)
                if bm_name.lower() in self.SHARP_BOOKS:
                    if market not in sharp or odds_val < sharp[market]:
                        sharp[market] = odds_val

        avg = {m: float(np.mean(v)) for m, v in sums.items()}
        return best, avg, sharp

    def _compute_sharp_probs(self, sharp_odds: Dict[str, float]) -> Dict[str, float]:
        """
        Retire la marge Pinnacle pour obtenir les probabilités "vraies" du marché.
        Pinnacle a ~2% de marge → probas très proches des vraies valeurs.
        """
        sharp_probs: Dict[str, float] = {}

        # Pour 1X2, retire la marge ensemble
        if all(k in sharp_odds for k in ["home", "draw", "away"]):
            p_h, p_d, p_a = remove_bookmaker_margin(
                sharp_odds["home"], sharp_odds["draw"], sharp_odds["away"]
            )
            sharp_probs["home"] = p_h
            sharp_probs["draw"] = p_d
            sharp_probs["away"] = p_a

        # Pour les autres marchés (O/U, BTTS) : correction simple
        for market in ["over_15", "under_15", "over_25", "under_25", "over_35", "under_35"]:
            opp = market.replace("over", "under") if "over" in market else market.replace("under", "over")
            if market in sharp_odds and opp in sharp_odds:
                p, _ = remove_bookmaker_margin(sharp_odds[market], 999, sharp_odds[opp])
                # Approximation: p_market ≈ (1/odds) / overround_paire
                overround = 1/sharp_odds[market] + 1/sharp_odds[opp]
                if overround > 0:
                    sharp_probs[market] = (1/sharp_odds[market]) / overround
            elif market in sharp_odds:
                sharp_probs[market] = round(1 / sharp_odds[market], 4)

        for market in ["btts_yes", "btts_no"]:
            if "btts_yes" in sharp_odds and "btts_no" in sharp_odds:
                overround = 1/sharp_odds["btts_yes"] + 1/sharp_odds["btts_no"]
                if overround > 0 and market in sharp_odds:
                    sharp_probs[market] = (1/sharp_odds[market]) / overround
            elif market in sharp_odds:
                sharp_probs[market] = round(1 / sharp_odds[market], 4)

        return sharp_probs

    def _compute_confidence(
        self,
        prob_model: float,
        sharp_prob: float,
        market: str,
        recent_form_home: float,
        recent_form_away: float,
        n_injuries_home: int,
        n_injuries_away: int,
    ) -> float:
        """
        Confiance composite basée sur plusieurs facteurs.

        Facteurs positifs:
        - Accord entre modèle et Pinnacle
        - Probabilité élevée (marché clair)
        - Forme favorable

        Facteurs négatifs:
        - Désaccord fort avec Pinnacle
        - Blessures importantes
        - Marché sur les nuls (difficile à prédire)
        """
        base = prob_model

        # Accord avec Pinnacle (signal fort)
        if sharp_prob > 0:
            agreement = 1 - abs(prob_model - sharp_prob)
            base = 0.6 * prob_model + 0.4 * agreement

        # Pénalité pour les nuls (marché le plus difficile)
        if market == "draw":
            base *= 0.85

        # Bonus forme (si domicile en grande forme)
        form_bonus = (recent_form_home - 0.5) * 0.1
        base = min(0.95, base + form_bonus)

        # Pénalité blessures
        injury_penalty = min(0.15, (n_injuries_home + n_injuries_away) * 0.03)
        base = max(0.10, base - injury_penalty)

        return round(base, 3)

    def _generate_explanation(
        self, market: str, home_team: str, away_team: str,
        prob_model: float, sharp_prob: float, bm_odds: float, edge: float,
        recent_form_home: float, recent_form_away: float,
        n_injuries_home: int, n_injuries_away: int,
        is_important_match: bool,
    ) -> Tuple[List[str], List[str]]:
        """Génère les raisons et avertissements pour une value bet."""
        reasons = []
        warnings = []

        # Raisons positives
        reasons.append(f"Edge mathématique de +{edge*100:.1f}% sur ce marché")

        if prob_model > 0.60:
            reasons.append(f"Probabilité modèle élevée ({prob_model:.0%})")

        if sharp_prob > 0 and abs(prob_model - sharp_prob) < 0.05:
            reasons.append("Accord entre notre modèle et le marché sharp (Pinnacle)")
        elif sharp_prob > 0 and prob_model > sharp_prob + 0.05:
            reasons.append(f"Notre modèle estime {prob_model:.0%} vs {sharp_prob:.0%} pour Pinnacle")

        if recent_form_home > 0.65 and market in ["home", "1X", "12", "over_25", "btts_yes"]:
            reasons.append(f"{home_team} en excellente forme récente")
        if recent_form_away < 0.35 and market in ["home", "1X", "12"]:
            reasons.append(f"{away_team} en mauvaise forme récente")

        cote_juste = round(1 / prob_model, 2)
        reasons.append(f"Cote juste estimée: {cote_juste} vs bookmaker: {bm_odds}")

        # Avertissements
        if market == "draw":
            warnings.append("Le nul est le résultat le plus difficile à prédire (variance élevée)")

        if bm_odds > 5.0:
            warnings.append(f"Cote élevée ({bm_odds}) → risque de perte élevé malgré la value")

        if n_injuries_home > 1:
            warnings.append(f"{home_team} a {n_injuries_home} blessés importants")
        if n_injuries_away > 1:
            warnings.append(f"{away_team} a {n_injuries_away} blessés importants")

        if is_important_match:
            warnings.append("Match à fort enjeu — résultat atypique possible (motivation, pression)")

        if edge < 0.05:
            warnings.append("Edge faible (<5%) — mise très réduite recommandée")

        return reasons, warnings

    def _market_label(self, market: str) -> str:
        LABELS = {
            "home": "1X2 — Domicile",
            "draw": "1X2 — Nul",
            "away": "1X2 — Extérieur",
            "1X":   "Double Chance 1X",
            "X2":   "Double Chance X2",
            "12":   "Double Chance 12",
            "over_15": "O/U 1.5 — Over",
            "under_15": "O/U 1.5 — Under",
            "over_25": "O/U 2.5 — Over",
            "under_25": "O/U 2.5 — Under",
            "over_35": "O/U 3.5 — Over",
            "under_35": "O/U 3.5 — Under",
            "btts_yes": "BTTS — Oui",
            "btts_no":  "BTTS — Non",
        }
        return LABELS.get(market, market)

    def scan_portfolio(
        self,
        matches: List[Dict],
        top_n: int = 20,
    ) -> List[MarketAnalysis]:
        """
        Scanne un portefeuille de matchs et retourne les meilleures value bets.

        Args:
            matches: Liste de dicts avec clés: match_id, home_team, away_team,
                     model_probs, bookmaker_odds, match_date, ...
            top_n: Nombre maximum de value bets à retourner

        Returns:
            Meilleures value bets triées par edge décroissant
        """
        all_vbs: List[MarketAnalysis] = []

        for match in matches:
            try:
                vbs = self.analyze_match(
                    match_id=match.get("match_id", ""),
                    home_team=match.get("home_team", ""),
                    away_team=match.get("away_team", ""),
                    model_probs=match.get("model_probs", {}),
                    bookmaker_odds=match.get("bookmaker_odds", {}),
                    match_date=match.get("match_date"),
                    recent_form_home=match.get("form_home", 0.5),
                    recent_form_away=match.get("form_away", 0.5),
                    n_injuries_home=match.get("injuries_home", 0),
                    n_injuries_away=match.get("injuries_away", 0),
                    is_important_match=match.get("is_important", False),
                )
                all_vbs.extend(vbs)
            except Exception as e:
                logger.warning(f"[VALUE] Erreur match {match.get('match_id')}: {e}")

        # Trier par edge et dédupliquer par match+market
        seen = set()
        unique_vbs = []
        for vb in sorted(all_vbs, key=lambda x: -x.edge_vs_model):
            key = f"{vb.match_id}_{vb.selection}"
            if key not in seen:
                seen.add(key)
                unique_vbs.append(vb)

        return unique_vbs[:top_n]


# ─── Analyse de mouvement de cotes ────────────────────────────────────────────

class OddsMovementDetector:
    """
    Détecte les mouvements suspects de cotes (smart money signal).

    Signaux surveillés:
    - Baisse rapide d'une cote (argent sharp entrant)
    - Hausse sur un favori (surpression publique)
    - Divergence entre bookmakers
    - Mouvement contraire à la tendance publique
    """

    def __init__(self, significant_drop_pct: float = 5.0):
        self.significant_drop_pct = significant_drop_pct

    def analyze_movement(
        self,
        opening_odds: Dict[str, float],
        current_odds: Dict[str, float],
        bookmaker: str = "avg",
    ) -> Dict:
        """
        Compare les cotes d'ouverture aux cotes actuelles.

        Returns:
            {
              "moves": [{"market": "home", "open": 2.10, "current": 1.85, "pct": -11.9, "signal": "SHARP_MONEY"}],
              "overall_signal": "WATCH" / "SHARP" / "NEUTRAL",
              "smart_money_side": "home" / "away" / None,
            }
        """
        moves = []
        sharp_signals = []

        for market in opening_odds:
            if market not in current_odds:
                continue

            open_odd = opening_odds[market]
            curr_odd = current_odds[market]

            if open_odd <= 0 or curr_odd <= 0:
                continue

            pct_change = (curr_odd - open_odd) / open_odd * 100

            signal = "NEUTRAL"
            if pct_change <= -self.significant_drop_pct:
                signal = "SHARP_MONEY"  # Argent sharp → cote chute
                sharp_signals.append(market)
            elif pct_change >= self.significant_drop_pct:
                signal = "PUBLIC_MONEY"  # Argent public → cote monte
            elif abs(pct_change) >= 3:
                signal = "MODERATE_MOVE"

            moves.append({
                "market":    market,
                "open_odds": open_odd,
                "current_odds": curr_odd,
                "pct_change": round(pct_change, 2),
                "signal":    signal,
            })

        # Signal global
        if len(sharp_signals) >= 2:
            overall = "SHARP"
        elif sharp_signals:
            overall = "WATCH"
        else:
            overall = "NEUTRAL"

        # Côté favorisé par l'argent sharp
        smart_money_side = sharp_signals[0] if sharp_signals else None

        return {
            "moves":            moves,
            "overall_signal":   overall,
            "smart_money_side": smart_money_side,
            "sharp_markets":    sharp_signals,
        }
