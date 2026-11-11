$ErrorActionPreference='Stop'
$log=Join-Path $PSScriptRoot '..\evidence\runs\current-slope-stage-20261110.txt'
$staged=$false
try {
 $stageOutput = & (Join-Path $PSScriptRoot 'current_slope_ac_probe.ps1') -Mode Stage *>&1 | Out-String
 $staged=$true
 $stageOutput | Set-Content -LiteralPath $log -Encoding UTF8
 foreach ($name in @('CodexGpuSlopeGuard','CodexGpuSlopeRollback')) {
  Export-ScheduledTask -TaskName $name -ErrorAction Stop | Add-Content -LiteralPath $log -Encoding UTF8
 }
} catch {
 $message='ERROR: '+$_.Exception.ToString()
 if ($staged) {
  try {
   $rollback = & (Join-Path $PSScriptRoot 'current_slope_ac_probe.ps1') -Mode Rollback *>&1 | Out-String
   $message += "`r`nCleanup after staging: $rollback"
  } catch { $message += "`r`nCleanup failed: $($_.Exception.ToString())" }
 }
 $message | Set-Content -LiteralPath $log -Encoding UTF8
 exit 1
}
