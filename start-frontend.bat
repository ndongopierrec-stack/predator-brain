@echo off
title Predator Brain - Frontend Next.js
color 0B

echo ============================================================
echo   PREDATOR BRAIN - Frontend Next.js (port 3001)
echo ============================================================
echo.

cd /d "%~dp0frontend"

REM Vérifier que Node est disponible
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Node.js n'est pas installe ou pas dans le PATH.
    echo Telecharger : https://nodejs.org/
    pause
    exit /b 1
)

REM Installer les dependances si node_modules absent
if not exist "node_modules\" (
    echo [1/2] Installation des dependances npm...
    npm install
    if errorlevel 1 (
        echo [ERREUR] Echec npm install.
        pause
        exit /b 1
    )
) else (
    echo [1/2] node_modules OK.
)

echo [2/2] Demarrage du serveur de developpement...
echo.
echo   Frontend : http://localhost:3001
echo   Dashboard : http://localhost:3001/dashboard
echo.
echo Assurez-vous que le backend tourne sur le port 8001.
echo Appuyez sur Ctrl+C pour arreter.
echo.

npm run dev

pause
