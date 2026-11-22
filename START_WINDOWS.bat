@echo off
setlocal
rem Default since 2026-11-08 (FLEURS replays, docs/codex-gpu-h-2026-11-08.md):
rem Faster-Whisper large-v3-turbo + Ollama gemma3:4b + 3.5 s soft cut.
rem Values already set win, so other start files can override them.
rem If turbo is not on this computer, the launcher falls back to small; nothing is downloaded.
rem Previous default: START_WINDOWS_SMALL_QWEN.bat
if not defined MOSA_NMT_MODEL set "MOSA_NMT_MODEL=gemma3:4b"
if not defined MOSA_ASR_MODEL set "MOSA_ASR_MODEL=large-v3-turbo"
if not defined MOSA_SOFT_CUT_MS set "MOSA_SOFT_CUT_MS=3500"
cd /d "%~dp0"
if exist ".venv-gpu-test\Scripts\python.exe" (
 set PYTHONIOENCODING=utf-8
 ".venv-gpu-test\Scripts\python.exe" windows\launch.py
 pause
 exit /b
)
if not exist ".venv-win\Scripts\python.exe" (
 echo Run INSTALL_WINDOWS.bat first.
 pause
 exit /b 1
)
set PYTHONIOENCODING=utf-8
".venv-win\Scripts\python.exe" windows\launch.py
pause
