param([ValidateRange(1,60)][int]$Seconds = 15)

# Read-only capture. Does not start or stop any workload or enforce a limit.
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot ('..\evidence\runs\memory-state-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.csv')
'timestamp,pstate,memory_mhz,graphics_mhz,temperature_c,gpu_load_pct,memory_load_pct,sw_power_cap,sw_thermal_slowdown' |
    Set-Content -LiteralPath $path -Encoding UTF8
for ($i = 0; $i -lt $Seconds; $i++) {
    $row = & nvidia-smi --query-gpu=timestamp,pstate,clocks.current.memory,clocks.current.graphics,temperature.gpu,utilization.gpu,utilization.memory,clocks_event_reasons.sw_power_cap,clocks_event_reasons.sw_thermal_slowdown --format=csv,noheader,nounits 2>&1
    if ($LASTEXITCODE -ne 0 -or @($row).Count -ne 1) { throw "GPU telemetry query failed: $row" }
    $row | Add-Content -LiteralPath $path -Encoding UTF8
    $row
    if ($i -lt ($Seconds - 1)) { Start-Sleep -Seconds 1 }
}
Write-Output "Capture: $path"
