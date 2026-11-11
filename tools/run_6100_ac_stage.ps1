$log=Join-Path $PSScriptRoot '..\evidence\runs\6100-ac-stage-20261109.txt'
try {
 & (Join-Path $PSScriptRoot '6100_ac_manual_probe.ps1') -Mode Stage *>&1 | Out-String | Set-Content -LiteralPath $log -Encoding UTF8
 foreach ($task in @('CodexGpu6100AcGuard','CodexGpu6100AcRollback')) { Export-ScheduledTask -TaskName $task -ErrorAction Stop | Add-Content -LiteralPath $log -Encoding UTF8 }
} catch { ('ERROR: '+$_.Exception.ToString()) | Add-Content -LiteralPath $log -Encoding UTF8; exit 1 }
