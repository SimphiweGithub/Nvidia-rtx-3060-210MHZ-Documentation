$log=Join-Path $PSScriptRoot '..\evidence\runs\stock-override-inspect-admin-20261109.txt'
try {
  & (Join-Path $PSScriptRoot 'stock_override_probe.ps1') -Mode Inspect | Out-String | Set-Content $log -Encoding UTF8
  Get-ScheduledTask -TaskName 'CodexStockVbiosProbeRollback' -ErrorAction Stop | Format-List * | Out-String | Add-Content $log -Encoding UTF8
  Export-ScheduledTask -TaskName 'CodexStockVbiosProbeRollback' -ErrorAction Stop | Add-Content $log -Encoding UTF8
} catch { ('ERROR: '+$_.Exception.ToString()) | Add-Content $log -Encoding UTF8; exit 1 }
