---
name: recursive-training
description: 'Use after accumulating completed recursive-mode runs to extract durable, repo-specific experiential knowledge. Combines ReasoningBank structured memory and GRPO variance-filtered group comparison with winner-only fallback. Discovers ALL markdown files in each run folder, groups runs by subsystem only (not task_type), extracts ALL learnings from each subsystem through the companion extractor script where each item self-declares its own task_type (commit-workflow, test-validation, requirements-scoping, etc.), distributes items to training memory files by their self-declared task_type, and writes them to the canonical memory plane plus registry-backed summaries. No parameter updates — all learning through context.'
---

# recursive-training

## Purpose

Use this skill when a repository has accumulated 2+ completed recursive-mode runs and you want the agent to learn from historical successes and failures in a structured, retrievable way.

This skill synthesizes two research advances:
- **ReasoningBank** (Google): Structured memory items with title/description/content/schema that embed and retrieve via similarity search
- **Training-Free GRPO** (Tencent): Variance-filtered group comparison — only extract when a group has both winners (all gates pass) and losers (any gate fails)

**New: Winner-only extraction mode.** When all runs in a group are successful (no losers), the skill falls back to extracting consistent patterns, conventions, and repo-specific practices across the successful runs. This supports high-quality repos where every run passes gates but still contains rich experiential knowledge.

The canonical overall workflow lives in `/.recursive/RECURSIVE.md`. This skill covers the training, memory, and experience-sync discipline that happens after runs complete and before new runs begin.

## Architecture Overview

```
.recursive/run/<run-id>/          → parse → RecursiveRollout objects
  ANY *.md file                       ↓
                                    group by SUBSYSTEM only
                                        ↓
                              ┌──────────────────────┐
                              │  Subsystem Group      │
                              │  (all runs in scope)  │
                              └──────────────────────┘
                                        ↓
                              ┌──────────────────────┐
                              │  Group Classification │
                              │  contrastive | winner │
                              └──────────────────────┘
                                        ↓
                          ┌───────────────────────────────┐
                          │  Script Extraction:           │
                          │  One subsystem → many items   │
                          │  Each item has its own        │
                          │  task_type (commit-workflow,  │
                          │  test-validation, etc.)       │
                          └───────────────────────────────┘
                                        ↓
                          ┌───────────────────────────────┐
                          │  Distribute by item.task_type │
                          │  → training/<tt>.md          │
                          │  → domains/<subsystem>.md    │
                          └───────────────────────────────┘
                                        ↓
.recursive/memory/domains/<sub>.md
.recursive/memory/training/<tt>.md
.cursorrules / CLAUDE.md / copilot-instructions.md   (bootstrap-managed pointer files)
```

## Hard Rules

1. **Repository-local only.** Experiences never leak between repos. All training data, memory storage, and generated instruction files are scoped to the current git working tree.

2. **No parameter updates.** Learning happens through external memory/context optimization.

3. **Dual extraction modes.**
   - **Contrastive (GRPO)**: Group must contain both winners and losers to produce contrastive signal. Uniform groups with variance skip to winner-only mode.
   - **Winner-only**: Group contains only winners but has enough runs (default: 2+) to extract consistent patterns. The extractor is asked for repo conventions rather than failure avoidance.

4. **Subsystem-only grouping.** Runs are grouped by `subsystem` (e.g., `packages/artifacts`, `apps/web`). A single run can produce learnings about MANY different kinds of work — requirements scoping, planning, implementation, testing, QA, commit workflow, cleanup. The extractor script extracts ALL learnings from a subsystem's runs and tags each item with its own `task_type`. Items are then distributed to training memory files by their self-declared task_type.

5. **ReasoningBank structured memory.** Every memory item has: title (identifier), description (one-line summary), content (distilled steps/rationale), schema (task_type, subsystem, source_runs, applies_to, created_at, success_rate).

6. **Evidence-grounded only.** Every memory item traces back to at least one completed recursive-mode run with explicit pass/fail evidence.

7. **`.recursive/memory/` is the ONLY canonical store.** All experiential knowledge lives under `/.recursive/memory/`. Nothing outside this directory is authoritative. `.cursorrules`, `CLAUDE.md`, and `.github/copilot-instructions.md` are bootstrap-managed pointer files that should reference the memory system rather than mirror extracted content. The loader reads only from `/.recursive/memory/`. The training script writes only to `/.recursive/memory/`. If a pointer file conflicts with a memory file, the memory file wins.

