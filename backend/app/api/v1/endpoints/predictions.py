"""
API Predictions — Predator Brain

Endpoints:
  POST /api/v1/predictions/analyze        Analyse complète d'un match
  POST /api/v1/predictions/value-bets     Détection de value bets
  POST /api/v1/predictions/ticket         Génération de ticket
  GET  /api/v1/predictions/model-status   État du modèle
  POST /api/v1/predictions/retrain        Réentraîner le modèle
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger("predator.api.predictions")
router = APIRouter(prefix="/predictions", tags=["Predictions"])


# ─── Schémas ──────────────────────────────────────────────────────────────────

class MatchAnalysisRequest(BaseModel):
    home_team: str = Field(..., min_length=2, example="Arsenal")
    away_team: str = Field(..., min_length=2, example="Chelsea")
    league: Optional[str] = Field(None, example="PL")
    match_date: Optional[str] = None

    # Cotes bookmaker (optionnel — pour value bets)
    bookmaker_odds: Optional[Dict[str, Dict[str, float]]] = Field(
        None,
        description='{"pinnacle": {"home": 2.10, "draw": 3.40, "away": 3.80, "over_25": 1.85}}',
        example={"bet365": {"home": 2.10, "draw": 3.40, "away": 3.80, "over_25": 1.85}}
    )

    # Context (améliore la confiance)
    form_home: float = Field(0.5, ge=0, le=1, description="Ratio forme domicile 0-1")
    form_away: float = Field(0.5, ge=0, le=1, description="Ratio forme extérieur 0-1")
    injuries_home: int = Field(0, ge=0, description="Nombre de blessés importants domicile")
    injuries_away: int = Field(0, ge=0, description="Nombre de blessés importants extérieur")
    is_important_match: bool = Field(False, description="Match décisif / titre / relégation")


class ValueBetScanRequest(BaseModel):
    matches: List[Dict] = Field(
        ...,
        description="Liste de matchs avec bookmaker_odds et context",
        example=[{
            "match_id": "ars_che_2025",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "league": "PL",
            "bookmaker_odds": {"bet365": {"home": 2.10, "draw": 3.40, "away": 3.80}},
            "form_home": 0.7,
            "form_away": 0.4,
        }]
    )
    min_edge: float = Field(0.03, ge=0.01, le=0.30)
    top_n: int = Field(20, ge=1, le=100)


class TicketRequest(BaseModel):
    available_bets: List[Dict] = Field(..., description="Value bets disponibles")
    ticket_type: str = Field("balanced", description="safe / balanced / risky / jackpot")
    n_tickets: int = Field(3, ge=1, le=10)
    bankroll: float = Field(10_000.0, gt=0)


class RetrainRequest(BaseModel):
    csv_dir: Optional[str] = None
    min_matches: int = Field(200, ge=50)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/model-status")
def model_status():
    """État du modèle Dixon-Coles."""
    from app.core.model_registry import registry

    return {
        "is_trained":        registry.is_trained,
        "n_matches":         registry.n_matches,
        "n_teams":           len(registry.dc.teams_) if registry.dc else 0,
        "training_leagues":  registry.training_leagues,
        "gamma":             round(registry.dc.gamma_, 4) if registry.dc else 0,
        "rho":               round(registry.dc.rho_, 4) if registry.dc else 0,
        "status":            "ready" if registry.is_trained else "not_trained",
        "message": (
            "Modèle prêt — toutes les fonctionnalités disponibles"
            if registry.is_trained
            else "Modèle non entraîné — lancez POST /retrain ou les prédictions utiliseront les valeurs par défaut"
        ),
    }


@router.post("/retrain")
async def retrain_model(req: RetrainRequest, bg: BackgroundTasks):
    """
    Réentraîne le modèle Dixon-Coles sur les données CSV.
    Opération asynchrone (peut prendre 30-60 secondes).
    """
    from app.core.model_registry import registry

    def _train():
        result = registry.train_from_csv(req.csv_dir, req.min_matches)
        logger.info(f"[RETRAIN] Résultat: {result}")

    bg.add_task(_train)
    return {
        "status": "training_started",
        "message": "Entraînement lancé en arrière-plan. Vérifiez /model-status dans 30-60 secondes.",
    }


@router.post("/analyze")
def analyze_match(req: MatchAnalysisRequest):
    """
    Analyse complète d'un match.

    Retourne:
    - Probabilités 1X2 (Dixon-Coles)
    - Probabilités Over/Under 1.5 / 2.5 / 3.5
    - Probabilités BTTS
    - Scores les plus probables
    - Cotes justes (sans marge)
    - Value bets si cotes bookmaker fournies
    - Explications IA
    """
    from app.core.model_registry import registry

    # Prédiction
    probs = registry.predict(req.home_team, req.away_team, req.form_home, req.form_away)

    # Cotes justes
    fair_odds = {}
    if registry.dc and registry.is_trained:
        fair_odds = registry.dc.get_fair_odds(req.home_team, req.away_team)

    # Value bets (si cotes fournies)
    value_bets = []
    if req.bookmaker_odds and registry.dc and registry.is_trained:
        try:
            analyses = registry.value_engine.analyze_match(
                match_id=f"{req.home_team}_{req.away_team}",
                home_team=req.home_team,
                away_team=req.away_team,
                model_probs={
                    "home":      probs["prob_home"],
                    "draw":      probs["prob_draw"],
                    "away":      probs["prob_away"],
                    "over_15":   probs.get("prob_over_15", 0.75),
                    "over_25":   probs.get("prob_over_25", 0.55),
                    "over_35":   probs.get("prob_over_35", 0.32),
                    "under_25":  probs.get("prob_under_25", 0.45),
                    "btts_yes":  probs.get("prob_btts_yes", 0.52),
                    "btts_no":   probs.get("prob_btts_no", 0.48),
                    "1X":        probs.get("prob_1X", 0.72),
                    "X2":        probs.get("prob_X2", 0.54),
                    "12":        probs.get("prob_12", 0.74),
                },
                bookmaker_odds=req.bookmaker_odds,
                match_date=datetime.fromisoformat(req.match_date) if req.match_date else None,
                recent_form_home=req.form_home,
                recent_form_away=req.form_away,
                n_injuries_home=req.injuries_home,
                n_injuries_away=req.injuries_away,
                is_important_match=req.is_important_match,
            )
            value_bets = [
                {
                    "market":          vb.market,
                    "selection":       vb.selection,
                    "bookmaker":       vb.best_bookmaker,
                    "bookmaker_odds":  vb.best_bookmaker_odds,
                    "prob_model":      vb.prob_model,
                    "prob_sharp":      vb.prob_sharp,
                    "fair_odds":       round(1 / vb.prob_model, 3) if vb.prob_model > 0 else 0,
                    "edge_pct":        vb.edge_vs_model,
                    "value_rating":    vb.value_rating,
                    "confidence":      vb.confidence,
                    "kelly_stake_pct": vb.kelly_fraction,
                    "reasons":         vb.reasons,
                    "warnings":        vb.warnings,
                }
                for vb in analyses
            ]
        except Exception as e:
            logger.error(f"[ANALYZE] Value bets error: {e}")

    # Explications IA
    explanations = _generate_ai_explanations(req, probs, value_bets)

    # Construire le bloc prediction (attendu par le frontend)
    score_matrix_raw = probs.get("score_matrix", {})
    # Convertir dict {"1-0": 0.12} → liste 2D [[p00, p01,...], [p10,...], ...]
    if isinstance(score_matrix_raw, dict):
        size = 6
        matrix_2d = [[0.0] * size for _ in range(size)]
        for key, val in score_matrix_raw.items():
            try:
                h, a = map(int, str(key).split("-"))
                if h < size and a < size:
                    matrix_2d[h][a] = float(val)
            except Exception:
                pass
    elif isinstance(score_matrix_raw, list):
        matrix_2d = score_matrix_raw
    else:
        matrix_2d = []

    prediction_block = {
        "prob_home":     probs["prob_home"],
        "prob_draw":     probs["prob_draw"],
        "prob_away":     probs["prob_away"],
        "prob_over_15":  probs.get("prob_over_15", 0.75),
        "prob_over_25":  probs.get("prob_over_25", 0.55),
        "prob_over_35":  probs.get("prob_over_35", 0.32),
        "prob_under_15": probs.get("prob_under_15", 0.25),
        "prob_under_25": probs.get("prob_under_25", 0.45),
        "prob_under_35": probs.get("prob_under_35", 0.68),
        "prob_btts_yes": probs.get("prob_btts_yes", 0.52),
        "prob_btts_no":  probs.get("prob_btts_no", 0.48),
        "lambda_home":   probs.get("lambda_home", 1.4),
        "lambda_away":   probs.get("lambda_away", 1.1),
        "most_likely_score": probs.get("most_likely_score", "1-0"),
        "score_matrix":  matrix_2d,
        "confidence":    probs.get("confidence", 0.5),
        "dc_known":      probs.get("dc_known", False),
        "is_fallback":   probs.get("is_fallback", True),
    }

    return {
        "match": {
            "home_team": req.home_team,
            "away_team": req.away_team,
            "league": req.league,
            "match_date": req.match_date,
        },
        # Alias pour le frontend (prediction = même chose que probabilities)
        "prediction": prediction_block,
        # Rétrocompat
        "probabilities": {
            "home":     probs["prob_home"],
            "draw":     probs["prob_draw"],
            "away":     probs["prob_away"],
            "over_25":  probs.get("prob_over_25", 0.55),
            "under_25": probs.get("prob_under_25", 0.45),
            "btts_yes": probs.get("prob_btts_yes", 0.52),
            "btts_no":  probs.get("prob_btts_no", 0.48),
        },
        "expected_goals": {
            "lambda_home": probs.get("lambda_home", 1.4),
            "lambda_away": probs.get("lambda_away", 1.1),
        },
        "score_prediction": {
            "most_likely":  probs.get("most_likely_score", "1-0"),
            "score_matrix": score_matrix_raw,
        },
        "fair_odds": fair_odds,
        "value_bets": value_bets,
        "ai_analysis": explanations,
        "model_meta": {
            "dc_known":    probs.get("dc_known", False),
            "is_fallback": probs.get("is_fallback", True),
            "model":       "Dixon-Coles + Ensemble",
        },
    }


@router.post("/value-bets")
def scan_value_bets(req: ValueBetScanRequest):
    """
    Scanne plusieurs matchs et retourne les meilleures value bets.
    """
    from app.core.model_registry import registry

    enriched_matches = []
    for match in req.matches:
        home = match.get("home_team", "")
        away = match.get("away_team", "")

        if not home or not away:
            continue

        probs = registry.predict(
            home, away,
            match.get("form_home", 0.5),
            match.get("form_away", 0.5),
        )

        enriched_matches.append({
            **match,
            "model_probs": {
                "home": probs["prob_home"], "draw": probs["prob_draw"],
                "away": probs["prob_away"],
                "over_25": probs.get("prob_over_25", 0.55),
                "under_25": probs.get("prob_under_25", 0.45),
                "btts_yes": probs.get("prob_btts_yes", 0.52),
                "btts_no": probs.get("prob_btts_no", 0.48),
                "1X": probs.get("prob_1X", 0.72),
                "X2": probs.get("prob_X2", 0.54),
            },
        })

    # Scanner avec le moteur de value
    engine = registry.value_engine
    engine.min_edge = req.min_edge
    results = engine.scan_portfolio(enriched_matches, top_n=req.top_n)

    return {
        "total_matches_scanned": len(req.matches),
        "value_bets_found":      len(results),
        "value_bets": [
            {
                "match":           f"{vb.home_team} vs {vb.away_team}",
                "league":          match.get("league", "?"),
                "market":          vb.market,
                "selection":       vb.selection,
                "bookmaker":       vb.best_bookmaker,
                "bookmaker_odds":  vb.best_bookmaker_odds,
                "prob_model":      vb.prob_model,
                "fair_odds":       round(1 / vb.prob_model, 3) if vb.prob_model > 0 else 0,
                "edge_pct":        vb.edge_vs_model,
                "value_rating":    vb.value_rating,
                "confidence":      vb.confidence,
                "kelly_stake_pct": vb.kelly_fraction,
                "reasons":         vb.reasons[:3],
            }
            for vb, match in zip(
                results,
                [m for m in req.matches for _ in range(10)][:len(results)]  # match context
            )
        ],
    }


@router.post("/ticket")
def generate_ticket(req: TicketRequest):
    """
    Génère des tickets combinés intelligents.
    """
    from app.core.model_registry import registry
    from app.services.engines.ticket_generator import TicketGenerator, TicketType

    ticket_type_map = {
        "safe":     TicketType.SAFE,
        "balanced": TicketType.BALANCED,
        "risky":    TicketType.RISKY,
        "jackpot":  TicketType.JACKPOT,
    }
    t_type = ticket_type_map.get(req.ticket_type, TicketType.BALANCED)

    gen = TicketGenerator(bankroll=req.bankroll)
    tickets = gen.generate(req.available_bets, ticket_type=t_type, n_tickets=req.n_tickets)

    return {
        "ticket_type":   req.ticket_type,
        "tickets_found": len(tickets),
        "tickets": [
            {
                "legs": len(t.legs),
                "total_odds": t.total_odds,
                "combined_prob": t.combined_prob,
                "fair_odds": t.fair_odds,
                "implied_edge_pct": t.implied_edge_pct,
                "quality_score": t.quality_score,
                "risk_rating": t.risk_rating,
                "is_recommended": t.is_recommended,
                "recommended_stake_pct": t.recommended_stake_pct,
                "recommended_stake_abs": t.recommended_stake_abs,
                "summary": t.summary,
                "warnings": t.warnings,
                "selections": [
                    {
                        "match": f"{leg.home_team} vs {leg.away_team}",
                        "league": leg.league,
                        "selection": leg.selection,
                        "market": leg.market_label,
                        "bookmaker": leg.bookmaker,
                        "odds": leg.odds,
                        "prob_model": leg.prob_model,
                        "edge_pct": leg.edge_pct,
                        "confidence": leg.confidence,
                        "reasons": leg.reasons[:2],
                    }
                    for leg in t.legs
                ],
            }
            for t in tickets
        ],
    }


@router.get("/model-quality")
def model_quality():
    """
    Rapport de qualité du modèle Dixon-Coles.
    Retourne les métriques de calibration, la couverture par championnat,
    et des avertissements si les données sont insuffisantes.
    """
    from app.core.model_registry import registry
    from datetime import datetime

    if not registry.is_trained or registry.dc is None:
        return {
            "is_trained": False,
            "warning": "MODÈLE NON ENTRAÎNÉ — les prédictions utilisent des valeurs par défaut (46%/26%/28%).",
            "warning_level": "CRITICAL",
            "recommendations": [
                "Placez des CSV football-data.co.uk dans data/raw/",
                "Cliquez sur 'Réentraîner' dans les Paramètres",
                "N'utilisez PAS ce logiciel pour parier sans données réelles",
            ],
        }

    dc = registry.dc
    df = registry._df_cache

    # ── Métriques de base ─────────────────────────────────────────────────────
    n_teams   = len(dc.teams_)
    n_matches = registry.n_matches
    leagues   = registry.training_leagues

    # ── Statistiques du dataset ───────────────────────────────────────────────
    dataset_stats = {}
    if df is not None and not df.empty:
        dataset_stats = {
            "total_matches":  len(df),
            "date_from":      str(df["match_date"].min().date()) if "match_date" in df.columns else "?",
            "date_to":        str(df["match_date"].max().date()) if "match_date" in df.columns else "?",
            "avg_goals":      round(df["total_goals"].mean(), 2) if "total_goals" in df.columns else None,
            "home_win_rate":  round((df["ftr"] == "H").mean() * 100, 1) if "ftr" in df.columns else None,
            "draw_rate":      round((df["ftr"] == "D").mean() * 100, 1) if "ftr" in df.columns else None,
            "away_win_rate":  round((df["ftr"] == "A").mean() * 100, 1) if "ftr" in df.columns else None,
            "over_25_rate":   round(df["over_25"].mean() * 100, 1) if "over_25" in df.columns else None,
            "btts_rate":      round(df["btts"].mean() * 100, 1) if "btts" in df.columns else None,
        }

    # ── Performance par championnat ────────────────────────────────────────────
    by_league = {}
    if df is not None and "league" in df.columns:
        for lg, grp in df.groupby("league"):
            teams_in_league = set(grp["team_home"].tolist() + grp["team_away"].tolist())
            known = sum(1 for t in teams_in_league if t in dc.attack_)
            by_league[str(lg)] = {
                "matches":    len(grp),
                "teams":      len(teams_in_league),
                "known_teams": known,
                "coverage_pct": round(known / len(teams_in_league) * 100, 0) if teams_in_league else 0,
            }

    # ── Paramètres du modèle ──────────────────────────────────────────────────
    model_params = {
        "gamma":  round(dc.gamma_, 4),   # avantage domicile
        "rho":    round(dc.rho_, 4),     # correction DC (attendu ≈ -0.13)
        "n_teams": n_teams,
        "n_matches_trained": n_matches,
    }

    # Top 5 attaques et défenses
    top_attacks  = sorted(dc.attack_.items(),  key=lambda x: x[1], reverse=True)[:5]
    top_defenses = sorted(dc.defense_.items(), key=lambda x: x[1])[:5]  # plus bas = meilleur

    # ── Avertissements ─────────────────────────────────────────────────────────
    warnings = []
    warning_level = "OK"

    if n_matches < 500:
        warnings.append(f"⚠️ Seulement {n_matches} matchs d'entraînement — minimum recommandé : 2 000+")
        warning_level = "WARNING"
    if n_teams < 40:
        warnings.append(f"⚠️ Seulement {n_teams} équipes — peu de couverture internationale")
        warning_level = "WARNING"
    if n_matches < 200:
        warnings.append("🔴 CRITIQUE : données insuffisantes — NE PAS UTILISER pour paris réels")
        warning_level = "CRITICAL"
    if len(leagues) < 3:
        warnings.append("⚠️ Moins de 3 championnats — les prédictions hors-données sont peu fiables")
    if abs(dc.rho_) < 0.01:
        warnings.append("⚠️ Paramètre ρ proche de zéro — optimisation possiblement non convergée")

    if not warnings:
        warnings.append("✅ Modèle correctement calibré sur des données suffisantes")

    return {
        "is_trained":     True,
        "warning_level":  warning_level,
        "warnings":       warnings,
        "model_params":   model_params,
        "dataset":        dataset_stats,
        "leagues":        leagues,
        "by_league":      by_league,
        "top_teams": {
            "attack":  [{"team": t, "score": round(s, 3)} for t, s in top_attacks],
            "defense": [{"team": t, "score": round(s, 3)} for t, s in top_defenses],
        },
        "interpretation": {
            "gamma_meaning": (
                f"Avantage domicile: +{dc.gamma_:.2f} (élevé > 0.4, normal ≈ 0.2-0.35)"
                if dc.gamma_ > 0.2 else f"Avantage domicile faible: {dc.gamma_:.2f}"
            ),
            "rho_meaning": (
                f"Correction DC ρ={dc.rho_:.3f} — correction active sur 0-0/1-0/0-1/1-1"
                if dc.rho_ < -0.05 else "ρ proche de 0 — correction Dixon-Coles peu active"
            ),
        },
        "recommendations": [
            "✅ Utiliser les marchés 1X2 sur les équipes avec coverage=100%",
            "⚠️ Éviter les équipes non présentes dans le modèle (dc_known=false)",
            "⚠️ Ne jamais miser plus de 2% du bankroll par pari en mode débutant",
            "✅ Vérifier CLV > 0 sur 30+ paris avant d'augmenter les mises",
        ],
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_ai_explanations(req: MatchAnalysisRequest, probs: dict, value_bets: list) -> dict:
    """Génère des explications IA basées uniquement sur les données calculées."""
    home = req.home_team
    away = req.away_team

    prob_h = probs.get("prob_home", 0.46)
    prob_d = probs.get("prob_draw", 0.26)
    prob_a = probs.get("prob_away", 0.28)
    prob_ov25 = probs.get("prob_over_25", 0.55)
    prob_btts = probs.get("prob_btts_yes", 0.52)

    # Décision principale
    max_prob = max(prob_h, prob_d, prob_a)
    if max_prob == prob_h:
        decision = "DOMICILE"
        decision_reason = f"Le modèle estime une victoire domicile à {prob_h:.0%}"
    elif max_prob == prob_a:
        decision = "EXTÉRIEUR"
        decision_reason = f"L'équipe extérieure est favorite à {prob_a:.0%}"
    else:
        decision = "NUL"
        decision_reason = f"Match équilibré — probabilité de nul {prob_d:.0%}"

    # Recommandation O/U
    ou_reco = "OVER 2.5" if prob_ov25 > 0.55 else "UNDER 2.5"
    btts_reco = "BTTS OUI" if prob_btts > 0.55 else "BTTS NON"

    # Signal de confiance
    confidence_label = "FORTE" if max_prob > 0.60 else "MODÉRÉE" if max_prob > 0.50 else "FAIBLE"

    lines = []
    lines.append(f"Pour {home} vs {away}, le modèle recommande : {decision} ({decision_reason}).")

    if value_bets:
        best = value_bets[0]
        lines.append(f"Meilleure value bet détectée : {best['market']} @ {best['bookmaker_odds']} "
                     f"avec un edge de +{best['edge_pct']:.1f}%.")

    if prob_ov25 > 0.60:
        lines.append(f"Match offensif attendu (xG combinés : {probs.get('lambda_home',1.4):.1f} + "
                     f"{probs.get('lambda_away',1.1):.1f}) — {ou_reco} probable à {prob_ov25:.0%}.")
    elif prob_ov25 < 0.45:
        lines.append(f"Match fermé attendu — UNDER 2.5 probable à {1-prob_ov25:.0%}.")

    if not value_bets:
        lines.append("Aucune value bet détectée avec les cotes fournies — "
                     "les cotes reflètent déjà l'avantage du modèle.")

    return {
        "decision":        decision,
        "confidence":      confidence_label,
        "ou_recommendation": ou_reco,
        "btts_recommendation": btts_reco,
        "narrative":       " ".join(lines),
        "key_stats": {
            f"prob_{decision.lower()}": max_prob,
            "over_25": prob_ov25,
            "btts_yes": prob_btts,
        },
    }
