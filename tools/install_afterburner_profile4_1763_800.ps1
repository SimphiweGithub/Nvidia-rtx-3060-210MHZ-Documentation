$ErrorActionPreference = 'Stop'
$dir = Join-Path $PSScriptRoot '..\evidence\runs'
$log = Join-Path $dir 'afterburner-profile4-1763-800-install.txt'
$src = 'C:\Program Files (x86)\MSI Afterburner\Profiles\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1&BUS_1&DEV_0&FN_0.cfg'
$candidate = Join-Path $dir 'afterburner-profile4-1763-800-prepared.cfg'
$manifest = Get-Content -Raw (Join-Path $dir 'afterburner-profile4-1763-800-prepared.json') | ConvertFrom-Json
$backup = Join-Path $dir 'afterburner-profiles-before-1763-800.cfg'
$tmp = $src + '.codex-1763-800-tmp'
$replaceBackup = $src + '.codex-1763-800-backup-tmp'
$replaced = $false
try {
    if (Get-Process -Name MSIAfterburner -ErrorAction SilentlyContinue) { throw 'Afterburner must be closed.' }
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $manifest.source_sha256) { throw 'Profile configuration changed; prepare again.' }
    if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash -ne $manifest.candidate_sha256) { throw 'Candidate hash mismatch.' }
    if ((Test-Path -LiteralPath $backup) -or (Test-Path -LiteralPath $tmp) -or (Test-Path -LiteralPath $replaceBackup)) { throw 'Backup or temporary file exists; refusing overwrite.' }
    Copy-Item -LiteralPath $src -Destination $backup
    [IO.File]::WriteAllBytes($tmp, [IO.File]::ReadAllBytes((Resolve-Path $candidate).Path))
    [IO.File]::Replace($tmp, $src, $replaceBackup)
    $replaced = $true
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $manifest.candidate_sha256) { throw 'Verification failed.' }
    Remove-Item -LiteralPath $replaceBackup -Force
    'Profile 4 1763 MHz / 800 mV installed; not applied or runtime-verified.' | Set-Content -LiteralPath $log -Encoding UTF8
} catch {
    $message = 'ERROR: ' + $_.Exception.ToString()
    try {
        if ($replaced) { Copy-Item -LiteralPath $backup -Destination $src -Force }
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
        if (Test-Path -LiteralPath $replaceBackup) { Remove-Item -LiteralPath $replaceBackup -Force }
        $message += "`r`nCleanup attempted."
    } catch { $message += "`r`nCleanup failed: $($_.Exception.Message)" }
    $message | Set-Content -LiteralPath $log -Encoding UTF8
    exit 1
}
