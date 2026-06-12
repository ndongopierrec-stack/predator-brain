"""API CLV — Predator Brain"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

logger = logging.getLogger("predator.api.clv")
router = APIRouter(prefix="/clv", tags=["CLV"])


class RecordBetRequest(BaseModel):
    bet_id: str
    match_id: str
    home_team: str
    away_team: str
    league: str = "unknown"
    market: str = "1X2_H"
    bookmaker: str
    odds_taken: float = Field(..., gt=1.0)
    stake: float = Field(..., gt=0)
    prob_model: float = Field(0.5, ge=0, le=1)
    model_edge_pct: float = 0.0
    bankroll_before: float = 10_000.0
    match_date: Optional[str] = None


class UpdateClosingRequest(BaseModel):
    bet_id: str
    closing_odds: float = Field(..., gt=1.0)


class SettleRequest(BaseModel):
    bet_id: str
    won: bool
    bankroll_after: Optional[float] = None


class CLVReportRequest(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None


@router.post("/record-bet")
def record_bet(req: RecordBetRequest):
    from app.core.model_registry import registry
    from app.services.engines.clv_engine import BetRecord

    record = BetRecord(
        bet_id=req.bet_id,
        match_id=req.match_id,
        home_team=req.home_team,
        away_team=req.away_team,
        league=req.league,
        market=req.market,
        bookmaker=req.bookmaker,
        odds_taken=req.odds_taken,
        stake=req.stake,
        prob_model=req.prob_model,
        model_edge_at_placement=req.model_edge_pct / 100,
        bankroll_before=req.bankroll_before,
        match_date=datetime.fromisoformat(req.match_date) if req.match_date else datetime.utcnow(),
    )
    registry.clv_engine.record_bet(record)
    return {"status": "recorded", "bet_id": req.bet_id}


@router.post("/update-closing")
def update_closing(req: UpdateClosingRequest):
    from app.core.model_registry import registry
    rec = registry.clv_engine.update_closing_odds(req.bet_id, req.closing_odds)
    if not rec:
        raise HTTPException(404, f"Pari {req.bet_id} non trouvé")
    return {
        "bet_id": req.bet_id,
        "odds_taken": rec.odds_taken,
        "odds_closing": rec.odds_closing,
        "clv_pct": rec.clv_pct,
        "clv_signal": rec.clv_signal,
    }


@router.post("/settle")
def settle_bet(req: SettleRequest):
    from app.core.model_registry import registry
    rec = registry.clv_engine.settle_bet(req.bet_id, req.won, req.bankroll_after)
    if not rec:
        raise HTTPException(404, f"Pari {req.bet_id} non trouvé")
    return {
        "bet_id": req.bet_id,
        "result": rec.result_actual,
        "profit": rec.profit,
        "clv_pct": rec.clv_pct,
    }


@router.post("/report")
def clv_report(req: CLVReportRequest):
    from app.core.model_registry import registry

    from_dt = datetime.fromisoformat(req.from_date) if req.from_date else None
    to_dt   = datetime.fromisoformat(req.to_date) if req.to_date else None

    report = registry.clv_engine.generate_report(from_dt, to_dt)

    return {
        "period": {
            "from": report.period_start.isoformat(),
            "to":   report.period_end.isoformat(),
        },
        "clv": {
            "total_bets":         report.total_bets,
            "avg_clv_pct":        report.avg_clv_pct,
            "median_clv_pct":     report.median_clv_pct,
            "clv_positive_rate":  round(report.clv_positive_rate * 100, 1),
            "distribution": {
                "excellent": report.excellent,
                "good":      report.good,
                "neutral":   report.neutral,
                "bad":       report.bad,
                "terrible":  report.terrible,
            },
        },
        "performance": {
            "roi_actual":     report.roi_actual,
            "total_profit":   report.total_profit,
            "total_staked":   report.total_staked,
            "win_rate":       round(report.win_rate * 100, 1),
            "sharpe_ratio":   report.sharpe_ratio,
            "max_drawdown":   round(report.max_drawdown * 100, 2),
        },
        "by_league":          report.by_league,
        "by_market":          report.by_market,
        "by_bookmaker":       report.by_bookmaker,
        "by_confidence_tier": report.by_confidence_tier,
        "equity_curve":       report.equity_curve[-200:],
        "clv_cumulative":     report.clv_cumulative[-200:],
        "verdict":            report.verdict,
        "is_profitable":      report.is_profitable,
    }


@router.get("/summary")
def clv_summary():
    from app.core.model_registry import registry
    return registry.clv_engine.summary_stats()


@router.post("/project-roi")
def project_roi(avg_clv_pct: float, avg_odds: float = 2.5, n_bets: int = 500):
    from app.core.model_registry import registry
    return registry.clv_engine.project_roi_from_clv(avg_clv_pct, avg_odds, n_bets)
