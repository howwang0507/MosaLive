@echo off
setlocal
rem Previous default: Faster-Whisper small + Ollama qwen2.5:7b, with the 3.5 s soft cut.
rem Use it if large-v3-turbo or gemma3:4b is unavailable or misbehaves on this computer.
set "MOSA_ASR_MODEL=small"
set "MOSA_NMT_MODEL=qwen2.5:7b"
set "MOSA_SOFT_CUT_MS=3500"
call "%~dp0START_WINDOWS.bat"
endlocal
