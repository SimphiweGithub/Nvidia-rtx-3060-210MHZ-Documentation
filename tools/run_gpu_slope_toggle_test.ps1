param([ValidateSet('Enable','Disable')][string]$Action)
$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot ('..\evidence\runs\toggle-test-' + $Action.ToLowerInvariant() + '.txt')
try {
    "Starting $Action test." | Set-Content -LiteralPath $log -Encoding UTF8
    & (Join-Path $PSScriptRoot 'gpu_slope_toggle.ps1') -Action $Action -Apply *>&1 |
        Out-String | Add-Content -LiteralPath $log -Encoding UTF8
    'Finished.' | Add-Content -LiteralPath $log -Encoding UTF8
} catch {
    ('ERROR: ' + $_.Exception.ToString()) | Add-Content -LiteralPath $log -Encoding UTF8
    exit 1
}