8. **All documents in a run folder are training data.** The parser discovers every `*.md` file in `.recursive/run/<id>/` — not just the 00-08 convention. Audit reports, addenda, evidence summaries, and any agent-created documentation are all included.

## Memory Schema (ReasoningBank-style)

Each memory item is a structured dict with these fields:

```yaml
title: "Branch-based commit workflow"
description: "Always create feature branches before committing remediation work"
content: |
  1. Create branch from stage HEAD: git checkout -b fix/<issue>
  2. Make changes and verify with tests
  3. Push branch and open PR — never commit directly to stage
schema:
  task_type: "commit-remediation"
  subsystem: "git-workflow"
  source_runs: ["phase15b-commit-remediation", "phase17-cleanup"]
  applies_to: [".worktrees/", "git workflow", "stage branch"]
  created_at: "2026-04-30T12:00:00Z"
  status: "active"
  success_rate: 0.95
  rb_id: "RB-0"
```

The flat text injected into prompts becomes:
```
- [RB-0] **Branch-based commit workflow**: Always create feature branches before committing remediation work. When committing remediation work, create a feature branch from stage HEAD first — never commit directly to stage. (applies to: .worktrees/, git workflow, stage branch)
```

## Training Data Source

The parser discovers **ALL `*.md` files** in each run folder. No naming convention is enforced — any markdown document the agent created during a run is included.

Primary artifacts (read into named fields if present):
- `00-requirements.md`      → Query (task description)
- `01-as-is.md`             → Baseline understanding
- `02-to-be-plan.md`        → Strategy
- `03-implementation-summary.md` → Actions + changed files
- `04-test-summary.md`      → Test results
- `05-manual-qa.md`         → QA results
- `06-decisions-update.md`  → Decisions
- `07-state-update.md`      → State changes
- `08-memory-impact.md`     → Memory updates

Supplementary artifacts (also scanned for signals):
- `AUDIT-*.md`              → Implementation audits, gap analysis
- `CANONICAL-SPEC.md`       → Specifications
- Any other `*.md`          → Addenda, evidence, notes, remediation plans

Reward signals extracted deterministically from ALL documents:
- Audit Verdict: PASS/FAIL in any audited phase
- Coverage: PASS/FAIL
- Approval: PASS/FAIL
- QA Verdict: PASS/FAIL (flexible detection, see below)
- Test counts via multiple patterns:
  - `94/94 pass` (slash format)
  - `65 files, 541 tests` (table format)
  - `507 passed (507 tests)` (parentheses format)
  - `94 pass` (single count, assumed all passed)
  - `Tests: 94 pass` (labeled format)
- Build / typecheck pass or fail

## Flexible QA Verdict Detection

Different recursive-mode repos express QA approval differently:
- **Ambiens style**: `05-manual-qa.md` contains explicit `## QA Verdict` heading with PASS/FAIL
- **Role-model style**: `05-manual-qa.md` contains `Approval: PASS` gate but no explicit QA Verdict heading
- **Generic**: `05-manual-qa.md` exists with no FAIL signals anywhere

The parser handles all three:
1. First, look for `## QA Verdict` with PASS/FAIL
2. If not found, check `Approval: PASS/FAIL` within the `05-manual-qa.md` document
3. If neither, assume PASS if `05-manual-qa.md` exists and contains no FAIL signals
4. Otherwise, QA = FAIL (missing QA doc or explicit failure)

## Flexible Evidence Detection

Instead of requiring specific 00-08 files, the parser checks for **evidence categories** across all discovered documents:

- **Implementation evidence** exists if ANY document contains: `03-implementation-summary.md`, `AUDIT-*.md`, or keywords like "implemented", "refactor", "changed files", "commit", "git diff", "diff --stat", "requirements completed"
- **Test evidence** exists if ANY document contains: `04-test-summary.md`, or keywords like "tests pass", "test suite", "vitest", "npx vitest", "test result", "npm test", "passed", "full suite"

A run is only marked as critically missing if it has **neither** implementation evidence **nor** test evidence across its entire document set.

## Grouping Strategy

Runs are grouped **by subsystem only**. The task_type is NOT used for grouping.

```
groups = group_by_subsystem(rollouts)
# e.g., "packages/artifacts" → [phase15b, phase23b, ...]
# e.g., "apps/web" → [phase17, phase25, ...]
```

**Why subsystem-only?**

