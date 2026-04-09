[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Phase,
    [string]$RepoRoot = (Get-Location).Path,
    [string]$PreviewLog = "",
    [string]$PreviewUrl = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-closeout.py"
$argsList = @(
    $scriptPath,
    "--repo-root", $RepoRoot,
    "--run-id", $RunId,
    "--phase", $Phase
)
if (-not [string]::IsNullOrWhiteSpace($PreviewLog)) {
    $argsList += @("--preview-log", $PreviewLog)
}
if (-not [string]::IsNullOrWhiteSpace($PreviewUrl)) {
    $argsList += @("--preview-url", $PreviewUrl)
}
if ($Force.IsPresent) {
    $argsList += "--force"
}

& $python @argsList
exit $LASTEXITCODE
