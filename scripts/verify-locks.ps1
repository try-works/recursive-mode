[CmdletBinding()]
param(
    [string]$RunId = "",
    [string]$RepoRoot = (Get-Location).Path,
    [switch]$Fix,
    [switch]$ShowHashes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "verify-locks.py"
$argsList = @($scriptPath, "--repo-root", $RepoRoot)
if ($RunId) { $argsList += @("--run-id", $RunId) }
if ($Fix.IsPresent) { $argsList += "--fix" }
if ($ShowHashes.IsPresent) { $argsList += "--show-hashes" }

& $python @argsList
exit $LASTEXITCODE
