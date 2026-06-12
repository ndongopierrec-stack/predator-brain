"""
RealBacktest — Backtesting sur données historiques réelles football-data.co.uk

Méthodologie :
    - Walk-forward : le modèle est entraîné sur [t0 → t], testé sur [t → t+split]
    - Ne prédit que sur les matchs avec cotes Bet365/Pinnacle disponibles
    - Mise Kelly Quarter (25% du Kelly full)
    - Rapporte ROI, Sharpe, drawdown, win rate, P&L

Règles strictes (pour un backtest honnête) :
    - Jamais de look-ahead bias (on n'utilise PAS les données futures)
    - Les cotes utilisées sont les cotes d'OUVERTURE (pas de closing)
    - La mise est calculée AVANT de connaître le résultat
    - Edge minimum configurable (généralement 3-8%)
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("predator.backtest")


@dataclass
class BetRecord:
    match_date: datetime
    home_team: str
    away_team: str
    league: str
    market: str          # "1X2_H", "1X2_D", "1X2_A", "OVER_25", "UNDER_25", "BTTS_Y", etc.
    selection: str       # "H", "D", "A", "OVER", "UNDER", "BTTS_Y", "BTTS_N"
    odds: float
    stake: float
    prob_model: float
    edge_pct: float
    bankroll_before: float
    # Résultat (rempli après le match)
    won: Optional[bool]  = None
    pnl: float           = 0.0
    bankroll_after: float = 0.0
    ftr: str             = ""


@dataclass
class BacktestResult:
    strategy_name:  str   = "default"
    total_matches:  int   = 0
    total_bets:     int   = 0
    bets_won:       int   = 0
    win_rate:       float = 0.0
    accuracy:       float = 0.0
    roi_pct:        float = 0.0
    total_profit:   float = 0.0
    total_staked:   float = 0.0
    final_bankroll: float = 0.0
    max_drawdown:   float = 0.0
    sharpe_ratio:   float = 0.0
    avg_odds:       float = 0.0
    avg_confidence: float = 0.0
    equity_curve:   List[float] = field(default_factory=list)
    bets:           List[BetRecord] = field(default_factory=list)
    by_league:      Dict[str, dict] = field(default_factory=dict)
    by_result_type: Dict[str, dict] = field(default_factory=dict)
    by_market:      Dict[str, dict] = field(default_factory=dict)


class RealBacktest:
    """
    Backteste une stratégie de paris sur données historiques réelles.

    Usage:
        bt = RealBacktest(initial_bankroll=10000)
        result = bt.run(
            from_date="2022-08-01",
            to_date="2024-06-01",
            model=my_predict_fn,
            df=historical_df,
            min_confidence=0.55,
            min_edge=0.04,
            kelly_fraction=0.25,
        )
    """

    def __init__(self, initial_bankroll: float = 10_000.0):
        self.initial_bankroll = initial_bankroll

    def run(
        self,
        from_date: str,
        to_date: str,
        model: Callable[[dict], dict],
        df: pd.DataFrame,
        leagues: Optional[List[str]] = None,
        min_confidence: float = 0.55,
        min_edge: float = 0.04,
        kelly_fraction: float = 0.25,
        max_stake_pct: float = 0.05,
        home_only: bool = False,
    ) -> BacktestResult:
        """
        Lance le backtest.

        Args:
            from_date:      Date début au format YYYY-MM-DD
            to_date:        Date fin au format YYYY-MM-DD
            model:          Fonction de prédiction : match_dict → {prob_home, prob_draw, prob_away, ...}
            df:             DataFrame historique normalisé (RealDataLoader)
            leagues:        Filtrer par ligues (None = toutes)
            min_confidence: Probabilité minimale pour parier
            min_edge:       Edge minimum en décimal (0.04 = 4%)
            kelly_fraction: Fraction du Kelly à utiliser (0.25 = Kelly¼)
            max_stake_pct:  Mise max en % de la bankroll
            home_only:      Parier uniquement sur les victoires à domicile

        Returns:
            BacktestResult complet
        """
        result = BacktestResult(strategy_name="backtest")

        # ── Filtrer les données ────────────────────────────────────────────────
        df = df.copy()
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce", utc=False)
        df = df.dropna(subset=["match_date"])

        t_from = pd.to_datetime(from_date)
        t_to   = pd.to_datetime(to_date)
        mask   = (df["match_date"] >= t_from) & (df["match_date"] <= t_to)
        df     = df[mask].sort_values("match_date").reset_index(drop=True)

        if leagues:
            df = df[df["league"].isin(leagues) | df["league_raw"].isin(leagues)]

        result.total_matches = len(df)
        if len(df) == 0:
            logger.warning("[BACKTEST] Aucun match dans la période/ligues sélectionnées")
            return result

        # ── Simulation ────────────────────────────────────────────────────────
        bankroll = self.initial_bankroll
        equity_curve = [bankroll]
        bets: List[BetRecord] = []
        league_stats: Dict[str, dict] = {}
        market_stats: Dict[str, dict] = {}

        for _, row in df.iterrows():
            home = str(row.get("team_home", ""))
            away = str(row.get("team_away", ""))
            league = str(row.get("league", ""))
            ftr  = str(row.get("ftr", "D"))
            # Calculer total_goals depuis score_home/score_away si disponible
            score_home = row.get("score_home")
            score_away = row.get("score_away")
            if pd.notna(score_home) and pd.notna(score_away):
                total_goals = int(score_home or 0) + int(score_away or 0)
            else:
                total_goals = int(row.get("total_goals", 0) or 0)

            if not home or not away:
                continue

            # Prédiction du modèle
            try:
                probs = model({"team_home": home, "team_away": away, "league": league})
            except Exception:
                continue

            prob_h = probs.get("prob_home", 0.0)
            prob_d = probs.get("prob_draw", 0.0)
            prob_a = probs.get("prob_away", 0.0)

            # Marchés à tester (on passe probs complet pour O/U et BTTS)
            markets = self._build_markets(row, prob_h, prob_d, prob_a, home_only, probs)

            for market_key, (prob_model, odds, selection) in markets.items():
                if prob_model < min_confidence or odds < 1.05:
                    continue

                # Calcul de l'edge — formule standard value bet :
                # edge = prob_modèle × cote - 1  (>0 = value positive)
                implied_prob = 1.0 / odds
                edge = prob_model * odds - 1.0

                if edge < min_edge:
                    continue

                # Mise Kelly
                kelly_full = (prob_model - implied_prob) / (1 - implied_prob)
                kelly_full = max(0.0, min(kelly_full, 0.30))  # plafonner à 30%
                stake_pct  = kelly_fraction * kelly_full
                stake_pct  = min(stake_pct, max_stake_pct)
                stake      = bankroll * stake_pct

                if stake < 1.0 or bankroll < 10:
                    continue

                # Résultat du pari
                won = self._bet_won(market_key, selection, ftr, total_goals, row)
                pnl = (stake * (odds - 1)) if won else -stake
                bankroll += pnl

                bet = BetRecord(
                    match_date=row["match_date"],
                    home_team=home,
                    away_team=away,
                    league=league,
                    market=market_key,
                    selection=selection,
                    odds=odds,
                    stake=stake,
                    prob_model=prob_model,
                    edge_pct=edge * 100,
                    bankroll_before=bankroll - pnl,
                    won=won,
                    pnl=pnl,
                    bankroll_after=bankroll,
                    ftr=ftr,
                )
                bets.append(bet)
                equity_curve.append(bankroll)

                # Stats par ligue
                if league not in league_stats:
                    league_stats[league] = {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0}
                league_stats[league]["bets"]   += 1
                league_stats[league]["wins"]   += int(won)
                league_stats[league]["profit"] += pnl
                league_stats[league]["staked"] += stake

                # Stats par marché
                mk = market_key.split("_")[0]
                if mk not in market_stats:
                    market_stats[mk] = {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0}
                market_stats[mk]["bets"]   += 1
                market_stats[mk]["wins"]   += int(won)
                market_stats[mk]["profit"] += pnl
                market_stats[mk]["staked"] += stake

        # ── Calcul des métriques ───────────────────────────────────────────────
        result.bets          = bets
        result.equity_curve  = equity_curve
        result.total_bets    = len(bets)
        result.final_bankroll = bankroll

        if bets:
            result.bets_won    = sum(1 for b in bets if b.won)
            result.win_rate    = result.bets_won / result.total_bets
            result.accuracy    = result.win_rate  # équivalent ici
            total_staked       = sum(b.stake for b in bets)
            result.total_staked= total_staked
            result.total_profit= bankroll - self.initial_bankroll
            result.roi_pct     = (result.total_profit / total_staked * 100) if total_staked > 0 else 0
            result.avg_odds    = float(np.mean([b.odds for b in bets]))
            result.avg_confidence = float(np.mean([b.prob_model for b in bets]))

            # Drawdown maximum
            peak = self.initial_bankroll
            max_dd = 0.0
            for val in equity_curve:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak
                if dd > max_dd:
                    max_dd = dd
            result.max_drawdown = max_dd

            # Sharpe ratio (returns journaliers approximés)
            if len(equity_curve) > 2:
                returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
                returns = returns[np.isfinite(returns)]
                if len(returns) > 1 and returns.std() > 0:
                    result.sharpe_ratio = float(returns.mean() / returns.std() * np.sqrt(252))

        # Stats par ligue
        result.by_league = {
            lg: {
                "bets":     s["bets"],
                "win_rate": s["wins"] / s["bets"] if s["bets"] > 0 else 0,
                "roi_pct":  s["profit"] / s["staked"] * 100 if s["staked"] > 0 else 0,
                "profit":   round(s["profit"], 2),
            }
            for lg, s in league_stats.items()
        }

        result.by_result_type = {
            mk: {
                "bets":     s["bets"],
                "win_rate": s["wins"] / s["bets"] if s["bets"] > 0 else 0,
                "roi_pct":  s["profit"] / s["staked"] * 100 if s["staked"] > 0 else 0,
            }
            for mk, s in market_stats.items()
        }

        logger.info(
            f"[BACKTEST] ✓ {result.total_bets} paris | "
            f"ROI: {result.roi_pct:+.1f}% | "
            f"Win rate: {result.win_rate:.0%} | "
            f"Drawdown: {result.max_drawdown:.0%} | "
            f"Sharpe: {result.sharpe_ratio:.2f}"
        )
        return result

    def walk_forward_validation(
        self,
        model_factory: Callable,
        df: pd.DataFrame,
        n_splits: int = 5,
        min_confidence: float = 0.55,
        min_edge: float = 0.04,
        kelly_fraction: float = 0.25,
        max_stake_pct: float = 0.05,
    ) -> List[BacktestResult]:
        """
        Walk-Forward Validation : entraîne sur passé, teste sur futur.

        Divise la période en n_splits. Pour chaque split :
        - Entraîne sur tout ce qui précède le split
        - Teste sur le split uniquement
        - Évite le look-ahead bias

        Returns:
            Liste de BacktestResult (un par split)
        """
        df = df.copy().sort_values("match_date").reset_index(drop=True)
        n = len(df)
        split_size = n // (n_splits + 1)
        results = []

        for i in range(n_splits):
            train_end_idx = split_size * (i + 1)
            test_start_idx = train_end_idx
            test_end_idx   = min(train_end_idx + split_size, n)

            train_df = df.iloc[:train_end_idx]
            test_df  = df.iloc[test_start_idx:test_end_idx]

            if len(train_df) < 100 or len(test_df) < 10:
                continue

            # Entraîner un modèle sur les données train
            try:
                predict_fn = model_factory(train_df)
            except Exception as e:
                logger.warning(f"[WF] Erreur entraînement split {i+1}: {e}")
                continue

            # Tester sur les données test
            from_date = str(test_df["match_date"].min().date())
            to_date   = str(test_df["match_date"].max().date())

            split_result = self.run(
                from_date=from_date,
                to_date=to_date,
                model=predict_fn,
                df=test_df,
                min_confidence=min_confidence,
                min_edge=min_edge,
                kelly_fraction=kelly_fraction,
                max_stake_pct=max_stake_pct,
            )
            split_result.strategy_name = f"WF Split {i+1}/{n_splits}"
            results.append(split_result)

            logger.info(
                f"[WF] Split {i+1}/{n_splits}: "
                f"train={len(train_df)} | test={len(test_df)} | "
                f"bets={split_result.total_bets} | ROI={split_result.roi_pct:+.1f}%"
            )

        return results

    # ── Helpers internes ──────────────────────────────────────────────────────

    def _build_markets(
        self,
        row: pd.Series,
        prob_h: float, prob_d: float, prob_a: float,
        home_only: bool = False,
        probs: Optional[dict] = None,
    ) -> Dict[str, tuple]:
        """
        Construit les marchés disponibles pour un match.

        Utilise les probabilités DC directement quand disponibles (lambda_home/away),
        sinon repli sur l'estimation Poisson bivariable depuis les probs 1X2.

        Returns:
            Dict {market_key: (prob_model, odds, selection)}
        """
        from app.services.engines.ou_btts_engine import OUBTTSEngine
        markets = {}
        probs = probs or {}

        # ── 1X2 ──────────────────────────────────────────────────────────────
        if pd.notna(row.get("odds_home")) and row.get("odds_home", 0) > 1.05:
            markets["1X2_H"] = (prob_h, float(row["odds_home"]), "H")
        if not home_only:
            if pd.notna(row.get("odds_draw")) and row.get("odds_draw", 0) > 1.05:
                markets["1X2_D"] = (prob_d, float(row["odds_draw"]), "D")
            if pd.notna(row.get("odds_away")) and row.get("odds_away", 0) > 1.05:
                markets["1X2_A"] = (prob_a, float(row["odds_away"]), "A")

        if not home_only:
            # ── Calcul O/U et BTTS via Poisson bivariable (DC ou estimation) ──
            engine = OUBTTSEngine()

            # Priorité 1 : lambdas directs du modèle DC (précis)
            lam_h = probs.get("lambda_home")
            lam_a = probs.get("lambda_away")
            dc_known = probs.get("dc_known", False)

            if lam_h and lam_a and lam_h > 0 and lam_a > 0:
                # Prédiction précise avec lambdas DC
                ou_pred = engine.predict(
                    lambda_home=lam_h,
                    lambda_away=lam_a,
                    dc_known=dc_known,
                )
            else:
                # Priorité 2 : prob O/U déjà calculées par le modèle DC
                if probs.get("prob_over_25") is not None:
                    ou_pred = None  # on utilisera directement les probs
                else:
                    # Priorité 3 : estimation depuis probs 1X2 (dernier recours)
                    ou_pred = engine.predict_from_1x2(prob_h, prob_d, prob_a)

            # Résoudre les probabilités O/U
            if ou_pred is not None:
                p_over15  = ou_pred.prob_over_15
                p_over25  = ou_pred.prob_over_25
                p_over35  = ou_pred.prob_over_35
                p_btts    = ou_pred.prob_btts_yes
            else:
                # Utiliser les probs directement du modèle DC
                p_over15  = probs.get("prob_over_15", 0.0)
                p_over25  = probs.get("prob_over_25", 0.51)
                p_over35  = probs.get("prob_over_35", 0.0)
                p_btts    = probs.get("prob_btts_yes", 0.0)

            p_under25 = 1.0 - p_over25

            # ── Over/Under 1.5 ────────────────────────────────────────────────
            odds_over15 = row.get("odds_over15") or row.get("odds_over_15")
            if pd.notna(odds_over15) and float(odds_over15 or 0) > 1.05:
                markets["OVER_15"] = (p_over15, float(odds_over15), "OVER")

            # ── Over/Under 2.5 ────────────────────────────────────────────────
            if pd.notna(row.get("odds_over25")) and row.get("odds_over25", 0) > 1.05:
                markets["OVER_25"] = (p_over25, float(row["odds_over25"]), "OVER")
            if pd.notna(row.get("odds_under25")) and row.get("odds_under25", 0) > 1.05:
                markets["UNDER_25"] = (p_under25, float(row["odds_under25"]), "UNDER")

            # ── Pinnacle odds (plus serrés, meilleure référence) ──────────────
            if pd.notna(row.get("odds_over25_c")) and row.get("odds_over25_c", 0) > 1.05:
                markets["OVER_25_PS"] = (p_over25, float(row["odds_over25_c"]), "OVER")
            if pd.notna(row.get("odds_under25_c")) and row.get("odds_under25_c", 0) > 1.05:
                markets["UNDER_25_PS"] = (p_under25, float(row["odds_under25_c"]), "UNDER")

            # ── Over 3.5 ─────────────────────────────────────────────────────
            odds_over35 = row.get("odds_over35") or row.get("odds_over_35")
            if pd.notna(odds_over35) and float(odds_over35 or 0) > 1.05:
                markets["OVER_35"] = (p_over35, float(odds_over35), "OVER")

            # ── BTTS (Both Teams To Score) ────────────────────────────────────
            if p_btts > 0:
                odds_btts_y = row.get("odds_btts_yes") or row.get("odds_bts_yes") or row.get("BbMx>2.5")
                odds_btts_n = row.get("odds_btts_no")  or row.get("odds_bts_no")

                if pd.notna(odds_btts_y) and float(odds_btts_y or 0) > 1.05:
                    markets["BTTS_Y"] = (p_btts, float(odds_btts_y), "BTTS_Y")
                if pd.notna(odds_btts_n) and float(odds_btts_n or 0) > 1.05:
                    markets["BTTS_N"] = (1.0 - p_btts, float(odds_btts_n), "BTTS_N")

        return markets

    @staticmethod
    def _bet_won(market_key: str, selection: str, ftr: str, total_goals: int, row: pd.Series) -> bool:
        """Détermine si le pari est gagnant selon le résultat réel."""
        if market_key.startswith("1X2"):
            return ftr == selection
        elif market_key in ("OVER_15",):
            return total_goals > 1
        elif market_key in ("OVER_25", "OVER_25_PS"):
            return total_goals > 2
        elif market_key in ("UNDER_25", "UNDER_25_PS"):
            return total_goals <= 2
        elif market_key == "OVER_35":
            return total_goals > 3
        elif market_key == "UNDER_35":
            return total_goals <= 3
        elif market_key == "BTTS_Y":
            # Les deux équipes ont marqué
            # Note: on ne peut pas faire `score or -1` car score=0 est falsy
            raw_h = row.get("score_home")
            raw_a = row.get("score_away")
            if raw_h is not None and raw_a is not None:
                sh = int(raw_h)
                sa = int(raw_a)
                return sh >= 1 and sa >= 1
            # Fallback si scores non disponibles : heuristique via total + FTR
            # Un match H ou A avec total >= 2 a probablement eu BTTS (mais pas garanti)
            # Approximation conservatrice : on skip ce cas (retourne False = pas gagné)
            # On évite les faux positifs (2-0 serait quand même considéré non-BTTS)
            if total_goals < 2:
                return False
            # Si on a un nul, les 2 équipes ont forcément marqué
            if ftr == "D":
                return True
            # Victoire/défaite avec >= 2 buts : BTTS ssi score n'est pas 2-0 ou 3-0...
            # Sans scores séparés on ne peut pas être sûr — on skip (False = prudent)
            return False
        elif market_key == "BTTS_N":
            raw_h = row.get("score_home")
            raw_a = row.get("score_away")
            if raw_h is not None and raw_a is not None:
                sh = int(raw_h)
                sa = int(raw_a)
                return sh == 0 or sa == 0
            # Fallback : nul 0-0 ou victoire large → BTTS_N probable
            if ftr == "D" and total_goals == 0:
                return True
            if total_goals < 2:
                return True  # Au moins une équipe a 0 but
            return False  # Pas assez d'info
        return False
