[CmdletBinding()]
param(
  [string]$RepoRoot = (Get-Location).Path,
  [switch]$SkipRecursiveUpdate
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
    Write-Output "[OK] Created directory: $Path"
  } else {
    Write-Output "[OK] Directory exists: $Path"
  }
}

function Ensure-File {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    $parent = Split-Path -Path $Path -Parent
    if ($parent) {
      Ensure-Directory -Path $parent
    }
    Write-Utf8NoBom -Path $Path -Content $Content
    Write-Output "[OK] Created file: $Path"
  } else {
    Write-Output "[OK] File exists: $Path"
  }
}

function Resolve-CanonicalWorkflowPath {
  param([Parameter(Mandatory = $true)][string]$SkillRoot)

  $candidates = @(
    (Join-Path (Join-Path $SkillRoot "references") "bootstrap\RECURSIVE.md"),
    (Join-Path (Join-Path $SkillRoot ".recursive") "RECURSIVE.md")
  )

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) {
      Write-Output "[INFO] Using canonical workflow template: $candidate"
      return $candidate
    }
  }

  throw ("Missing canonical workflow template. Expected one of: " + ($candidates -join ", "))
}

function Upsert-MarkedBlock {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string]$StartMarker,
    [Parameter(Mandatory = $true)][string]$EndMarker,
    [Parameter(Mandatory = $true)][string]$BlockBody
  )

  $existing = ""
  if (Test-Path -LiteralPath $FilePath) {
    $existing = Get-Content -LiteralPath $FilePath -Raw -Encoding UTF8
    if ($null -eq $existing) {
      $existing = ""
    }
  }

  $block = "$StartMarker`r`n$BlockBody`r`n$EndMarker"
  $pattern = "(?s)$([regex]::Escape($StartMarker)).*?$([regex]::Escape($EndMarker))"

  if ([regex]::IsMatch($existing, $pattern)) {
    $updated = [regex]::Replace(
      $existing,
      $pattern,
      [System.Text.RegularExpressions.MatchEvaluator] { param($m) $block }
    )
  } elseif ([string]::IsNullOrWhiteSpace($existing)) {
    $updated = "$block`r`n"
  } else {
    $trimmed = $existing.TrimEnd("`r", "`n")
    $updated = "$trimmed`r`n`r`n$block`r`n"
  }

  if ($updated -ne $existing) {
    Write-Utf8NoBom -Path $FilePath -Content $updated
    Write-Output "[OK] Updated file: $FilePath"
  } else {
    Write-Output "[OK] File already up to date: $FilePath"
  }
}

