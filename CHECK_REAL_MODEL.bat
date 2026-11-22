@echo off
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
if exist ".venv-gpu-test\Scripts\python.exe" (
 ".venv-gpu-test\Scripts\python.exe" windows\probe_inference.py
) else (
 ".venv-win\Scripts\python.exe" windows\probe_inference.py
)
pause
