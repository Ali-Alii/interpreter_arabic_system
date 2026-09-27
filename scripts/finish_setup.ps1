param(
    [Parameter(Mandatory=$true)][int]$WheelProcessId,
    [Parameter(Mandatory=$true)][int]$ModelProcessId,
    [Parameter(Mandatory=$true)][int]$ServerProcessId
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$statusPath = Join-Path $projectRoot '.cache\setup-status.json'
function Write-SetupStatus([string]$Stage, [string]$Message) {
    @{stage=$Stage; message=$Message; updated=(Get-Date).ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
}
try {
    Write-SetupStatus 'downloading' 'Downloading speech weights and the GPU runtime. The interface is available; transcription is not ready yet.'
    if (Get-Process -Id $WheelProcessId -ErrorAction SilentlyContinue) {
        Wait-Process -Id $WheelProcessId -ErrorAction SilentlyContinue
    }
    $wheel = Get-ChildItem -LiteralPath '.cache\wheels' -Filter 'torch-2.11.0+cu128-*.whl' | Select-Object -First 1
    for ($retry = 0; -not $wheel -and $retry -lt 5; $retry++) {
        Write-SetupStatus 'downloading' 'Resuming the GPU runtime after a connection interruption. Saved download pieces are retained.'
        & .\.venv\Scripts\python.exe -u scripts\download_gpu.py
        $wheel = Get-ChildItem -LiteralPath '.cache\wheels' -Filter 'torch-2.11.0+cu128-*.whl' | Select-Object -First 1
        if (-not $wheel) { Start-Sleep -Seconds 15 }
    }
    if (-not $wheel) { throw 'CUDA wheel download did not finish. Run setup.ps1 to retry.' }
    Write-SetupStatus 'installing' 'Installing the GPU runtime. Speech weights may still be downloading.'
    & .\.venv\Scripts\python.exe -m pip install $wheel.FullName
    if ($LASTEXITCODE -ne 0) { throw 'CUDA runtime installation failed. Run setup.ps1 to retry.' }
    if (Get-Process -Id $ModelProcessId -ErrorAction SilentlyContinue) {
        Write-SetupStatus 'downloading' 'GPU runtime installed. Waiting for the speech weights download.'
        Wait-Process -Id $ModelProcessId -ErrorAction SilentlyContinue
    }
    $weights = Join-Path $projectRoot '.cache\huggingface\hub\models--NAMAA-Space--Cohere-Speech-Tashkeel-2B\snapshots\710704bf787fa3c27f7567aa08078861925aeee2\model.safetensors'
    if (-not (Test-Path -LiteralPath $weights)) { throw 'Speech weights download did not finish. Run python scripts/download_weights.py to resume.' }
    Write-SetupStatus 'loading' 'Downloads complete. Loading the speech model on the GPU.'
    if (Get-Process -Id $ServerProcessId -ErrorAction SilentlyContinue) { Stop-Process -Id $ServerProcessId }
    Start-Process -FilePath (Join-Path $projectRoot '.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput '.cache\server.log' -RedirectStandardError '.cache\server-error.log'
    $serverReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try { $null = Invoke-RestMethod 'http://127.0.0.1:8000/api/status'; $serverReady = $true; break }
        catch { Start-Sleep -Seconds 2 }
    }
    if (-not $serverReady) { throw 'Server did not restart. Run start.ps1.' }
    $result = Invoke-RestMethod 'http://127.0.0.1:8000/api/prepare' -Method Post -TimeoutSec 1800
    if ($result.state -ne 'ready') { throw 'Model loading failed. See server-error.log.' }
    Write-SetupStatus 'ready' 'Speech model loaded. You can record now. Accuracy still needs evaluation on real recordings.'
} catch {
    Write-SetupStatus 'error' $_.Exception.Message
    throw
}