function Get-MemoryRouterBody {
  @'
## Memory Router

This file is the durable memory router for the repository.
It is not a knowledge dump. Store durable memory in sharded docs under `domains/`, `patterns/`, `incidents/`, `episodes/`, `skills/`, or `archive/`.

Control-plane docs are not memory docs:
- `/.recursive/RECURSIVE.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- `/.codex/AGENTS.md`
- `/AGENTS.md`
- `/.agent/PLANS.md`

## Retrieval Rules

- Read this file before loading any other memory docs.
- Load only the memory docs relevant to the current task.
- If the task plans delegated review, subagent help, review bundles, smoke-harness portability work, or capability-sensitive execution, read `/.recursive/memory/skills/SKILLS.md` and then load the relevant skill-memory shards.
- If Phase 8 will need to promote durable lessons, first capture run-local skill usage in the run artifact and only then promote generalized conclusions into skill-memory shards.
- Prefer `Status: CURRENT` docs for planning and execution.
- `Status: SUSPECT` docs may be used as leads, but revalidate them before trust.
- Exclude `STALE` and `DEPRECATED` docs from default retrieval unless doing historical analysis.

## Registry

- `domains/` - stable functional-area knowledge with `Owns-Paths`
- `patterns/` - reusable playbooks and solution patterns
- `incidents/` - recurring failure signatures and fixes
- `episodes/` - distilled lessons from specific runs
- `skills/` - durable skill and capability memory, routed via `skills/SKILLS.md`
- `archive/` - historical or deprecated memory docs

## Freshness Rules

- Durable memory docs must declare the metadata defined in `references/artifact-template.md`.
- Any doc whose `Owns-Paths` or `Watch-Paths` overlaps final changed code paths must be reviewed in Phase 8.
- Affected `CURRENT` docs should be downgraded to `SUSPECT` until revalidated against final code, `STATE.md`, and `DECISIONS.md`.
- If changed paths have no owning domain doc, create one or record the uncovered-path follow-up in `08-memory-impact.md`.
- Skill-memory docs should record source runs, last validated date, environment notes, and current trust/fit guidance.
- If a run materially teaches the repo something about skill availability, delegated-review quality, review-bundle usage, or toolchain fallback behavior, Phase 8 must either create/refresh a skill-memory shard or record why no durable lesson was promoted.
- If the repo itself is a reusable skill/workflow distribution, durable memory must remain generalized. Do not store current-session run residue or temp-environment observations as if they were universal truth.
'@
}

function Get-SkillMemoryRouterBody {
  @'
## Skill Memory Router

This file routes durable skill and capability knowledge for the repository.
It summarizes what skills were available, what was attempted, what worked, what failed, and how future runs should use those skills.

Use the subfolders for durable Markdown-only skill memory:

- `availability/` - environment-specific skill availability and capability probe notes
- `usage/` - stable usage guidance and fit for specific skills
- `issues/` - recurring skill failures, limitations, or confusing behavior
- `patterns/` - reusable multi-skill operating patterns and delegation playbooks

Keep this file concise. Link to child docs instead of duplicating them.

## Retrieval Hints

- If the run may use delegated review, subagents, or review bundles:
  - read this router
  - read only the most relevant skill-memory docs that are actually present for the current environment and workflow
- If the run may need specialized external capability:
  - prefer the `find-skills` skill when available
  - otherwise use the Skills CLI directly and treat discovered packages as candidates until quality is checked
- If the run changes the smoke harness or cross-toolchain behavior:
  - read the most relevant availability/usage notes if any have been intentionally promoted into skill memory
- In Phase 8, promote durable skill lessons into one of these shards:
  - `availability/` for capability probes and environment constraints
  - `usage/` for stable fit/use guidance
  - `issues/` for recurring failure modes
  - `patterns/` for reusable operating playbooks
- Before promoting anything durable, capture run-local skill usage in the Phase 8 artifact:
  - what skills were available
  - what skills were sought
  - what skills were attempted or used
  - what worked well or poorly
  - what future guidance should change

## Current Docs

- `/.recursive/memory/skills/usage/skill-discovery-and-evaluation.md`
- `/.recursive/memory/skills/patterns/delegated-verification-and-refresh.md`
- `/.recursive/memory/skills/patterns/phase8-skill-memory-promotion.md`
- Add child docs here only when they are intentionally promoted as reusable repository guidance.
'@
}

function Get-SkillDiscoveryMemoryDoc {
  @'
Type: `pattern`
Status: `CURRENT`
Scope: `How recursive-mode runs should discover, evaluate, and record external skills or missing capabilities.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/SKILL.md`
- `/README.md`
Source-Runs:
- `none (generic repository guidance)`
Validated-At-Commit: `generic-repository-guidance`
Last-Validated: `2026-04-09T00:00:00Z`
Tags:
- `skills`
- `discovery`
- `find-skills`
- `capability`

# Skill Discovery And Evaluation

Use this guidance when a run needs a specialized capability that is not already available.

## Preferred Order

1. Use the `find-skills` skill if it is already installed.
2. Otherwise use the Skills CLI directly.
3. If nothing suitable exists, proceed with built-in capability and record that no suitable external skill was available.

## Useful Commands

- `npx skills find <query>`
- `npx skills add <package-or-repo>`
- `npx skills add <package-or-repo> --skill <skill-name>`
- `npx skills check`
- `npx skills update`

## Evaluation Rules

- Prefer skills from reputable publishers or organizations.
- Prefer higher install counts when the skills are otherwise comparable.
- Check upstream repository quality before recommending or installing a skill.
- Do not treat search results as proof of quality; verify source and documentation first.

## Phase 8 Recording

If a run materially used skill discovery, capture it in `08-memory-impact.md` under:

- `## Run-Local Skill Usage Capture`
- `## Skill Memory Promotion Review`

Promote only durable, reusable conclusions into skill memory. Leave one-off session notes in the run artifact instead of turning them into durable guidance.
'@
}

