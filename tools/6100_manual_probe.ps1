param([ValidateSet('Inspect','Stage','Guard','Rollback')][string]$Mode = 'Inspect')

# Experimental one-boot test. The GPU can initialize before the boot task runs;
# battery reporting is delayed and the clock range is not a measured power cap.
# This script cannot guarantee board-power protection.
$ErrorActionPreference = 'Stop'
$expectedHash = '6ED6FA9BD749C173B0EB191221FFD3F6EBC78F1C7151BE67BC01A7A780C067BF'
$payload = Join-Path $PSScriptRoot '..\evidence\runs\OFFLINE-ONLY-6100mW-candidate-relocated-20261109.bin'
$root = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
$guardName = 'CodexGpu6100ManualGuard'
$backupName = 'CodexGpu6100ManualRollback'
$log = Join-Path $PSScriptRoot '..\evidence\runs\6100-manual-guard-20261109.txt'
$gpuKeys = @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue | Where-Object {
    $_.GetValue('MatchingDeviceId', '') -ieq 'pci\ven_10de&dev_2520&subsys_0a641028'
})
if ($gpuKeys.Count -ne 1) { throw "Expected one matching GPU key; found $($gpuKeys.Count)." }
$key = $gpuKeys[0]
if ($Mode -in @('Inspect','Stage') -and (Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Candidate hash mismatch.' }
$value = $key.GetValue('vbios', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$names = @($key.GetValueNames())
$storedHash = if ($value -is [byte[]]) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($value)).Replace('-','') } finally { $sha.Dispose() }
} else { $null }
if ($Mode -eq 'Inspect') {
    $battery = @(Get-CimInstance -Namespace root\WMI -ClassName BatteryStatus)
    [pscustomobject]@{ DriverKey=$key.Name; PayloadBytes=(Get-Item $payload).Length; PayloadSha256=$expectedHash;
        ExistingVbios=($names -contains 'vbios'); ExistingVbiosSha256=$storedHash;
        PowerOnline=@($battery | ForEach-Object PowerOnline); Discharging=@($battery | ForEach-Object Discharging);
        Action='No changes made' } | Format-List
    return
}
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as administrator.' }
if ($Mode -eq 'Rollback') {
    if (($names -contains 'vbios') -and $storedHash -ne $expectedHash) { throw 'Override differs from candidate; not removing it.' }
    if ($storedHash -eq $expectedHash) { Remove-ItemProperty -LiteralPath $key.PSPath -Name 'vbios' }
    foreach ($name in @($guardName,$backupName)) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
    }
    'Override removed; the GPU must restart before the original image is active.'
    return
}
if ($Mode -eq 'Guard') {
    $reason = 'bounded observation completed'
    try {
        $battery = @(Get-CimInstance -Namespace root\WMI -ClassName BatteryStatus)
        if ($battery.Count -ne 1 -or $battery[0].PowerOnline -or -not $battery[0].Discharging) { throw 'Battery-only state not established.' }
        $response = & nvidia-smi -i 0 --lock-gpu-clocks=210,600 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Clock range request failed: $response" }
        $deadline = (Get-Date).AddMinutes(10)
        while ((Get-Date) -lt $deadline) {
            $battery = @(Get-CimInstance -Namespace root\WMI -ClassName BatteryStatus)
            if ($battery.Count -ne 1 -or $battery[0].PowerOnline -or -not $battery[0].Discharging) { throw 'Battery-only state lost.' }
            $gpu = & nvidia-smi --query-gpu=clocks.current.graphics,temperature.gpu,power.draw,utilization.gpu,clocks_event_reasons.sw_power_cap --format=csv,noheader,nounits 2>&1
            if ($LASTEXITCODE -ne 0 -or "$gpu" -notmatch '^\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+|\[N/A\])\s*,\s*(\d+)\s*,\s*(Active|Not Active|\[N/A\])\s*$') { throw 'GPU telemetry unavailable.' }
            $clock=[int]$Matches[1]; $temperature=[int]$Matches[2]
            $reportedPower=$Matches[3]; $utilization=[int]$Matches[4]; $powerCap=$Matches[5]
            $rate=[long]$battery[0].DischargeRate
            "$(Get-Date -Format o),clock_mhz=$clock,temp_c=$temperature,reported_power_w=$reportedPower,utilization_pct=$utilization,sw_power_cap=$powerCap,battery_discharge_mw=$rate" | Add-Content -LiteralPath $log -Encoding UTF8
            if ($clock -gt 600) { throw 'Reported graphics clock exceeds 600 MHz.' }
            if ($temperature -ge 75) { throw 'GPU temperature reached 75 C.' }
            if ($rate -le 0 -or $rate -ge 100000) { throw 'Battery discharge rate unavailable or at least 100 W.' }
            Start-Sleep -Seconds 2
        }
    } catch { $reason = $_.Exception.Message }
    finally {
        "$(Get-Date -Format o),ending=$reason" | Add-Content -LiteralPath $log -Encoding UTF8
        try { & $PSCommandPath -Mode Rollback | Add-Content -LiteralPath $log -Encoding UTF8 }
        catch { ('Rollback error: '+$_.Exception.Message) | Add-Content -LiteralPath $log -Encoding UTF8 }
        # User must save work before starting: reboot is needed to unload the image.
        & shutdown.exe /r /t 30 /c 'GPU test ended; restarting to unload the experimental VBIOS.'
    }
    return
}
$battery = @(Get-CimInstance -Namespace root\WMI -ClassName BatteryStatus)
if ($battery.Count -ne 1 -or $battery[0].PowerOnline -or -not $battery[0].Discharging) { throw 'Stage only on battery.' }
if (($names -contains 'vbios') -or @($names | Where-Object { $_ -match '^(romOverride[0-9a-f]{2}|VixLoaderPreviousEnableGpuFirmware)$' }).Count) { throw 'An override already exists.' }
foreach ($name in @($guardName,$backupName)) { if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw "Task $name already exists." } }
$exe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$guardTrigger = New-ScheduledTaskTrigger -AtStartup
$backupTrigger = New-ScheduledTaskTrigger -AtStartup; $backupTrigger.Delay = 'PT12M'
$guardAction = New-ScheduledTaskAction -Execute $exe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode Guard"
$backupAction = New-ScheduledTaskAction -Execute $exe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode Rollback"
try {
    Register-ScheduledTask -TaskName $guardName -Action $guardAction -Trigger $guardTrigger -Principal $principal -Settings $settings | Out-Null
    Register-ScheduledTask -TaskName $backupName -Action $backupAction -Trigger $backupTrigger -Principal $principal -Settings $settings | Out-Null
    New-ItemProperty -LiteralPath $key.PSPath -Name 'vbios' -PropertyType Binary -Value ([IO.File]::ReadAllBytes((Resolve-Path $payload).Path)) | Out-Null
    $stored = (Get-Item -LiteralPath $key.PSPath).GetValue('vbios')
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $actual = [BitConverter]::ToString($sha.ComputeHash($stored)).Replace('-','') } finally { $sha.Dispose() }
    if ($actual -ne $expectedHash) { throw 'Registry readback mismatch.' }
} catch {
    try { & $PSCommandPath -Mode Rollback } catch { Write-Warning $_ }
    throw
}
'Candidate staged. Restart manually only when ready; guard will observe for at most 10 minutes and then schedule a restart.'