A single run spans multiple document types (requirements, plan, implementation, tests, QA), and each document type teaches a DIFFERENT kind of lesson:
- `00-requirements.md` → how to scope requirements for this repo
- `02-to-be-plan.md` → how to structure plans for this subsystem
- `03-implementation-summary.md` → how to implement in this codebase
- `04-test-summary.md` → how to test this subsystem
- `05-manual-qa.md` → how to verify this subsystem

If we grouped by task_type, a `commit-cleanup-validate` run could only produce `commit-cleanup-validate` learnings — losing the test-validation lessons, the requirements-scoping lessons, and the planning lessons embedded in the same run.

**Subsystem inference** — from changed file paths across ALL documents:
  e.g., `packages/artifacts`, `apps/api-worker`, `web-frontend`, `role-model-router`, `protocol`

The parser tallies file path prefixes and picks the most frequent. This naturally clusters runs that touched the same code area, even if their primary task was different.

## Group Classification & Extraction Modes

After grouping, each group is classified:

| Classification | Condition | Extraction Prompt |
|---|---|---|
| **Contrastive** | ≥1 winner AND ≥1 loser | "Why winners succeeded where losers failed" |
| **Winner-only** | Only winners, count ≥ threshold | "What consistent patterns appear across successful runs" |
| **Insufficient** | Mixed but below thresholds | Skipped |

The winner-only threshold is configurable (default: 2). For winner-only groups, the extractor receives only successful run summaries and is asked to extract:
- Build/test commands specific to this repo
- File organization patterns that repeat
- Architectural conventions (e.g., TS→Go bridging, vendored module management)
- Common verification approaches
- Repo quirks an external agent would need to know

## Extraction Output

For both modes, the extractor returns a JSON array of structured memory items. **Each item includes its own `task_type` — a single run can produce items with different task_types.**

```json
[
  {
    "title": "Use corepack pnpm for nested commands",
    "description": "Root scripts must use corepack pnpm instead of bare pnpm",
    "content": "1. Root package.json scripts must invoke nested workspace commands through `corepack pnpm ...`. 2. This ensures PATH-independent resolution on Windows.",
    "task_type": "infrastructure-scripting",
    "applies_to": ["package.json", "pnpm scripts"]
  },
  {
    "title": "Branch before committing remediation",
    "description": "Always create a feature branch before committing remediation work",
    "content": "1. Create branch from stage HEAD: git checkout -b fix/<issue>. 2. Make changes and verify. 3. Push branch and open PR.",
    "task_type": "commit-workflow",
    "applies_to": [".worktrees/", "git workflow", "stage branch"]
  },
  {
    "title": "Validate with vitest before commit",
    "description": "Run the full vitest suite before considering a run complete",
    "content": "1. Run `npx vitest run packages/<pkg>/src/<pkg>.test.ts`. 2. Verify all tests pass. 3. Only then proceed to QA.",
    "task_type": "test-validation",
    "applies_to": ["vitest", "test commands", "packages/*"]
  }
]
```

Requirements for each item:
- **title**: ≤ 6 words, acts as identifier
- **description**: ≤ 20 words, one-line summary
- **content**: max 100 words, distilled actionable steps
- **task_type**: the kind of work this learning applies to. Be specific and descriptive. Examples: `commit-workflow`, `test-validation`, `frontend-implementation`, `requirements-scoping`, `planning`, `cleanup`, `qa-verification`, `api-design`.
- **applies_to**: list of file paths, commands, or conceptual tags
- Focus on THIS repo's quirks, not generic advice

## Memory Plane Integration

Memory items are written to TWO locations:

1. **Domain memory**: `/.recursive/memory/domains/<subsystem>.md`
   - ALL items from a subsystem group are written here (regardless of their individual task_type)
   - Standard domain metadata (Type, Scope, Owns-Paths, Source-Runs)
   - Items appended under `## ReasoningBank Items`

2. **Training memory**: `/.recursive/memory/training/<task_type>.md`
   - Items are distributed here by their **self-declared task_type**
   - A single extraction pass over a subsystem can produce items that land in multiple training memory files
   - Standard training-memory shard format
   - Items appended under `## Extracted Reasoning Items`

Each write includes:
- RB-ID (ReasoningBank ID, e.g., RB-0, RB-1)
- Full structured item (title, description, content)
- Schema metadata (source_runs, applies_to, success_rate)
- Timestamp

## Output Contract

After training completes:

```
/.recursive/memory/domains/<subsystem>.md      ← domain-specific items
/.recursive/memory/training/<task>.md          ← task-type patterns
.cursorrules                                   ← bootstrap-managed memory pointer
CLAUDE.md                                       ← bootstrap-managed memory pointer
.github/copilot-instructions.md                ← bootstrap-managed memory pointer
```

