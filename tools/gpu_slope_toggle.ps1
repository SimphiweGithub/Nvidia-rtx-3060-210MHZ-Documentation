param([ValidateSet('Menu','Status','Enable','Disable')][string]$Action = 'Menu', [switch]$Apply)

# Experimental per-machine switch. No firmware flashing; no Windows reboot.
# Spoofed feedback cannot provide verified measured board-power protection.
$ErrorActionPreference = 'Stop'
$expected = '8BCEBB313011F95CF879751BF11685E58495CE02C2A7D3F946CD60B5C4754153'
$payload = Join-Path $PSScriptRoot '..\evidence\runs\OFFLINE-ONLY-current-slope-relocated-20261110.bin'
$root = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
$hardware = 'pci\ven_10de&dev_2520&subsys_0a641028'
$instance = 'PCI\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1\4&412752A&0&0008'

function HashBytes([byte[]]$data) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($data)).Replace('-','') } finally { $sha.Dispose() }
}
function GetGpuKey {
    $keys = @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue | Where-Object { $_.GetValue('MatchingDeviceId', '') -ieq $hardware })
    if ($keys.Count -ne 1) { throw "Expected one GPU registry key, found $($keys.Count)." }
    return $keys[0]
}
if ($Action -eq 'Menu') {
    Write-Host 'RTX 3060 experimental slope override'
    Write-Host '1: Status   2: Enable   3: Disable   Q: Quit'
    Write-Host 'Enable/Disable restarts the GPU device and can interrupt graphics applications.'
    $choice = Read-Host 'Choose'
    $next = switch ($choice) { '1' {'Status'} '2' {'Enable'} '3' {'Disable'} default {return} }
    if ($next -eq 'Status') { & $PSCommandPath -Action Status; return }
    Write-Host 'This uses altered power/current feedback. Save your work before continuing.'
    if ((Read-Host "Type $next to continue") -cne $next) { return }
    Write-Host 'The administrator window will stay open so you can read the result. Close it when finished.'
    $args = @('-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"'),'-Action',$next,'-Apply')
    Start-Process powershell.exe -Verb RunAs -ArgumentList $args -Wait
    return
}
$key = GetGpuKey
$value = $key.GetValue('vbios', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$names = @($key.GetValueNames())
$hash = if ($value -is [byte[]]) { HashBytes $value } else { $null }
if ($Action -eq 'Status') {
    $state = if ($hash -eq $expected) {'Slope override configured'} elseif ($names -contains 'vbios') {'Other override configured'} else {'No startup override'}
    Write-Host $state
    Get-PnpDevice -InstanceId $instance | Select-Object FriendlyName,Status,Problem | Format-List
    & nvidia-smi --query-gpu=pstate,clocks.current.graphics,clocks.current.memory,temperature.gpu,power.draw --format=csv,noheader,nounits
    Write-Host 'A removed override can remain loaded until a device or Windows restart.'
    Write-Host 'For exact loaded-image verification use tools/verify_loaded_slope_image.py.'
    return
}
if (-not $Apply) { throw 'No change: pass -Apply or use the menu.' }
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator rights required.' }
if (Get-ScheduledTask -TaskName 'CodexGpuSlopeGuard','CodexGpuSlopeRollback','CodexGpuSlopeDeviceTimeout' -ErrorAction SilentlyContinue) {
    throw 'A temporary slope test is active; wait for its rollback before using the switch.'
}
if (@($names | Where-Object { $_ -match '^(romOverride[0-9a-f]{2}|VixLoaderPreviousEnableGpuFirmware)$' }).Count) { throw 'Another loader override exists.' }
if (($names -contains 'vbios') -and $hash -ne $expected) { throw 'A different VBIOS override exists; it will not be changed.' }
if ($Action -eq 'Enable') {
    if ((Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash -ne $expected) { throw 'Candidate hash mismatch.' }
    if (-not ($names -contains 'vbios')) { New-ItemProperty -LiteralPath $key.PSPath -Name 'vbios' -PropertyType Binary -Value ([IO.File]::ReadAllBytes((Resolve-Path $payload).Path)) | Out-Null }
    $value = (Get-Item -LiteralPath $key.PSPath).GetValue('vbios')
    if ($value -isnot [byte[]] -or (HashBytes $value) -ne $expected) { throw 'Registry readback failed; inspect the override before restarting.' }
} else {
    if ($hash -eq $expected) { Remove-ItemProperty -LiteralPath $key.PSPath -Name 'vbios' }
}
Write-Host 'Restarting the GPU device...'
$result = & pnputil.exe /restart-device $instance 2>&1
$code = $LASTEXITCODE
$result | Write-Host
if ($code -ne 0) { throw "GPU restart failed ($code). Registry setting may have changed; check Status and use Safe Mode if needed." }
$device = Get-PnpDevice -InstanceId $instance -ErrorAction Stop
if ($device.Status -ne 'OK' -or $device.Problem -ne 'CM_PROB_NONE') { throw "GPU did not start normally: $($device.Problem). Registry setting may have changed." }
Write-Host 'Device restart completed. Verify the loaded image and clocks; no Windows restart was requested.'
