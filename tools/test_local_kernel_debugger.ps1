$ErrorActionPreference = 'Stop'
$output = Join-Path $PSScriptRoot '..\evidence\runs\local-kernel-debugger.txt'
try {
$package = Get-AppxPackage -Name Microsoft.WinDbg
if (-not $package) { 'WinDbg package not found.' | Set-Content -LiteralPath $output; exit 1 }
$kd = Join-Path $package.InstallLocation 'amd64\kd.exe'
if (-not (Test-Path -LiteralPath $kd)) { 'KD executable not found.' | Set-Content -LiteralPath $output; exit 1 }
$temporaryOutput = Join-Path $env:TEMP 'codex-kd-check-out.txt'
$temporaryError = Join-Path $env:TEMP 'codex-kd-check-err.txt'
$commands = '.reload;.echo VALID;dq ffff920c19ece000+2310 L1;.echo PARENT;dq ffff920c09dae550+30 L4;.echo DESC_A;dq poi(ffff920c09dae550+30) L10;.echo DESC_B;dq poi(ffff920c09dae550+38) L10;.echo FIRST_PAGE;dd ffff87f0c260b000 L8;.echo END;q'
$p = Start-Process -FilePath $kd -ArgumentList @('-kl','-c', ('"' + $commands + '"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput $temporaryOutput -RedirectStandardError $temporaryError
if (-not $p.WaitForExit(90000)) { Stop-Process -Id $p.Id; $timedOut = $true } else { $timedOut = $false }
@('Read-only local kernel debugger check', "Timed out: $timedOut", 'stdout:', (Get-Content -LiteralPath $temporaryOutput -Raw), 'stderr:', (Get-Content -LiteralPath $temporaryError -Raw)) | Set-Content -LiteralPath $output -Encoding UTF8
} catch {
    @('Read-only local kernel debugger check', ('Error: ' + $_.Exception.ToString())) | Set-Content -LiteralPath $output -Encoding UTF8
    exit 1
}





































