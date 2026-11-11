$ErrorActionPreference = 'Continue'
$output = Join-Path $PSScriptRoot '..\evidence\runs\kernel-debug-readiness.txt'
$lines = @()
$lines += 'Kernel debugging readiness (read-only)'
$lines += 'Time: ' + (Get-Date -Format o)
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$lines += 'Administrator: ' + $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$lines += 'Boot settings:'
$lines += (& bcdedit.exe /enum '{current}' 2>&1 | Out-String)
$lines += 'Secure Boot:'
try { $lines += (Confirm-SecureBootUEFI | Out-String) } catch { $lines += $_.Exception.Message }
$lines += 'OS drive protection:'
try {
    $volume = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
    $lines += ('VolumeStatus={0}; ProtectionStatus={1}' -f $volume.VolumeStatus, $volume.ProtectionStatus)
} catch { $lines += $_.Exception.Message }
$lines | Set-Content -LiteralPath $output -Encoding UTF8
