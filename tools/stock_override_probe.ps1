param(
    [ValidateSet('Inspect','Stage','Rollback')]
    [string]$Mode = 'Inspect'
)

# A one-boot, stock-derived compatibility probe. This does not change power tables.
# Stage requires elevation and a later manual restart. The scheduled rollback deletes
# only the exact value written by this probe; it does not restart Windows.
$ErrorActionPreference = 'Stop'
$expectedHash = '4929334FF54A1A660826F68D0C6C5349D1E6109410976BB7E505C73C578C5A7E'
$payload = Join-Path $PSScriptRoot '..\evidence\runs\nvapi-stock-ampere-relocated-20261109.bin'
$classRoot = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
$taskName = 'CodexStockVbiosProbeRollback'
$gpuKeys = @(Get-ChildItem -LiteralPath $classRoot -ErrorAction SilentlyContinue | Where-Object {
    $id = $_.GetValue('MatchingDeviceId', '')
    $id -ieq 'pci\ven_10de&dev_2520&subsys_0a641028'
})
if ($gpuKeys.Count -ne 1) { throw "Expected one matching GPU driver key; found $($gpuKeys.Count)." }
$key = $gpuKeys[0]
$hash = (Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash
if ($hash -ne $expectedHash) { throw 'Stock-derived payload hash differs from the reviewed file.' }
$names = @($key.GetValueNames())
$value = $key.GetValue('vbios', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$valueHash = if ($value -is [byte[]]) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($value)).Replace('-','') } finally { $sha.Dispose() }
} else { $null }
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($Mode -eq 'Inspect') {
    [pscustomobject]@{ DriverKey=$key.Name; PayloadBytes=(Get-Item -LiteralPath $payload).Length;
        PayloadSha256=$hash; ExistingVbios=($names -contains 'vbios'); ExistingVbiosSha256=$valueHash;
        ExistingRelatedValues=@($names | Where-Object { $_ -match '^(romOverride[0-9a-f]{2}|VixLoaderPreviousEnableGpuFirmware)$' });
        RollbackTaskExists=($null -ne $task); Action='No changes made' } | Format-List
    return
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as administrator.' }
if ($Mode -eq 'Rollback') {
    if (($names -contains 'vbios') -and $valueHash -ne $expectedHash) {
        throw 'Existing vbios value does not match this probe; it was not changed.'
    }
    if ($valueHash -eq $expectedHash) { Remove-ItemProperty -LiteralPath $key.PSPath -Name 'vbios' }
    if ($task) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
    'Probe value removed. Restart Windows to return the driver to the card VBIOS.'
    return
}
if (($names -contains 'vbios') -or @($names | Where-Object { $_ -match '^(romOverride[0-9a-f]{2}|VixLoaderPreviousEnableGpuFirmware)$' }).Count -gt 0) {
    throw 'An override or related record already exists; nothing was changed.'
}
if ($task) { throw 'Rollback task already exists; inspect it before proceeding.' }
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode Rollback"
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT5M'
$runAs = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $runAs -Settings $settings | Out-Null
try {
    $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $payload).Path)
    New-ItemProperty -LiteralPath $key.PSPath -Name 'vbios' -PropertyType Binary -Value $bytes | Out-Null
    $check = (Get-Item -LiteralPath $key.PSPath).GetValue('vbios')
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $checkHash = [BitConverter]::ToString($sha.ComputeHash($check)).Replace('-','') } finally { $sha.Dispose() }
    if ($checkHash -ne $expectedHash) { throw 'Registry readback did not match the reviewed payload.' }
} catch {
    # Roll back only if the stored bytes match our exact reviewed payload.
    & $PSCommandPath -Mode Rollback
    throw
}
'Stock-derived override staged. Save work, then restart manually to test. The rollback task removes the registry value five minutes after startup; a second restart is needed to restore the original loaded image.'
