# recursive-mode

`recursive-mode` is an installable skill package for structured AI-assisted software development.

It gives an agent a file-backed workflow for requirements, planning, implementation, testing, review, closeout, and memory, instead of leaving that process in chat history alone.

## Who It Is For

- people who want a stricter, auditable agent workflow inside a repo
- teams who want requirements and implementation evidence recorded in files
- users who want installable subskills for requirements/spec authoring, worktrees, debugging, TDD, delegated review, and subagent support, plus an optional benchmarking add-on when needed

## What It Includes

This repo currently ships these default installable skills:

- `recursive-mode`
- `recursive-spec`
- `recursive-worktree`
- `recursive-debugging`
- `recursive-tdd`
- `recursive-review-bundle`
- `recursive-subagent`

Optional add-on source:

- `recursive-benchmark`

## Included Subskills

| Skill | Purpose |
| --- | --- |
| `recursive-spec` | Co-authors repo-aware requirements for a new run from plan/spec prompts, keeps the draft outside the repo until approval, then creates the run and writes `00-requirements.md`. |
| `recursive-worktree` | Sets up an isolated worktree before implementation starts. |
| `recursive-debugging` | Adds structured root-cause analysis before fixing bugs or failing tests. |
| `recursive-tdd` | Enforces RED-GREEN-REFACTOR discipline for implementation work. |
| `recursive-review-bundle` | Builds canonical review bundles for delegated Phase 3.5 review. |
| `recursive-subagent` | Helps delegate bounded implementation, audit, or review work and verify the results. |

Optional add-on:

| Skill | Purpose |
| --- | --- |
| `recursive-benchmark` | Creates paired recursive-off and recursive-on benchmark repos, supports easy/medium/hard packaged scenarios, can run arms sequentially or in parallel with runner-specific fallback when needed, captures logs/timings/screenshots, and writes a comparison report. |

## Functionality

The workflow package includes functionality for:

- turning a repo task into a staged, file-backed implementation run
- co-authoring repo-aware requirements/specs before creating a new run
- benchmarking recursive-mode against a non-recursive baseline in paired disposable repos when the optional benchmark add-on is installed
- collecting screenshot artifacts taken during benchmark validation and embedding them in the report when present
- capturing requirements, analysis, plans, implementation evidence, and validation in durable artifacts
- enforcing audited phase progression with explicit pass/lock behavior
- preserving arbitrary `00-requirements.md` content through Phase 1 `Source Requirement Inventory` and Phase 2 lossless requirement mapping
- isolating work in a dedicated git worktree before implementation begins
- running strict or pragmatic TDD with recorded RED/GREEN evidence
- recording QA in explicit human, agent-operated, or hybrid modes
- packaging delegated reviews into canonical review bundles
- recording and checking subagent contributions before they are accepted
- updating decisions, state, and memory as part of closeout
- maintaining reusable skill-memory and capability guidance over time

## Workflow Overview

```mermaid
flowchart TD
    A[Create run in /.recursive/run/<run-id>/] --> B[Phase 0-2: requirements, AS-IS, plan]
    B --> C[Phase 3: implementation in isolated worktree]
    C --> D[Phase 3.5: delegated review or self-audit]
    D --> E[Phase 4: tests and verification]
    E --> F[Phase 5: manual QA or agent-operated QA]
    F --> G[Phase 6-8: decisions, state, memory closeout]
    G --> H[Lock artifacts and verify locks]
    H --> I[Future runs start with better context]

    B -. addenda update understanding .-> B
    C -. draft -> audit -> repair -> re-audit .-> C
    D -. main agent verifies delegated work .-> D
    G -. durable lessons promoted into memory .-> I
    I -. prior decisions, state, memory reread .-> B
```

At a high level, the workflow turns a task into a durable run, moves that run through audited phases, and then feeds validated outcomes back into decisions, state, and memory so later runs start from better context.

The main non-optional guardrails are:

- repository documents, not prompts, are the source of truth for requirements, plans, and phase inputs
- audited phases must pass through `draft -> audit -> repair -> re-audit -> pass -> lock`
- locked history is not rewritten; later corrections are handled through addenda and downstream reconciliation
- in-scope requirements need explicit dispositions and supporting implementation or verification evidence
- Phase 2 in the current workflow profile must preserve source obligations losslessly with `Source Requirement Inventory`, `Requirement Mapping`, and `Plan Drift Check`
- delegated work is not trusted on its own; the main agent must verify it against real files, diffs, and artifacts
- TDD, QA, review, and closeout all require explicit recorded modes, evidence, and phase outputs

