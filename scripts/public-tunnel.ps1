param([string]$Cloudflared='')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$runtime=Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force $runtime | Out-Null
if (-not $Cloudflared) { $Cloudflared=Join-Path $runtime 'cloudflared.exe' }
if (-not (Test-Path -LiteralPath $Cloudflared)) {
  Invoke-WebRequest 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile $Cloudflared
}
$null=Invoke-RestMethod 'http://127.0.0.1:8088/healthz' -TimeoutSec 3
$process=Start-Process -FilePath $Cloudflared -ArgumentList 'tunnel','--url','http://127.0.0.1:8088','--protocol','http2','--no-autoupdate' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'tunnel.stdout.log') -RedirectStandardError (Join-Path $runtime 'tunnel.stderr.log')
[IO.File]::WriteAllText((Join-Path $runtime 'tunnel.pid'), [string]$process.Id)
Write-Output "Tunnel process: $($process.Id). Temporary HTTPS URL will appear in .runtime/tunnel.stderr.log"
Write-Output 'Quick Tunnel is a demonstration only; use non-streaming requests (SSE is not supported).'
