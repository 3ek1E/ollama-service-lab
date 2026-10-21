param([ValidateSet('all','ollama','chat','responses','anthropic')][string]$Api='all', [switch]$Stream, [string]$BaseUrl='http://127.0.0.1:8088')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$env:SERVICE_API_KEY=[IO.File]::ReadAllText((Join-Path $projectRoot '.local/service.key')).Trim()
$exampleArgs=@('-X','utf8',(Join-Path $projectRoot 'examples/call_four_apis.py'),'--api',$Api,'--base-url',$BaseUrl)
if ($Stream) { $exampleArgs+='--stream' }
& python @exampleArgs
exit $LASTEXITCODE
