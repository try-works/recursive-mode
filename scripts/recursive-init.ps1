[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [string]$RepoRoot = (Get-Location).Path,
    [ValidateSet("feature", "bugfix", "refactor")][string]$Template = "feature",
    [string]$FromIssue = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -Path $Path -ItemType Directory -Force | Out-Null
        Write-Host ("[OK] Created directory: {0}" -f $Path)
    } else {
        Write-Host ("[OK] Directory exists: {0}" -f $Path)
    }
}

function Run-Git {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )

    $output = & git -C $RepoRoot @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        return [pscustomobject]@{
            Success = $false
            Output = (($output | Out-String).Trim())
        }
    }

    return [pscustomobject]@{
        Success = $true
        Output = (($output | Out-String).Trim())
    }
}

function Get-MdFieldValue {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$FieldName
    )

    $pattern = "(?m)^[ \t]*(?:[-*][ \t]+)?{0}:\s*(.+?)\s*$" -f [regex]::Escape($FieldName)
    $match = [regex]::Match($Content, $pattern)
    if (-not $match.Success) {
        return $null
    }
    return ($match.Groups[1].Value.Trim() -replace '^[`"'']+|[`"'']+$', "")
}

function Normalize-BaselineType {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $compact = ((($Value.Trim() -replace '^[`"'']+|[`"'']+$', "")).ToLowerInvariant() -replace "-", " ")
    $compact = [regex]::Replace($compact, "\s+", " ")
    $aliases = @{
        "commit" = "local commit"
        "branch" = "local branch"
        "remote" = "remote ref"
        "remote branch" = "remote ref"
        "merge base" = "merge-base derived"
    }
    $allowed = @("local commit", "local branch", "remote ref", "merge-base derived")
    if ($allowed -contains $compact) {
        return $compact
    }
    if ($aliases.ContainsKey($compact)) {
        return $aliases[$compact]
    }
    return $null
}

function Normalize-ComparisonReference {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $compact = ($Value.Trim() -replace '^[`"'']+|[`"'']+$', "")
    if (@("working-tree", "working-tree@head", "worktree", "working-tree+head") -contains $compact.ToLowerInvariant()) {
        return "working-tree"
    }
    return $compact
}

