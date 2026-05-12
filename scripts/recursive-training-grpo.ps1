#Requires -Version 5.1
<#
.SYNOPSIS
    Repository-local Training-Free GRPO for recursive-mode runs (PowerShell wrapper).

.DESCRIPTION
    Thin wrapper that calls recursive-training-grpo.py with the same arguments.
    Falls back to instructions if Python is not available.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter()]
    [ValidateSet("kimi", "openai", "anthropic")]
    [string]$LlmProvider = "kimi",

    [Parameter()]
    [switch]$Incremental,

    [Parameter()]
    [string]$RunId
)

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $python) {
    Write-Error "Python is required but not found. Please install Python 3.10+ and the 'openai' package."
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "recursive-training-grpo.py"

$argsList = @("--repo-root", $RepoRoot, "--llm-provider", $LlmProvider)
if ($Incremental) {
    $argsList += "--incremental"
}
if ($RunId) {
    $argsList += @("--run-id", $RunId)
}

& $python.Source $pyScript @argsList
