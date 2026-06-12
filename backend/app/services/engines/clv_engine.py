"""
CLV Engine — Closing Line Value

Inspiré de Pinnacle / Trademate Sports.

Le CLV (Closing Line Value) est LE meilleur indicateur de la qualité d'un parieur.
Si vous battez régulièrement la cote de fermeture de Pinnacle, vous êtes un parieur
mathématiquement profitable à long terme — indépendamment des résultats à court terme.

Formule:
    CLV% = (cote_prise / cote_fermeture) - 1

    CLV > 0 → Vous avez parié avant que le marché ne bouge contre vous (bon signal)
    CLV < 0 → Le marché a bougé en votre faveur → votre pari était mauvais

Références:
    - Pinnacle: "How to measure betting skill" (pinnacle.com/betting-articles)
    - Trademate Sports: CLV tracking methodology
    - Joseph Buchdahl: "Squares & Sharps, Suckers & Sharks"
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger("predator.clv")


class CLVSignal(str, Enum):
    EXCELLENT  = "EXCELLENT"   # CLV > +8%
    GOOD       = "GOOD"        # CLV entre +3% et +8%
    NEUTRAL    = "NEUTRAL"     # CLV entre -2% et +3%
    BAD        = "BAD"         # CLV entre -8% et -2%
    TERRIBLE   = "TERRIBLE"    # CLV < -8%


@dataclass
class BetRecord:
    """Enregistrement d'un pari avec tracking CLV."""
    bet_id: str
    match_id: str
    home_team: str
    away_team: str
    league: str
    match_date: datetime

    # Pari
    market: str           # "1X2_H", "OU25_O", "BTTS_Y", etc.
    bookmaker: str
    odds_taken: float     # Cote au moment de la prise
    stake: float          # Mise en EUR/XOF

    # CLV data
    odds_closing: Optional[float] = None    # Cote de fermeture Pinnacle
    clv_pct: Optional[float] = None         # CLV en %
    clv_signal: Optional[CLVSignal] = None

    # Résultat
    result_actual: Optional[str] = None     # "W" / "L" / "V" (void)
    profit: Optional[float] = None
    settled_at: Optional[datetime] = None

    # Méta
    placed_at: datetime = field(default_factory=datetime.utcnow)
    model_edge_at_placement: float = 0.0
    bankroll_before: float = 0.0
    bankroll_after: Optional[float] = None

    # Proba modèle au moment du pari
    prob_model: float = 0.0
    prob_closing: float = 0.0


@dataclass
class CLVReport:
    """Rapport de performance CLV sur une période."""
    period_start: datetime
    period_end: datetime

    total_bets: int = 0
    avg_clv_pct: float = 0.0
    median_clv_pct: float = 0.0
    clv_positive_rate: float = 0.0   # % paris avec CLV > 0

    # Distribution
    excellent: int = 0
    good: int = 0
    neutral: int = 0
    bad: int = 0
    terrible: int = 0

    # ROI réel
    roi_actual: float = 0.0
    total_profit: float = 0.0
    total_staked: float = 0.0
    win_rate: float = 0.0

    # Métriques avancées
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    kelly_growth: float = 0.0

    # Par segment
    by_league: Dict[str, Dict] = field(default_factory=dict)
    by_market: Dict[str, Dict] = field(default_factory=dict)
    by_bookmaker: Dict[str, Dict] = field(default_factory=dict)
    by_confidence_tier: Dict[str, Dict] = field(default_factory=dict)

    # Bankroll
    equity_curve: List[float] = field(default_factory=list)
    clv_cumulative: List[float] = field(default_factory=list)

    # Verdict
    verdict: str = ""
    is_profitable: bool = False


# ─── Moteur CLV ───────────────────────────────────────────────────────────────