Files NEVER modified:
- Assistant internals
- Any file outside current git working tree
- Prior-phase run artifacts (locked per RECURSIVE.md)

## Phase 8 Integration: From Run-Local Observations to Cross-Run Memory

Phase 8 (`08-memory-impact.md`) is where the **current run records its own observations** — what worked, what failed, what should be remembered. This is **run-local capture**, not cross-run extraction. The training script reads `08-memory-impact.md` from ALL completed runs as input, then extracts patterns that span multiple runs.

### The Flow: Phase 8 → Training → Memory

```
Run N executes:
  Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8
                                                                    ↓
                                                              08-memory-impact.md
                                                              (run-local observations)
                                                                    ↓
Run N: Phase 8 LOCKED
  ↓
Run: recursive-training-phase8-trigger.py
  ↓
Checks: ≥ 2 completed runs?
  ↓
YES → recursive-training-grpo.py --incremental --run-id <RunN>
  ↓
  Reads ALL runs (including Run N's 08-memory-impact.md)
  ↓
  Groups by subsystem
  ↓
  Extractor script extracts cross-run patterns
  ↓
  Writes items to .recursive/memory/
  ↓
  recursive-training-sync.py prints startup reading guidance
  ↓
  Registry refreshed
  ↓
Run N+1 starts
  ↓
  [LOADING POINT] recursive-training-loader.py reads .recursive/memory/
  ↓
  Agent receives relevant context before Phase 0
```

### What Phase 8 Captures vs What Training Extracts

| | **Phase 8** (`08-memory-impact.md`) | **Training** (`recursive-training-grpo.py`) |
|---|---|---|
| **Scope** | Single run | All completed runs |
| **Content** | Run-local observations | Cross-run patterns |
| **Examples** | "Auth took longer than expected" | "Always implement auth before features that depend on it" |
| **Author** | Agent writing Phase 8 | Extractor pass over all Phase 8s + other artifacts |
| **Storage** | `.recursive/run/<id>/08-memory-impact.md` | `.recursive/memory/domains/` + `.recursive/memory/training/` |
| **Reader** | Future training extraction | `recursive-training-loader.py` |

Phase 8 is **input** to training. Training is the **processor** that turns many Phase 8s into structured memory.

### Trigger: When Training Runs After Phase 8

`recursive-training-phase8-trigger.py` runs immediately after Phase 8 locks. This is a **thin wrapper** — it checks preconditions and delegates to `recursive-training-grpo.py`. It does NOT handle extraction policy or extractor-script details. That is the grpo script's job.

What the trigger does:
1. Count completed runs (checks for `08-memory-impact.md` with `LockedAt`)
2. If < 2 runs: skip with explanation
3. If no `--auto`: print the command and exit (user runs it manually)
4. If `--auto`: call `recursive-training-grpo.py --incremental --run-id <id>`
5. After grpo succeeds: the updated memory files are ready for future runs to load

| Completed Runs | `--auto` | Behavior |
|---|---|---|
| **0–1** | any | Skip. "Need at least 2 runs." |
| **2+** | no | Print command, exit. User runs manually. |
| **2+** | yes | Run training immediately |

### Commands

**Manual trigger (default):**
```bash
python .recursive/scripts/recursive-training-phase8-trigger.py \
  --repo-root . --run-id phase25-organizations-teams-rbac
```
→ Prints the grpo command. User runs it.

**Auto-trigger (CI/CD or scripted workflow):**
```bash
python .recursive/scripts/recursive-training-phase8-trigger.py \
  --repo-root . --run-id phase25-organizations-teams-rbac --auto
```
→ Runs grpo immediately.

**Pass extra args to grpo:**
```bash
python .recursive/scripts/recursive-training-phase8-trigger.py \
  --repo-root . --run-id phase25 --auto \
  --grpo-args "--winner-only-threshold 3"
```

**Direct training (skip trigger entirely):**
```bash
python .recursive/scripts/recursive-training-grpo.py \
  --repo-root . --incremental --run-id phase25
```

### The `/.recursive/memory/` Directory Is Canonical

**All experiential knowledge lives in `/.recursive/memory/`.** Nothing outside this directory is authoritative.

