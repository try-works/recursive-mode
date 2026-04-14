#!/usr/bin/env pwsh
#
# Optional template - NOT auto-installed by Skills CLI.
# If your agent/runtime supports hooks, you may wire this up manually.
#
# Session Start Hook for recursive-mode

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PluginRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))

function Invoke-RecursiveBootstrap {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    if (Test-Path (Join-Path $RepoRoot ".recursive\RECURSIVE.md")) {
        return $true
    }

    Write-Output "Bootstrapping recursive-mode scaffold in $RepoRoot ..."

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python (Join-Path $PluginRoot "scripts\install-recursive-mode.py") --repo-root $RepoRoot
        if ($LASTEXITCODE -eq 0) { return $true }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 (Join-Path $PluginRoot "scripts\install-recursive-mode.py") --repo-root $RepoRoot
        if ($LASTEXITCODE -eq 0) { return $true }
    }
    if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        & pwsh -NoProfile -File (Join-Path $PluginRoot "scripts\install-recursive-mode.ps1") -RepoRoot $RepoRoot
        if ($LASTEXITCODE -eq 0) { return $true }
    }
    if (Get-Command powershell -ErrorAction SilentlyContinue) {
        & powershell -ExecutionPolicy Bypass -File (Join-Path $PluginRoot "scripts\install-recursive-mode.ps1") -RepoRoot $RepoRoot
        if ($LASTEXITCODE -eq 0) { return $true }
    }

    Write-Warning "Could not auto-bootstrap recursive-mode. Run one of the install-recursive-mode scripts manually."
    return $false
}

Write-Output ""
Write-Output "recursive-mode"
Write-Output "====================="
Write-Output ""

try {
    $RepoRoot = git rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -eq 0 -and $RepoRoot) {
        Write-Output "Repository: $(Split-Path $RepoRoot -Leaf)"
        Invoke-RecursiveBootstrap -RepoRoot $RepoRoot | Out-Null
    } else {
        Write-Warning "Not in a git repository. recursive-mode expects version control."
    }
} catch {
    Write-Warning "Not in a git repository. recursive-mode expects version control."
}

Write-Output ""
Write-Output "Available Skills:"
Write-Output "  - recursive-mode       - Main workflow orchestration"
Write-Output "  - recursive-spec       - Repo-aware requirements/spec authoring"
Write-Output "  - recursive-benchmark  - Paired recursive benchmark runs"
Write-Output "  - recursive-worktree   - Required worktree isolation"
Write-Output "  - recursive-tdd        - TDD discipline for implementation"
Write-Output "  - recursive-debugging  - Root-cause analysis"
Write-Output "  - recursive-review-bundle - Canonical delegated review bundles"
Write-Output "  - recursive-subagent   - Parallel execution with fallback"
Write-Output ""

Write-Output "Quick Start:"
Write-Output "  1. Use recursive-spec to draft requirements, or identify the source plan"
Write-Output "  2. Use recursive-benchmark to compare recursive-off vs recursive-on"
Write-Output "  3. Invoke: 'Implement the run' or 'Implement requirement <run-id>'"
Write-Output "  4. recursive-mode should bootstrap missing scaffold automatically before proceeding"
Write-Output ""

Write-Output "Documentation:"
Write-Output "  - Canonical workflow: .recursive/RECURSIVE.md"
Write-Output "  - Artifact templates: references/artifact-template.md"
Write-Output ""

Write-Output "====================="
Write-Output ""

$env:RECURSIVE_MODE_ROOT = $PluginRoot
$env:RECURSIVE_MODE_VERSION = "2.0.0"

Write-Output "[OK] recursive-mode ready"
Write-Output ""
