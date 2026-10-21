$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$pidPath=Join-Path $projectRoot '.runtime/gateway.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output 'No gateway PID recorded'; exit }
$gatewayPid=[int]([IO.File]::ReadAllText($pidPath))
$proc=Get-CimInstance Win32_Process -Filter "ProcessId=$gatewayPid" -ErrorAction SilentlyContinue
if ($proc -and $proc.Name -like 'python*' -and $proc.CommandLine -match 'gateway\.py' -and (Get-NetTCPConnection -State Listen -LocalPort 8088 -ErrorAction SilentlyContinue | Where-Object OwningProcess -eq $gatewayPid)) {
  Stop-Process -Id $gatewayPid
  Write-Output "Gateway $gatewayPid stopped"
} elseif ($proc) { throw 'PID ownership could not be verified; no process was stopped' }
