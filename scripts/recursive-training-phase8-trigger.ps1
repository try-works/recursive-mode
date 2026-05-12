#Requires -Version 5.1
<#
.SYNOPSIS
    Post-Phase 8 training trigger for recursive-mode.

.DESCRIPTION
    Called by the harness immediately after Phase 8 (08-memory-impact.md) is locked.
    Checks whether training should run, constructs the appropriate command, and
    executes it.

.PARAMETER RepoRoot
    Path to the git repository root.

.PARAMETER RunId
    The run that just completed Phase 8.

.PARAMETER LlmProvider
    LLM provider for extraction (default: kimi).

.PARAMETER Auto
    Skip user confirmation and run training immediately.

.PARAMETER WinnerOnlyThreshold
    Minimum winners for winner-only mode (default: 2).

.PARAMETER Quiet
    Suppress non-error output.

.EXAMPLE
    .\recursive-training-phase8-trigger.ps1 -RepoRoot . -RunId phase25 -Auto
#
>
param(
    [Parameter(Mandatory)]
    [string]$RepoRoot,

    [Parameter(Mandatory)]
    [string]$RunId,

    [string]$LlmProvider = "kimi",
    [switch]$Auto,
    [int]$WinnerOnlyThreshold = 2,
    [switch]$Quiet
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "recursive-training-phase8-trigger.py"

$argsList = @("--repo-root", $RepoRoot, "--run-id", $RunId, "--llm-provider", $LlmProvider)

if ($Auto) { $argsList += "--auto" }
if ($WinnerOnlyThreshold -ne 2) { $argsList += @("--winner-only-threshold", $WinnerOnlyThreshold) }
if ($Quiet) { $argsList += "--quiet" }

& python $pyScript @argsList
