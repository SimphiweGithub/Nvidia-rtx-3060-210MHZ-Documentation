$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot '..\evidence\runs\toggle-disable-debug.txt'
try {
    'Before:' | Set-Content -LiteralPath $log -Encoding UTF8
    $before = & bcdedit.exe /enum '{current}' 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Could not read current boot entry: $before" }
    $before | Add-Content -LiteralPath $log -Encoding UTF8
    $out = & bcdedit.exe /debug '{current}' off 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Could not disable kernel debugging: $out" }
    $out | Add-Content -LiteralPath $log -Encoding UTF8
    'After:' | Add-Content -LiteralPath $log -Encoding UTF8
    & bcdedit.exe /enum '{current}' 2>&1 | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify updated boot entry.' }
    'Restart required to apply.' | Add-Content -LiteralPath $log -Encoding UTF8
} catch {
    ('ERROR: ' + $_.Exception.Message) | Add-Content -LiteralPath $log -Encoding UTF8
    exit 1
}
