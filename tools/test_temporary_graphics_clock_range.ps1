$ErrorActionPreference='Stop'
$log=Join-Path $PSScriptRoot '..\evidence\runs\clock-range-support-20261109.txt'
$lines=@('Temporary 210-600 MHz graphics clock range support test; no workload.')
$setSucceeded=$false
try {
 $lines+=('Before: '+((& nvidia-smi --query-gpu=clocks.current.graphics,temperature.gpu --format=csv,noheader,nounits) -join ' '))
 $response=& nvidia-smi -i 0 --lock-gpu-clocks=210,600 2>&1
 $code=$LASTEXITCODE
 $lines+=('Set exit code: '+$code); $lines+=($response | Out-String)
 if ($code -eq 0) {
  $setSucceeded=$true
  Start-Sleep -Seconds 3
  $lines+=('During: '+((& nvidia-smi --query-gpu=clocks.current.graphics,temperature.gpu --format=csv,noheader,nounits) -join ' '))
 }
} catch { $lines+=('ERROR: '+$_.Exception.ToString()) }
finally {
 if ($setSucceeded) {
  $response=& nvidia-smi -i 0 --reset-gpu-clocks 2>&1
  $lines+=('Reset exit code: '+$LASTEXITCODE); $lines+=($response | Out-String)
 }
 $lines | Set-Content -LiteralPath $log -Encoding UTF8
}
