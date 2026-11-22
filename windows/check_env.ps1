$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path -Parent $PSScriptRoot
function Show-Check($name, $ok, $detail) {
    $label = if ($ok) { '[OK]' } else { '[CHECK]' }
    $color = if ($ok) { 'Green' } else { 'Yellow' }
    Write-Host "$label $name : $detail" -ForegroundColor $color
}
$pythonPath = Join-Path $projectRoot '.venv-gpu-test\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { $pythonPath = Join-Path $projectRoot '.venv-win\Scripts\python.exe' }
Show-Check 'Python environment' (Test-Path -LiteralPath $pythonPath) $pythonPath
if (Test-Path -LiteralPath $pythonPath) {
    'import fastapi, faster_whisper, ctranslate2, sherpa_onnx' | & $pythonPath -
    Show-Check 'Python dependencies' ($LASTEXITCODE -eq 0) 'See import result above'
    'import ctranslate2; print(ctranslate2.get_cuda_device_count())' | & $pythonPath -
    Show-Check 'CUDA device query' ($LASTEXITCODE -eq 0) 'Device count above; zero means no available CUDA device'
}
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) {
    $nodeVersion = & $nodeCommand.Source --version
    $nodeMajor = ($nodeVersion.TrimStart('v') -split '\.')[0]
    Show-Check 'Node.js >= 22' ([int]$nodeMajor -ge 22) "Major version $nodeMajor"
} else { Show-Check 'Node.js' $false 'Not found in PATH' }
$gpuCommand = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($gpuCommand) { & $gpuCommand.Source --query-gpu=name,memory.used,memory.total --format=csv,noheader }
else { Show-Check 'NVIDIA driver' $false 'nvidia-smi unavailable; GPU status unknown' }
foreach ($entry in @(@('Ollama','http://127.0.0.1:11434/api/tags'),@('Backend','http://127.0.0.1:8790/health'),@('Bridge','http://127.0.0.1:8787/health'))) {
    try {
        $response = Invoke-RestMethod -Uri $entry[1] -TimeoutSec 3
        if ($entry[0] -eq 'Backend') { Show-Check $entry[0] ($response.ready -eq $true) "Startup ready=$($response.ready); error=$($response.error)" }
        elseif ($entry[0] -eq 'Ollama') { Show-Check $entry[0] $true ('Installed models: '+($response.models.name -join ', ')) }
        else { Show-Check $entry[0] $true 'HTTP reachable' }
    } catch { Show-Check $entry[0] $false 'Not reachable; start service or inspect its window' }
}
Write-Host 'Checks do not prove real inference works. Run the real audio test at http://localhost:8787.'
foreach ($servicePort in @(8787,8790)) {
    $listeners = Get-NetTCPConnection -LocalPort $servicePort -State Listen -ErrorAction SilentlyContinue
    if ($listeners) { Write-Host "Port $servicePort listening, PID: $($listeners.OwningProcess -join ', ')" }
    else { Write-Host "Port $servicePort has no listening service" -ForegroundColor Yellow }
}
Write-Host 'Use CHECK_REAL_MODEL.bat for an actual audio and translation request. Check extension version in its popup.'
