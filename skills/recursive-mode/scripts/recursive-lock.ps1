[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Artifact,
    [string]$RepoRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-lock.py"
$argsList = @(
    $scriptPath,
    "--repo-root", $RepoRoot,
    "--run-id", $RunId,
    "--artifact", $Artifact
)

& $python @argsList
exit $LASTEXITCODE
