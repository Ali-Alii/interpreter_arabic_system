$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
# CUDA build for NVIDIA GPUs. Use a matching supported wheel from pytorch.org
# instead on machines without NVIDIA hardware.
& .\.venv\Scripts\python.exe -m pip install torch==2.11.0+cu128 --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'GPU dependency installation failed.' }
& .\.venv\Scripts\python.exe scripts\prepare_model.py
if ($LASTEXITCODE -ne 0) { throw 'Model preparation failed. See the error above.' }
Write-Host 'Ready. Run .\start.ps1 and open http://127.0.0.1:8000'
