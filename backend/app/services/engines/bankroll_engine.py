"""
Bankroll Management Engine — Predator Brain

Gestion professionnelle du capital de paris.
Implémente :
  - Kelly fractionné (recommandé)
  - Flat stake
  - Kelly complet (agressif, non recommandé solo)
  - Limites de risque par période / par match / par championnat
  - Avertissements automatiques
  - Tracking de la bankroll en temps réel
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger("predator.bankroll")


class StakeStrategy(str, Enum):
    FLAT        = "flat"          # Mise fixe absolue
    FLAT_PCT    = "flat_pct"      # Pourcentage fixe de la bankroll
    KELLY_FULL  = "kelly_full"    # Kelly complet (très agressif)
    KELLY_HALF  = "kelly_half"    # Demi-Kelly
    KELLY_QUARTER = "kelly_quarter"  # Quart-Kelly (recommandé)
    KELLY_TENTH = "kelly_tenth"   # 1/10 Kelly (ultra-conservateur)


class RiskLevel(str, Enum):
    CONSERVATIVE = "conservative"   # 1-2% bankroll max
    MODERATE     = "moderate"       # 2-4% bankroll max
    AGGRESSIVE   = "aggressive"     # 4-8% bankroll max
    VERY_HIGH    = "very_high"      # > 8% (déconseillé)


@dataclass
class StakeRecommendation:
    """Recommandation de mise pour un pari."""
    strategy: StakeStrategy
    stake_amount: float       # Montant absolu
    stake_pct: float          # Pourcentage de la bankroll
    max_allowed: float        # Mise maximum selon les limites

    # Analyse
    edge_pct: float
    kelly_full_pct: float     # Kelly complet (référence)
    kelly_quarter_pct: float  # Quart-Kelly (recommandé)

    # Décision
    is_recommended: bool
    risk_level: RiskLevel
    message: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class BankrollSnapshot:
    """État de la bankroll à un instant T."""
    timestamp: datetime
    total: float
    available: float          # Total - mises en cours
    reserved: float           # Mises en cours (non réglées)
    daily_profit: float
    weekly_profit: float
    monthly_profit: float
    drawdown_current: float   # Drawdown depuis le pic
    drawdown_max: float       # Drawdown max historique
    peak: float               # Pic historique


@dataclass
class RiskAlert:
    """Alerte de risque."""
    severity: str             # "WARNING" / "DANGER" / "CRITICAL"
    message: str
    action: str               # Action recommandée
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ─── Moteur de bankroll ───────────────────────────────────────────────────────

class BankrollEngine:
    """
    Gestion complète du capital de paris.

    Features:
    - Calcul de mise selon Kelly / Flat / % fixe
    - Limites de risque configurables
    - Alertes automatiques (drawdown, surexposition, série de pertes)
    - Tracking complet de la performance
    - Recommandations intelligentes par marché
    """

    def __init__(
        self,
        initial_bankroll: float = 10_000.0,
        strategy: StakeStrategy = StakeStrategy.KELLY_QUARTER,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        flat_stake_pct: float = 0.02,        # 2% pour flat_pct
        flat_stake_abs: float = 100.0,       # Montant fixe pour flat
        max_stake_pct: float = 0.05,         # 5% max par pari
        max_daily_loss_pct: float = 0.10,    # Stop-loss journalier: -10%
        max_open_bets: int = 10,             # Nombre max de paris ouverts
        max_exposure_pct: float = 0.20,      # 20% bankroll max en jeu simultanément
        max_single_league_pct: float = 0.10, # 10% max par championnat
        kelly_fraction: float = 0.25,        # Fraction Kelly (override si strategy != KELLY*)
    ):
        self.initial_bankroll      = initial_bankroll
        self.current_bankroll      = initial_bankroll
        self.peak_bankroll         = initial_bankroll
        self.strategy              = strategy
        self.risk_level            = risk_level
        self.flat_stake_pct        = flat_stake_pct
        self.flat_stake_abs        = flat_stake_abs
        self.max_stake_pct         = max_stake_pct
        self.max_daily_loss_pct    = max_daily_loss_pct
        self.max_open_bets         = max_open_bets
        self.max_exposure_pct      = max_exposure_pct
        self.max_single_league_pct = max_single_league_pct

        # Mapping stratégie → fraction Kelly
        self._kelly_fractions = {
            StakeStrategy.KELLY_FULL:    1.0,
            StakeStrategy.KELLY_HALF:    0.5,
            StakeStrategy.KELLY_QUARTER: 0.25,
            StakeStrategy.KELLY_TENTH:   0.10,
        }

        # State
        self._open_bets: Dict[str, Dict] = {}           # bet_id → {stake, league, ...}
        self._daily_losses: float = 0.0
        self._daily_reset: datetime = datetime.utcnow().replace(hour=0, minute=0)
        self._history: List[Dict] = []
        self._alerts: List[RiskAlert] = []
        self._max_drawdown: float = 0.0

    # ── Calcul de mise ────────────────────────────────────────────────────────

    def recommend_stake(
        self,
        edge_pct: float,
        odds: float,
        prob_model: float,
        league: str = "unknown",
        market: str = "1X2",
        n_legs: int = 1,                   # 1 pour simple, >1 pour combo
    ) -> StakeRecommendation:
        """
        Calcule la mise recommandée pour un pari.

        Args:
            edge_pct:    Edge en % (ex: 5.2)
            odds:        Cote décimale (ex: 2.10)
            prob_model:  Probabilité estimée (ex: 0.52)
            league:      Code championnat (pour limites)
            market:      Type de marché
            n_legs:      Nombre de sélections (combo)
        """
        warnings: List[str] = []
        edge_frac = edge_pct / 100

        # ── Calcul Kelly ────────────────────────────────────────────────
        b = odds - 1  # gain net par unité
        q = 1 - prob_model

        kelly_full = 0.0
        if b > 0 and prob_model > 0:
            kelly_full = max(0.0, (b * prob_model - q) / b)

        kelly_quarter = kelly_full * 0.25

        # ── Calcul selon la stratégie ────────────────────────────────
        if self.strategy == StakeStrategy.FLAT:
            stake_pct = self.flat_stake_abs / max(self.current_bankroll, 1)
        elif self.strategy == StakeStrategy.FLAT_PCT:
            stake_pct = self.flat_stake_pct
        else:
            # Kelly selon fraction
            frac = self._kelly_fractions.get(self.strategy, 0.25)
            stake_pct = kelly_full * frac

        # ── Ajustements ──────────────────────────────────────────────

        # Penalité pour les combos (variance multipliée)
        if n_legs > 1:
            stake_pct *= (0.5 ** (n_legs - 1))
            if n_legs >= 3:
                warnings.append(f"Combo {n_legs} sélections — mise réduite automatiquement (variance ×{n_legs})")

        # Limite max par pari
        stake_pct = min(stake_pct, self.max_stake_pct)

        # Vérifier la disponibilité (exposition totale)
        current_exposure = self._get_current_exposure_pct()
        available_pct = max(0.0, self.max_exposure_pct - current_exposure)
        stake_pct = min(stake_pct, available_pct)

        # Limite par championnat
        league_exposure = self._get_league_exposure_pct(league)
        remaining_league = max(0.0, self.max_single_league_pct - league_exposure)
        stake_pct = min(stake_pct, remaining_league)

        # Stop-loss journalier
        if self._daily_losses >= self.max_daily_loss_pct * self.initial_bankroll:
            stake_pct = 0.0
            warnings.append(f"⛔ Stop-loss journalier atteint ({self.max_daily_loss_pct:.0%}) — pause recommandée")

        # Avertissements
        if current_exposure > self.max_exposure_pct * 0.8:
            warnings.append(f"Exposition élevée ({current_exposure:.0%} de la bankroll en jeu)")

        if odds > 6.0:
            warnings.append(f"Cote très haute ({odds}) — mise réduite conseillée malgré la value")
            stake_pct *= 0.5

        if len(self._open_bets) >= self.max_open_bets:
            stake_pct = 0.0
            warnings.append(f"Limite de {self.max_open_bets} paris simultanés atteinte")

        # Calcul montant final
        stake_amount = round(stake_pct * self.current_bankroll, 2)
        stake_amount = max(stake_amount, 0.0)

        # Risk level
        if stake_pct >= 0.06:
            risk = RiskLevel.VERY_HIGH
        elif stake_pct >= 0.04:
            risk = RiskLevel.AGGRESSIVE
        elif stake_pct >= 0.02:
            risk = RiskLevel.MODERATE
        else:
            risk = RiskLevel.CONSERVATIVE

        is_recommended = stake_pct > 0.001 and edge_pct >= 3.0

        # Message
        if stake_pct == 0:
            msg = "Mise non recommandée — limite atteinte"
        elif edge_pct >= 8:
            msg = f"Mise forte recommandée — edge exceptionnel ({edge_pct:.1f}%)"
        elif edge_pct >= 5:
            msg = f"Bonne value ({edge_pct:.1f}% edge) — mise standard"
        elif edge_pct >= 3:
            msg = f"Value modérée ({edge_pct:.1f}%) — mise réduite"
        else:
            msg = "Edge insuffisant pour parier"

        return StakeRecommendation(
            strategy=self.strategy,
            stake_amount=stake_amount,
            stake_pct=round(stake_pct * 100, 2),
            max_allowed=round(self.max_stake_pct * self.current_bankroll, 2),
            edge_pct=edge_pct,
            kelly_full_pct=round(kelly_full * 100, 2),
            kelly_quarter_pct=round(kelly_quarter * 100, 2),
            is_recommended=is_recommended,
            risk_level=risk,
            message=msg,
            warnings=warnings,
        )

    # ── Gestion des paris ouverts ─────────────────────────────────────────────

    def place_bet(
        self, bet_id: str, stake: float, league: str = "unknown",
        market: str = "1X2", odds: float = 2.0,
    ) -> Tuple[bool, str]:
        """
        Enregistre un pari ouvert.
        Returns: (success, message)
        """
        # Vérifications
        if stake > self.current_bankroll:
            return False, "Mise supérieure à la bankroll disponible"

        if len(self._open_bets) >= self.max_open_bets:
            return False, f"Limite de {self.max_open_bets} paris simultanés atteinte"

        if stake / self.current_bankroll > self.max_stake_pct:
            return False, f"Mise dépasse {self.max_stake_pct:.0%} de la bankroll"

        self._open_bets[bet_id] = {
            "stake":  stake,
            "league": league,
            "market": market,
            "odds":   odds,
            "placed_at": datetime.utcnow(),
        }

        logger.info(f"[BANKROLL] Pari ouvert: {bet_id} | Mise: {stake} | "
                    f"Bankroll: {self.current_bankroll:.0f}")
        return True, "Pari enregistré"

    def settle_bet(self, bet_id: str, won: bool) -> Tuple[float, float]:
        """
        Règle un pari et met à jour la bankroll.
        Returns: (profit, new_bankroll)
        """
        if bet_id not in self._open_bets:
            logger.warning(f"[BANKROLL] Pari {bet_id} non trouvé")
            return 0.0, self.current_bankroll

        bet = self._open_bets.pop(bet_id)
        odds   = bet["odds"]
        stake  = bet["stake"]

        if won:
            profit = round(stake * (odds - 1), 2)
        else:
            profit = -stake
            # Suivi pertes journalières
            self._refresh_daily_losses()
            self._daily_losses += abs(profit)

        self.current_bankroll = round(self.current_bankroll + profit, 2)

        # Mise à jour du pic et drawdown
        self.peak_bankroll = max(self.peak_bankroll, self.current_bankroll)
        drawdown = (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll
        self._max_drawdown = max(self._max_drawdown, drawdown)

        # Historique
        self._history.append({
            "bet_id":    bet_id,
            "won":       won,
            "profit":    profit,
            "bankroll":  self.current_bankroll,
            "drawdown":  round(drawdown, 4),
            "settled_at": datetime.utcnow(),
        })

        # Alertes
        self._check_alerts(drawdown)

        logger.info(f"[BANKROLL] {bet_id}: {'✓ GAGNÉ' if won else '✗ PERDU'} | "
                    f"profit={profit:+.2f} | bankroll={self.current_bankroll:.2f}")

        return profit, self.current_bankroll

    # ── État de la bankroll ───────────────────────────────────────────────────

    def get_snapshot(self) -> BankrollSnapshot:
        """Retourne l'état actuel de la bankroll."""
        reserved = sum(b["stake"] for b in self._open_bets.values())
        available = max(0.0, self.current_bankroll - reserved)

        # Profits par période
        now = datetime.utcnow()
        daily  = self._profit_since(now - timedelta(days=1))
        weekly = self._profit_since(now - timedelta(days=7))
        monthly = self._profit_since(now - timedelta(days=30))

        drawdown = (self.peak_bankroll - self.current_bankroll) / max(self.peak_bankroll, 1)

        return BankrollSnapshot(
            timestamp=now,
            total=self.current_bankroll,
            available=round(available, 2),
            reserved=round(reserved, 2),
            daily_profit=round(daily, 2),
            weekly_profit=round(weekly, 2),
            monthly_profit=round(monthly, 2),
            drawdown_current=round(drawdown, 4),
            drawdown_max=round(self._max_drawdown, 4),
            peak=round(self.peak_bankroll, 2),
        )

    def get_equity_curve(self) -> List[float]:
        """Courbe d'équité (bankroll au fil des paris)."""
        return [self.initial_bankroll] + [h["bankroll"] for h in self._history]

    def get_roi(self) -> float:
        """ROI global depuis le début."""
        total_profit = sum(h["profit"] for h in self._history)
        total_staked = sum(
            self._open_bets.get(h["bet_id"], {}).get("stake", 0) or
            abs(h["profit"]) / (self._find_odds(h["bet_id"]) - 1 + 1e-8)
            for h in self._history
        )
        if total_staked <= 0:
            return 0.0
        return round(total_profit / total_staked * 100, 2)

    # ── Alertes ───────────────────────────────────────────────────────────────

    def _check_alerts(self, current_drawdown: float):
        """Vérifie les conditions d'alerte."""
        if current_drawdown >= 0.25:
            self._alerts.append(RiskAlert(
                severity="CRITICAL",
                message=f"Drawdown critique: -{current_drawdown:.0%} depuis le pic",
                action="Arrêtez de parier immédiatement. Réexaminez votre stratégie.",
            ))
        elif current_drawdown >= 0.15:
            self._alerts.append(RiskAlert(
                severity="DANGER",
                message=f"Drawdown élevé: -{current_drawdown:.0%}",
                action="Réduisez les mises de 50% jusqu'à récupération",
            ))
        elif current_drawdown >= 0.10:
            self._alerts.append(RiskAlert(
                severity="WARNING",
                message=f"Drawdown modéré: -{current_drawdown:.0%}",
                action="Soyez plus sélectif sur les paris à venir",
            ))

        # Vérifier la bankroll minimale (< 30% de l'initiale)
        if self.current_bankroll < self.initial_bankroll * 0.30:
            self._alerts.append(RiskAlert(
                severity="CRITICAL",
                message=f"Bankroll critique: {self.current_bankroll:.0f} "
                        f"({self.current_bankroll/self.initial_bankroll:.0%} de l'initial)",
                action="STOP total. Repartez avec une nouvelle bankroll ou changez de stratégie.",
            ))

    def get_alerts(self, unread_only: bool = True) -> List[RiskAlert]:
        """Retourne les alertes actives."""
        if unread_only:
            return [a for a in self._alerts if a.severity in ("CRITICAL", "DANGER")]
        return self._alerts[-20:]  # 20 dernières

    # ── Rapport de performance ────────────────────────────────────────────────

    def performance_report(self) -> Dict:
        """Rapport de performance complet."""
        hist = self._history
        if not hist:
            return {"total_bets": 0, "roi": 0.0, "message": "Aucun pari réglé"}

        profits = [h["profit"] for h in hist]
        wins    = sum(1 for h in hist if h["won"])

        profit_arr = np.array(profits)
        sharpe = (
            float(profit_arr.mean() / (profit_arr.std() + 1e-8) * np.sqrt(365))
            if len(profits) > 1 else 0.0
        )

        return {
            "total_bets":    len(hist),
            "wins":          wins,
            "win_rate":      round(wins / len(hist), 3),
            "total_profit":  round(sum(profits), 2),
            "roi":           self.get_roi(),
            "current_bankroll": self.current_bankroll,
            "initial_bankroll": self.initial_bankroll,
            "growth_pct":    round((self.current_bankroll / self.initial_bankroll - 1) * 100, 2),
            "max_drawdown":  round(self._max_drawdown * 100, 2),
            "sharpe_ratio":  round(sharpe, 2),
            "avg_profit":    round(float(profit_arr.mean()), 2),
            "open_bets":     len(self._open_bets),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_current_exposure_pct(self) -> float:
        total_reserved = sum(b["stake"] for b in self._open_bets.values())
        return total_reserved / max(self.current_bankroll, 1)

    def _get_league_exposure_pct(self, league: str) -> float:
        league_reserved = sum(
            b["stake"] for b in self._open_bets.values()
            if b.get("league") == league
        )
        return league_reserved / max(self.current_bankroll, 1)

    def _profit_since(self, since: datetime) -> float:
        return sum(h["profit"] for h in self._history
                   if h["settled_at"] >= since)

    def _find_odds(self, bet_id: str) -> float:
        bet = self._open_bets.get(bet_id)
        return bet["odds"] if bet else 2.0

    def _refresh_daily_losses(self):
        """Remet à zéro les pertes journalières si nouveau jour."""
        now = datetime.utcnow()
        if now.date() > self._daily_reset.date():
            self._daily_losses = 0.0
            self._daily_reset = now