function Get-DelegatedVerificationMemoryDoc {
  @'
Type: `pattern`
Status: `CURRENT`
Scope: `How the main agent verifies delegated review or audit work before accepting it as lockable evidence.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/skills/recursive-subagent/SKILL.md`
- `/agents/code-reviewer.md`
- `/agents/implementer.md`
Source-Runs:
- `none (generic repository guidance)`
Validated-At-Commit: `generic-repository-guidance`
Last-Validated: `2026-04-09T00:00:00Z`
Tags:
- `skills`
- `subagent`
- `verification`
- `review-bundle`

# Delegated Verification And Refresh

Delegated work is optional helper output, not autonomous authority.

## Main-Agent Acceptance Rules

Before accepting meaningful delegated work, the main agent should verify:

- claimed file impact against the actual diff-owned file set
- claimed artifact reads or updates against files that actually exist
- review-bundle contents against the current reviewed artifact and artifact hash
- requirement, plan, addenda, and prior recursive docs that materially informed acceptance
- whether any post-review repair made the delegated context stale

## Record In The Phase Artifact

When delegated work materially contributes, `## Subagent Contribution Verification` should record:

- `Reviewed Action Records`
- `Main-Agent Verification Performed`
- `Acceptance Decision`
- `Refresh Handling`
- `Repair Performed After Verification`

## Refresh Rule

If repairs materially change the reviewed artifact, changed-file scope, or evidence basis, refresh the review bundle or action record before relying on delegated work for lockable evidence.

## Rejection Rule

If the main agent cannot verify delegated claims against actual files, actual artifacts, and the actual diff scope, reject the delegated result and fall back to self-audit for lockable completion evidence.
'@
}

function Get-Phase8SkillMemoryDoc {
  @'
Type: `pattern`
Status: `CURRENT`
Scope: `How Phase 8 captures run-local skill usage and promotes only durable lessons into skill memory.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/references/artifact-template.md`
- `/scripts/recursive-closeout.py`
- `/scripts/lint-recursive-run.py`
- `/scripts/recursive-status.py`
Source-Runs:
- `none (generic repository guidance)`
Validated-At-Commit: `generic-repository-guidance`
Last-Validated: `2026-04-09T00:00:00Z`
Tags:
- `skills`
- `memory`
- `phase8`
- `promotion`

# Phase 8 Skill Memory Promotion

Skill memory should be operational, not accidental.

## First Capture It Run-Locally

Before promoting durable guidance, record run-local skill usage in `08-memory-impact.md`:

- what skills were available
- what skills were sought
- what skills were attempted or used
- what worked well
- what issues were encountered
- what future guidance changed
- what promotion candidates exist

## Then Decide What Becomes Durable

Promote only lessons that are:

- reusable across runs
- specific enough to change future planning or verification behavior
- not merely one-off environmental noise

## Keep The Boundary Honest

- Run-local observations belong in the run artifact first.
- Durable memory should contain generalized guidance, not session history.
- In reusable skill/workflow repos, do not turn current-session implementation residue into durable memory unless it has been rewritten as generic repository guidance.
'@
}

function Get-RecursiveAgentsRouterBody {
  @'
## .recursive AGENTS Router

This file is a lightweight routing/index doc for agents already working inside the repository.
It exists to reduce blind doc-by-doc scanning. It is not a second workflow spec.

## Canonical Rule

- Treat `/.recursive/RECURSIVE.md` as the single workflow source of truth.
- If this file conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

## Suggested Read Order

1. Read `/.recursive/RECURSIVE.md` first for workflow rules and required behavior.
2. Read `/.recursive/STATE.md` when the current repo state matters.
3. Read `/.recursive/DECISIONS.md` when prior rationale or relevant earlier work matters.
4. Read `/.recursive/memory/MEMORY.md` when task context may depend on durable memory.
5. Read `/.recursive/memory/skills/SKILLS.md` when the task may use delegated review, subagents, review bundles, smoke-harness portability work, or other capability-sensitive execution.
6. Read `/.recursive/README.md` for repo-maintainer/bootstrap notes when changing the package itself.

## Task Routing

- Starting or resuming a recursive-mode run:
  - `/.recursive/RECURSIVE.md`
  - `/.recursive/STATE.md`
  - `/.recursive/DECISIONS.md`
  - `/.recursive/memory/MEMORY.md`
- Working on reusable package/bootstrap/docs for this repo:
  - `/.recursive/README.md`
  - `/README.md`
  - `/scripts/install-recursive-mode.py`
  - `/scripts/install-recursive-mode.ps1`
- Working on phase artifact structure or lint expectations:
  - `/references/artifact-template.md`
  - `/scripts/lint-recursive-run.py`
  - `/scripts/recursive-status.py`
- Working on delegated review or subagent behavior:
  - `/.recursive/memory/skills/SKILLS.md`
  - `/skills/recursive-subagent/SKILL.md`
  - `/skills/recursive-review-bundle/SKILL.md`
- Working on memory behavior:
  - `/.recursive/memory/MEMORY.md`
  - `/.recursive/memory/skills/SKILLS.md`

## Non-Canonical Bridges

These are adapters, not second specs:

- `/.codex/AGENTS.md`
- `/AGENTS.md`
- `/.agent/PLANS.md`

Read them only when the tool or host expects those entrypoints.
'@
}

