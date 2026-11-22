$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Run-Checked([scriptblock]$Command) {
  & $Command
  if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE). See output above." }
}
foreach ($command in @('py','node','ollama')) {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Missing $command. Read WINDOWS_README.md, install prerequisites, then reopen." }
}
Run-Checked { py -3.11 -m venv .venv-win }
Run-Checked { & '.\.venv-win\Scripts\python.exe' -m pip install -r windows/requirements.txt }
Run-Checked { & '.\.venv-win\Scripts\python.exe' windows/setup_streaming.py }
Run-Checked { ollama pull gemma3:4b }
# Fallback translator used by START_WINDOWS_SMALL_QWEN.bat.
Run-Checked { ollama pull qwen2.5:7b }
# Default speech model (about 1.6 GB) into the project cache that START_WINDOWS.bat searches.
Run-Checked { & '.\.venv-win\Scripts\python.exe' -c "from huggingface_hub import snapshot_download; snapshot_download('mobiuslabsgmbh/faster-whisper-large-v3-turbo', cache_dir='.models/windows')" }
Write-Host 'Installed. Run START_WINDOWS.bat. CUDA 12 + cuDNN 9 DLLs must be available for GPU ASR.'
