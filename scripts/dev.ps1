param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$NpmLocal = Join-Path $PSScriptRoot "npm-local.ps1"
$PythonExe = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = Join-Path $Backend "venv\Scripts\python.exe"
}

if (-not (Test-Path $PythonExe)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python was not found. Create backend\venv or install Python 3.12+."
    }
    $PythonExe = $PythonCommand.Source
}

$BackendCommand = "cd `"$Backend`"; & `"$PythonExe`" -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort"
$FrontendCommand = "cd `"$Frontend`"; `$env:NEXT_PUBLIC_API_URL='http://localhost:$BackendPort'; & `"$NpmLocal`" run dev -- --port $FrontendPort"

Start-Process -WindowStyle Hidden -FilePath "powershell" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand)
Start-Process -WindowStyle Hidden -FilePath "powershell" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand)

Write-Host "Backend:  http://127.0.0.1:$BackendPort/docs"
Write-Host "Frontend: http://localhost:$FrontendPort"
