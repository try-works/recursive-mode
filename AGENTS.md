# AGENTS.md

<!-- RECURSIVE-MODE-AGENTS:START -->
## recursive-mode bridge

This repository uses `recursive-mode`.

The single canonical workflow spec lives in `/.recursive/RECURSIVE.md`.
Read that file before starting or resuming any recursive-mode work.

For Codex, the primary AGENTS bridge target is `/.codex/AGENTS.md`.
If the repo also carries other `AGENTS.md` files, they may mirror this same bridge block.

Bridge guidance only:

- Treat this file as a harness adapter, not as a second workflow spec.
- If this file conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.
- Control-plane docs live under `/.recursive/`.
- Runs live under `/.recursive/run/<run-id>/`.
- Durable memory lives under `/.recursive/memory/`.
- If recursive-mode is invoked in a repo that does not yet contain the `/.recursive/` scaffold, bootstrap it automatically with the supported install script before continuing. Do not require the user to run a separate manual bootstrap step unless no supported runtime is available.

How users can invoke the skill:

- Treat short prompts such as `Implement the run`, `Implement run 75`, `Implement the plan`, `Create a new run based on the plan`, and `Start a recursive run` as valid recursive-mode entry commands.
- If a run id is given, use that run.
- If no run id is given and exactly one active/incomplete run exists, resume that run.
- If the user asks to implement/start based on a plan, create a new run only when a unique source plan or requirements artifact can be identified from repo docs or immediate task context.
- If the command is ambiguous, ask for the run id or the repo path of the source plan/requirements artifact.
- Prompts are still commands, not specifications: read the repo docs that define the run before proceeding.

Required recursive-mode audit behavior:

- Audited phases must follow `draft -> audit -> repair -> re-audit -> pass -> lock`.
- When subagents are unavailable, perform the same audit as `self-audit`; do not weaken or skip it.
- Delegate audits only when you can provide the full context bundle:
  - phase name and artifact path
  - upstream artifact paths reread for the audit
  - diff basis from `00-worktree.md`
  - changed file list and targeted code references
  - phase-specific audit questions/checklist
- If the context bundle is incomplete, do not delegate; perform the audit yourself and record `Audit Execution Mode: self-audit`.
- If subagents are available and the context bundle is complete, delegated audit/review is the default path.
- If subagents are available but the controller still chooses `self-audit`, record a concrete `Delegation Override Reason`.
- Do not set `Coverage: PASS` or `Approval: PASS` for an audited phase unless the artifact ends with `Audit: PASS`.
- Record `Subagent Capability Probe` and `Delegation Decision Basis` in every audited phase.
- If meaningful subagent work contributes to a phase, require a durable action record under `/.recursive/run/<run-id>/subagents/` and verify it against actual files, actual recursive artifacts, and the actual diff before acceptance. For review/audit delegation, prefer a stable reviewed artifact for `Current Artifact`.
- Store routed assistant output, raw transcripts, stdout/stderr captures, and invocation metadata under `/.recursive/run/<run-id>/evidence/router/`; cite them from action records rather than placing raw transcript Markdown directly under `subagents/`.
- Store initial routed prompt bundles only under run-scoped paths such as `/.recursive/run/<run-id>/router-prompts/`; do not bootstrap top-level `/.recursive/router-prompts/`.
- Treat `success: false` or any nonzero routed-assistant exit code as a failed attempt: preserve diagnostics, instruct the bounded routed role to repair owned issues when applicable, rerun the route, then verify the result before acceptance or record an explicit fallback.
- If delegated work is accepted after main-agent checks reveal issues, record the concrete repair performed after verification; do not accept stale delegated context silently.
- For Phase 3, declare `TDD Mode: strict|pragmatic`. Strict mode requires RED and GREEN evidence paths. Pragmatic mode requires an explicit exception rationale plus compensating evidence.
- For Phase 5, declare `QA Execution Mode: human|agent-operated|hybrid`. Human and hybrid require user sign-off. Agent-operated and hybrid require execution metadata plus evidence paths.
- For delegated review, prefer `recursive-review-bundle` and record `Review Bundle Path` in Phase 3.5 when review is delegated.
- Treat addenda as authoritative effective inputs. If relevant addenda exist, list them in `Inputs`, re-read them, and reconcile them explicitly.
- Review bundles should include relevant addenda automatically, and the written review should cite upstream artifacts, relevant addenda, prior recursive evidence, and changed files/code refs from that bundle in the review narrative.
- Audited phases must include machine-checkable `Requirement Completion Status` entries for every in-scope `R#`; Traceability alone is not enough.
- `implemented` and `verified` requirement dispositions must cite concrete `Changed Files`, and `verified` also requires distinct verification evidence.
- `00-worktree.md` is the source of truth for diff basis. Record baseline type/reference, comparison reference, normalized baseline/comparison, and normalized diff command; do not silently substitute a different basis later.
- Diff audit ignores incidental runtime byproducts such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/` unless the repo intentionally tracks them.
- Treat Phase 6, Phase 7, and Phase 8 receipts as concise delta receipts that point to final control-plane docs instead of duplicating them.
- Phase 8 should capture run-local skill usage and update skill memory under `/.recursive/memory/skills/` when the run teaches the repo something durable about skill availability, skill fit, delegated-review quality, or skill-discovery outcomes.
- If a run needs missing specialized capability, prefer the `find-skills` skill when available. Otherwise use the Skills CLI (`npx skills find`, `npx skills add`, `npx skills check`, `npx skills update`) and record the outcome when skill usage is relevant.
- When working inside a reusable skill/workflow repo, do not leave committed run residue such as concrete `/.recursive/run/<run-id>/` folders, evidence logs, review bundles, action records, or temp-path references unless they are intentional fixtures or examples.

Useful helpers:

Invoke these helper names from the installed recursive-mode skill directory or the source package checkout:

- `install-recursive-mode`
- `recursive-init`
- `recursive-status`
- `lint-recursive-run`
- `recursive-review-bundle`
- `recursive-subagent-action`
- `recursive-training-grpo`
- `recursive-training-phase8-trigger`
- `recursive-training-sync`
- `recursive-training-loader`
- `recursive-training-mcp`
- `recursive-lock`
- `verify-locks`
- `check-reusable-repo-hygiene`

Diff ownership rules:

- Phase 2 owns planned product/worktree scope only.
- Phase 3, Phase 3.5, and Phase 4 own actual product/worktree drift reconciliation.
- Phase 6 owns `/.recursive/DECISIONS.md`.
- Phase 7 owns `/.recursive/STATE.md`.
- Phase 8 owns `/.recursive/memory/**`.
- Do not treat later control-plane or memory churn as retroactive invalidation of earlier locked phases.

Locking rule:

- Use `recursive-lock` as the primary supported way to write `Status: LOCKED`, `LockedAt`, and `LockHash`.
- `recursive-lock` enforces monotonic phase gating: all earlier phases that exist in the run directory must be LOCKED before the target phase can be locked.
- To reopen a locked artifact (reset to DRAFT and invalidate downstream receipts), pass `--reopen` to `recursive-lock`.
<!-- RECURSIVE-MODE-AGENTS:END -->
