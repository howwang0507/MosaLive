@echo off
setlocal
rem Builds the MosaLive desktop installer (dist\desktop\MosaLive-Setup-<version>.exe).
rem Needs Node.js 22+ and internet access the first time (Electron and electron-builder).
cd /d "%~dp0desktop"
where npm >nul 2>nul || (echo Install Node.js 22+ first: https://nodejs.org/ & pause & exit /b 1)
call npm install --no-audit --no-fund || (echo npm install failed. & pause & exit /b 1)
call npm test || (echo Tests failed; installer not built. & pause & exit /b 1)
call npm run dist || (echo Build failed. & pause & exit /b 1)
echo.
echo Done. Installer: %~dp0dist\desktop
explorer "%~dp0dist\desktop"
pause
