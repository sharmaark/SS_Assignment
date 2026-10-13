$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runDirectory = Join-Path $repoRoot ".run"

foreach ($name in @("work-order", "workforce", "dispatch", "notification")) {
    $pidPath = Join-Path $runDirectory "$name.pid"
    if (Test-Path -LiteralPath $pidPath) {
        $servicePid = [int](Get-Content -LiteralPath $pidPath)
        $process = Get-Process -Id $servicePid -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $servicePid
            Write-Host "Stopped $name (PID $servicePid)"
        }
        Remove-Item -LiteralPath $pidPath
    }
}
