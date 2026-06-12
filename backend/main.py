"""
Predator Brain — API FastAPI principale

Démarrer: uvicorn predator_brain.backend.main:app --reload --port 8001
Docs:      http://localhost:8001/docs
"""

import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Setup path
_BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("predator.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage: charge et entraîne le modèle si les données sont disponibles."""
    logger.info("=" * 60)
    logger.info("  PREDATOR BRAIN API — Démarrage")
    logger.info("=" * 60)

    try:
        from predator_brain.backend.app.core.model_registry import registry
        logger.info("[STARTUP] Entraînement du modèle Dixon-Coles...")
        result = registry.train_from_csv()
        if result["success"]:
            logger.info(f"[STARTUP] ✓ Modèle prêt — {result['n_matches']} matchs, "
                        f"{result['n_teams']} équipes")
        else:
            logger.warning(f"[STARTUP] Modèle non entraîné: {result.get('error')} "
                           "— les endpoints fonctionneront avec les valeurs par défaut")
    except Exception as e:
        logger.error(f"[STARTUP] Erreur initialisation: {e}")

    yield

    logger.info("[SHUTDOWN] Predator Brain arrêté")


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Predator Brain API",
    description="""
## 🎯 Predator Brain — Moteur de pronostics professionnels

API RESTful pour la détection de value bets, l'analyse statistique des matchs
et la gestion de bankroll. Inspiré de Trademate Sports, Pinnacle CLV et RebelBetting.

### Modules disponibles:
- **Predictions** — Analyse Dixon-Coles, probabilités 1X2/O-U/BTTS/Scores
- **Value Bets** — Détection d'edge positif contre les bookmakers
- **Backtesting** — Test historique avec Walk-Forward validation
- **CLV** — Closing Line Value tracking (meilleur indicateur de qualité)
- **Bankroll** — Gestion Kelly + alertes de risque
- **Tickets** — Générateur de combinés intelligents

### Sources de données:
- football-data.co.uk (CSV historiques avec cotes)
- The Odds API (cotes temps réel — légal)
- football-data.org (API officielle stats)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

from predator_brain.backend.app.api.v1.endpoints.predictions import router as pred_router
from predator_brain.backend.app.api.v1.endpoints.backtesting import router as bt_router
from predator_brain.backend.app.api.v1.endpoints.bankroll import router as bk_router
from predator_brain.backend.app.api.v1.endpoints.clv import router as clv_router

PREFIX = "/api/v1"
app.include_router(pred_router, prefix=PREFIX)
app.include_router(bt_router,   prefix=PREFIX)
app.include_router(bk_router,   prefix=PREFIX)
app.include_router(clv_router,  prefix=PREFIX)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    from predator_brain.backend.app.core.model_registry import registry
    return {
        "status":      "ok",
        "version":     "1.0.0",
        "model_ready": registry.is_trained,
        "n_matches":   registry.n_matches,
        "n_teams":     len(registry.dc.teams_) if registry.dc else 0,
    }


@app.get("/", tags=["System"])
def root():
    return {
        "name":    "Predator Brain API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/health",
        "modules": [
            "POST /api/v1/predictions/analyze",
            "POST /api/v1/predictions/value-bets",
            "POST /api/v1/predictions/ticket",
            "POST /api/v1/backtest/run",
            "POST /api/v1/backtest/walk-forward",
            "GET  /api/v1/backtest/strategies",
            "POST /api/v1/bankroll/calculate-stake",
            "GET  /api/v1/bankroll/snapshot",
            "POST /api/v1/clv/report",
            "POST /api/v1/clv/record-bet",
        ],
    }
