"""
Ticket Generator — Predator Brain

Génère des tickets combinés intelligents à partir des value bets détectées.
Inspiré de la logique de construction de paliers des pros.

Règles fondamentales:
  1. Ne jamais mélanger des paris corrélés (ex: domicile + BTTS du même match)
  2. Limiter à 6 sélections max (au-delà la variance devient ingérable)
  3. Vérifier la cote totale vs la probabilité réelle
  4. Ajuster la mise selon le Kelly des combinés

Types de tickets:
  - SAFE:     2-3 sélections, edge fort, cote 2.5-5
  - BALANCED: 3-4 sélections, bon mix, cote 5-12
  - RISKY:    4-5 sélections, value bets, cote 12-40
  - JACKPOT:  5-6 sélections, cote 40+
  - CUSTOM:   Défini par l'utilisateur
"""

import logging
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import numpy as np

logger = logging.getLogger("predator.tickets")


class TicketType(str, Enum):
    SAFE     = "safe"
    BALANCED = "balanced"
    RISKY    = "risky"
    JACKPOT  = "jackpot"
    CUSTOM   = "custom"


@dataclass
class TicketLeg:
    """Une sélection dans un ticket combiné."""
    match_id: str
    home_team: str
    away_team: str
    league: str
    market: str          # "1X2_H", "OU25_O", "BTTS_Y", etc.
    market_label: str    # Label lisible
    selection: str       # "Domicile", "Over 2.5", "BTTS Oui", etc.
    bookmaker: str
    odds: float
    prob_model: float
    edge_pct: float
    confidence: float
    match_date: Optional[datetime] = None
    reasons: List[str] = field(default_factory=list)


@dataclass
class Ticket:
    """Ticket combiné avec toutes ses métriques."""
    ticket_type: TicketType
    legs: List[TicketLeg]

    # Métriques combinées
    total_odds: float           # Produit des cotes
    combined_prob: float        # Produit des probabilités modèle
    fair_odds: float            # 1 / combined_prob
    implied_edge_pct: float     # (total_odds × combined_prob - 1) × 100

    # Mise recommandée
    recommended_stake_pct: float   # % bankroll
    recommended_stake_abs: float   # Montant absolu (ex: 200 XOF pour bankroll 10k)
    potential_gain_ratio: float    # Gain potentiel × 1 unité

    # Qualité
    quality_score: float        # 0-100 (score composite)
    risk_rating: str            # "FAIBLE" / "MODÉRÉ" / "ÉLEVÉ" / "TRÈS ÉLEVÉ"
    is_recommended: bool

    # Explication IA
    summary: str
    warnings: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


# ─── Matrice de corrélation ───────────────────────────────────────────────────

# Marchés corrélés au sein d'un même match (ne jamais combiner)
CORRELATED_MARKETS = {
    "1X2_H": {"DC_1X", "DC_12"},
    "1X2_D": {"DC_1X", "DC_X2"},
    "1X2_A": {"DC_X2", "DC_12"},
    "OU25_O": {"OU35_O", "BTTS_Y"},
    "OU15_U": {"OU25_U", "OU35_U"},
}

# Corrélation inter-matchs (ex: deux grosses équipes offensives → sur-BTTS)
# Pour l'instant on l'ignore mais on l'indique dans les warnings


def compute_correlation_penalty(legs: List[TicketLeg]) -> float:
    """
    Calcule un coefficient de pénalité pour les tickets corrélés.
    0 = aucune corrélation (idéal)
    1 = très corrélé (éviter)
    """
    if len(legs) < 2:
        return 0.0

    # Penalité si même match dans plusieurs legs
    match_ids = [leg.match_id for leg in legs]
    if len(match_ids) != len(set(match_ids)):
        return 1.0  # Corrélation maximale

    # Penalité si même ligue (résultats parfois liés en fin de saison)
    leagues = [leg.league for leg in legs]
    league_diversity = len(set(leagues)) / len(leagues)
    return round(1 - league_diversity, 2)


def are_legs_compatible(leg1: TicketLeg, leg2: TicketLeg) -> bool:
    """Vérifie que deux sélections ne sont pas corrélées de manière problématique."""
    # Même match = jamais combiner
    if leg1.match_id == leg2.match_id:
        return False
    # Cote < 1.1 = sans intérêt en combo
    if leg1.odds < 1.10 or leg2.odds < 1.10:
        return False
    return True


# ─── Générateur principal ─────────────────────────────────────────────────────

