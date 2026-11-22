@echo off
setlocal
rem The 3.5 s soft cut is now part of START_WINDOWS.bat; this file is kept for old shortcuts.
rem Once a turn passes 3.5 s, a short breath finalizes it: captions come sooner on long turns.
set MOSA_SOFT_CUT_MS=3500
call "%~dp0START_WINDOWS.bat"
endlocal
