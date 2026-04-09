[CmdletBinding()]
param(
    [string]$RunId = "",
    [string]$RepoRoot = (Get-Location).Path,
    [switch]$AllRuns,
    [switch]$Strict
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "lint-recursive-run.py"
$argsList = @($scriptPath, "--repo-root", $RepoRoot)
if ($RunId) { $argsList += @("--run-id", $RunId) }
if ($AllRuns.IsPresent) { $argsList += "--all-runs" }
if ($Strict.IsPresent) { $argsList += "--strict" }

& $python @argsList
exit $LASTEXITCODE