class TicketGenerator:
    """
    Construit des tickets combinés intelligents à partir d'une liste de value bets.

    Algorithme:
    1. Filtrer les meilleures sélections selon le type de ticket
    2. Éliminer les sélections corrélées
    3. Calculer les métriques du combiné
    4. Évaluer la qualité
    5. Recommander une mise
    """

    # Profils de tickets
    TICKET_PROFILES = {
        TicketType.SAFE: {
            "min_legs": 2, "max_legs": 3,
            "min_odds_total": 2.5, "max_odds_total": 6.0,
            "min_edge_per_leg": 3.0,
            "min_confidence": 0.60,
            "kelly_fraction": 0.25,
            "max_stake_pct": 0.04,
            "description": "Ticket prudent — 2 à 3 sélections solides, cote 2.5 à 6",
        },
        TicketType.BALANCED: {
            "min_legs": 3, "max_legs": 5,
            "min_odds_total": 5.0, "max_odds_total": 15.0,
            "min_edge_per_leg": 2.0,
            "min_confidence": 0.55,
            "kelly_fraction": 0.15,
            "max_stake_pct": 0.02,
            "description": "Ticket équilibré — 3 à 5 sélections, cote 5 à 15",
        },
        TicketType.RISKY: {
            "min_legs": 4, "max_legs": 6,
            "min_odds_total": 10.0, "max_odds_total": 50.0,
            "min_edge_per_leg": 1.5,
            "min_confidence": 0.50,
            "kelly_fraction": 0.10,
            "max_stake_pct": 0.01,
            "description": "Ticket risqué — 4 à 6 sélections, cote 10 à 50",
        },
        TicketType.JACKPOT: {
            "min_legs": 5, "max_legs": 8,
            "min_odds_total": 40.0, "max_odds_total": 200.0,
            "min_edge_per_leg": 1.0,
            "min_confidence": 0.48,
            "kelly_fraction": 0.05,
            "max_stake_pct": 0.005,
            "description": "Jackpot — 5 à 8 sélections, cote 40+",
        },
    }

    def __init__(
        self,
        bankroll: float = 10_000.0,
        min_legs: int = 2,
        max_legs: int = 6,
    ):
        self.bankroll = bankroll
        self.min_legs = min_legs
        self.max_legs = max_legs

    def generate(
        self,
        available_bets: List[Dict],      # Liste de value bets disponibles
        ticket_type: TicketType = TicketType.BALANCED,
        n_tickets: int = 3,              # Nombre de tickets à générer
        strategy_hint: str = "",         # "high_btts", "over_goals", "home_favorites", ...
    ) -> List[Ticket]:
        """
        Génère les meilleurs tickets pour le type donné.

        Args:
            available_bets: Résultats de ValueBettingEngine.scan_portfolio()
                            ou liste de dicts avec: match_id, home_team, away_team,
                            league, market, selection, odds, prob_model, edge_pct,
                            confidence, bookmaker, match_date, reasons
            ticket_type:    Type de ticket désiré
            n_tickets:      Nombre de tickets à générer
            strategy_hint:  Filtre stratégique optionnel
        """
        profile = self.TICKET_PROFILES[ticket_type]

        # Convertir en TicketLeg
        legs_pool = self._build_legs_pool(available_bets, profile, strategy_hint)

        if len(legs_pool) < profile["min_legs"]:
            logger.warning(f"[TICKETS] Pas assez de sélections qualifiées "
                           f"({len(legs_pool)}/{profile['min_legs']} minimum)")
            return []

        # Générer les combinaisons possibles
        tickets = []
        best_combos = self._find_best_combinations(legs_pool, profile, n_tickets * 3)

        for combo in best_combos[:n_tickets]:
            ticket = self._build_ticket(combo, ticket_type, profile)
            if ticket:
                tickets.append(ticket)

        return sorted(tickets, key=lambda t: -t.quality_score)[:n_tickets]

    def generate_all_types(
        self, available_bets: List[Dict]
    ) -> Dict[str, List[Ticket]]:
        """Génère un ticket de chaque type et retourne le meilleur."""
        result = {}
        for ticket_type in [TicketType.SAFE, TicketType.BALANCED,
                             TicketType.RISKY, TicketType.JACKPOT]:
            tickets = self.generate(available_bets, ticket_type, n_tickets=1)
            result[ticket_type.value] = tickets
        return result

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_legs_pool(
        self, available_bets: List[Dict], profile: Dict, strategy_hint: str
    ) -> List[TicketLeg]:
        """Construit le pool de sélections valides pour ce type de ticket."""
        legs = []

        for bet in available_bets:
            # Filtrer par profil
            if bet.get("edge_pct", 0) < profile["min_edge_per_leg"]:
                continue
            if bet.get("confidence", 0) < profile["min_confidence"]:
                continue

            odds = bet.get("best_bookmaker_odds") or bet.get("odds", 0)
            if odds < 1.10 or odds > 15.0:
                continue

            # Filtre stratégique
            if strategy_hint and not self._matches_strategy(bet, strategy_hint):
                continue

            leg = TicketLeg(
                match_id=bet.get("match_id", ""),
                home_team=bet.get("home_team", ""),
                away_team=bet.get("away_team", ""),
                league=bet.get("league", "unknown"),
                market=bet.get("selection", ""),
                market_label=bet.get("market", ""),
                selection=self._get_selection_label(bet),
                bookmaker=bet.get("best_bookmaker") or bet.get("bookmaker", ""),
                odds=odds,
                prob_model=bet.get("prob_model", 0.5),
                edge_pct=bet.get("edge_pct", 0),
                confidence=bet.get("confidence", 0.5),
                match_date=bet.get("match_date"),
                reasons=bet.get("reasons", []),
            )
            legs.append(leg)

        # Trier par edge décroissant
        return sorted(legs, key=lambda l: -l.edge_pct)

    def _find_best_combinations(
        self,
        legs: List[TicketLeg],
        profile: Dict,
        n_combinations: int,
    ) -> List[List[TicketLeg]]:
        """Trouve les meilleures combinaisons de sélections."""
        min_l = profile["min_legs"]
        max_l = min(profile["max_legs"], len(legs), self.max_legs)

        candidates = []

        # Essayer toutes les combinaisons de taille min à max
        # (limité aux N meilleures sélections pour éviter l'explosion combinatoire)
        pool = legs[:min(25, len(legs))]  # Top 25 max

        for n in range(min_l, max_l + 1):
            for combo in itertools.combinations(pool, n):
                combo = list(combo)

                # Vérifier la compatibilité
                compatible = all(
                    are_legs_compatible(combo[i], combo[j])
                    for i in range(len(combo))
                    for j in range(i+1, len(combo))
                )
                if not compatible:
                    continue

                # Calculer les métriques
                total_odds = np.prod([leg.odds for leg in combo])
                combined_prob = np.prod([leg.prob_model for leg in combo])

                # Vérifier les bornes de cotes
                if not (profile["min_odds_total"] <= total_odds <= profile["max_odds_total"]):
                    continue

                implied_edge = combined_prob * total_odds - 1

                # Score composite (edge + confiance + diversité)
                corr_penalty = compute_correlation_penalty(combo)
                avg_confidence = np.mean([leg.confidence for leg in combo])
                avg_edge = np.mean([leg.edge_pct for leg in combo])

                score = (
                    implied_edge * 100 * 0.5 +
                    avg_confidence * 30 +
                    avg_edge * 0.3 -
                    corr_penalty * 20
                )

                candidates.append((score, total_odds, combined_prob, implied_edge, combo))

        # Trier par score décroissant
        candidates.sort(key=lambda x: -x[0])
        return [c[4] for c in candidates[:n_combinations]]

    def _build_ticket(
        self, combo: List[TicketLeg], ticket_type: TicketType, profile: Dict
    ) -> Optional[Ticket]:
        """Construit un objet Ticket à partir d'une combinaison."""
        total_odds = round(np.prod([leg.odds for leg in combo]), 2)
        combined_prob = round(np.prod([leg.prob_model for leg in combo]), 4)

        if combined_prob <= 0:
            return None

        fair_odds = round(1 / combined_prob, 2)
        implied_edge = round((total_odds * combined_prob - 1) * 100, 2)

        # Mise Kelly pour les combinés
        b = total_odds - 1
        kelly_full = max(0.0, (b * combined_prob - (1 - combined_prob)) / b) if b > 0 else 0.0
        kelly_rec = kelly_full * profile["kelly_fraction"]
        stake_pct = min(kelly_rec, profile["max_stake_pct"])
        stake_abs = round(stake_pct * self.bankroll, 2)

        # Score qualité (0-100)
        avg_confidence = float(np.mean([leg.confidence for leg in combo]))
        corr_penalty   = compute_correlation_penalty(combo)

        quality = min(100, max(0, (
            implied_edge * 3 +
            avg_confidence * 40 +
            (1 - corr_penalty) * 20 +
            min(len(combo), 5) * 4
        )))

        # Risk rating
        if total_odds > 30 or len(combo) >= 6:
            risk = "TRÈS ÉLEVÉ"
        elif total_odds > 12 or len(combo) >= 4:
            risk = "ÉLEVÉ"
        elif total_odds > 6:
            risk = "MODÉRÉ"
        else:
            risk = "FAIBLE"

        is_recommended = implied_edge > 0 and quality >= 50

        # Avertissements
        warnings = []
        if corr_penalty > 0.3:
            warnings.append("Certaines ligues sont sur-représentées dans ce ticket")
        if total_odds > 15:
            warnings.append(f"Cote totale élevée ({total_odds:.1f}) — variance très haute")
        if len(combo) > 4:
            warnings.append(f"Ticket de {len(combo)} sélections — chaque sélection supplémentaire réduit la probabilité")
        if stake_pct < 0.005:
            warnings.append("Mise très faible recommandée — ticket à risque élevé")
        if implied_edge < 0:
            warnings.append("Edge négatif — évitez ce ticket ou attendez de meilleures cotes")

        # Résumé
        selections_text = " | ".join(
            f"{leg.home_team[:8]} vs {leg.away_team[:8]}: {leg.selection}"
            for leg in combo
        )
        summary = (
            f"Ticket {ticket_type.value.upper()} — {len(combo)} sélections | "
            f"Cote: {total_odds:.2f} | Probabilité réelle: {combined_prob:.1%} | "
            f"Edge: {implied_edge:+.1f}% | {selections_text}"
        )

        return Ticket(
            ticket_type=ticket_type,
            legs=combo,
            total_odds=total_odds,
            combined_prob=combined_prob,
            fair_odds=fair_odds,
            implied_edge_pct=implied_edge,
            recommended_stake_pct=round(stake_pct * 100, 3),
            recommended_stake_abs=stake_abs,
            potential_gain_ratio=total_odds,
            quality_score=round(quality, 1),
            risk_rating=risk,
            is_recommended=is_recommended,
            summary=summary,
            warnings=warnings,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_selection_label(self, bet: Dict) -> str:
        labels = {
            "home": "Victoire domicile",
            "draw": "Match nul",
            "away": "Victoire extérieur",
            "over_25": "Over 2.5 buts",
            "under_25": "Under 2.5 buts",
            "over_15": "Over 1.5 buts",
            "over_35": "Over 3.5 buts",
            "btts_yes": "BTTS Oui",
            "btts_no": "BTTS Non",
            "1X": "Double Chance 1X",
            "X2": "Double Chance X2",
            "12": "Double Chance 12",
        }
        return labels.get(bet.get("selection", ""), bet.get("market", "Sélection"))

    def _matches_strategy(self, bet: Dict, hint: str) -> bool:
        hint = hint.lower()
        selection = bet.get("selection", "").lower()
        if hint == "high_btts":
            return "btts" in selection or "over_25" in selection
        elif hint == "over_goals":
            return "over" in selection
        elif hint == "home_favorites":
            return selection == "home"
        elif hint == "double_chance":
            return selection in ("1X", "X2", "12")
        return True

    def explain_ticket(self, ticket: Ticket) -> str:
        """Génère une explication lisible du ticket."""
        lines = [
            f"=== TICKET {ticket.ticket_type.value.upper()} ===",
            f"Qualité: {ticket.quality_score:.0f}/100 | Risk: {ticket.risk_rating}",
            f"Cote totale: {ticket.total_odds:.2f} | Probabilité modèle: {ticket.combined_prob:.1%}",
            f"Edge total: {ticket.implied_edge_pct:+.1f}%",
            f"Mise recommandée: {ticket.recommended_stake_pct:.2f}% de la bankroll "
            f"({ticket.recommended_stake_abs:.0f} unités)",
            "",
            "SÉLECTIONS:",
        ]

        for i, leg in enumerate(ticket.legs, 1):
            lines.append(
                f"  {i}. {leg.home_team} vs {leg.away_team} [{leg.league}]\n"
                f"     {leg.selection} @ {leg.odds:.2f} | "
                f"Prob: {leg.prob_model:.0%} | Edge: +{leg.edge_pct:.1f}%"
            )

        if ticket.warnings:
            lines.append("\n⚠️ AVERTISSEMENTS:")
            for w in ticket.warnings:
                lines.append(f"  • {w}")

        return "\n".join(lines)
