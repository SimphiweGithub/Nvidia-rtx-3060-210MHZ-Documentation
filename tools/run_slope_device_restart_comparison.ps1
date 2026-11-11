$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot '..\evidence\runs\slope-device-restart-launch.txt'
try {
    'Launching device-restart comparison.' | Set-Content -LiteralPath $log -Encoding UTF8
    & (Join-Path $PSScriptRoot 'slope_device_restart_comparison.ps1') -Run *>&1 |
        Out-String | Add-Content -LiteralPath $log -Encoding UTF8
    'Comparison launch completed.' | Add-Content -LiteralPath $log -Encoding UTF8
} catch {
    ('ERROR: ' + $_.Exception.ToString()) | Add-Content -LiteralPath $log -Encoding UTF8
    exit 1
}
