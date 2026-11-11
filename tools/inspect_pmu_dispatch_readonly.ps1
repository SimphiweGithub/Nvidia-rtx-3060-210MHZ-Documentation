$ErrorActionPreference = 'Stop'
$outputPath = Join-Path $PSScriptRoot '..\evidence\runs\local-kernel-pmu-dispatch-forward-20261109.txt'
$kd = Join-Path (Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation 'amd64\kd.exe'
$stdoutPath = Join-Path $env:TEMP 'codex-pmu-dispatch-stdout.txt'
$stderrPath = Join-Path $env:TEMP 'codex-pmu-dispatch-stderr.txt'
$commands = '.reload;r @$t1=poi(poi(poi(nvlddmkm+13aad58)+200)+48240);r @$t2=poi(@$t1+2310);r @$t3=poi(@$t2+fa8);.echo OBJECTS;r @$t3;.echo OWNER_VTABLE;dq @$t3-8 L2;dq poi(@$t3-8)+68 L1;.echo FORWARD_TARGET;ln poi(poi(@$t3-8)+68);u poi(poi(@$t3-8)+68) L30;.echo END;q'
try {
 $process = Start-Process -FilePath $kd -ArgumentList @('-kl','-c',('"'+$commands+'"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
 $finished = $process.WaitForExit(90000)
 if (-not $finished) { Stop-Process -Id $process.Id }
 @("Completed: $finished",(Get-Content -LiteralPath $stdoutPath -Raw),(Get-Content -LiteralPath $stderrPath -Raw)) | Set-Content -LiteralPath $outputPath -Encoding UTF8
} catch { $_.Exception.ToString() | Set-Content -LiteralPath $outputPath -Encoding UTF8; exit 1 }
