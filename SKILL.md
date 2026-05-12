---
name: recursive-mode
description: 'Repository workflow orchestration skill for staged implementation, locked artifacts, late-phase receipts, and durable memory maintenance. Use when executing recursive-mode runs, resuming a run, locking a phase, or verifying locks.'
---

# recursive-mode

## Purpose

Use this skill to run the repository workflow defined in `/.recursive/RECURSIVE.md`.

This file is the installable entrypoint for the skill. It is not the canonical workflow spec.
For phase order, audit-loop rules, lock rules, addenda, late-phase receipts, state/decisions updates, and memory maintenance, follow `/.recursive/RECURSIVE.md`.

## Bootstrap

Before doing recursive-mode work, ensure the repo scaffold exists:

- `/.recursive/RECURSIVE.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- `/.recursive/memory/MEMORY.md`
- `/.recursive/memory/skills/SKILLS.md`
- `/.recursive/memory/{domains,patterns,incidents,episodes,archive}/`
- `/.recursive/memory/skills/{availability,usage,issues,patterns}/`
- `/.recursive/run/`
- `/.codex/AGENTS.md` primary Codex bridge doc
- `/.agent/PLANS.md` bridge doc
- optional mirrored `AGENTS.md` docs if the repo already uses them

If any of those are missing or stale, the agent should bootstrap the repo automatically before continuing. Do not ask the user to run the bootstrap manually unless no supported Python or shell runtime is available in the environment. PowerShell is optional, not required.

Preferred bootstrap commands:

```bash
python ./scripts/install-recursive-mode.py --repo-root .
python3 ./scripts/install-recursive-mode.py --repo-root .
bash ./scripts/install-recursive-mode.sh --repo-root .
powershell -ExecutionPolicy Bypass -File ./scripts/install-recursive-mode.ps1 -RepoRoot .
pwsh -NoProfile -File ./scripts/install-recursive-mode.ps1 -RepoRoot .
```

Important boundary:

- `npx skills add ...` installs the skill package into agent directories.
- The target repository scaffold should then be created automatically on first recursive-mode use or via a wired session-start hook.
- Python and Bash paths are first-class and should work on macOS and Linux without PowerShell.
- Manual bootstrap commands are the fallback path, not the preferred normal UX.

## Read Order

1. Read `/.recursive/RECURSIVE.md`.
2. Read `/.codex/AGENTS.md` as the primary Codex bridge if present.
3. Read any other `AGENTS.md` copies only as mirrored bridge guidance if the repo uses them.
4. Read `/.agent/PLANS.md` as the primary Codex plans bridge if present.
5. Read `/.recursive/STATE.md`.
6. Read `/.recursive/DECISIONS.md`.
7. Read `/.recursive/memory/MEMORY.md`.
8. Load only the relevant memory docs under `/.recursive/memory/`.

If any bridge doc conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

## Operational Surface

- Canonical run root: `/.recursive/run/<run-id>/`
- Canonical workflow spec: `/.recursive/RECURSIVE.md`
- Canonical state: `/.recursive/STATE.md`
- Canonical decisions ledger: `/.recursive/DECISIONS.md`
- Canonical memory router: `/.recursive/memory/MEMORY.md`

## Trigger Examples

- `Implement requirement '<run-id>'`
- `Run Recursive Phase 2 for .recursive/run/<run-id>/`
- `Resume requirement '<run-id>' after manual QA`
- `Verify locks for .recursive/run/<run-id>/`

## Utility Scripts

- `scripts/install-recursive-mode.py`
- `scripts/install-recursive-mode.ps1`
- `scripts/install-recursive-mode.sh`
- `scripts/recursive-init.py`
- `scripts/recursive-init.ps1`
- `scripts/recursive-status.py`
- `scripts/recursive-status.ps1`
- `scripts/lint-recursive-run.py`
- `scripts/lint-recursive-run.ps1`
- `scripts/recursive-review-bundle.py`
- `scripts/recursive-review-bundle.ps1`
- `scripts/recursive-router-init.py`
- `scripts/recursive-router-init.ps1`
- `scripts/recursive-router-probe.py`
- `scripts/recursive-router-probe.ps1`
- `scripts/recursive-router-configure.py`
- `scripts/recursive-router-configure.ps1`
- `scripts/recursive-router-invoke.py`
- `scripts/recursive-router-invoke.ps1`
- `scripts/recursive-router-resolve.py`
- `scripts/recursive-router-resolve.ps1`
- `scripts/recursive-router-validate.py`
- `scripts/recursive-router-validate.ps1`
- `scripts/recursive-subagent-action.py`
- `scripts/recursive-subagent-action.ps1`
- `scripts/recursive-lock.py`
- `scripts/recursive-lock.ps1`
- `scripts/verify-locks.py`
- `scripts/verify-locks.ps1`
- `scripts/check-reusable-repo-hygiene.py`
- `scripts/check-reusable-repo-hygiene.ps1`
- `.recursive/scripts/recursive-training-grpo.py`
- `.recursive/scripts/recursive-training-grpo.ps1`
- `.recursive/scripts/recursive-training-phase8-trigger.py`
- `.recursive/scripts/recursive-training-phase8-trigger.ps1`
- `.recursive/scripts/recursive-training-sync.py`
- `.recursive/scripts/recursive-training-sync.ps1`
- `.recursive/scripts/recursive-training-loader.py`
- `.recursive/scripts/recursive-training-loader.ps1`
- `.recursive/scripts/recursive-training-mcp.py`
- `.recursive/scripts/recursive-training-mcp.ps1`

## Subskills

- `skills/recursive-spec/SKILL.md`
- `skills/recursive-worktree/SKILL.md`
- `skills/recursive-debugging/SKILL.md`
- `skills/recursive-tdd/SKILL.md`
- `skills/recursive-review-bundle/SKILL.md`
- `skills/recursive-router/SKILL.md`
- `skills/recursive-subagent/SKILL.md`
- `skills/recursive-training/SKILL.md` — extract durable experiential knowledge from completed runs

Use those subskills for their specialized discipline, but keep `/.recursive/RECURSIVE.md` as the single source of truth for the overall workflow contract.

Canonical routed CLI config lives under:

- `/.recursive/config/recursive-router.json`
- `/.recursive/config/recursive-router-discovered.json`

## Router-aware delegated execution

When this skill or any recursive subskill is about to call another model or external CLI for delegated audit, review, bounded implementation, or other routed subagent work, re-read these routing files from disk immediately before choosing the CLI/model.

Do not hardcode provider or model strings for routed delegation when repo policy already defines the route or fallback behavior.

If routed delegation is in scope, prefer `skills/recursive-router/SKILL.md` plus the canonical `recursive-router-resolve` and `recursive-router-invoke` scripts over bespoke model selection logic.

If routed delegation has been explicitly requested, or if `recursive-router-resolve` for the selected role returns `external-cli`, do not satisfy that delegated slot with local/self-audit work unless the effective route is `fallback-local`, `local-only`, `blocked`, or `ask-user` and that outcome is recorded. The controller may reject routed output after checking it against the actual files, diffs, and recursive artifacts, but unverified local work is not a substitute for a configured routed implementer, tester, reviewer, auditor, or planner role.

If a routed invocation returns `success: false`, exits nonzero, or reports issues that the bounded role is responsible for fixing, run an audit-repair-retry loop: preserve the failed attempt as evidence, tell the routed subagent exactly what to fix, rerun the same route after repair, then verify the new output locally before acceptance. Do not mark the delegated role or phase gate complete from a nonzero-exit routed attempt.

Before dispatching from an isolated worktree, make sure the routing policy and discovery inventory are present and current in that same worktree. Discovery inventory is often untracked, so a newly created worktree can have `/.recursive/config/recursive-router.json` without `/.recursive/config/recursive-router-discovered.json`; refresh discovery from the worktree or copy the current inventory from the controller/source repo before resolving or invoking a route, then record the paths and outcome in the phase artifact or action record.

## Optional add-on

- `recursive-benchmark` is intentionally excluded from the default exported recursive-mode package because it carries large packaged benchmark fixtures.
- Install it only when a user explicitly asks to benchmark recursive-mode, preferably via `find-skills` or by adding its dedicated benchmark add-on package or repo source.

For audited phases, the installed workflow requires `draft -> audit -> repair -> re-audit -> pass -> lock`, with `Audit: PASS` required before Coverage/Approval may pass.
Treat `## Worktree Diff Audit` as phase-scoped: Phase 2 owns planning completeness plus expected product/worktree paths, Phase 3-4 own actual product/worktree drift, Phase 6 owns `/.recursive/DECISIONS.md`, Phase 7 owns `/.recursive/STATE.md`, and Phase 8 owns `/.recursive/memory/**`.
New runs should use `Workflow version: recursive-mode-audit-v2`, where Phase 1 must include `## Source Requirement Inventory` and Phase 2 must include `## Requirement Mapping`, `## Plan Drift Check`, and plan-stage `## Requirement Completion Status`.
For Phase 3, declare `TDD Mode: strict|pragmatic`. Strict mode requires concrete RED and GREEN evidence paths. Pragmatic mode requires an explicit exception rationale plus compensating evidence.
For Phase 5, declare `QA Execution Mode: human|agent-operated|hybrid`. Do not fake human sign-off for agent-operated QA, and do not omit sign-off for human or hybrid QA.
For delegated review, prefer `scripts/recursive-review-bundle.py` or `scripts/recursive-review-bundle.ps1` so Phase 3.5 records a canonical `Review Bundle Path`.
If meaningful subagent work contributes to a phase, record it under `/.recursive/run/<run-id>/subagents/` and verify the action record against actual files, actual diffs, and actual recursive artifacts before accepting it. For review/audit delegation, prefer a stable reviewed artifact for `Current Artifact` rather than a mutable draft receipt.
Audited phases must record `Subagent Capability Probe`, `Delegation Decision Basis`, `## Subagent Contribution Verification`, and `## Requirement Completion Status`.
When subagents are available and the context bundle is complete, delegated audit/review is the default path. If the controller still uses `Audit Execution Mode: self-audit`, record a concrete `Delegation Override Reason`.
Use the stronger requirement disposition fields in `## Requirement Completion Status`: `Changed Files`, `Implementation Evidence`, `Verification Evidence`, `Deferred By`, `Scope Decision`, `Blocking Evidence`, and `Addendum` as appropriate to the chosen status.
Do not mark `implemented` or `verified` without concrete `Changed Files`. Do not mark `verified` without distinct verification evidence.
Treat addenda as authoritative effective inputs. When relevant addenda exist, list them under `Inputs`, re-read them in `## Effective Inputs Re-read`, and reconcile them in `## Earlier Phase Reconciliation`.
Review bundles should include relevant addenda automatically, and the written Phase 3.5 review should cite bundle-grounded upstream artifacts, addenda, and changed files or code refs in the review narrative.
`00-worktree.md` is the source of truth for diff basis. Record baseline type/reference, comparison reference, normalized baseline/comparison, and normalized diff command; do not silently improvise a different basis later.
Use Phase 8 to update skill memory under `/.recursive/memory/skills/` when the run teaches the repo something durable about skill availability, fit, delegated-review quality, or skill-discovery outcomes.
Phase 8 should also capture run-local skill usage before promoting any lesson into durable memory.
If the run plans delegated review, review bundles, or smoke-harness portability work, read `/.recursive/memory/skills/SKILLS.md` and the relevant skill-memory shards before planning or auditing.
If the run needs a specialized capability that is not already available, prefer the `find-skills` skill when it exists. Otherwise use the Skills CLI directly (`npx skills find`, `npx skills add`, `npx skills check`, `npx skills update`) and record the result when skill usage is relevant.
Diff audit ignores incidental runtime byproducts such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/` unless the repo intentionally tracks them.
Treat Phase 6, Phase 7, and Phase 8 receipts as concise delta receipts that point to the final control-plane docs instead of restating large sections.
Use `scripts/recursive-lock.py` or `scripts/recursive-lock.ps1` as the normal locking path instead of manually editing `Status`, `LockedAt`, and `LockHash`.
On Windows, run Node/Vite/Vitest commands from the real worktree path rather than `subst` or mapped-drive aliases.
When evaluating or building browser-local apps, consult `references/local-first-web-app-checklist.md` for common import/persistence/QA edge cases.
If the repository being improved is itself a reusable skill/workflow repo, do not commit current-session run folders, evidence logs, review bundles, subagent action records, or temp-path references unless they are intentional fixtures; use `scripts/check-reusable-repo-hygiene.py` or `scripts/check-reusable-repo-hygiene.ps1` before calling the repo clean.
