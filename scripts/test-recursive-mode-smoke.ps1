[CmdletBinding()]
param(
    [ValidateSet("quick", "full", "subagent")][string]$Scenario = "quick",
    [ValidateSet("python", "powershell", "mixed", "both")][string]$Toolchain = "mixed",
    [string]$TempRoot = "",
    [switch]$KeepTemp,
    [int]$CommandTimeout = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $python -and -not $pyLauncher) {
    throw "Python launcher not found. Install python or py before running the smoke harness."
}

$scriptPath = Join-Path $PSScriptRoot "test-recursive-mode-smoke.py"
$argsList = @(
    $scriptPath,
    "--scenario", $Scenario,
    "--toolchain", $Toolchain,
    "--command-timeout", $CommandTimeout.ToString()
)
if (-not [string]::IsNullOrWhiteSpace($TempRoot)) {
    $argsList += @("--temp-root", $TempRoot)
}
if ($KeepTemp) {
    $argsList += "--keep-temp"
}

if ($python) {
    & $python.Source @argsList
} else {
    & $pyLauncher.Source -3 @argsList
}
exit $LASTEXITCODE
