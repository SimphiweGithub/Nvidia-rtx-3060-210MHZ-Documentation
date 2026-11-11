$ErrorActionPreference='Stop'
$out = Join-Path $PSScriptRoot '..\evidence\runs\local-kernel-6100-live-policies-20261109.txt'
$package=Get-AppxPackage -Name Microsoft.WinDbg
$kd=Join-Path $package.InstallLocation 'amd64\kd.exe'
$tmpOut=Join-Path $env:TEMP 'codex-bios-kd-out.txt'
$tmpErr=Join-Path $env:TEMP 'codex-bios-kd-err.txt'
$commands='.reload;r @$t1=poi(poi(poi(nvlddmkm+13aad58)+200)+48240);r @$t2=poi(@$t1+2510);.echo GPU_PMGR;r @$t1;r @$t2;.echo R0;dd poi(poi(@$t2+1c98)) Lc0;.echo R1;dd poi(poi(@$t2+1c98)+8) Lc0;.echo R2;dd poi(poi(@$t2+1c98)+10) Lc0;.echo R9;dd poi(poi(@$t2+1c98)+48) Lc0;.echo R16;dd poi(poi(@$t2+1c98)+80) Lc0;.echo R17;dd poi(poi(@$t2+1c98)+88) Lc0;.echo END;q'
try {
 $p=Start-Process -FilePath $kd -ArgumentList @('-kl','-c',('"'+$commands+'"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr
 $completed=$p.WaitForExit(90000)
 if (-not $completed) { Stop-Process -Id $p.Id }
 @("Completed: $completed",(Get-Content -LiteralPath $tmpOut -Raw),(Get-Content -LiteralPath $tmpErr -Raw)) | Set-Content -LiteralPath $out -Encoding UTF8
} catch { $_.Exception.ToString() | Set-Content -LiteralPath $out -Encoding UTF8 }






