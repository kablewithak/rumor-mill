param(
  [string]  $Date    = (Get-Date -Format 'yyyy-MM-dd'),
  [string[]]$Domains = @('ai','finance','science'),
  [switch]  $Open,
  [switch]  $Clean
)

if ($Clean -and (Test-Path .\__pycache__)) {
  Remove-Item .\__pycache__ -Recurse -Force
}

# Ensure artifacts folder exists
if (-not (Test-Path .\artifacts)) { New-Item -ItemType Directory -Path .\artifacts | Out-Null }

$log = Join-Path 'artifacts' ("run-{0}.log" -f $Date)

# Build ONLY the arguments; call python separately
$argsList = @(
  'rumor_mill.py',
  '--date',   $Date,
  '--verbose',
  '--log-file', $log,
  '--domains'
) + $Domains

# Optional: show what we’re about to run
Write-Host "CMD: python $($argsList -join ' ')" -ForegroundColor Cyan

# Execute
& python @argsList

if ($LASTEXITCODE -ne 0) {
  Write-Host "Run failed with exit code $LASTEXITCODE" -ForegroundColor Red
  exit $LASTEXITCODE
}

if ($Open) {
  $md = Join-Path 'artifacts' ("{0}.md" -f $Date)
  if (Test-Path $md) { code $md }
}
