$ErrorActionPreference='Stop'
$log=Join-Path $PSScriptRoot '..\evidence\runs\stock-override-stage-20261109.txt'
try {
  & (Join-Path $PSScriptRoot 'stock_override_probe.ps1') -Mode Stage *>&1 | Out-String | Set-Content -LiteralPath $log -Encoding UTF8
} catch {
  ('ERROR: ' + $_.Exception.ToString()) | Set-Content -LiteralPath $log -Encoding UTF8
  exit 1
}
