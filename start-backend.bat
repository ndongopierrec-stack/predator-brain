@echo off
title Predator Brain - Backend API
color 0A

echo ============================================================
echo   PREDATOR BRAIN - Backend FastAPI (port 8001)
echo ============================================================
echo.

cd /d "%~dp0backend"

REM Vérifier que Python est disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Telecharger : https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Installer les dependances si necessaire
echo [1/2] Verification des dependances...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERREUR] Echec pip install. Verifiez votre connexion internet.
    pause
    exit /b 1
)

echo [2/2] Demarrage du serveur...
echo.
echo   API :  http://localhost:8001
echo   Docs : http://localhost:8001/docs
echo   Health : http://localhost:8001/health
echo.
echo Appuyez sur Ctrl+C pour arreter.
echo.

uvicorn main:app --reload --port 8001 --host 0.0.0.0

pause