## Benefits

Using the workflow can help you:

- keep important implementation context in repository files instead of losing it in chat history
- make agent work easier to audit, review, and resume later
- reduce vague “done” claims by requiring explicit evidence and phase completion records
- improve reliability through structured planning, testing, review, and closeout
- make delegated or subagent work safer by requiring controller verification
- preserve project decisions and operational lessons in a reusable form
- keep long-running agent work more consistent across sessions, contributors, and repositories

## Recursion

This workflow applies recursion in practice by making later work continuously refer back to, check, and refine earlier work.

In concrete terms:

- each phase consumes artifacts produced by earlier phases instead of starting from scratch
- audited phases repeatedly loop through `draft -> audit -> repair -> re-audit` until the work is actually ready
- downstream phases can correct or extend earlier understanding through addenda without rewriting locked history
- closeout phases feed validated lessons back into decisions, state, and memory so future runs can start from better context
- delegated review is recursive too: subagent work is not accepted on its own, but is reviewed again by the main agent against the repo’s real files, diffs, and artifacts

So the workflow is “recursive” not because it uses a programming-language recursion trick, but because the process repeatedly revisits its own outputs, uses them as inputs, and improves future work through structured feedback loops.

## Memory

The workflow includes a file-based memory layer under `/.recursive/memory/`.

In practice, that memory is used to store durable project knowledge such as:

- domain context
- reusable implementation patterns
- recurring incidents or failure modes
- capability and skill guidance
- lessons that were strong enough to keep beyond a single run

It is intentionally separated from:

- current repository state
- current decisions
- run-local working artifacts

That separation matters because it lets the workflow distinguish between:

- what is true right now
- what happened in one specific run
- and what has been learned repeatedly enough to be worth remembering long-term

Benefits of this memory model include:

- future runs can start from better context instead of rediscovering the same facts
- stable patterns and cautions can be reused across multiple tasks
- one-off session noise does not have to be treated as durable truth
- memory can be updated gradually as the codebase and workflow evolve
- skill-related knowledge, such as when a subskill helps or when a capability is missing, can become part of the workflow’s long-term operating knowledge

## Install

Install the main skill:

```bash
npx skills add try-works/recursive-mode
```

List everything in the package:

```bash
npx skills add try-works/recursive-mode --list
npx skills add try-works/recursive-mode --list --full-depth
```

Install all included skills:

```bash
npx skills add try-works/recursive-mode --skill '*' --full-depth
```

Install a single subskill:

```bash
npx skills add try-works/recursive-mode --skill recursive-spec --full-depth
```

Install the benchmark add-on only when you explicitly want benchmark runs:

```bash
npx skills add <recursive-benchmark-package-or-repo> --full-depth
```

## Quick Start

After installing the skill package into your agent environment, the intended normal flow is:

1. open a target git repository
2. if requirements do not exist yet, use `recursive-spec` to draft them from plan/spec prompts such as `create a plan`, `help me plan`, or `create a spec`
3. invoke recursive-mode with a short command such as `Implement the run`
4. if `/.recursive/` is missing, the skill should auto-bootstrap it before continuing

`recursive-spec` is intentionally approval-gated: it should collaborate on the draft first, keep that draft in temporary/session storage, and only create `/.recursive/run/<run-id>/00-requirements.md` after the user approves the spec.

If you want to measure recursive-mode itself, install `recursive-benchmark` on demand from its dedicated add-on package or repo source and then use it to create paired `recursive-off` and `recursive-on` benchmark repos from the packaged benchmark fixture and generate a markdown comparison report with logs, scores, and screenshot artifacts when present.

Manual bootstrap commands remain the fallback path when the runtime cannot auto-run the installer:

```bash
python "<SKILL_DIR>/scripts/install-recursive-mode.py" --repo-root .
bash "<SKILL_DIR>/scripts/install-recursive-mode.sh" --repo-root .
pwsh -NoProfile -File "<SKILL_DIR>/scripts/install-recursive-mode.ps1" -RepoRoot .
```

That creates the reusable `/.recursive/` scaffold, bridge docs, memory routers, and run layout used by the workflow.
The bundled installer carries its own canonical workflow template, so bootstrap works from the installed skill package even when hidden repo directories are not present in the package layout.

