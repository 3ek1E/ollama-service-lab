param([switch]$Lan, [string]$Model='qwen3.5:0.8b')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$runtime=Join-Path $projectRoot '.runtime'
$local=Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Force $runtime,$local | Out-Null
$ollamaCmd=Get-Command ollama -ErrorAction SilentlyContinue
$ollama=if ($ollamaCmd) { $ollamaCmd.Source } else { Join-Path $env:LOCALAPPDATA 'Programs/Ollama/ollama.exe' }
if (-not (Test-Path -LiteralPath $ollama)) { throw 'Install Ollama first: https://ollama.com/download/windows' }
$pythonCmd=Get-Command python -ErrorAction Stop
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_MODEL=$Model
$env:NO_PROXY='localhost,127.0.0.1,::1'
try { $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 } catch {
  $env:OLLAMA_MODELS=Join-Path $runtime 'models'
  $env:OLLAMA_NO_CLOUD='1'
  Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'ollama.stdout.log') -RedirectStandardError (Join-Path $runtime 'ollama.stderr.log')
  $ready=$false
  for ($i=0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try { $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $ready=$true; break } catch {}
  }
  if (-not $ready) { throw 'Ollama failed to start; inspect .runtime logs' }
}
& $ollama pull $Model
if ($LASTEXITCODE -ne 0) { throw 'Model download failed' }
$keyPath=Join-Path $local 'service.key'
if (-not (Test-Path -LiteralPath $keyPath)) {
  $keyBytes=New-Object byte[] 32
  $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($keyBytes)
  $rng.Dispose()
  [IO.File]::WriteAllText($keyPath, ([BitConverter]::ToString($keyBytes).Replace('-','').ToLowerInvariant()))
}
$env:SERVICE_API_KEY=[IO.File]::ReadAllText($keyPath).Trim()
$env:SERVICE_HOST=if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
$env:SERVICE_PORT='8088'
$env:OLLAMA_BASE_URL='http://127.0.0.1:11434'
$existing=Get-NetTCPConnection -State Listen -LocalPort 8088 -ErrorAction SilentlyContinue
if ($existing) { throw 'Port 8088 already in use. Stop the existing service before restarting.' }
$process=Start-Process -FilePath $pythonCmd.Source -ArgumentList '-X','utf8','gateway.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'gateway.stdout.log') -RedirectStandardError (Join-Path $runtime 'gateway.stderr.log')
[IO.File]::WriteAllText((Join-Path $runtime 'gateway.pid'), [string]$process.Id)
Write-Output "Gateway process: $($process.Id); listener: $($env:SERVICE_HOST):8088"
Write-Output 'Key is stored locally at .local/service.key (excluded from Git).'
Write-Output 'Health: http://127.0.0.1:8088/healthz'
