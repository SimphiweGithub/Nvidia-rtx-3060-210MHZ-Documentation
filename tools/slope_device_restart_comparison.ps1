param([switch]$Run)

# PREPARED ONLY: no changes without -Run and administrator rights.
# Experimental device reload; measured board/current protection is unavailable.
# No automatic Windows reboot. GPU monitoring begins only after device restart.
$ErrorActionPreference = 'Stop'
$probe = Join-Path $PSScriptRoot 'current_slope_ac_probe.ps1'
$timeoutName = 'CodexGpuSlopeDeviceTimeout'
$gpuId = 'PCI\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1\4&412752A&0&0008'
$log = Join-Path $PSScriptRoot '..\evidence\runs\slope-device-restart-comparison.txt'

if (-not $Run) {
    'Preparation inspection only. No device, task, or registry changes.'
    Get-PnpDevice -InstanceId $gpuId | Select-Object FriendlyName,Status,Problem,InstanceId
    & $probe -Mode Inspect
    return
}
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator rights required.' }
if (Get-ScheduledTask -TaskName $timeoutName -ErrorAction SilentlyContinue) { throw 'Timeout task already exists.' }
$gpu = Get-PnpDevice -InstanceId $gpuId -ErrorAction Stop
if ($gpu.Status -ne 'OK' -or $gpu.Problem -ne 'CM_PROB_NONE') { throw 'GPU is not healthy; no changes made.' }
$root = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
$keys = @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue | Where-Object { $_.GetValue('MatchingDeviceId', '') -ieq 'pci\ven_10de&dev_2520&subsys_0a641028' })
$battery = @(Get-CimInstance -Namespace root\WMI -ClassName BatteryStatus)
if ($keys.Count -ne 1 -or $keys[0].GetValueNames() -contains 'vbios' -or $battery.Count -ne 1 -or -not $battery[0].PowerOnline) {
    throw 'Existing override or AC state invalid; no changes made.'
}
$exe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(12)
$action = New-ScheduledTaskAction -Execute $exe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$probe`" -Mode Rollback"
$timeoutCreated = $false
$staged = $false
try {
    Register-ScheduledTask -TaskName $timeoutName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    $timeoutCreated = $true
    $stageOutput = & $probe -Mode Stage | Out-String
    $staged = $true
    $stageOutput | Set-Content -LiteralPath $log -Encoding UTF8
    $stored = (Get-Item -LiteralPath $keys[0].PSPath).GetValue('vbios')
    if ($stored -isnot [byte[]]) { throw 'Staged override missing.' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = [BitConverter]::ToString($sha.ComputeHash($stored)).Replace('-','') } finally { $sha.Dispose() }
    if ($hash -ne '8BCEBB313011F95CF879751BF11685E58495CE02C2A7D3F946CD60B5C4754153') { throw 'Staged override readback mismatch.' }
    'Requesting GPU device restart.' | Add-Content -LiteralPath $log
    $out = & pnputil.exe /restart-device $gpuId 2>&1
    $exitCode = $LASTEXITCODE
    $out | Out-String | Add-Content -LiteralPath $log
    if ($exitCode -ne 0) { throw "GPU device restart failed: $exitCode" }
    $gpu = Get-PnpDevice -InstanceId $gpuId -ErrorAction Stop
    if ($gpu.Status -ne 'OK' -or $gpu.Problem -ne 'CM_PROB_NONE') { throw "GPU did not recover: $($gpu.Problem)" }
    # Boot trigger does not cover a device restart; start the existing guard explicitly.
    Start-ScheduledTask -TaskName 'CodexGpuSlopeGuard' -ErrorAction Stop
    'Guard start requested. Verify its log and live image before testing.' | Add-Content -LiteralPath $log
} catch {
    $err = $_
    if ($staged) { try { & $probe -Mode Rollback | Out-Null } catch { Write-Warning "Rollback failed: $_" } }
    if ($timeoutCreated) { try { Unregister-ScheduledTask -TaskName $timeoutName -Confirm:$false } catch { Write-Warning "Timeout cleanup failed: $_" } }
    throw $err
}