Important boundary:

- `npx skills add ...` installs the skill package into agent directories
- the target repo scaffold should then be created automatically on first recursive-mode use
- the large benchmark fixture set is intentionally excluded from the default exported recursive-mode package and should be installed separately only when benchmarking is requested
- Python and Bash are first-class bootstrap paths, so macOS and Linux users do not need PowerShell
- if your runtime supports session-start hooks, the templates under `docs/templates/hooks/` can auto-bootstrap the scaffold at session start

From there, the canonical workflow contract lives in:

- `/.recursive/RECURSIVE.md`

If an agent is already inside the repo and needs a lightweight index of what to read under `/.recursive/`, start with:

- `/.recursive/AGENTS.md`

The installable root skill entrypoint is:

- `/SKILL.md`

## Benchmarking recursive-mode

The packaged benchmark flow is meant to answer a simple question: **does recursive-mode improve real coding-agent outcomes on the same project?**

The packaged benchmark set uses React + TypeScript + Vite projects that:

- works from a temp folder
- runs entirely in the browser
- requires no database or external server
- is suitable for build/test/preview validation and later screenshot review

The benchmark harness creates paired repos for `recursive-off` and `recursive-on`, bootstraps the recursive-mode scaffold into the recursive-on repo, records the selected runner and model, enforces a timeout budget, evaluates build/test/preview outcomes, supports GitHub Copilot CLI, Codex CLI, and Kimi CLI, runs a mandatory controller-side judge review for every completed arm with `gpt-5.4` when available and the benchmarked model as fallback, writes per-arm progress files so live status can be inferred from workspace changes, keeps repo-local `.benchmark-workspaces/` ignored, and writes a markdown scoreboard report that separates runner health from product outcome, reports whether the recursive-on arm actually completed the recursive run artifact set, surfaces the recursive-on worktree isolation decision from `00-worktree.md`, supports timestamp fallback evidence, applies optional hint penalties, embeds screenshots when available, and includes a combined benchmark score that blends heuristic rubric coverage (70%) with the judge metric (30%).

Packaged scenario tiers:

- `local-first-planner` - easy
- `team-capacity-board` - medium
- `release-readiness-dashboard` - hard
- `scientific-calculator-rust` - xhard

The xhard Rust/WASM fixture intentionally starts from a bootstrap-only dependency scaffold rather than a placeholder calculator app, so the benchmarked agent must create the actual product code instead of only transforming preseeded UI and logic files.

Maintainer entrypoints:

```bash
python "<SKILL_DIR>/scripts/run-recursive-benchmark.py" --runner all --scenario local-first-planner
python "<SKILL_DIR>/scripts/run-recursive-benchmark.py" --runner kimi --scenario team-capacity-board --arm-mode parallel
python "<SKILL_DIR>/scripts/run-recursive-benchmark.py" --runner codex --scenario scientific-calculator-rust
pwsh -NoProfile -File "<SKILL_DIR>/scripts/run-recursive-benchmark.ps1" -Runner all
```

## How To Start A Run

Once a repo is bootstrapped and the requirements or plan live in repository files, the user should be able to start or resume work with short commands instead of long prompts.

Examples:

- `Implement the run`
- `Implement run 75`
- `Implement requirement '75'`
- `Implement the plan`
- `Create a new run based on the plan`
- `Start a recursive run`

How those are interpreted:

- if a run id is explicit, the agent should use that run
- if no run id is given and there is exactly one active or incomplete run, the agent should resume it
- if the user refers to a plan, the agent should create a new run only when a unique source plan or requirements artifact can be identified from repo docs or immediate task context
- if the command is ambiguous, the agent should ask for the run id or the repo path of the source plan/requirements artifact

The important boundary is that prompts stay short and command-like, while the actual requirements and plan still live in repository documents.

## Repository Structure

High level:

```text
SKILL.md
skills/
scripts/
references/
.recursive/
```

- `SKILL.md`: installable root skill entrypoint
- `skills/`: installable subskills
- `scripts/`: bootstrap, lint, status, lock, bundle, closeout, smoke, and hygiene tools
- `references/`: templates and reusable guidance
- `.recursive/`: canonical workflow spec, internal routing/index docs, and durable repo-internal control-plane docs

## Historical Note

This repository evolved from the older `rlm-workflow` project. That name remains historical only; `recursive-mode` is the current product and package surface.