- **Training writes to:** `/.recursive/memory/domains/` and `/.recursive/memory/training/`
- **Loader reads from:** `/.recursive/memory/domains/` and `/.recursive/memory/training/`
- **Registry lives at:** `/.recursive/memory/MEMORY.md`
- **Bootstrap-managed pointer files** (`.cursorrules`, `CLAUDE.md`, `.github/copilot-instructions.md`) should point agents back to `/.recursive/memory/`; they are not per-sync mirrors of extracted memory
- **If a pointer conflicts with a memory file, the memory file wins**
- **Training never edits any `AGENTS.md`; bootstrap owns AGENTS upserts**

Never treat pointer files as authoritative. Always update memory via training, then re-sync the registry that derives from it.

## Loading: Consuming Memories for a New Run

Loading is the **separate** operation that happens at the start of Run N+1, **before Phase 0**.

| Operation | Script | When | Input | Output |
|---|---|---|---|---|
| **Extract** (training) | `recursive-training-grpo.py` | **After Phase 8** | All completed runs | New items in `/.recursive/memory/` |
| **Load** (consuming) | `recursive-training-loader.py` | **Before Phase 0** | Current task context | Formatted context for agent |
| **Sync** (guidance) | `recursive-training-sync.py` | **At run start or on demand** | Current memory plane | Startup reading guidance |

## How to Invoke Training

Training extraction is triggered by the user after Phase 8 completes, or deferred to a later time. Agents and workflows can recognize intent through natural language and slash commands.

### Trigger Patterns

Recognize the following as training requests:

| Pattern | Examples |
|---|---|
| **Standalone** | `"train"`, `"training"`, `"extract memories"`, `"learn from runs"` |
| **With scope** | `"train my repo"`, `"run training on this repo"`, `"start training"` |
| **With skill name** | `"recursive training"`, `"use recursive-training"`, `"run recursive-training"` |
| **Slash command** | `/recursive-training`, `/train`, `/extract-memories` |
| **Post-run** | `"train from the latest run"`, `"extract learnings from phase25"` |
| **Incremental** | `"update training"`, `"retrain with new runs"`, `"incremental training"` |

### Response Flow

When a training trigger is detected, follow this flow:

```
1. Check .recursive/scripts/ for training scripts
   └─ Missing? → "Training scripts not found. Run recursive-mode installation first."
   
2. Check .recursive/run/ for completed runs
   └─ Empty? → "No completed runs found. Complete some recursive-mode runs first."
   
3. Count runs and determine mode
   ├─ < 2 runs? → "Only N run(s) found. Need at least 2 for meaningful extraction."
   └─ ≥ 2 runs? → Proceed
   
4. Ask user for scope (unless intent is clear)
   ├─ "Full training (all runs) or incremental (latest run only)?"
   ├─ Default: full training
   
5. Construct and execute command
   
6. Stream output to user
   
7. On success: the updated memory files are ready for future loading
   └─ Notify: "Training complete. N items extracted across M task types."
```

### Default Parameters

When the user triggers training without specifying details, use these defaults:

```bash
python .recursive/scripts/recursive-training-grpo.py \
  --repo-root . \
  --winner-only-threshold 2
```

### Incremental Training (after a specific run)

When the user mentions a specific run or says "incremental":

```bash
python .recursive/scripts/recursive-training-grpo.py \
  --repo-root . \
  --incremental \
  --run-id <latest-run-id>
```

Auto-detect the latest run from `.recursive/run/` if not specified.

### Sync-Only Trigger

When the user says "sync memories" or "what should I read":

```bash
python .recursive/scripts/recursive-training-sync.py --repo-root .
```

This prints startup guidance without mutating `MEMORY.md` or any memory docs.

### Example Conversations

**User**: "train"
**Script runner**: "Starting full training on all completed runs..."
→ Runs `recursive-training-grpo.py` with defaults

**User**: "train from my latest run"
**Script runner**: "Starting incremental training from phase25-organizations-teams-rbac..."
→ Runs `recursive-training-grpo.py --incremental --run-id phase25-organizations-teams-rbac`

**User**: "/recursive-training"
**Script runner**: "Found 8 completed runs. Running full training..."
→ Runs `recursive-training-grpo.py` with defaults

**User**: "update training with the new frontend run"
**Script runner**: "Starting incremental training from phase17-frontend-ground-up-rebuild..."
→ Runs `recursive-training-grpo.py --incremental --run-id phase17-frontend-ground-up-rebuild`

**User**: "sync my memories"
**Script runner**: "Printing startup memory guidance..."
→ Runs `recursive-training-sync.py`

### Error Handling

