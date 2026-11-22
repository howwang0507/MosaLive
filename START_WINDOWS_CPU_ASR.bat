@echo off
setlocal
set MOSA_ASR_DEVICE=cpu
rem large-v3-turbo is too slow on CPU; keep small unless chosen explicitly.
if not defined MOSA_ASR_MODEL set "MOSA_ASR_MODEL=small"
call "%~dp0START_WINDOWS.bat"
endlocal
