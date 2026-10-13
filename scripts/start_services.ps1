$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$runDirectory = Join-Path $repoRoot ".run"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Missing .venv. Follow the README setup commands first."
}

New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
$services = @(
    @{ Name = "work-order"; App = "services.work_order.src.api:app"; Port = 8001 },
    @{ Name = "workforce"; App = "services.workforce.src.api:app"; Port = 8002 },
    @{ Name = "dispatch"; App = "services.dispatch.src.api:app"; Port = 8003 },
    @{ Name = "notification"; App = "services.notification.src.api:app"; Port = 8004 }
)

foreach ($service in $services) {
    $stdoutPath = Join-Path $runDirectory "$($service.Name).log"
    $stderrPath = Join-Path $runDirectory "$($service.Name).error.log"
    $process = Start-Process -FilePath $pythonPath -ArgumentList @("-m", "uvicorn", $service.App, "--host", "127.0.0.1", "--port", $service.Port) -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
    Set-Content -LiteralPath (Join-Path $runDirectory "$($service.Name).pid") -Value $process.Id
    Write-Host "Started $($service.Name) on port $($service.Port) (PID $($process.Id))"
}
