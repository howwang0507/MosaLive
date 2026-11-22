@echo off
rem Save low-VRAM Ollama settings for the current Windows user so the translator stays on the GPU.
rem Restart Ollama afterwards. Undo: delete these four entries in "Edit environment variables for your account".
setx OLLAMA_FLASH_ATTENTION 1
setx OLLAMA_KV_CACHE_TYPE q8_0
setx OLLAMA_NUM_PARALLEL 1
setx OLLAMA_MAX_LOADED_MODELS 1
echo.
echo Saved. Quit Ollama from the system tray, start it again, then run START_WINDOWS.bat.
pause
