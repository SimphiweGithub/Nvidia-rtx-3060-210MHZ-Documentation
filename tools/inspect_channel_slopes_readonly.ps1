$ErrorActionPreference='Stop'
$out=Join-Path $PSScriptRoot '..\evidence\runs\local-kernel-channel-slopes-20261110.txt'
$kd=Join-Path (Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation 'amd64\kd.exe'
$stdout=Join-Path $env:TEMP 'codex-channel-slopes-out.txt'
$stderr=Join-Path $env:TEMP 'codex-channel-slopes-err.txt'
$commands='.reload;r @$t1=poi(poi(poi(nvlddmkm+13aad58)+200)+48240);r @$t2=poi(@$t1+2510);.echo OBJECTS;r @$t1;r @$t2;.echo C3;dd poi(poi(@$t2+8a0)+18) L20;.echo C5;dd poi(poi(@$t2+8a0)+28) L20;.echo C18;dd poi(poi(@$t2+8a0)+90) L20;.echo C19;dd poi(poi(@$t2+8a0)+98) L20;.echo END;q'
try {
 $p=Start-Process -FilePath $kd -ArgumentList @('-kl','-c',('"'+$commands+'"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
 $done=$p.WaitForExit(90000)
 if(-not $done){Stop-Process -Id $p.Id}
 @("Completed: $done",(Get-Content -LiteralPath $stdout -Raw),(Get-Content -LiteralPath $stderr -Raw)) | Set-Content -LiteralPath $out -Encoding UTF8
}catch{$_.Exception.ToString() | Set-Content -LiteralPath $out -Encoding UTF8;exit 1}
