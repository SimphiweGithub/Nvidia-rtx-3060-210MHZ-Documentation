# Temporarily test NVIDIA's platform controller, then restore its original state.
# Run in an elevated PowerShell. Do not reboot while the test is running.
$ErrorActionPreference = 'Stop'
$deviceId = 'ACPI\NVDA0820\NPCF'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator PowerShell is required. No device state was changed.'
}
$device = Get-PnpDevice -InstanceId $deviceId
if ($device.Status -ne 'OK' -or [string]$device.Problem -ne 'CM_PROB_NONE') {
    throw "Device was not initially healthy/enabled ($($device.Status), $($device.Problem)); no state changed."
}
$folder = Join-Path $PSScriptRoot '..\evidence\runs'
$log = Join-Path $folder ('nvpcf-temporary-test-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')
function Record([string]$message) {
    Write-Host $message
    Add-Content -LiteralPath $log -Encoding utf8 -Value $message
}
function Measure-Gpu([string]$stage) {
    Record "`n[$stage] $(Get-Date -Format o)"
    $gpu = & nvidia-smi --query-gpu=driver_version,clocks.gr,power.draw,clocks_throttle_reasons.sw_power_cap --format=csv,noheader 2>&1
    Record ($gpu | Out-String).Trim()
    $device = Get-PnpDevice -InstanceId $deviceId
    Record "Platform device: status=$($device.Status), problem=$($device.Problem)"
}
$attempted = $false
try {
    Record 'NVPCF temporary test. The device was enabled at the start.'
    Measure-Gpu 'Before'
    $attempted = $true
    Disable-PnpDevice -InstanceId $deviceId -Confirm:$false -ErrorAction Stop
    Start-Sleep -Seconds 5
    Measure-Gpu 'After temporary disable'
} catch {
    Record "TEST ERROR: $($_.Exception.Message)"
} finally {
    if ($attempted) {
        try {
            $device = Get-PnpDevice -InstanceId $deviceId -ErrorAction Stop
            if ($device.Status -ne 'OK' -or [string]$device.Problem -ne 'CM_PROB_NONE') {
                Enable-PnpDevice -InstanceId $deviceId -Confirm:$false -ErrorAction Stop
                Start-Sleep -Seconds 2
            }
            Measure-Gpu 'After restore'
            $device = Get-PnpDevice -InstanceId $deviceId
            if ($device.Status -ne 'OK' -or [string]$device.Problem -ne 'CM_PROB_NONE') {
                Record 'RESTORE NOT CONFIRMED. In an administrator PowerShell run: Enable-PnpDevice -InstanceId ''ACPI\NVDA0820\NPCF'' -Confirm:$false'
            } else {
                Record 'Restore confirmed: platform device is enabled and reports OK.'
            }
        } catch {
            Record "RESTORE ERROR: $($_.Exception.Message)"
            Record 'In an administrator PowerShell run: Enable-PnpDevice -InstanceId ''ACPI\NVDA0820\NPCF'' -Confirm:$false'
        }
    }
    Record "Results: $log"
}