function Get-PlansBridgeBody {
  @'
## recursive-mode plans bridge

This file exists only for tools that expect the Codex plans bridge at `/.agent/PLANS.md`.

The canonical workflow specification lives in `/.recursive/RECURSIVE.md`.
Do not maintain a second authoritative workflow here.

If this bridge conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

Short user commands that should trigger recursive-mode orchestration include:

- `Implement the run`
- `Implement run <run-id>`
- `Implement requirement '<run-id>'`
- `Implement the plan`
- `Create a new run based on the plan`
- `Start a recursive run`

Resolution rule:

- If a run id is explicit, use that run.
- If exactly one active/incomplete run exists and no run id is given, resume it.
- If the user refers to a plan, create a new run only when a unique source plan/requirements artifact can be identified from repo docs or immediate task context.
- If the command is ambiguous, ask for the run id or the repo path of the source plan/requirements artifact.

Audit delegation rule:

- If subagents are available and the audit/review context bundle is complete, delegated audit/review is the default path.
- If the controller still chooses `self-audit`, record a concrete `Delegation Override Reason` in the audited phase artifact.
'@
}

$resolvedRepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
Write-Output "[INFO] Repo root: $resolvedRepoRoot"

$skillRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$canonicalWorkflowPath = Resolve-CanonicalWorkflowPath -SkillRoot $skillRoot
$agentsBlockPath = Join-Path (Join-Path $skillRoot "references") "agents-block.md"

$recursiveRoot = Join-Path $resolvedRepoRoot ".recursive"
$codexRoot = Join-Path $resolvedRepoRoot ".codex"
$agentRoot = Join-Path $resolvedRepoRoot ".agent"
$memoryRoot = Join-Path $recursiveRoot "memory"
$skillMemoryRoot = Join-Path $memoryRoot "skills"
$runRoot = Join-Path $recursiveRoot "run"

$recursivePath = Join-Path $recursiveRoot "RECURSIVE.md"
$recursiveAgentsPath = Join-Path $recursiveRoot "AGENTS.md"
$statePath = Join-Path $recursiveRoot "STATE.md"
$decisionsPath = Join-Path $recursiveRoot "DECISIONS.md"
$memoryRouterPath = Join-Path $memoryRoot "MEMORY.md"
$skillMemoryRouterPath = Join-Path $skillMemoryRoot "SKILLS.md"
$skillDiscoveryPath = Join-Path (Join-Path $skillMemoryRoot "usage") "skill-discovery-and-evaluation.md"
$delegatedVerificationPath = Join-Path (Join-Path $skillMemoryRoot "patterns") "delegated-verification-and-refresh.md"
$phase8SkillMemoryPath = Join-Path (Join-Path $skillMemoryRoot "patterns") "phase8-skill-memory-promotion.md"
$codexAgentsPath = Join-Path $codexRoot "AGENTS.md"
$rootAgentsPath = Join-Path $resolvedRepoRoot "AGENTS.md"
$plansPath = Join-Path $agentRoot "PLANS.md"

$recursiveStartMarker = "<!-- RECURSIVE-MODE-CANONICAL:START -->"
$recursiveEndMarker = "<!-- RECURSIVE-MODE-CANONICAL:END -->"
$memoryStartMarker = "<!-- RECURSIVE-MODE-MEMORY:START -->"
$memoryEndMarker = "<!-- RECURSIVE-MODE-MEMORY:END -->"
$agentsStartMarker = "<!-- RECURSIVE-MODE-AGENTS:START -->"
$agentsEndMarker = "<!-- RECURSIVE-MODE-AGENTS:END -->"
$plansStartMarker = "<!-- RECURSIVE-MODE-PLANS-BRIDGE:START -->"
$plansEndMarker = "<!-- RECURSIVE-MODE-PLANS-BRIDGE:END -->"

