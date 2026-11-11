$ErrorActionPreference='Stop'
$log=Join-Path $PSScriptRoot '..\evidence\runs\multi-v2-stage-20261110.txt'
try {
 & (Join-Path $PSScriptRoot 'multi_v2_ac_probe.ps1') -Mode Stage *>&1 | Out-String | Set-Content -LiteralPath $log -Encoding UTF8
 foreach ($name in @('CodexGpuMultiV2Guard','CodexGpuMultiV2Rollback')) {
  Export-ScheduledTask -TaskName $name -ErrorAction Stop | Add-Content -LiteralPath $log -Encoding UTF8
 }
} catch { ('ERROR: '+$_.Exception.ToString()) | Set-Content -LiteralPath $log -Encoding UTF8; exit 1 }
