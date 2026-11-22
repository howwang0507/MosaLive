@echo off
setlocal
rem Runs the MosaLive desktop app from source (no installer). The models still run locally.
cd /d "%~dp0desktop"
where npm >nul 2>nul || (echo Install Node.js 22+ first: https://nodejs.org/ & pause & exit /b 1)
if not exist "node_modules\electron" (
 call npm install --no-audit --no-fund || (echo npm install failed. & pause & exit /b 1)
)
call npm start
