[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [switch]$Json,
    [switch]$NoWrite,
    [int]$TimeoutMs = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-router-probe.py"
$argsList = @($scriptPath, "--repo-root", $RepoRoot)
if ($Json) { $argsList += "--json" }
if ($NoWrite) { $argsList += "--no-write" }
if ($TimeoutMs -gt 0) { $argsList += @("--timeout-ms", $TimeoutMs) }

& $python @argsList
exit $LASTEXITCODE