class CLVEngine:
    """
    Calcule, enregistre et analyse le Closing Line Value de tous les paris.

    Usage:
        engine = CLVEngine()
        engine.record_bet(bet_record)
        engine.update_closing_odds(bet_id, closing_odds=1.85)
        engine.settle_bet(bet_id, won=True)
        report = engine.generate_report(from_date, to_date)
    """

    def __init__(self, clv_threshold_excellent: float = 8.0,
                 clv_threshold_good: float = 3.0,
                 clv_threshold_neutral: float = -2.0,
                 clv_threshold_bad: float = -8.0):
        self.records: List[BetRecord] = []
        self.thresholds = {
            "excellent": clv_threshold_excellent,
            "good":      clv_threshold_good,
            "neutral":   clv_threshold_neutral,
            "bad":       clv_threshold_bad,
        }

    # ── Enregistrement ────────────────────────────────────────────────────────

    def record_bet(self, record: BetRecord) -> BetRecord:
        """Enregistre un nouveau pari pour tracking CLV."""
        self.records.append(record)
        logger.info(f"[CLV] Pari enregistré: {record.home_team} vs {record.away_team} "
                    f"| {record.market} @ {record.odds_taken} | {record.stake} EUR")
        return record

    def update_closing_odds(
        self, bet_id: str, closing_odds: float, source: str = "pinnacle"
    ) -> Optional[BetRecord]:
        """
        Met à jour la cote de fermeture et calcule le CLV.
        Appelé juste avant le coup d'envoi du match.
        """
        record = self._find_record(bet_id)
        if not record:
            logger.warning(f"[CLV] Pari {bet_id} non trouvé")
            return None

        record.odds_closing = closing_odds
        record.clv_pct = self._compute_clv(record.odds_taken, closing_odds)
        record.clv_signal = self._classify_clv(record.clv_pct)

        # Probabilité à la fermeture
        if closing_odds > 1:
            record.prob_closing = round(1 / closing_odds, 4)

        logger.info(f"[CLV] Update {bet_id}: cote_prise={record.odds_taken} | "
                    f"fermeture={closing_odds} | CLV={record.clv_pct:+.1f}% ({record.clv_signal})")
        return record

    def settle_bet(
        self, bet_id: str, won: bool,
        bankroll_after: Optional[float] = None
    ) -> Optional[BetRecord]:
        """Marque un pari comme réglé avec son résultat."""
        record = self._find_record(bet_id)
        if not record:
            return None

        record.result_actual = "W" if won else "L"
        record.settled_at = datetime.utcnow()

        if won:
            record.profit = round(record.stake * (record.odds_taken - 1), 2)
        else:
            record.profit = -record.stake

        if bankroll_after is not None:
            record.bankroll_after = bankroll_after

        return record

    # ── Calcul CLV ────────────────────────────────────────────────────────────

    def _compute_clv(self, odds_taken: float, odds_closing: float) -> float:
        """
        CLV% = (odds_taken / odds_closing - 1) × 100

        Interpretation:
        +5% → Vous avez obtenu une cote 5% meilleure que la fermeture
              = le marché a confirmé que votre pari avait de la value
        -5% → La cote a bougé en votre faveur → vous avez mal lu le marché
        """
        if odds_closing <= 1.0 or odds_taken <= 1.0:
            return 0.0
        return round((odds_taken / odds_closing - 1) * 100, 2)

    def _classify_clv(self, clv_pct: float) -> CLVSignal:
        t = self.thresholds
        if clv_pct >= t["excellent"]:
            return CLVSignal.EXCELLENT
        elif clv_pct >= t["good"]:
            return CLVSignal.GOOD
        elif clv_pct >= t["neutral"]:
            return CLVSignal.NEUTRAL
        elif clv_pct >= t["bad"]:
            return CLVSignal.BAD
        else:
            return CLVSignal.TERRIBLE

    # ── Rapports ─────────────────────────────────────────────────────────────

    def generate_report(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        min_bets: int = 10,
    ) -> CLVReport:
        """
        Génère un rapport CLV complet sur la période.

        Inclut:
        - CLV moyen et distribution
        - ROI réel vs ROI attendu par CLV
        - Analyse par ligue / marché / bookmaker
        - Courbe d'équité et CLV cumulatif
        - Verdict sur la qualité du modèle
        """
        records = self._filter_records(from_date, to_date)
        settled = [r for r in records if r.result_actual in ("W", "L")]
        with_clv = [r for r in records if r.clv_pct is not None]

        report = CLVReport(
            period_start=from_date or (records[0].placed_at if records else datetime.utcnow()),
            period_end=to_date or datetime.utcnow(),
            total_bets=len(records),
        )

        if not records:
            report.verdict = "Pas assez de données (0 paris)"
            return report

        # ── CLV stats ─────────────────────────────────────────────────────
        if with_clv:
            clv_values = [r.clv_pct for r in with_clv]
            report.avg_clv_pct    = round(float(np.mean(clv_values)), 2)
            report.median_clv_pct = round(float(np.median(clv_values)), 2)
            report.clv_positive_rate = round(sum(1 for v in clv_values if v > 0) / len(clv_values), 3)

            # Distribution
            for r in with_clv:
                sig = self._classify_clv(r.clv_pct or 0)
                if sig == CLVSignal.EXCELLENT:  report.excellent += 1
                elif sig == CLVSignal.GOOD:     report.good += 1
                elif sig == CLVSignal.NEUTRAL:  report.neutral += 1
                elif sig == CLVSignal.BAD:      report.bad += 1
                else:                           report.terrible += 1

            # CLV cumulatif
            cum = 0.0
            for r in sorted(with_clv, key=lambda x: x.placed_at):
                cum += r.clv_pct or 0
                report.clv_cumulative.append(round(cum, 2))

        # ── ROI réel ──────────────────────────────────────────────────────
        if settled:
            total_profit  = sum(r.profit for r in settled if r.profit is not None)
            total_staked  = sum(r.stake for r in settled)
            wins          = sum(1 for r in settled if r.result_actual == "W")

            report.total_profit  = round(total_profit, 2)
            report.total_staked  = round(total_staked, 2)
            report.roi_actual    = round(total_profit / max(total_staked, 1) * 100, 2)
            report.win_rate      = round(wins / len(settled), 3)

            # Equity curve
            bankroll = 10_000.0
            peak = bankroll
            profits = []
            for r in sorted(settled, key=lambda x: x.placed_at):
                p = r.profit or 0
                bankroll += p
                peak = max(peak, bankroll)
                profits.append(p)
                report.equity_curve.append(round(bankroll, 2))
                dd = (peak - bankroll) / peak
                report.max_drawdown = max(report.max_drawdown, dd)

            # Sharpe ratio
            if profits:
                profits_arr = np.array(profits)
                report.sharpe_ratio = round(
                    float(profits_arr.mean() / (profits_arr.std() + 1e-8) * np.sqrt(365)), 2
                )

        # ── Analyses segmentées ──────────────────────────────────────────
        report.by_league    = self._segment_analysis(settled, "league")
        report.by_market    = self._segment_analysis(settled, "market")
        report.by_bookmaker = self._segment_analysis(settled, "bookmaker")

        # Par niveau de confiance (basé sur edge au moment du pari)
        report.by_confidence_tier = self._confidence_tier_analysis(settled)

        # ── Verdict ───────────────────────────────────────────────────────
        report.verdict    = self._generate_verdict(report, len(settled))
        report.is_profitable = report.roi_actual > 0 and report.avg_clv_pct > 0

        return report

    def _segment_analysis(
        self, records: List[BetRecord], segment_key: str
    ) -> Dict[str, Dict]:
        """Analyse par segment (ligue, marché, bookmaker)."""
        segments: Dict[str, List[BetRecord]] = {}
        for r in records:
            val = getattr(r, segment_key, "unknown")
            segments.setdefault(val, []).append(r)

        result = {}
        for seg, recs in segments.items():
            wins   = sum(1 for r in recs if r.result_actual == "W")
            profit = sum(r.profit or 0 for r in recs)
            staked = sum(r.stake for r in recs)
            clv_vals = [r.clv_pct for r in recs if r.clv_pct is not None]

            result[str(seg)] = {
                "bets":      len(recs),
                "win_rate":  round(wins / max(len(recs), 1), 3),
                "roi_pct":   round(profit / max(staked, 1) * 100, 2),
                "profit":    round(profit, 2),
                "avg_clv":   round(float(np.mean(clv_vals)), 2) if clv_vals else 0.0,
            }
        return dict(sorted(result.items(), key=lambda x: -x[1]["roi_pct"]))

    def _confidence_tier_analysis(self, records: List[BetRecord]) -> Dict[str, Dict]:
        """Analyse par tranche de confiance (edge au moment du pari)."""
        tiers = {
            "edge_3-5%":  [r for r in records if 0.03 <= r.model_edge_at_placement < 0.05],
            "edge_5-8%":  [r for r in records if 0.05 <= r.model_edge_at_placement < 0.08],
            "edge_8-12%": [r for r in records if 0.08 <= r.model_edge_at_placement < 0.12],
            "edge_12+%":  [r for r in records if r.model_edge_at_placement >= 0.12],
        }
        result = {}
        for tier, recs in tiers.items():
            if not recs:
                continue
            wins   = sum(1 for r in recs if r.result_actual == "W")
            profit = sum(r.profit or 0 for r in recs)
            staked = sum(r.stake for r in recs)
            result[tier] = {
                "bets":     len(recs),
                "win_rate": round(wins / max(len(recs), 1), 3),
                "roi_pct":  round(profit / max(staked, 1) * 100, 2),
                "profit":   round(profit, 2),
            }
        return result

    def _generate_verdict(self, report: CLVReport, n_settled: int) -> str:
        """Génère un verdict textuel sur la qualité du parieur."""
        if n_settled < 30:
            return (f"Seulement {n_settled} paris réglés — "
                    "besoin d'au moins 100 paris pour une évaluation statistique fiable")

        lines = []

        if report.avg_clv_pct >= 5:
            lines.append(f"🟢 EXCELLENT : CLV moyen de +{report.avg_clv_pct:.1f}% "
                         "— vous battez systématiquement le marché sharp")
        elif report.avg_clv_pct >= 2:
            lines.append(f"🟡 BON : CLV moyen de +{report.avg_clv_pct:.1f}% "
                         "— modèle probablement rentable à long terme")
        elif report.avg_clv_pct >= 0:
            lines.append(f"🟠 NEUTRE : CLV de +{report.avg_clv_pct:.1f}% "
                         "— légèrement positif, continuez à collecter les données")
        else:
            lines.append(f"🔴 NÉGATIF : CLV de {report.avg_clv_pct:.1f}% "
                         "— votre modèle ne bat pas le marché sur ce set de données")

        lines.append(f"ROI réel: {report.roi_actual:+.1f}% | "
                     f"Win rate: {report.win_rate:.1%} | "
                     f"Sharpe: {report.sharpe_ratio:.2f}")

        if report.max_drawdown > 0.25:
            lines.append(f"⚠️ Drawdown max élevé ({report.max_drawdown:.1%}) — "
                         "réduire la taille des mises")

        return " | ".join(lines)

    # ── Projection ROI ────────────────────────────────────────────────────────

    def project_roi_from_clv(
        self, avg_clv_pct: float, avg_odds: float = 2.5, n_bets: int = 1000
    ) -> Dict:
        """
        Projette le ROI attendu à partir du CLV moyen.

        Formule de base:
            ROI_attendu ≈ CLV_moyen / (avg_odds - 1)

        C'est une approximation basée sur la théorie de l'efficience des marchés.
        Un CLV moyen de +3% sur des cotes moyennes de 2.5 → ROI attendu ≈ +2%
        """
        if avg_odds <= 1.0:
            return {}

        # Formule approximative
        roi_projected = avg_clv_pct / (avg_odds - 1)

        # Intervalle de confiance (95%) basé sur la loi des grands nombres
        sigma = np.sqrt(roi_projected * (1 - roi_projected) / max(n_bets, 1)) * 100

        return {
            "avg_clv_pct":    round(avg_clv_pct, 2),
            "avg_odds":       round(avg_odds, 2),
            "roi_projected":  round(roi_projected, 2),
            "roi_95_low":     round(roi_projected - 2 * sigma, 2),
            "roi_95_high":    round(roi_projected + 2 * sigma, 2),
            "n_bets_for_significance": max(100, int((2 / max(avg_clv_pct / 100, 0.01)) ** 2)),
            "interpretation": (
                f"Avec un CLV moyen de +{avg_clv_pct:.1f}% sur des cotes de {avg_odds:.2f}, "
                f"le ROI attendu est de {roi_projected:.1f}% sur {n_bets} paris"
            ),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_record(self, bet_id: str) -> Optional[BetRecord]:
        for r in self.records:
            if r.bet_id == bet_id:
                return r
        return None

    def _filter_records(
        self,
        from_date: Optional[datetime],
        to_date: Optional[datetime],
    ) -> List[BetRecord]:
        records = self.records
        if from_date:
            records = [r for r in records if r.placed_at >= from_date]
        if to_date:
            records = [r for r in records if r.placed_at <= to_date]
        return sorted(records, key=lambda r: r.placed_at)

    def summary_stats(self) -> Dict:
        """Stats rapides sans filtrage de date."""
        total = len(self.records)
        with_clv = [r for r in self.records if r.clv_pct is not None]
        settled  = [r for r in self.records if r.result_actual in ("W", "L")]

        avg_clv = float(np.mean([r.clv_pct for r in with_clv])) if with_clv else 0.0
        roi = (
            sum(r.profit or 0 for r in settled) /
            max(sum(r.stake for r in settled), 1) * 100
        ) if settled else 0.0

        return {
            "total_bets":      total,
            "settled":         len(settled),
            "with_clv":        len(with_clv),
            "avg_clv_pct":     round(avg_clv, 2),
            "roi_actual":      round(roi, 2),
            "win_rate":        round(
                sum(1 for r in settled if r.result_actual == "W") / max(len(settled), 1), 3
            ),
        }
