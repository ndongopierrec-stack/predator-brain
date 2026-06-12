"""
Predator Brain — Point d'entrée production (Railway)
Lance avec: uvicorn main_prod:app --host 0.0.0.0 --port $PORT
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ─── Path setup ───────────────────────────────────────────────────────────────
# En prod Railway, le CWD est le dossier backend
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
logger = logging.getLogger("predator.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  PREDATOR BRAIN API — Production Railway")
    logger.info("=" * 60)
    try:
        from app.core.model_registry import registry
        result = registry.train_from_csv()
        if result["success"]:
            logger.info(f"✓ Modèle Dixon-Coles — {result['n_matches']} matchs, {result['n_teams']} équipes")
        else:
            logger.warning(f"Modèle non entraîné: {result.get('error')} — mode fallback actif")
    except Exception as e:
        logger.error(f"Erreur init: {e}")
    yield
    logger.info("Arrêt Predator Brain")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Predator Brain API",
    description="Moteur de pronostics professionnels — Dixon-Coles, Value Bets, CLV, Backtesting",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS — autorise le frontend Railway ──────────────────────────────────────

FRONTEND_URL = os.getenv("FRONTEND_URL", "")
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://localhost:3001",
]
if FRONTEND_URL:
    ALLOWED_ORIGINS.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

from app.api.v1.endpoints.predictions import router as pred_router
from app.api.v1.endpoints.backtesting  import router as bt_router
from app.api.v1.endpoints.bankroll     import router as bk_router
from app.api.v1.endpoints.clv          import router as clv_router

PREFIX = "/api/v1"
app.include_router(pred_router, prefix=PREFIX)
app.include_router(bt_router,   prefix=PREFIX)
app.include_router(bk_router,   prefix=PREFIX)
app.include_router(clv_router,  prefix=PREFIX)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    try:
        from app.core.model_registry import registry
        return {
            "status":      "ok",
            "version":     "1.0.0",
            "model_ready": registry.is_trained,
            "n_matches":   registry.n_matches,
            "n_teams":     len(registry.dc.teams_) if registry.dc else 0,
            "env":         "railway",
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@app.get("/", tags=["System"])
def root():
    return {
        "name":    "Predator Brain API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/health",
        "status":  "running on Railway 🚀",
    }
