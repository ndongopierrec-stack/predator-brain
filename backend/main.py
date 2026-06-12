"""
Predator Brain — API FastAPI (développement local)

Lancer depuis le dossier backend/ :
    uvicorn main:app --reload --port 8001

Docs : http://localhost:8001/docs
"""

import sys
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

# ── Path setup : ajoute backend/ au sys.path pour les imports relatifs ────────
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("predator.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage : lance l'entraînement du modèle en arrière-plan (non-bloquant)."""
    logger.info("=" * 60)
    logger.info("  PREDATOR BRAIN API — Démarrage (local)")
    logger.info("=" * 60)

    def _train_background():
        try:
            from app.core.model_registry import registry
            logger.info("[STARTUP] Entraînement Dixon-Coles en arrière-plan...")
            result = registry.train_from_csv()
            if result["success"]:
                logger.info(
                    f"[STARTUP] ✓ Modèle prêt — {result['n_matches']} matchs, "
                    f"{result['n_teams']} équipes"
                )
            else:
                logger.warning(
                    f"[STARTUP] Mode fallback : {result.get('error', 'pas de données')}. "
                    "Les endpoints répondent avec valeurs par défaut."
                )
        except Exception as e:
            logger.error(f"[STARTUP] Erreur init: {e}", exc_info=True)

    # Lancer l'entraînement dans un thread daemon — uvicorn répond immédiatement
    t = threading.Thread(target=_train_background, daemon=True, name="dc-trainer")
    t.start()
    logger.info("[STARTUP] API disponible immédiatement — modèle en cours d'entraînement...")

    yield

    logger.info("[SHUTDOWN] Predator Brain arrêté")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Predator Brain API",
    description="""
## 🎯 Predator Brain — Moteur de pronostics professionnels

API RESTful pour la détection de value bets, l'analyse statistique des matchs
et la gestion de bankroll.

### Modules :
- **Predictions** — Dixon-Coles, probabilités 1X2/Over-Under/BTTS/Scores
- **Value Bets** — Détection d'edge positif contre les bookmakers
- **Backtesting** — Test historique walk-forward
- **CLV** — Closing Line Value tracking
- **Bankroll** — Gestion Kelly + alertes de risque
- **Tickets** — Générateur de combinés intelligents

### Sources légales :
- football-data.co.uk (CSV historiques)
- The Odds API (cotes temps réel)
- football-data.org (stats officielles)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (local uniquement) ────────────────────────────────────────────────────

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

# ── Routers ───────────────────────────────────────────────────────────────────

from app.api.v1.endpoints.predictions import router as pred_router
from app.api.v1.endpoints.backtesting  import router as bt_router
from app.api.v1.endpoints.bankroll     import router as bk_router
from app.api.v1.endpoints.clv          import router as clv_router
from app.api.v1.endpoints.ou_btts      import router as ou_btts_router
from app.api.v1.endpoints.validation   import router as val_router

PREFIX = "/api/v1"
app.include_router(pred_router,    prefix=PREFIX)
app.include_router(bt_router,      prefix=PREFIX)
app.include_router(bk_router,      prefix=PREFIX)
app.include_router(clv_router,     prefix=PREFIX)
app.include_router(ou_btts_router, prefix=PREFIX)
app.include_router(val_router,     prefix=PREFIX)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    from app.core.model_registry import registry
    return {
        "status":      "ok",
        "version":     "1.0.0",
        "model_ready": registry.is_trained,
        "n_matches":   registry.n_matches,
        "n_teams":     len(registry.dc.teams_) if registry.dc else 0,
        "env":         "local",
    }


@app.get("/", tags=["System"])
def root():
    return {
        "name":    "Predator Brain API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/health",
        "endpoints": {
            "predictions":  "POST /api/v1/predictions/analyze",
            "value_bets":   "GET  /api/v1/predictions/value-bets",
            "retrain":      "POST /api/v1/predictions/retrain",
            "model_status": "GET  /api/v1/predictions/model-status",
            "backtest":     "POST /api/v1/backtest/run",
            "strategies":   "GET  /api/v1/backtest/strategies",
            "bankroll":     "GET  /api/v1/bankroll/snapshot",
            "stake":        "POST /api/v1/bankroll/calculate-stake",
            "clv":          "GET  /api/v1/clv/summary",
            "clv_record":   "POST /api/v1/clv/record-bet",
            "ticket":       "POST /api/v1/predictions/ticket",
            "ou_btts":      "POST /api/v1/ou-btts/analyze",
            "ou_btts_scan": "POST /api/v1/ou-btts/scan",
        },
    }
