#Requires -Version 5.1
<#
.SYNOPSIS
    Progressive memory loader for recursive-mode experiential knowledge.

.DESCRIPTION
    Reads the memory router plus the repository memory plane, scores memory docs
    by relevance to the current task, reads the most relevant docs, scores
    individual items, and returns formatted context for the agent.

    This is the canonical way to load repo-specific experiential knowledge.
    Any harness can call it — no MCP required.

.PARAMETER RepoRoot
    Path to the git repository root.

.PARAMETER Query
    Description of the current task (e.g., "implementing frontend feature").

.PARAMETER Files
    Comma-separated list of file paths being modified.

.PARAMETER Subsystem
    Target subsystem (e.g., "web", "artifacts", "api-worker").

.PARAMETER TaskType
    Target task type (e.g., "commit-workflow", "test-validation").

.PARAMETER MaxDocs
    Maximum memory docs to load (default: 3).

.PARAMETER MaxItems
    Maximum items to return (default: 10).

.PARAMETER DryRun
    Show what would be loaded without returning content.

.PARAMETER All
    Load all items as flat list.

.EXAMPLE
    .\recursive-training-loader.ps1 -RepoRoot . -Query "frontend feature" -Files "apps/web/src/App.tsx"

.EXAMPLE
    .\recursive-training-loader.ps1 -RepoRoot . -Subsystem "web" -MaxDocs 5

.EXAMPLE
    .\recursive-training-loader.ps1 -RepoRoot . -TaskType "commit-workflow" -MaxItems 20
#>
param(
    [Parameter(Mandatory)]
    [string]$RepoRoot,

    [string]$Query = "",
    [string]$Files = "",
    [string]$Subsystem = "",
    [string]$TaskType = "",
    [int]$MaxDocs = 3,
    [int]$MaxItems = 10,
    [switch]$DryRun,
    [switch]$All
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "recursive-training-loader.py"

$argsList = @("--repo-root", $RepoRoot)

if ($Query) { $argsList += @("--query", $Query) }
if ($Files) { $argsList += @("--files", $Files) }
if ($Subsystem) { $argsList += @("--subsystem", $Subsystem) }
if ($TaskType) { $argsList += @("--task-type", $TaskType) }
if ($MaxDocs -ne 3) { $argsList += @("--max-docs", $MaxDocs) }
if ($MaxItems -ne 10) { $argsList += @("--max-items", $MaxItems) }
if ($DryRun) { $argsList += "--dry-run" }
if ($All) { $argsList += "--all" }

& python $pyScript @argsList
