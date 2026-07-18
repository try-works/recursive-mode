[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [switch]$RequireCleanGit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "check-reusable-repo-hygiene.py"
$argsList = @($scriptPath, "--repo-root", $RepoRoot)
if ($RequireCleanGit.IsPresent) { $argsList += "--require-clean-git" }

& $python @argsList
exit $LASTEXITCODE
