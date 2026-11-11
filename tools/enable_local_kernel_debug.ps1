$ErrorActionPreference = 'Stop'
$output = Join-Path $PSScriptRoot '..\evidence\runs\enable-local-kernel-debug.txt'
$lines = @('Kernel-debug setup', ('Time: ' + (Get-Date -Format o)))
try {
    $before = & bcdedit.exe /dbgsettings 2>&1
    $lines += 'Previous global debug settings:'
    $lines += $before
    $lines += 'Enabling debugging for current boot entry:'
    $result = & bcdedit.exe /debug '{current}' on 2>&1
    $code = $LASTEXITCODE
    $lines += $result
    $lines += ('Exit code: ' + $code)
    if ($code -ne 0) { throw 'Failed to enable kernel debugging; no restart should be performed.' }
    $lines += 'Current boot entry:'
    $lines += (& bcdedit.exe /enum '{current}' 2>&1)
} catch {
    $lines += ('Error: ' + $_.Exception.Message)
} finally {
    $lines | Set-Content -LiteralPath $output -Encoding UTF8
}