function New-RequirementsContent {
    param(
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$Template,
        [string]$FromIssue
    )

    $inputs = @("- [chat summary or source notes if captured in repo]")
    if (-not [string]::IsNullOrWhiteSpace($FromIssue)) {
        $inputs += "- Source: $FromIssue"
    }
    $inputsBlock = ($inputs -join "`r`n")

    return (@'
Run: `/.recursive/run/{0}/`
Phase: `00 Requirements`
Status: `DRAFT`
Workflow version: `recursive-mode-audit-v1`
Inputs:
{1}
Outputs:
- `/.recursive/run/{0}/00-requirements.md`
Scope note: This document defines stable requirement identifiers and acceptance criteria. (Template: {2})

## TODO

- [ ] Elicit requirements from user/context
- [ ] Define requirement identifiers (R1, R2, ...)
- [ ] Write acceptance criteria for each requirement
- [ ] Document out of scope items (OOS1, OOS2, ...)
- [ ] List constraints and assumptions
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Requirements

### `R1` <short title>

Description:
Acceptance criteria:
- [observable condition 1]
- [observable condition 2]

## Out of Scope

- `OOS1`: ...

## Constraints

- ...

## Assumptions

- ...

## Coverage Gate
...
Coverage: FAIL

## Approval Gate
...
Approval: FAIL
'@) -f $RunId, $inputsBlock, $Template
}

function Get-GitContext {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $headResult = Run-Git -RepoRoot $RepoRoot "rev-parse" "--verify" "HEAD^{commit}"
    if (-not $headResult.Success -or [string]::IsNullOrWhiteSpace($headResult.Output)) {
        return [pscustomobject]@{
            Context = $null
            Error = "Unable to resolve HEAD commit for Phase 0 diff basis prefill: $($headResult.Output)"
        }
    }

    $branchResult = Run-Git -RepoRoot $RepoRoot "symbolic-ref" "--quiet" "--short" "HEAD"
    $branchName = if ($branchResult.Success -and -not [string]::IsNullOrWhiteSpace($branchResult.Output)) {
        $branchResult.Output
    } else {
        "(detached HEAD)"
    }

    $headSha = $headResult.Output
    return [pscustomobject]@{
        Context = [pscustomobject]@{
            baseline_type = "local commit"
            baseline_reference = $headSha
            comparison_reference = "working-tree"
            normalized_baseline = $headSha
            normalized_comparison = "working-tree"
            normalized_diff_command = "git diff --name-only $headSha"
            base_branch = $branchName
            worktree_branch = $branchName
            base_commit = $headSha
            notes = "recursive-init prefilled this executable diff basis from the current HEAD commit. If Phase 0 later changes the chosen baseline, update every diff-basis field and rerun lint before locking."
        }
        Error = $null
    }
}

function New-WorktreeContent {
    param(
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [pscustomobject]$GitContext,
        [string]$PrefillError
    )

    $baseBranch = if ($GitContext) { $GitContext.base_branch } else { "(resolve during Phase 0)" }
    $worktreeBranch = if ($GitContext) { $GitContext.worktree_branch } else { "(resolve during Phase 0)" }
    $baseCommit = if ($GitContext) { $GitContext.base_commit } else { "<resolve-before-locking>" }
    $baselineType = if ($GitContext) { $GitContext.baseline_type } else { "local commit" }
    $baselineReference = if ($GitContext) { $GitContext.baseline_reference } else { "<resolve-before-locking>" }
    $comparisonReference = if ($GitContext) { $GitContext.comparison_reference } else { "working-tree" }
    $normalizedBaseline = if ($GitContext) { $GitContext.normalized_baseline } else { "<resolve-before-locking>" }
    $normalizedComparison = if ($GitContext) { $GitContext.normalized_comparison } else { "working-tree" }
    $normalizedDiffCommand = if ($GitContext) { $GitContext.normalized_diff_command } else { "git diff --name-only <resolve-before-locking>" }
    $notes = if ($GitContext) {
        $GitContext.notes
    } else {
        "Populate an executable diff basis before locking Phase 0. Lint and lock will fail until the normalized basis matches live git state."
    }

    $setupNote = if ([string]::IsNullOrWhiteSpace($PrefillError)) {
        "recursive-init detected the current repository context and prefilled the Phase 0 diff basis."
    } else {
        "recursive-init could not prefill the Phase 0 diff basis automatically: $PrefillError"
    }

    return (@'
Run: `/.recursive/run/{0}/`
Phase: `00 Worktree`
Status: `DRAFT`
Inputs:
- `/.recursive/run/{0}/00-requirements.md`
- Current git repository state
Outputs:
- `/.recursive/run/{0}/00-worktree.md`
Scope note: This document records the Phase 0 worktree context and the executable diff basis that all later audited phases must reuse.

## TODO

- [ ] Confirm the selected worktree location and isolation approach
- [ ] Confirm the base branch and worktree branch values
- [ ] Run setup and verify the clean test baseline
- [ ] Confirm the diff basis fields still match live git state
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Directory Selection

- Repository root: `{1}`
- Preferred worktree location: `.worktrees/{0}/`
- Update this section with the actual selected location before locking Phase 0.

## Safety Verification

- Original branch / repo state observed at init time: `{2}`
- Isolation still must be confirmed after the actual worktree is created.

## Worktree Creation

- Intended worktree branch: `{3}`
- Record the actual worktree creation command and output before locking.

## Main Branch Protection

- Base branch source of truth at init time: `{2}`
- Explicitly document any deviation from isolated worktree execution before locking.

## Project Setup

- Init-time note: {4}
- Replace this section with the actual setup commands and results during Phase 0.

## Test Baseline Verification

- Record the baseline commands and results after setup completes.

## Worktree Context

- Base branch: `{2}`
- Worktree branch: `{3}`
- Base commit: `{5}`

## Diff Basis For Later Audits

- Baseline type: `{6}`
- Baseline reference: `{7}`
- Comparison reference: `{8}`
- Normalized baseline: `{9}`
- Normalized comparison: `{10}`
- Normalized diff command: `{11}`
- Base branch: `{2}`
- Worktree branch: `{3}`
- Diff basis notes: `{12}`

## Traceability

- Recursive workflow safety -> Phase 0 records a reusable executable diff basis before audited phases begin.

## Coverage Gate

- [ ] Worktree location and branch context are recorded
- [ ] Setup and clean baseline verification are recorded
- [ ] Diff basis fields are executable against live git state

Coverage: FAIL

## Approval Gate

- [ ] Phase 0 context is ready for downstream audited phases
- [ ] No unresolved setup or diff-basis inconsistencies remain

Approval: FAIL
'@) -f $RunId, $RepoRoot, $baseBranch, $worktreeBranch, $setupNote, $baseCommit, $baselineType, $baselineReference, $comparisonReference, $normalizedBaseline, $normalizedComparison, $normalizedDiffCommand, $notes
}

function Test-Phase0DiffBasis {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$RunDir
    )

    $worktreePath = Join-Path $RunDir "00-worktree.md"
    if (-not (Test-Path -LiteralPath $worktreePath)) {
        return "00-worktree.md is missing."
    }

    $content = Get-Content -LiteralPath $worktreePath -Raw -Encoding UTF8
    $baselineType = Normalize-BaselineType (Get-MdFieldValue -Content $content -FieldName "Baseline type")
    $baselineReference = Get-MdFieldValue -Content $content -FieldName "Baseline reference"
    $comparisonReference = Normalize-ComparisonReference (Get-MdFieldValue -Content $content -FieldName "Comparison reference")
    $normalizedBaseline = Get-MdFieldValue -Content $content -FieldName "Normalized baseline"
    $normalizedComparison = Normalize-ComparisonReference (Get-MdFieldValue -Content $content -FieldName "Normalized comparison")
    $normalizedDiffCommand = Get-MdFieldValue -Content $content -FieldName "Normalized diff command"

    $missingFields = @()
    if (-not $baselineType) { $missingFields += "Baseline type" }
    if ([string]::IsNullOrWhiteSpace($baselineReference)) { $missingFields += "Baseline reference" }
    if (-not $comparisonReference) { $missingFields += "Comparison reference" }
    if ([string]::IsNullOrWhiteSpace($normalizedBaseline)) { $missingFields += "Normalized baseline" }
    if (-not $normalizedComparison) { $missingFields += "Normalized comparison" }
    if ([string]::IsNullOrWhiteSpace($normalizedDiffCommand)) { $missingFields += "Normalized diff command" }
    if ($missingFields.Count -gt 0) {
        return "Diff basis is missing required field(s): {0}" -f ($missingFields -join ", ")
    }

    $comparisonGitRef = if ($normalizedComparison -eq "working-tree") { "HEAD" } else { $normalizedComparison }
    if ($baselineType -eq "merge-base derived") {
        $baselineResult = Run-Git -RepoRoot $RepoRoot "merge-base" $comparisonGitRef $baselineReference
        if (-not $baselineResult.Success) {
            return "Unable to compute merge-base for diff basis: $($baselineResult.Output)"
        }
        $computedBaseline = $baselineResult.Output
    } else {
        $baselineResult = Run-Git -RepoRoot $RepoRoot "rev-parse" "--verify" "$baselineReference^{commit}"
        if (-not $baselineResult.Success) {
            return "Unable to resolve baseline reference '$baselineReference': $($baselineResult.Output)"
        }
        $computedBaseline = $baselineResult.Output
    }

    if ($normalizedBaseline -ne $computedBaseline) {
        return "Recorded Normalized baseline does not match the executable diff basis ($normalizedBaseline != $computedBaseline)"
    }

    if ($normalizedComparison -eq "working-tree") {
        $expectedCommand = "git diff --name-only $computedBaseline"
    } else {
        $comparisonResult = Run-Git -RepoRoot $RepoRoot "rev-parse" "--verify" "$normalizedComparison^{commit}"
        if (-not $comparisonResult.Success) {
            return "Unable to resolve comparison reference '$normalizedComparison': $($comparisonResult.Output)"
        }
        $computedComparison = $comparisonResult.Output
        if ($normalizedComparison -ne $computedComparison) {
            return "Recorded Normalized comparison does not match the executable diff basis ($normalizedComparison != $computedComparison)"
        }
        $expectedCommand = "git diff --name-only $computedBaseline..$computedComparison"
    }

    if ($normalizedDiffCommand -ne $expectedCommand) {
        return "Recorded Normalized diff command does not match the executable diff basis ($normalizedDiffCommand != $expectedCommand)"
    }

    return $null
}

$resolvedRepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
Write-Host ("[INFO] Repo root: {0}" -f $resolvedRepoRoot)

$runRoot = Join-Path $resolvedRepoRoot ".recursive/run"
$runDir = Join-Path $runRoot $RunId

Ensure-Directory -Path $runRoot
Ensure-Directory -Path $runDir
Ensure-Directory -Path (Join-Path $runDir "addenda")
Ensure-Directory -Path (Join-Path $runDir "subagents")

$evidenceDir = Join-Path $runDir "evidence"
Ensure-Directory -Path $evidenceDir
Ensure-Directory -Path (Join-Path $evidenceDir "screenshots")
Ensure-Directory -Path (Join-Path $evidenceDir "logs")
Ensure-Directory -Path (Join-Path $evidenceDir "perf")
Ensure-Directory -Path (Join-Path $evidenceDir "traces")
Ensure-Directory -Path (Join-Path $evidenceDir "review-bundles")
Ensure-Directory -Path (Join-Path $evidenceDir "other")

$requirementsPath = Join-Path $runDir "00-requirements.md"
if ((Test-Path -LiteralPath $requirementsPath) -and (-not $Force)) {
    Write-Host ("[INFO] Requirements file exists, not overwriting: {0}" -f $requirementsPath)
} else {
    $content = New-RequirementsContent -RunId $RunId -Template $Template -FromIssue $FromIssue
    Write-Utf8NoBom -Path $requirementsPath -Content $content
    Write-Host ("[OK] Wrote requirements template: {0}" -f $requirementsPath)
}

$gitContextResult = Get-GitContext -RepoRoot $resolvedRepoRoot
if ($gitContextResult.Error) {
    Write-Host ("[WARN] {0}" -f $gitContextResult.Error)
}

$worktreePath = Join-Path $runDir "00-worktree.md"
if ((Test-Path -LiteralPath $worktreePath) -and (-not $Force)) {
    Write-Host ("[INFO] Worktree file exists, not overwriting: {0}" -f $worktreePath)
} else {
    $worktreeContent = New-WorktreeContent -RunId $RunId -RepoRoot $resolvedRepoRoot -GitContext $gitContextResult.Context -PrefillError $gitContextResult.Error
    Write-Utf8NoBom -Path $worktreePath -Content $worktreeContent
    Write-Host ("[OK] Wrote Phase 0 worktree template: {0}" -f $worktreePath)
}

$diffBasisError = Test-Phase0DiffBasis -RepoRoot $resolvedRepoRoot -RunDir $runDir
if ($diffBasisError) {
    Write-Host ("[FAIL] 00-worktree.md diff basis is not executable yet: {0}" -f $diffBasisError)
    Write-Host "       Fix the Phase 0 diff-basis fields before locking or relying on downstream audit tooling."
    exit 1
}

Write-Host "[OK] Phase 0 diff basis is executable against live git state."
Write-Host ""
Write-Host "Next steps:"
Write-Host ("1) Edit: .recursive/run/{0}/00-requirements.md" -f $RunId)
Write-Host ("2) Edit: .recursive/run/{0}/00-worktree.md" -f $RunId)
Write-Host ("3) Run:  Implement requirement '{0}'" -f $RunId)
Write-Host "4) Complete the run through the audited Phase 8 closeout before considering it done."
