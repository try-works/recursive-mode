param(
    [ValidateSet("local-first-planner", "team-capacity-board", "release-readiness-dashboard")]
    [string]$Scenario = "local-first-planner",
    [ValidateSet("codex", "kimi", "opencode", "all")]
    [string]$Runner = "all",
    [string]$WorkspaceRoot = "",
    [string]$CodexModel = "gpt-5.1",
    [string]$KimiModel = "kimi-k2-5",
    [string]$OpenCodeModel = "opencode/gpt-5-nano",
    [int]$MaxMinutes = 60,
    [int]$CommandTimeout = 900,
    [int]$PreviewTimeout = 45,
    [string]$NpmCommand = "npm",
    [ValidateSet("sequential", "parallel")]
    [string]$ArmMode = "sequential",
    [double]$HintPenalty = 5,
    [switch]$ListScenarios,
    [switch]$PrepareOnly,
    [switch]$SkipNpmInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
} else {
    throw "Python is required to run run-recursive-benchmark.py."
}

$scriptPath = Join-Path $PSScriptRoot "run-recursive-benchmark.py"
$arguments = @()

if ($python -eq "py") {
    $arguments += "-3"
}

$arguments += $scriptPath
$arguments += "--scenario"
$arguments += $Scenario
$arguments += "--runner"
$arguments += $Runner
$arguments += "--codex-model"
$arguments += $CodexModel
$arguments += "--kimi-model"
$arguments += $KimiModel
$arguments += "--opencode-model"
$arguments += $OpenCodeModel
$arguments += "--max-minutes"
$arguments += $MaxMinutes
$arguments += "--command-timeout"
$arguments += $CommandTimeout
$arguments += "--preview-timeout"
$arguments += $PreviewTimeout
$arguments += "--npm-command"
$arguments += $NpmCommand
$arguments += "--arm-mode"
$arguments += $ArmMode
$arguments += "--hint-penalty"
$arguments += $HintPenalty

if ($WorkspaceRoot) {
    $arguments += "--workspace-root"
    $arguments += $WorkspaceRoot
}
if ($ListScenarios) {
    $arguments += "--list-scenarios"
}
if ($PrepareOnly) {
    $arguments += "--prepare-only"
}
if ($SkipNpmInstall) {
    $arguments += "--skip-npm-install"
}

& $python @arguments
exit $LASTEXITCODE
