param(
    [switch]$Run,
    [switch]$RestoreWatchdog,
    [string]$LogPath
)
# Diagnostic only. The live test is disruptive and requires administrator rights.
# Watchdog and finally restoration are best effort; neither survives every crash.
$ErrorActionPreference = 'Stop'
$platformId = 'ACPI\NVDA0820\NPCF'
$gpuId = 'PCI\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1\4&412752A&0&0008'

function Write-Log([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    Write-Host $line
    if ($LogPath) {
        try { Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8 -ErrorAction Stop }
        catch { Write-Warning "Could not write test log: $($_.Exception.Message)" }
    }
}
function Restore-Platform {
    try {
        $device = Get-PnpDevice -InstanceId $platformId -ErrorAction Stop
        if ($device.Problem -eq 'CM_PROB_DISABLED') {
            Enable-PnpDevice -InstanceId $platformId -Confirm:$false -ErrorAction Stop
            Start-Sleep -Seconds 3
            $device = Get-PnpDevice -InstanceId $platformId -ErrorAction Stop
        }
        Write-Log "Platform restore status: $($device.Status), $($device.Problem)"
        if ($device.Status -ne 'OK' -or $device.Problem -ne 'CM_PROB_NONE') {
            Write-Log "RESTORE NOT CONFIRMED. Administrator command: Enable-PnpDevice -InstanceId '$platformId' -Confirm:`$false"
        }
    } catch { Write-Log "RESTORE ERROR: $($_.Exception.Message)" }
}
if ($RestoreWatchdog) {
    if (-not $LogPath) { throw 'Watchdog requires a log path.' }
    $LogPath = "$LogPath.watchdog"
    Write-Log 'Watchdog armed.'
    Start-Sleep -Seconds 90
    Write-Log 'Watchdog checking platform restoration.'
    Restore-Platform
    exit
}
if (-not $Run) {
    Write-Host 'DRY RUN ONLY: no device or configuration changes.'
    Get-PnpDevice -InstanceId $platformId, $gpuId | Select-Object Status, FriendlyName, InstanceId, Problem | Format-List
    & nvidia-smi --query-gpu=driver_version,power.draw,clocks.current.graphics,clocks_throttle_reasons.sw_power_cap --format=csv,noheader
    Write-Host 'Live mode would temporarily disable NVPCF, restart the NVIDIA GPU device, sample, then restore NVPCF.'
    Write-Host 'It can interrupt GPU applications; restoration is best effort. No reboot is requested.'
    exit
}
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator rights required; no changes made.' }
foreach ($id in @($platformId, $gpuId)) {
    $d = Get-PnpDevice -InstanceId $id -ErrorAction Stop
    if ($d.Status -ne 'OK' -or $d.Problem -ne 'CM_PROB_NONE') { throw "Device is not healthy: $id; no changes made." }
}
$dir = Join-Path $PSScriptRoot '..\evidence\runs'
$LogPath = Join-Path $dir ('nvpcf-gpu-restart-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')
Write-Log 'Starting platform-disable and GPU-restart test; watchdog will restore after 90 seconds.'
$watchArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-RestoreWatchdog', '-LogPath', ('"' + $LogPath + '"'))
$watchdog = Start-Process -FilePath powershell.exe -ArgumentList $watchArgs -WindowStyle Hidden -PassThru
$armed = $false
for ($i = 0; $i -lt 40; $i++) {
    if ($watchdog.HasExited) { break }
    if (Select-String -LiteralPath "$LogPath.watchdog" -SimpleMatch 'Watchdog armed.' -Quiet -ErrorAction SilentlyContinue) { $armed = $true; break }
    Start-Sleep -Milliseconds 250
}
if (-not $armed -or $watchdog.HasExited) { throw 'Restore watchdog did not confirm startup; no devices changed.' }
try {
    Write-Log ((& nvidia-smi --query-gpu=power.draw,clocks.current.graphics,clocks_throttle_reasons.sw_power_cap --format=csv,noheader 2>&1 | Out-String).Trim())
    Disable-PnpDevice -InstanceId $platformId -Confirm:$false -ErrorAction Stop
    $d = Get-PnpDevice -InstanceId $platformId
    if ($d.Problem -ne 'CM_PROB_DISABLED') { throw 'Platform disable not confirmed; GPU restart skipped.' }
    Write-Log 'Platform disabled; requesting NVIDIA GPU device restart.'
    $restartOutput = & pnputil.exe /restart-device $gpuId 2>&1
    $restartExit = $LASTEXITCODE
    Write-Log (($restartOutput | Out-String).Trim())
    Write-Log "PnP restart exit code: $restartExit"
    if ($restartExit -ne 0) { throw 'GPU restart did not report success.' }
    Start-Sleep -Seconds 5
    $beforeSample = Get-PnpDevice -InstanceId $platformId -ErrorAction Stop
    if ($beforeSample.Problem -ne 'CM_PROB_DISABLED') { throw 'Platform no longer disabled before the sample; result is inconclusive.' }
    $sample = & nvidia-smi --query-gpu=power.draw,clocks.current.graphics,clocks_throttle_reasons.sw_power_cap --format=csv,noheader 2>&1
    $sampleExit = $LASTEXITCODE
    $afterSample = Get-PnpDevice -InstanceId $platformId -ErrorAction Stop
    Write-Log (($sample | Out-String).Trim())
    Write-Log "nvidia-smi exit code: $sampleExit; platform during sample: $($beforeSample.Problem) -> $($afterSample.Problem)"
    if ($sampleExit -ne 0 -or $afterSample.Problem -ne 'CM_PROB_DISABLED') { throw 'Sample invalid or platform was restored during sampling; result is inconclusive.' }
    $g = Get-PnpDevice -InstanceId $gpuId
    Write-Log "GPU status: $($g.Status), $($g.Problem)"
    Write-Log 'A successful PnP restart request alone does not establish that the driver fully unloaded and reinitialized.'
} catch { Write-Log "TEST ERROR: $($_.Exception.Message)" }
finally { Restore-Platform; Write-Log 'Test finished; watchdog will independently recheck restoration.' }