| Situation | Expected Response |
|---|---|
| No `.recursive/scripts/` | "Training scripts not installed. Run `python scripts/install-recursive-mode.py --repo-root .` first." |
| No `.recursive/run/` | "No completed recursive-mode runs found. Complete at least 2 runs before training." |
| Only 1 run | "Only 1 run found. Need at least 2 for meaningful extraction. Complete another run and try again." |
| No training extractor | "Training skipped. The companion extractor script is unavailable in this environment." |
| Extraction returns empty | "No new learnings extracted. Runs may be too similar or lack sufficient variance." |

## Integration

Invoke after Phase 8 of a recursive-mode run, or periodically:

Full training:
  python .recursive/scripts/recursive-training-grpo.py --repo-root .

Incremental (after a new run):
  python .recursive/scripts/recursive-training-grpo.py --repo-root . \
    --incremental --run-id phase16-frontend-rebuild

With higher winner-only threshold:
  python .recursive/scripts/recursive-training-grpo.py --repo-root . \
    --winner-only-threshold 3

Sync only:
  python .recursive/scripts/recursive-training-sync.py --repo-root .

MCP server (for external MCP-compatible clients):
  python .recursive/scripts/recursive-training-mcp.py --repo-root .

Pre-Phase 0: When starting a new recursive-mode run, the agent reads
`/.recursive/RECURSIVE.md` and `/.recursive/memory/MEMORY.md`. The training
memory docs under `/.recursive/memory/training/` and
`/.recursive/memory/domains/` are loaded on demand when relevant to the
current task.

## Progressive Disclosure: How Memories Are Loaded

The memory system uses **three levels of progressive disclosure** to avoid context bloat while ensuring the agent sees relevant learnings.

### Level 1 — MEMORY.md (always read)

At the start of every session, read `/.recursive/memory/MEMORY.md`. This is a **lightweight router** (not a content dump) that explains the memory taxonomy, retrieval rules, and freshness policy.

The current memory plane itself provides the discoverable inputs:
- Domain memory docs (by subsystem) under `/.recursive/memory/domains/`
- Training memory docs (by task type) under `/.recursive/memory/training/`
- The router and retrieval rules in `/.recursive/memory/MEMORY.md`

### Level 2 — Loader Script (selective, task-aware)

After reading MEMORY.md, **call the loader script** with the current task context. The script lives at `.recursive/scripts/recursive-training-loader.py` (copied there during recursive-mode installation).

```bash
python .recursive/scripts/recursive-training-loader.py --repo-root . \
  --query "implementing frontend feature with react and tanstack router" \
  --files "apps/web/src/App.tsx,apps/web/src/stores/ui-store.ts" \
  --max-docs 3 \
  --max-items 10
```

The loader:
1. **Discovers docs** from the filesystem
2. **Scores each doc** by relevance to the task (task_type match, subsystem match, file path overlap)
3. **Reads the top-N docs** (default: 3)
4. **Scores each item** within those docs (query keyword overlap, applies_to overlap, success rate)
5. **Returns the top-M items** as formatted text ready to inject into the agent's context

**Why a Python script instead of MCP?**
- Works in **any environment** — pi, Claude Code, Cursor, Cline, Continue.dev, etc.
- No MCP server setup required
- Call it as a subprocess and inject the output into context
- More reliable than a markdown reference that the agent might skip

### Level 3 — Agent Applies Specific Items

The agent reads the returned context and applies specific items to its current task. Each item is self-contained with:
- What to do (content)
- Where it applies (applies_to)
- How reliable it is (success_rate)
- Where it came from (source_runs)

### MCP: Optional Enhancement

For MCP-compatible clients (Claude Desktop, Cline with MCP, Cursor MCP mode), the `.recursive/scripts/recursive-training-mcp.py` server provides a `get_repo_experiences` tool with the same scoring logic. This is an **optional convenience layer** — the Python loader is the canonical path.

**MCP vs Loader relationship:**
- **Loader** (`.recursive/scripts/recursive-training-loader.py`) is the canonical path — works everywhere and can be called directly
- **MCP** (`.recursive/scripts/recursive-training-mcp.py`) is an optional convenience for MCP-compatible clients
- Both read from the same memory files and use the same scoring logic
- **You only need one** — the loader is sufficient for all use cases

### Integration: When, How, and Where

#### When to Call the Loader

**Call the loader once per agent task/session**, immediately after reading `/.recursive/RECURSIVE.md` and `/.recursive/memory/MEMORY.md` but **before** the agent begins planning or implementing.

The exact timing depends on the caller architecture:

| Caller Type | When to Call |
|---|---|
| **Turn-based** (pi, Claude Code) | At the start of each new user request |
| **Session-based** (Cursor, Cline) | At the start of each chat/session |
| **CI/CD** (GitHub Actions) | Before the build/test step |
| **Subagent dispatch** | Before delegating to a subagent, pass loaded memories as context |

#### How to Call the Loader

Spawn the loader as a **subprocess**, capture stdout, and inject the output into the agent's context.

**Command pattern:**
```bash
python .recursive/scripts/recursive-training-loader.py \
  --repo-root <repo-root> \
  --query "<task description>" \
  --files "<comma-separated file paths>" \
  [--subsystem "<subsystem>"] \
  [--task-type "<task-type>"] \
  [--max-docs 3] \
  [--max-items 10]
```

**Required arguments:**
- `--repo-root`: Path to the git repository root
- `--query`: Description of the current task (used for relevance scoring)
- `--files`: Comma-separated list of file paths being modified (used for applies_to matching)

**Optional arguments:**
- `--subsystem`: Target subsystem for stronger matching
- `--task-type`: Target task type for stronger matching
- `--max-docs`: Maximum memory docs to load (default: 3)
- `--max-items`: Maximum items to return (default: 10)
- `--dry-run`: Preview what would be loaded without reading doc content

#### Where the Output Goes

The loader returns formatted text on stdout. Use this text in the agent's context in one of these ways:

**Option A: System prompt injection (recommended)**
Append the loader output to the system prompt before the first user message.

**Option B: Context message**
Send the loader output as a separate context message before the user's task description.

**Option C: Tool result (MCP-style)**
For MCP-compatible setups, return the loader output as a tool result that the agent can reference.

#### Integration Example (Python caller)

```python
import subprocess
from pathlib import Path

def load_repo_experiences(
    repo_root: str,
    task_description: str,
    modified_files: list[str],
    max_docs: int = 3,
    max_items: int = 10,
) -> str:
    """Load relevant experiential knowledge for the current task."""

    repo_path = Path(repo_root).resolve()
    loader = repo_path / ".recursive" / "scripts" / "recursive-training-loader.py"

    if not loader.exists():
        # Training scripts not installed — skip memory loading
        return ""

    result = subprocess.run(
        [
            "python", str(loader),
            "--repo-root", str(repo_path),
            "--query", task_description,
            "--files", ",".join(modified_files),
            "--max-docs", str(max_docs),
            "--max-items", str(max_items),
        ],
        capture_output=True,
        text=True,
        timeout=30,  # Loader should be fast (< 5s for typical repos)
    )

    if result.returncode != 0:
        print(f"Memory loader failed: {result.stderr}")
        return ""

    return result.stdout


# Usage at startup
task_desc = "implementing frontend feature with react and tanstack router"
files = ["apps/web/src/App.tsx", "apps/web/src/stores/ui-store.ts"]
memory_context = load_repo_experiences(".", task_desc, files)

if memory_context:
    # Inject into system prompt or send as context message
    system_prompt += f"\n\n{memory_context}"
```

#### Integration Example (Node.js caller)

```javascript
const { execSync } = require('child_process');
const path = require('path');

function loadRepoExperiences(repoRoot, taskDescription, modifiedFiles) {
    const loader = path.join(repoRoot, '.recursive', 'scripts', 'recursive-training-loader.py');

    if (!require('fs').existsSync(loader)) {
        return '';
    }

    try {
        const result = execSync(`python "${loader}" \
            --repo-root "${repoRoot}" \
            --query "${taskDescription}" \
            --files "${modifiedFiles.join(',')}" \
            --max-docs 3 \
            --max-items 10`, {
            encoding: 'utf-8',
            timeout: 30000,
        });
        return result;
    } catch (err) {
        console.error('Memory loader failed:', err.stderr);
        return '';
    }
}
```

#### Dry-Run Mode for Debugging

```bash
python .recursive/scripts/recursive-training-loader.py --repo-root . \
  --query "frontend feature" --files "apps/web/src/App.tsx" --dry-run
```

This shows which docs would be loaded and which items would be selected, without reading the actual doc content. Useful for debugging relevance scoring.

#### What If No Memories Exist Yet?

The loader returns a friendly message if no training memory exists:

```
No relevant experiences found for this task and file set.

Tip: If you're starting a new task type, run training first:
  python .recursive/scripts/recursive-training-grpo.py \
    --repo-root .
```