Ensure-Directory -Path $recursiveRoot
Ensure-Directory -Path $codexRoot
Ensure-Directory -Path $agentRoot
Ensure-Directory -Path $memoryRoot
Ensure-Directory -Path $skillMemoryRoot
Ensure-Directory -Path $runRoot
foreach ($subdir in @("domains", "patterns", "incidents", "episodes", "archive")) {
  $full = Join-Path $memoryRoot $subdir
  Ensure-Directory -Path $full
  Ensure-File -Path (Join-Path $full ".gitkeep") -Content ""
}
foreach ($subdir in @("availability", "usage", "issues", "patterns")) {
  $full = Join-Path $skillMemoryRoot $subdir
  Ensure-Directory -Path $full
  Ensure-File -Path (Join-Path $full ".gitkeep") -Content ""
}

Ensure-File -Path (Join-Path $runRoot ".gitkeep") -Content ""
Ensure-File -Path $recursivePath -Content "# RECURSIVE.md`n"
Ensure-File -Path $recursiveAgentsPath -Content "# AGENTS.md`n"
Ensure-File -Path $statePath -Content @"
# STATE.md

## Current State

- Initial state not documented yet.
"@
Ensure-File -Path $decisionsPath -Content @"
# DECISIONS.md

## Recursive Run Index

- No runs recorded yet.
"@
Ensure-File -Path $memoryRouterPath -Content "# MEMORY.md`n"
Ensure-File -Path $skillMemoryRouterPath -Content "# SKILLS.md`n"
Ensure-File -Path $skillDiscoveryPath -Content (Get-SkillDiscoveryMemoryDoc)
Ensure-File -Path $delegatedVerificationPath -Content (Get-DelegatedVerificationMemoryDoc)
Ensure-File -Path $phase8SkillMemoryPath -Content (Get-Phase8SkillMemoryDoc)
Ensure-File -Path $codexAgentsPath -Content "# AGENTS.md`n"
Ensure-File -Path $plansPath -Content "# PLANS.md`n"

Upsert-MarkedBlock `
  -FilePath $recursiveAgentsPath `
  -StartMarker $agentsStartMarker `
  -EndMarker $agentsEndMarker `
  -BlockBody ((Get-RecursiveAgentsRouterBody).TrimEnd("`r", "`n"))
Upsert-MarkedBlock `
  -FilePath $memoryRouterPath `
  -StartMarker $memoryStartMarker `
  -EndMarker $memoryEndMarker `
  -BlockBody ((Get-MemoryRouterBody).TrimEnd("`r", "`n"))
Upsert-MarkedBlock `
  -FilePath $skillMemoryRouterPath `
  -StartMarker $memoryStartMarker `
  -EndMarker $memoryEndMarker `
  -BlockBody ((Get-SkillMemoryRouterBody).TrimEnd("`r", "`n"))

if (-not (Test-Path -LiteralPath $agentsBlockPath)) {
  throw "Missing AGENTS bridge template: $agentsBlockPath"
}
$agentsBlock = (Get-Content -LiteralPath $agentsBlockPath -Raw -Encoding UTF8).TrimEnd("`r", "`n")
Upsert-MarkedBlock `
  -FilePath $codexAgentsPath `
  -StartMarker $agentsStartMarker `
  -EndMarker $agentsEndMarker `
  -BlockBody $agentsBlock

if (Test-Path -LiteralPath $rootAgentsPath) {
  Upsert-MarkedBlock `
    -FilePath $rootAgentsPath `
    -StartMarker $agentsStartMarker `
    -EndMarker $agentsEndMarker `
    -BlockBody $agentsBlock
}

Upsert-MarkedBlock `
  -FilePath $plansPath `
  -StartMarker $plansStartMarker `
  -EndMarker $plansEndMarker `
  -BlockBody ((Get-PlansBridgeBody).TrimEnd("`r", "`n"))

if (-not $SkipRecursiveUpdate) {
  $canonicalResolved = [System.IO.Path]::GetFullPath($canonicalWorkflowPath)
  $recursiveResolved = [System.IO.Path]::GetFullPath($recursivePath)
  if ($canonicalResolved -eq $recursiveResolved) {
    Write-Output "[INFO] Skipped RECURSIVE.md self-upsert because source and destination are the same file."
  } else {
    $canonicalBody = (Get-Content -LiteralPath $canonicalWorkflowPath -Raw -Encoding UTF8).TrimEnd("`r", "`n")
    Upsert-MarkedBlock `
      -FilePath $recursivePath `
      -StartMarker $recursiveStartMarker `
      -EndMarker $recursiveEndMarker `
      -BlockBody $canonicalBody
  }
} else {
  Write-Output "[INFO] Skipped RECURSIVE.md update by configuration."
}

Write-Output "[OK] recursive-mode installation bootstrap complete."
