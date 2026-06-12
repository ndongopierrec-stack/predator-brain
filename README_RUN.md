# 🎯 Predator Brain — Guide de lancement

## Prérequis

| Outil | Version minimale | Lien |
|-------|-----------------|------|
| Node.js | 18.17+ (testé avec v24) | https://nodejs.org |
| Python | 3.10+ (testé avec 3.12) | https://python.org |
| npm | 9+ | inclus avec Node.js |

---

## 🚀 Lancement rapide (Windows)

### Option A — Double-clic sur les scripts

1. Double-clic sur **`start-backend.bat`**
2. Double-clic sur **`start-frontend.bat`**
3. Ouvrir http://localhost:3001

### Option B — Terminal

**Terminal 1 — Backend :**
```cmd
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

**Terminal 2 — Frontend :**
```cmd
cd frontend
npm install
npm run dev
```

---

## 🌐 URLs locales

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Dashboard | http://localhost:3001/dashboard |
| API Health | http://localhost:8001/health |
| API Docs | http://localhost:8001/docs |

## 🌍 URLs production Railway

| Service | URL |
|---------|-----|
| Frontend | https://predator-brain-web-production.up.railway.app |
| Backend | https://determined-victory-production-be68.up.railway.app |

---

## 🔄 Réinstallation propre du frontend

```cmd
cd frontend
rmdir /s /q node_modules
del package-lock.json
npm install
npm run build
```

---

## ✅ Vérifications

```cmd
# TypeScript (0 erreur attendu)
cd frontend && npm run typecheck

# Build production
cd frontend && npm run build

# Health backend
curl http://localhost:8001/health
```

---

## 🔑 Variables d'environnement

### Frontend (`frontend/.env.local`)
```env
# Local
NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1

# Production (Railway)
# NEXT_PUBLIC_API_URL=https://determined-victory-production-be68.up.railway.app/api/v1
```

### Backend (`backend/.env`)
```env
# APIs données sportives (légales — optionnel pour données live)
THE_ODDS_API_KEY=your_key_here
FOOTBALL_DATA_API_KEY=your_key_here
API_FOOTBALL_KEY=your_key_here

# Bankroll par défaut
DEFAULT_BANKROLL=10000
KELLY_FRACTION=0.25
```

---

## 📊 Activer le modèle Dixon-Coles

Le modèle fonctionne en **mode fallback** sans données. Pour l'activer avec de vraies données :

1. Télécharger des CSV depuis https://www.football-data.co.uk/data.php
2. Placer les fichiers dans `data/raw/` à la racine du projet
3. Appuyer sur **"Réentraîner le modèle"** dans la page Paramètres
   — ou appeler `POST http://localhost:8001/api/v1/predictions/retrain`

---

## 🏗️ Structure du projet

```
predator_brain/
├── backend/                 # FastAPI — Python 3.12
│   ├── main.py              # Point d'entrée local
│   ├── main_prod.py         # Point d'entrée Railway
│   ├── requirements.txt     # Dépendances Python
│   └── app/
│       ├── api/v1/endpoints/  # Routes API
│       ├── core/              # Model registry
│       └── services/          # Moteurs (Dixon-Coles, Kelly, CLV...)
├── frontend/                # Next.js 14.2.35
│   ├── src/app/             # 11 pages
│   ├── src/lib/api.ts       # Client API typé
│   ├── src/components/      # Sidebar
│   └── package.json         # Versions verrouillées
├── data/raw/                # CSV football-data.co.uk (gitignored)
├── start-backend.bat        # Script Windows backend
├── start-frontend.bat       # Script Windows frontend
└── README_RUN.md            # Ce fichier
```

---

## ⚠️ Notes importantes

- **Aucun fichier copié depuis un autre projet** — installation 100% autonome via npm/pip
- **Sources légales uniquement** : football-data.co.uk, The Odds API, football-data.org
- **Pas de scraping**, pas d'API privée, pas de contournement de bookmaker
