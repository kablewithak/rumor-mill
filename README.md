Rumor Mill — Daily Rumor Digest

A tiny command-line script that fetches fresh rumor-ish stories from a few domains (AI, finance, science), scores & de-duplicates them, and writes a one-page Markdown brief plus machine-readable JSON snapshots.

Input: RSS/feeds defined in config.py

Core: simple heuristics + keyword cues, optional domain filtering

Output: artifacts/YYYY-MM-DD.md (+ raw and cluster JSON)

Quick start (Windows / PowerShell)
# 1) Clone and enter
git clone <your-repo-url> rumor-mill
cd rumor-mill

# 2) Create & activate venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Install deps
pip install -r requirements.txt

# 4) (Optional) create .env from example
Copy-Item .env.example .env

# 5) Run today’s brief with a dated log
$d = Get-Date -Format yyyy-MM-dd
python .\rumor_mill.py --date today --verbose --log-file "artifacts\run-$d.log"


Expected outputs (under artifacts\):

2025-10-22.md
2025-10-22.raw.json
2025-10-22.clusters.json
run-2025-10-22.log   # if --log-file was passed

How it works
collectors.py   -> fetch RSS/feeds (e.g., Google News queries)
ranker.py       -> rumor scoring, de-dupe, domain/topic filtering
agent.py        -> pick representative story per domain, build summary
formatter.py    -> render final Markdown
config.py       -> sources, keywords, excludes, caps
rumor_mill.py   -> CLI entrypoint orchestrating the run
scripts\        -> convenience PowerShell runner(s)
artifacts\      -> dated outputs (md, raw.json, clusters.json, logs)


High-level flow

Pull per-domain items from configured feeds (config.DOMAINS).

Optionally filter off-topic items (filter_by_domain).

Score & de-dupe (score_and_dedupe).

Cluster similar titles; pick a representative (agent.pick_one).

Render Markdown (formatter.to_markdown).

Write Markdown + raw + cluster JSON (+ optional run log).

Configuration

Edit config.py:

KEYWORDS: rumor cues (e.g., ["rumor","leak","reportedly","insider","speculation"])

DOMAINS: dict of domain → list of feed URLs

DOMAIN_KEYWORDS / DOMAIN_EXCLUDES: allow/block phrases per domain

MAX_ITEMS: per-run cap across sources

SUPPRESS_DUP_SUMMARY: True to avoid repeating the headline in summaries

Tip: science excludes are tuned to avoid finance-ish noise; extend as needed.

CLI usage
# Base (today)
python .\rumor_mill.py --date today

# Specific date
python .\rumor_mill.py --date 2025-10-22

# Choose domains
python .\rumor_mill.py --domains ai science

# Verbose + log to file
$d = Get-Date -Format yyyy-MM-dd
python .\rumor_mill.py --date today --verbose --log-file "artifacts\run-$d.log"

# Dry run (don’t write outputs)
python .\rumor_mill.py --dry-run --verbose

Output files

YYYY-MM-DD.md — the human brief

YYYY-MM-DD.raw.json — raw harvested items per domain

YYYY-MM-DD.clusters.json — cluster trace for debugging/picks

run-YYYY-MM-DD.log — optional run log if --log-file is used

Example Markdown (truncated)

# Rumor Mill — Daily Digest (2025-10-22)

## AI
**Meta is reportedly downsizing its legacy AI research team - The Verge**  *(Confidence: 0.70)*
Meta is reportedly downsizing its legacy AI research team. Coverage is emerging; details remain unconfirmed.
*Why it looks like a rumor:* Keyword signals: reportedly.
Sources: 1 link.
- [Meta is reportedly downsizing its legacy AI research team - The Verge](...)

Convenience runner (Windows)

scripts\run-today.ps1:

param(
  [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
  [string[]]$Domains = @('ai','finance','science'),
  [switch]$Open
)

$log = "artifacts\run-$Date.log"
$cmd = @('python','rumor_mill.py','--date', $Date, '--verbose', '--log-file', $log, '--domains') + $Domains
& $cmd

if ($LASTEXITCODE -ne 0) { Write-Host "Run failed with exit code $LASTEXITCODE" -ForegroundColor Red; exit $LASTEXITCODE }

if ($Open) {
  $md = Join-Path 'artifacts' ("{0}.md" -f $Date)
  if (Test-Path $md) { code $md }
}


Run it:

# (inside venv)
.\scripts\run-today.ps1           # today, all domains
.\scripts\run-today.ps1 -Open     # and open the MD after
.\scripts\run-today.ps1 -Date 2025-10-22 -Domains ai,science


If PowerShell blocks scripts, run once:

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Environment (.env)

python-dotenv loads .env automatically. You likely don’t need secrets for this prototype, but it’s ready for future keys.

# .env.example
# MODEL=gpt-4o-mini
# MAX_ITEMS=60

Copy-Item .env.example .env

Troubleshooting

ModuleNotFoundError: No module named 'dotenv' → pip install -r requirements.txt

PowerShell shows from not supported → you ran Python code in PowerShell; use:
python -c "from config import KEYWORDS; print(KEYWORDS[:5])"

Execution policy blocks scripts → Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Artifacts look stale / weird picks → inspect artifacts\*.raw.json and *.clusters.json; tune DOMAIN_EXCLUDES, KEYWORDS, or sources in config.py

Duplicate-y summaries → SUPPRESS_DUP_SUMMARY=True is enabled; we also Jaccard-check the first sentence vs title in agent.py

__pycache__ → safe to ignore; delete if you want a clean rebuild (Python will recreate it)

Repo layout
rumor-mill/
  artifacts/                # outputs: md, raw.json, clusters.json, logs
  scripts/run-today.ps1     # convenience runner
  agent.py  collectors.py  formatter.py  ranker.py  config.py  rumor_mill.py
  requirements.txt  README.md

Requirements

Python 3.10+ (tested on 3.11)

Windows PowerShell for the helper script (CLI works on any OS with Python)