$log=Join-Path $PSScriptRoot '..\evidence\runs\stock-override-watchdog-fix-20261109.txt'
try {
 $settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
 Set-ScheduledTask -TaskName 'CodexStockVbiosProbeRollback' -Settings $settings -ErrorAction Stop | Out-Null
 Export-ScheduledTask -TaskName 'CodexStockVbiosProbeRollback' -ErrorAction Stop | Set-Content -LiteralPath $log -Encoding UTF8
} catch { ('ERROR: '+$_.Exception.ToString()) | Set-Content -LiteralPath $log -Encoding UTF8; exit 1 }
