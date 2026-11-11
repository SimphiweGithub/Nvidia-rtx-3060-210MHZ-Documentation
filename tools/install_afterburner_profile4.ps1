$ErrorActionPreference = 'Stop'
$runDir = Join-Path $PSScriptRoot '..\evidence\runs'
$log = Join-Path $runDir 'afterburner-profile4-install.txt'
$source = 'C:\Program Files (x86)\MSI Afterburner\Profiles\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1&BUS_1&DEV_0&FN_0.cfg'
$marker = 'C:\Program Files (x86)\MSI Afterburner\Profiles\Profile4.cfg'
$candidate = Join-Path $runDir 'afterburner-profile4-prepared.cfg'
$manifest = Get-Content -Raw (Join-Path $runDir 'afterburner-profile4-prepared.json') | ConvertFrom-Json
$backup = Join-Path $runDir 'afterburner-profiles-before-profile4.cfg'
$temp = $source + '.codex-profile4-tmp'
$replaceBackup = $source + '.codex-profile4-backup-tmp'
$replaced = $false
$createdMarker = $false
try {
    if (Get-Process -Name MSIAfterburner -ErrorAction SilentlyContinue) { throw 'Close Afterburner completely first.' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $manifest.source_sha256) { throw 'Saved profiles changed; rebuild the candidate.' }
    if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash -ne $manifest.candidate_sha256) { throw 'Candidate hash mismatch.' }
    if ((Test-Path -LiteralPath $marker) -or (Test-Path -LiteralPath $temp) -or (Test-Path -LiteralPath $replaceBackup)) { throw 'Existing profile 4 or temporary file; refusing to overwrite.' }
    if (Test-Path -LiteralPath $backup) {
        if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $manifest.source_sha256) { throw 'Existing backup differs; refusing to overwrite.' }
    } else { Copy-Item -LiteralPath $source -Destination $backup }
    [IO.File]::WriteAllBytes($temp, [IO.File]::ReadAllBytes((Resolve-Path $candidate).Path))
    [IO.File]::Replace($temp, $source, $replaceBackup)
    $replaced = $true
    $file = [IO.File]::Open($marker, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    $createdMarker = $true
    try { $bytes = [Text.Encoding]::ASCII.GetBytes("[Settings]`r`nProfileContents=1`r`n"); $file.Write($bytes,0,$bytes.Length) } finally { $file.Dispose() }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $manifest.candidate_sha256) { throw 'Installed file verification failed.' }
    Remove-Item -LiteralPath $replaceBackup -Force
    'Installed profile 4; original saved to workspace backup. Curve not applied or runtime-verified.' | Set-Content -LiteralPath $log -Encoding UTF8
} catch {
    $message = 'ERROR: ' + $_.Exception.ToString()
    try {
        if ($createdMarker) { Remove-Item -LiteralPath $marker -Force }
        if ($replaced) { Copy-Item -LiteralPath $backup -Destination $source -Force }
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
        if (Test-Path -LiteralPath $replaceBackup) { Remove-Item -LiteralPath $replaceBackup -Force }
        $message += "`r`nCleanup attempted."
    } catch { $message += "`r`nCleanup failed: $($_.Exception.Message)" }
    $message | Set-Content -LiteralPath $log -Encoding UTF8
    exit 1
}
