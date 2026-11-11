$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $root 'evidence\runs'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$raw = Join-Path $runDir "nvml-kernel-profile-$stamp.etl"
$log = Join-Path $runDir "nvml-kernel-profile-$stamp.txt"
$xperf = (Get-Command xperf.exe -ErrorAction Stop).Source
$python = (Get-Command python.exe -ErrorAction Stop).Source
$started = $false
try {
    & $xperf -on PROC_THREAD+LOADER+PROFILE -stackwalk Profile -MaxFile 128 -FileMode Circular -f $raw 2>&1 | Out-File -LiteralPath $log -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "xperf start failed: $LASTEXITCODE" }
    $started = $true
    & $python -u (Join-Path $PSScriptRoot 'sample_nvml_query_loop.py') 2>&1 | Add-Content -LiteralPath $log -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "query loop failed: $LASTEXITCODE" }
} catch {
    $_ | Out-String | Add-Content -LiteralPath $log -Encoding utf8
} finally {
    if ($started) {
        & $xperf -stop 2>&1 | Add-Content -LiteralPath $log -Encoding utf8
        "xperf_stop_exit=$LASTEXITCODE" | Add-Content -LiteralPath $log -Encoding utf8
    }
}