Callers should detect this and either:
- Proceed without memory context (first run on a new repo)
- Prompt the user to run training (if runs exist but haven't been processed)

## Script Boundary

The training scripts stay script-facing. They construct prompts, parse structured output, and write memory files; they do not own transport-selection concerns.

## Scripts

- `.recursive/scripts/recursive-training-grpo.py`           — main orchestrator (GRPO + ReasoningBank)
- `.recursive/scripts/recursive-training-grpo.ps1`          — PowerShell wrapper
- `.recursive/scripts/recursive-training-phase8-trigger.py` — post-Phase 8 training trigger (runs after Phase 8 before extraction)
- `.recursive/scripts/recursive-training-phase8-trigger.ps1` — PowerShell wrapper
- `.recursive/scripts/recursive-training-sync.py`           — print startup memory guidance (read-only)
- `.recursive/scripts/recursive-training-sync.ps1`          — PowerShell wrapper
- `.recursive/scripts/recursive-training-loader.py`         — progressive memory loader (canonical retrieval path)
- `.recursive/scripts/recursive-training-loader.ps1`        — PowerShell wrapper
- `.recursive/scripts/recursive-training-mcp.py`            — MCP server (optional, for MCP-compatible clients)
- `.recursive/scripts/recursive-training-mcp.ps1`           — PowerShell wrapper

## Coverage Gate

- [x] ReasoningBank structured memory schema documented
- [x] GRPO variance filter documented (winners + losers required)
- [x] Winner-only extraction mode documented
- [x] Subsystem-only grouping documented (task_type not used for grouping)
- [x] Training data source defined (ALL .md files in .recursive/run/)
- [x] Experience library defined (/.recursive/memory/domains/ + training/)
- [x] Reward signal extraction documented (explicit gates + document-grounded fallback)
- [x] Flexible test count patterns documented (5 regex variants)
- [x] Flexible evidence detection documented (implementation + test keywords)
- [x] Flexible QA verdict detection documented (3 fallback levels)
- [x] Per-item task_type tagging documented (extractor declares task_type per learning)
- [x] Single run → multiple task_type learnings documented
- [x] Group classification documented (contrastive vs winner-only vs insufficient)
- [x] Extraction prompts documented (both modes)
- [x] Memory plane integration documented (domain + skill shards)
- [x] Tool-agnostic inference documented (.cursorrules, CLAUDE.md, copilot-instructions.md)
- [x] Recursive-mode phase hooks documented (post-Phase 8, pre-Phase 0)
- [x] Script-only extraction contract documented
- [x] Non-negotiable rules documented
- [x] Progressive disclosure documented (3 levels: index → selective docs → specific items)
- [x] Memory loader script documented (canonical Python retrieval path)
- [x] Script-runner integration example documented
- [x] MCP vs Loader relationship documented (MCP is optional, loader is canonical)
- [x] Read-only startup guidance documented for recursive-training-sync.py
- [x] Phase 8 integration documented (08-memory-impact.md → training → .recursive/memory/)
- [x] Post-Phase 8 trigger script documented (recursive-training-phase8-trigger.py)
- [x] Memory plane as ONLY canonical store documented
- [x] Phase 8 vs Training distinction documented (run-local vs cross-run)

Coverage: PASS

## Approval Gate

- [x] Skill follows `/.recursive/RECURSIVE.md` as canonical source of truth
- [x] Repository-local scoping enforced
- [x] No parameter updates required
- [x] GRPO variance filter enforced
- [x] Winner-only fallback for high-quality repos
- [x] ReasoningBank structured memory enforced
- [x] Evidence-grounded only
- [x] Compatible with recursive-mode workflow version recursive-mode-audit-v2
- [x] Compatible with delegated review and routed subagent patterns
- [x] All .md files in run folders treated as training data
- [x] Subsystem-only grouping enforced (no task_type constraint on grouping)
- [x] Per-item task_type tagging enforced (extractor declares task_type per learning)
- [x] Single run → multiple task_type learnings supported
- [x] Task type inference is content-first (document-based action + domain scoring, run_id fallback only)
- [x] Supports repos with all-winning runs (role-model style)
- [x] Supports repos with mixed winners/losers (Ambiens style)
- [x] Progressive memory loader is the canonical retrieval path (not MCP)
- [x] Loader works in any environment (no MCP dependency)
- [x] MEMORY.md is workflow-owned, updated during Phase 8, and remains both human-readable and machine-consumable as the concise memory router
- [x] MCP is optional convenience layer, not required
- [x] `.recursive/memory/` is the ONLY canonical store
- [x] Phase 8 trigger script copies during installation
- [x] Pointer files are read-only bootstrap-managed surfaces (not sync-regenerated mirrors)

Approval: PASS
