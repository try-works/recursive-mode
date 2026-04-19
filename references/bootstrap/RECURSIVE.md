## Canonical location

This file is the canonical source of truth for how agents work in this repository.



## Scope

This file defines:

- ExecPlans: a single, self-contained, novice-guiding execution plan for complex work.
- recursive-mode: a stage-gated, repo-document workflow that prevents "context rot" by making static repo documents the source of truth across phases, with explicit coverage and approval gates.

# recursive-mode workflow

recursive-mode is an extension of ExecPlans designed to prevent "context rot." In recursive-mode, substantive requirements and plans must live in static repository documents. Prompts must not carry requirements or plans; prompts only instruct an agent which phase to execute and which repo file(s) to use as inputs and outputs.

recursive-mode is recommended for: multi-step debugging, platform-specific behavior, risky refactors, migrations, or any change where an AS-IS analysis, explicit validation, and manual QA sign-off are necessary.

## Non-negotiable recursive-mode rules

1) Repo documents are the source of truth.

At the start of each phase, the agent must read the phase input document(s) from disk (including applicable addenda; see Addenda policy below) and treat them as authoritative. Conversational context may be used only to issue commands ("run Phase 2 using these file paths"), not to carry requirements.

2) Prompts are commands, not specifications.

Do not paste substantive requirements, acceptance criteria, test cases, or implementation plans into prompts. Place them in repo documents, then reference paths in the prompt.

3) One-way phases.

Within a phase, the agent may iterate on that phase's outputs until gates pass. After advancing to the next phase, the agent must not edit prior-phase artifacts. If a later phase discovers missing or incorrect information in an earlier phase, use an addendum in the current phase (see Addenda policy).

4) Explicit gates are mandatory.

Every phase output must end with:
- Coverage Gate: prove the output doc addresses everything relevant in the input doc (including input addenda).
- Approval Gate: prove the output is ready to proceed.

Manual QA approval depends on the declared `QA Execution Mode` in the Manual QA artifact. Human and hybrid QA require explicit user sign-off. Agent-operated QA does not.

5) Missing scaffold must be bootstrapped automatically.

If recursive-mode is invoked in a repository that does not yet contain the required `/.recursive/` scaffold and bridge docs, the agent should run the supported bootstrap installer automatically before continuing. Do not require the user to perform a separate manual bootstrap step unless no supported runtime is available to execute the installer.

## Global artifacts (across all recursive-mode runs)

recursive-mode uses two global documents shared by all requirements:

- `/.recursive/DECISIONS.md` — a global decision ledger and index of all completed (or aborted) runs. Each entry must reference the run folder and capture what changed and why.
- `/.recursive/STATE.md` — a global "current state of the app" document. It must reflect what is true now, not what was intended.

These two files are updated in later phases (see Phase 6 and Phase 7).

## Separate memory plane

recursive-mode maintains a separate durable memory plane under:

- `/.recursive/memory/MEMORY.md`
- `/.recursive/memory/domains/`
- `/.recursive/memory/patterns/`
- `/.recursive/memory/incidents/`
- `/.recursive/memory/episodes/`
- `/.recursive/memory/skills/SKILLS.md`
- `/.recursive/memory/skills/availability/`
- `/.recursive/memory/skills/usage/`
- `/.recursive/memory/skills/issues/`
- `/.recursive/memory/skills/patterns/`
- `/.recursive/memory/archive/`

These are memory docs. They are distinct from:

- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- `/.recursive/RECURSIVE.md`
- `/.codex/AGENTS.md`
- `/AGENTS.md`
- `/.agent/PLANS.md`

Those files remain control-plane docs and must not be repurposed as memory.

Required read behavior:

- At the start of every new session, read `/.recursive/STATE.md` to understand the current state of the app and codebase.
- At the start of every new session, read `/.recursive/DECISIONS.md` to understand prior work and the reasoning behind it.
- At the start of every new session, read `/.recursive/memory/MEMORY.md` to understand the memory router, taxonomy, and freshness policy.
- At the start of every new recursive-mode run, re-read `/.recursive/STATE.md`, `/.recursive/DECISIONS.md`, and `/.recursive/memory/MEMORY.md` before creating or updating run artifacts.
- At the start of every new recursive-mode run, use `/.recursive/DECISIONS.md` to identify any prior recursive-mode runs relevant to the new requirement or AS-IS analysis.
- If relevant prior runs are found, read only the docs needed from those runs to understand the affected codebase areas before writing the new run artifacts.
- If no relevant prior runs are identified, skip that step.
- After reading `MEMORY.md`, load only the memory docs relevant to the current task. Do not load the entire memory tree by default.
- If the run plans delegated review, subagent help, review bundles, smoke harness portability work, or other skill-sensitive execution, load `/.recursive/memory/skills/SKILLS.md` and the relevant skill-memory shards before planning or auditing.
- Prefer `Status: CURRENT` memory docs for planning/execution.
- `Status: SUSPECT` memory docs may be used as leads but must be revalidated before trust.
- `Status: STALE` and `Status: DEPRECATED` are excluded from default retrieval unless doing explicit historical investigation.

## Recursive run directory layout (per requirement)

Each recursive-mode run uses a stable folder:

`/.recursive/run/<run-id>/`

Required per-run artifacts:

- `00-requirements.md`
- `00-worktree.md` (REQUIRED - worktree isolation)
- `01-as-is.md`
- `02-to-be-plan.md`
- `03-implementation-summary.md`
- `04-test-summary.md`
- `05-manual-qa.md`
- `06-decisions-update.md`
- `07-state-update.md`
- `08-memory-impact.md`
- `addenda/` (see Addenda policy)
- `evidence/` (standardized evidence artifacts; screenshots/logs/perf/traces)

The run folder is the durable record for the requirement. It must be sufficient to understand and reproduce work without relying on chat logs.

When beginning a new run, use `/.recursive/DECISIONS.md` to locate earlier run folders relevant to the current requirement or AS-IS analysis. If any are found, read only the prior run artifacts most relevant to the same subsystem, workflow, or architectural area being changed. If none are found, skip this step.

## Memory taxonomy, metadata, and freshness

`MEMORY.md` is the router/index for the memory plane. It must remain concise and act as:

- registry
- retrieval guide
- freshness policy
- sharding guide
- ownership map

It must not become a giant knowledge dump.

Supported memory doc types:

- `index`
- `domain`
- `pattern`
- `incident`
- `episode`

Skill memory is a first-class part of the memory plane. Use `/.recursive/memory/skills/SKILLS.md` as the skill-memory router and shard durable skill knowledge under:

- `skills/availability/` for environment-specific capability probes and availability notes
- `skills/usage/` for stable skill fit and usage guidance
- `skills/issues/` for recurring skill failures or confusing behavior
- `skills/patterns/` for reusable multi-skill operating patterns

Phase 8 must update skill memory when a run teaches the repository something durable about skill availability, skill fit, delegated review quality, or repeated workflow friction.
Phase 8 must also record a run-local skill-usage capture before deciding what, if anything, is worth promoting into durable skill memory.

Every durable memory doc except `MEMORY.md` must include metadata near the top with at least:

- `Type`
- `Status`
- `Scope`
- `Owns-Paths`
- `Watch-Paths`
- `Source-Runs`
- `Validated-At-Commit`
- `Last-Validated`
- `Tags`

Optional metadata fields:

- `Parent`
- `Children`
- `Supersedes`
- `Superseded-By`

Allowed memory statuses:

- `CURRENT` — authoritative enough for planning and execution
- `SUSPECT` — may be read as a lead but must be revalidated before trust
- `STALE` — excluded from default retrieval
- `DEPRECATED` — historical only; excluded from default retrieval
- `DRAFT` — candidate memory, not yet durable

Freshness rules:

- `domain` docs use `Owns-Paths` for primary ownership of code surfaces.
- `pattern` and `incident` docs may declare `Watch-Paths` without being the primary owner.
- If a final validated code diff touches a path matched by `Owns-Paths` or `Watch-Paths`, that memory doc must be reviewed in Phase 8.
- Affected `CURRENT` docs must be downgraded to `SUSPECT` until semantic review is complete.
- Only after semantic review against final code, `STATE.md`, and `DECISIONS.md` may a `SUSPECT` doc return to `CURRENT`.
- If changed code paths have no matching owning `domain` doc, Phase 8 must either create a new domain memory doc or record an explicit uncovered-path follow-up.

Sharding rules:

- The memory model supports recursive splits such as `BACKEND.md` -> `BACKEND-api.md`, `BACKEND-db.md`, `BACKEND-jobs.md`.
- After a split, the parent doc becomes a summary/router and must not duplicate the full child content.
- Split a memory doc when it covers mostly independent modules, broad invalidation keeps making it too noisy, or retrieval materially improves with narrower child docs.

## Workflow Profiles

New runs should declare:

- `Workflow version: recursive-mode-audit-v2`

Compatibility aliases:

- `recursive-mode-audit-v1` for the earlier strict-audit profile
- `memory-phase8` for the earlier phase8-aware workflow
- legacy runs with no late-phase marker

`recursive-mode-audit-v2` is the current stable profile. It keeps the audited-phase contract from v1 and adds a lossless Phase 1/Phase 2 handoff:

- Phase 1 must include `## Source Requirement Inventory`
- Phase 2 must include `## Requirement Mapping`
- Phase 2 must include `## Plan Drift Check`
- Phase 2 `## Requirement Completion Status` uses planning dispositions such as `planned`, `planned-via-merge`, and `planned-indirectly`

`recursive-mode-audit-v1` remains supported for backward compatibility, but it does not require the stricter source-inventory and Phase 2 guardrail sections.

## Recursive phases

Recursive phases are stage-gated. The next phase uses the previous phase's output as input.

## Mandatory audit loop for audited phases

The following are audited phases:

- Phase 1 — AS-IS
- Phase 1.5 — Root Cause (when present)
- Phase 2 — TO-BE plan
- Phase 3 — Implementation summary
- Phase 3.5 — Code review (when present)
- Phase 4 — Test summary
- Phase 6 — Decisions update
- Phase 7 — State update
- Phase 8 — Memory impact

For every audited phase in `recursive-mode-audit-v1` and `recursive-mode-audit-v2`, the phase contract is:

1. Draft or revise the phase artifact.
2. Re-read the effective upstream artifacts.
3. Reconcile against the diff basis recorded in `00-worktree.md`.
4. Run the phase audit.
5. If gaps or drift remain, stay in the current phase.
6. Repair the work.
7. Re-run the audit.
8. Only after `Audit: PASS` may `Coverage: PASS` and `Approval: PASS`.
9. Only then may the artifact lock.

Mandatory audit recording for every audited phase:

- `Audit Execution Mode: subagent` or `Audit Execution Mode: self-audit`
- `Subagent Availability: available` or `Subagent Availability: unavailable`
- `Subagent Capability Probe:` with the concrete capability check or environmental fact used
- `Delegation Decision Basis:` explaining why delegation was or was not used
- `Delegation Override Reason:` required when `Subagent Availability: available` but `Audit Execution Mode: self-audit`
- `Audit Inputs Provided:` with the exact artifact paths, diff basis, changed files, and code references used

Every audited phase must also record:

- `## Subagent Contribution Verification`
- `## Requirement Completion Status`

When delegated work materially contributes, `## Subagent Contribution Verification` must record:

- `Reviewed Action Records:`
- `Main-Agent Verification Performed:`
- `Acceptance Decision: accepted|partially accepted|rejected`
- `Refresh Handling:`
- `Repair Performed After Verification:`

Controller verification references must be real. `Main-Agent Verification Performed` should cite existing files, diff-owned paths, bundles, or recursive artifacts actually checked by the controller, and any paths cited in `Repair Performed After Verification` should also resolve.

If subagents are available and the full context bundle can be assembled, delegated audit/review is the default path.
If the controller keeps `Audit Execution Mode: self-audit` despite available subagents, it must record `Delegation Override Reason` with the concrete reason the controller chose not to delegate.
If subagents are unavailable, the main agent must perform the same audit itself. Audit rigor is not optional.

## Canonical delegated review bundle

Delegated review and audit should use a canonical review bundle stored under:

- `/.recursive/run/<run-id>/evidence/review-bundles/`

Use `recursive-review-bundle` when possible to package the handoff. A valid bundle must include:

- phase name and artifact path
- artifact content hash
- reviewer role
- upstream artifacts to reread
- relevant addenda
- relevant prior recursive evidence
- relevant control-plane docs when needed
- normalized diff basis from `00-worktree.md`
- changed file list
- targeted code references
- evidence references
- phase-specific audit questions
- required output shape

For Phase 3.5, the phase artifact should record `Review Bundle Path` in `## Review Metadata`.
If repairs materially change the reviewed scope, refresh the bundle before re-audit.
`recursive-review-bundle` auto-discovers relevant addenda by default. Do not silently omit them from delegated review context.
The written Phase 3.5 review must cite the bundle path plus bundle-grounded upstream artifacts, relevant addenda, and changed files or code references in the review narrative, not only in metadata boilerplate.

## Canonical router policy for delegated model calls

Canonical routing files live under:

- `/.recursive/config/recursive-router.json`
- `/.recursive/config/recursive-router-discovered.json`

When the controller or any recursive subskill is about to call another model or external CLI for delegated audit, review, bounded implementation, or other routed subagent work, it must re-read the routing policy and discovery inventory from disk immediately before choosing the CLI/model.

Do not rely on stale chat context, earlier prompt text, or previously remembered route selections when these files may have changed during the run.

If routed delegation has been requested or the current task is already operating under routed policy, prefer the canonical `recursive-router` resolve/invoke path over hardcoded provider or model strings.

An active configured external route is policy, not a hint. When the selected role resolves to `external-cli`, the controller must dispatch through the canonical resolve/invoke path before claiming that delegated role was satisfied. Do not substitute local implementation, testing, review, or audit work just because the local path is faster or the change seems narrow.

If the effective route is unresolved, blocked, or falls back to `self-audit` or local execution, record that outcome explicitly in the phase artifact or subagent action record instead of silently bypassing routing.

When running from an isolated worktree, the routing policy and discovery inventory must be present and current in that worktree before route resolution. Discovery inventory is local and may be untracked, so refresh it with the router probe or copy the intended inventory from the controller/source repo before invoking a routed role.

The orchestrator may reject routed output after checking it against actual files, actual diffs, and actual recursive artifacts, then repair locally. If that happens, record the routed rejection and the concrete local repair; do not present the repair as evidence that the routed role performed or verified the work.

If `recursive-router-invoke` returns `success: false`, records a nonzero `exit_code`, or returns findings that the bounded routed role is responsible for fixing, the attempt is not acceptable phase evidence. Preserve routed output, stdout/stderr captures, and invocation metadata under `/.recursive/run/<run-id>/evidence/router/`, record a failed action record or phase note, instruct the routed role to fix the concrete issue when that role has bounded ownership, rerun the routed invocation, and repeat controller verification. If the route cannot produce an acceptable zero-exit result, record the fallback before relying on local repair or self-audit evidence.

When routed delegation is used, the relevant phase artifact, review bundle, or action record should cite:

- `Routing Config Path`
- `Routing Discovery Path`
- `Routed CLI`
- `Routed Model`

## Canonical subagent action records

Any meaningful subagent invocation must leave a durable action record under:

- `/.recursive/run/<run-id>/subagents/`

Routed assistant output, raw transcripts, stdout/stderr captures, and invocation metadata are evidence, not action records. Store them under the run evidence tree, preferably `/.recursive/run/<run-id>/evidence/router/`, and cite them from the generated action record. Initial prompt bundles are dispatch inputs for a concrete run; keep them under a run-scoped prompt-bundle location such as `/.recursive/run/<run-id>/router-prompts/` and cite them as `Prompt Bundle Path`. Do not bootstrap top-level `/.recursive/router-prompts/` in reusable repos. Do not place raw transcript Markdown files directly in `subagents/`; the run linter treats every Markdown file in that directory as a canonical subagent action record.

The action record is the canonical claim record for what the subagent says it did. The main agent must verify that record against the actual worktree diff, the actual files, the review bundle when present, and the relevant recursive artifacts before accepting the result.

Each action record must include:

- metadata (`Subagent ID`, `Run ID`, `Phase`, `Purpose`, `Execution Mode`, `Timestamp`)
- inputs provided (`Current Artifact`, `Upstream Artifacts`, `Addenda`, `Review Bundle`, `Diff Basis`, `Code Refs`, `Memory Refs`, `Audit / Task Questions`)
- claimed actions taken
- claimed file impact (`Created`, `Modified`, `Reviewed`, `Relevant but Untouched`)
- claimed artifact impact (`Read`, `Updated`, `Evidence Used`)
- claimed findings
- verification handoff

For meaningful delegated work, the action record must not be content-free. A `none everywhere` action record is not sufficient evidence for a passing audited phase.

For delegated review and audit, `Current Artifact` should normally point at the stable artifact the subagent actually reviewed, not a mutable controller-authored phase receipt that will keep changing after the subagent returns. If the referenced artifact changes materially after the subagent worked, refresh the action record before relying on it for lockable evidence.

If a phase materially used subagent work, the phase artifact must cite the reviewed action record paths in `## Subagent Contribution Verification` and must record whether the main agent accepted or rejected each one.

Main-agent verification must be grounded, not ceremonial. For meaningful delegated work, the controller must verify:

- claimed file impact against the actual diff-owned file set
- claimed artifact reads or updates against files that actually exist
- bundle claims against the current review bundle and reviewed artifact hash
- requirement, plan, addenda, and prior recursive docs that materially informed acceptance
- whether repairs after delegated work invalidated stale delegated context and required refresh

If those checks are incomplete, the delegated result must be treated as unaccepted and the phase must fall back to self-audit for lockable completion evidence.

## Skill discovery and capability extension

When a run needs a specialized capability that is not already available, do not improvise blindly. Prefer this escalation order:

1. If the `find-skills` skill is already available, use it first.
2. Otherwise use the Skills CLI directly.
3. If no suitable skill is found, proceed with built-in capability and record that no suitable external skill was available.

Useful Skills CLI commands:

- `npx skills find <query>`
- `npx skills add <package-or-repo>`
- `npx skills add <package-or-repo> --skill <skill-name>`
- `npx skills check`
- `npx skills update`

For discovery and evaluation, prefer skills with:

- meaningful install counts
- reputable publishers or source organizations
- healthy upstream repositories and documentation

If a run materially depends on skill discovery, record the result in Phase 8 under `## Run-Local Skill Usage Capture` and promote only durable, reusable conclusions into `/.recursive/memory/skills/`.

## Reusable-skill repository hygiene

Some repos use recursive-mode to improve a reusable skill, workflow, or template rather than to ship a normal product change. In those repos:

- do not commit current-session run folders under `/.recursive/run/<run-id>/`
- do not commit evidence logs, review bundles, subagent action records, or temp outputs as durable repo state unless they are intentional test fixtures
- do not update `STATE.md`, `DECISIONS.md`, or durable memory docs with session-specific implementation history unless that content is intentionally promoted as generic reusable guidance
- do not elevate environment-specific observations into durable memory without generalizing them first

Before closeout in a reusable-skill repo, run `scripts/check-reusable-repo-hygiene.py` or `scripts/check-reusable-repo-hygiene.ps1` and confirm the shipped repo contains only reusable workflow/skill content, not session residue.
For repo-improvement work in a reusable-skill repo, the task is not complete until the final handoff snapshot is clean:

- no committed run-instance artifacts
- no committed generated local residue such as `__pycache__/` or `*.pyc`
- no disposable validation outputs
- no temp-path residue
- no dirty worktree at handoff time

Use `scripts/check-reusable-repo-hygiene.py --require-clean-git` (or the PowerShell wrapper) as the final cleanliness check before calling the repo handoff-ready.

## Phase definitions

Phase 0 — Worktree Isolation (REQUIRED)
- Input: Git repository state, user preferences
- Output: `/.recursive/run/<run-id>/00-worktree.md`
- **The Iron Law:** NEVER WORK ON MAIN/MASTER BRANCH WITHOUT EXPLICIT CONSENT
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking
- Creates isolated git worktree at `.worktrees/<run-id>/` (or configured location)
- Verifies worktree directory is git-ignored (if project-local)
- Runs project setup (auto-detects: npm install, cargo build, pip install, etc.)
- Verifies clean test baseline (all tests passing before changes)
- Records reusable diff basis metadata for later audits:
  - baseline type
  - baseline reference
  - comparison reference
  - normalized baseline
  - normalized comparison
  - normalized diff command
  - any non-default basis notes
- `recursive-init` should prefill a safe default diff basis from the current `HEAD` commit when possible so Phase 0 starts from executable metadata instead of placeholders
- If Phase 0 changes the chosen baseline later, it must update the entire diff-basis block together and re-run lint before locking
- Must be LOCKED before Phase 1 can begin
- **All subsequent phases execute in worktree context**

Phase 0 — Requirements (user-created first)
- Input: chat discussion outside the repo documents
- Output: `/.recursive/run/<run-id>/00-requirements.md`
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking

Phase 1 — AS-IS analysis
- Input: `00-requirements.md` (plus addenda)
- Output: `01-as-is.md`
- Audit must reread earlier relevant run docs when they matter to the same subsystem, workflow, or architecture area
- Audit must record which upstream artifacts and prior recursive evidence were reread
- In `recursive-mode-audit-v2`, Phase 1 must include `## Source Requirement Inventory` so each source obligation is indexed with a source quote, normalized summary, and disposition before Phase 2 planning begins
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking

Phase 1.5 — Root Cause Analysis (Debug Mode, optional)
- Input: `01-as-is.md` (plus addenda)
- Output: `01.5-root-cause.md`
- **Use when:** Requirement involves debugging a bug, test failure, or unexpected behavior
- **The Iron Law:** NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
- Audit must confirm the root cause, not just the symptom, and must fail if the fix strategy is still guesswork
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking
- Must be LOCKED before Phase 2 when present

Phase 2 — TO-BE plan (ExecPlan-grade)
- Input: `01-as-is.md` (plus addenda) and by reference `00-requirements.md`
- If Phase 1.5 exists: also input `01.5-root-cause.md` (plus addenda)
- Output: `02-to-be-plan.md`
- Audit must fail unless:
  - every in-scope `R#` is planned in `recursive-mode-audit-v1`
  - every Phase 1 source-inventory item is accounted for in `recursive-mode-audit-v2`
  - targeted files/modules are concrete
  - tests and QA coverage are concrete
  - expected change surface is concrete enough for later diff reconciliation
- In `recursive-mode-audit-v2`, Phase 2 must include `## Requirement Mapping`, `## Plan Drift Check`, and plan-stage `## Requirement Completion Status`
- In `recursive-mode-audit-v2`, vague umbrella restatements are invalid unless `## Requirement Mapping` explicitly records the covered source-inventory items and any merge rationale
- Phase 2 owns planning completeness plus the expected product/worktree change surface only; later `/.recursive/DECISIONS.md`, `/.recursive/STATE.md`, and `/.recursive/memory/**` churn must not retroactively invalidate a locked Phase 2 artifact
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking

Phase 3 — Implementation (TDD discipline)
- Input: `02-to-be-plan.md` (plus addenda)
- Output: `03-implementation-summary.md`
- **The Iron Law:** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
- Must declare `TDD Mode: strict|pragmatic` in the TDD Compliance Log
- Strict mode is the default and requires explicit RED and GREEN evidence paths under `/.recursive/run/<run-id>/evidence/`
- Pragmatic mode is allowed only with an explicit exception rationale plus compensating validation evidence
- Must include TDD Compliance Log documenting RED-GREEN-REFACTOR cycles or the explicit pragmatic exception
- All requirements must have tests written before implementation
- Audit must reconcile:
  - `00-requirements.md`
  - `02-to-be-plan.md`
  - actual product/worktree changed files vs claimed scope
  - required implementation and test evidence
- Phase 3 owns drift reconciliation for product/worktree paths; downstream addenda may compensate for upstream plan gaps without editing locked history
- Subagents may assist with bounded, disjoint implementation sub-phases, but the controller remains responsible for the audit loop
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items for each sub-phase
- **TODO Enforcement:** ALL TODO items must be checked off before locking

Phase 3.5 — Code Review (optional but fully audited when present)
- Input: `02-to-be-plan.md` and `03-implementation-summary.md`
- Output: `03.5-code-review.md`
- **Use when:** High-risk changes, complex sub-phases, or extra confidence needed
- Delegated review is valid only with the full context bundle
- Before delegated dispatch, re-read `/.recursive/config/recursive-router.json` and `/.recursive/config/recursive-router-discovered.json` as required by `## Canonical router policy for delegated model calls`
- Prefer a canonical review bundle under `/.recursive/run/<run-id>/evidence/review-bundles/` and record its path in the phase artifact
- `## Changed Files Reviewed` must not be empty, and `## Targeted Code References` should overlap the changed-file scope being reviewed
- Audit must explicitly review requirements, plan alignment, product/worktree diff ownership, code quality, test adequacy, and TDD compliance
- If blocking issues remain, this phase must FAIL and send the run back to Phase 3 repair
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking
- Must be LOCKED before Phase 4 if present

Phase 4 - Tests and validation
- Input: `02-to-be-plan.md`, `03-implementation-summary.md`, and `03.5-code-review.md` when present
- Output: `04-test-summary.md`
- Use `recursive-closeout` as the standard starting scaffold for Phase 4 so the required sections, header fields, and effective-input lists are populated before authoring the final receipt
- Before running tests, perform a pre-test implementation audit against requirements, plan, current product/worktree diff ownership, changed files, and required test files/commands
- If the pre-test audit finds unfinished in-scope work, return to Phase 3 repair before relying on test results
- Test execution may be parallelized only inside the active phase and only after the pre-test audit is complete
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking

Phase 5 — Manual QA
- Input: QA scenarios defined in `02-to-be-plan.md` (plus addenda) and the implemented system
- Output: `05-manual-qa.md` (completed with observed results and the declared QA execution mode)
- Use `recursive-closeout` as the standard starting scaffold for Phase 5; when a preview-server log is available, capture the actual served URL from that log instead of copying the requested port blindly
- Must declare `QA Execution Mode: human|agent-operated|hybrid`
- Human mode requires user sign-off
- Agent-operated mode requires execution record, tools used, and evidence paths, but not human sign-off
- Hybrid mode requires both execution record/evidence and user sign-off
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking
- **Special:** A user-facing PAUSE is required only for human or hybrid QA execution

Phase 6 — Global DECISIONS update
- Input: `05-manual-qa.md`, all prior run artifacts (including addenda), current `/.recursive/DECISIONS.md`, and the validated repo state
- Output: update/append `/.recursive/DECISIONS.md` with a new run entry that references the run folder docs
- Output: `06-decisions-update.md` as a compact delta receipt documenting the exact changes made
- Use `recursive-closeout` as the standard starting scaffold for this late receipt so the delta-oriented structure is present before authoring details
- Audit must verify the ledger matches the run folder, reviewed final product/worktree paths, `/.recursive/DECISIONS.md`, and validated outcomes
- The receipt should point to the final ledger entry and summarize only the delta; do not restate large sections of `DECISIONS.md`

Phase 7 — Global STATE update
- Input: `06-decisions-update.md`, the run's DECISIONS entry, current `/.recursive/STATE.md`, and the validated repo state
- Output: update `/.recursive/STATE.md` to reflect the current state after the change
- Output: `07-state-update.md` as a compact delta receipt documenting the exact changes made
- Use `recursive-closeout` as the standard starting scaffold for this late receipt so header inputs/outputs and audited sections stay aligned with tooling
- Audit must verify `STATE.md` reflects what is true now in the codebase implied by the reviewed final product/worktree paths plus `/.recursive/STATE.md`
- The receipt should summarize the delta and reference the final state doc rather than duplicating it

Phase 8 — Memory maintenance and impact review
- Input: final validated run artifacts, updated `/.recursive/DECISIONS.md`, updated `/.recursive/STATE.md`, `/.recursive/memory/MEMORY.md`, and affected memory docs
- Output: updated docs under `/.recursive/memory/*`
- Output: `08-memory-impact.md` as a compact delta receipt documenting freshness review, status changes, uncovered paths, and any new/split/deprecated memory docs
- Use `recursive-closeout` as the standard starting scaffold for this late receipt so memory-closeout sections start from a lint-aligned structure instead of hand-built markdown
- Audit must verify memory updates and status transitions against reviewed final product/worktree paths, touched memory docs, prior memory truth, `STATE.md`, and `DECISIONS.md`
- Must include `## Run-Local Skill Usage Capture` with concrete availability / attempted / used / worked-well / issue / recommendation fields whenever skill usage is relevant to the run
- Must include `## Skill Memory Promotion Review` explaining what durable lessons were promoted, what stayed run-local, and why
- **TODO Requirement:** Phase artifact MUST include `## TODO` section with checkable items
- **TODO Enforcement:** ALL TODO items must be checked off before locking
- **Completion rule:** the run is not fully complete before Phase 8 passes
- The receipt should summarize the changed memory docs and outcomes, not restate full memory documents

## Recursive prompt contract (how users should invoke phases)

Recursive prompts must be concise and path-based. A good prompt:
- names the phase,
- names the input file path(s),
- names the required output file path(s),
- instructs the agent to enforce Audit, Coverage, and Approval gates when applicable,
- avoids pasting substantive content.

Example prompt pattern:

"Run Recursive Phase 2. Input: `/.recursive/run/<run-id>/01-as-is.md` (and addenda). Output: `/.recursive/run/<run-id>/02-to-be-plan.md` as an ExecPlan per `/.recursive/RECURSIVE.md`. Enforce the audit loop plus Coverage and Approval gates. Do not paste requirements into the prompt; only reference repo files."

## Required structure for every recursive-mode phase artifact (headers + gates)

Every per-run recursive-mode artifact (`00-requirements.md` through `08-memory-impact.md`, plus any addendum files) must begin with a short header and must end with Coverage and Approval gates.

For audited phases in `recursive-mode-audit-v1` and `recursive-mode-audit-v2`, the artifact must also contain explicit audit sections before Coverage and Approval, including:

- `## Audit Context`
- `## Effective Inputs Re-read`
- `## Earlier Phase Reconciliation`
- `## Subagent Contribution Verification`
- `## Worktree Diff Audit`
- `## Gaps Found`
- `## Repair Work Performed`
- `## Requirement Completion Status`
- `## Audit Verdict`

The following phases must also include `## Prior Recursive Evidence Reviewed`:

- Phase 1
- Phase 2
- Phase 4
- Phase 7
- Phase 8

Additional v2-only required sections:

- Phase 1 must include `## Source Requirement Inventory`
- Phase 2 must include `## Requirement Mapping`
- Phase 2 must include `## Plan Drift Check`

### Required header fields (top of file)

Each artifact must start with the following fields in plain markdown:

- Run: `/.recursive/run/<run-id>/`
- Phase: `01 AS-IS` (or the relevant phase number/name)
- Status: `DRAFT` or `LOCKED`
- Inputs: list repo-relative paths read to produce this artifact (include addenda when applicable)
- Outputs: list repo-relative paths written by this phase (usually this file, sometimes additional files)
- Scope note: one short paragraph stating what this artifact is intended to decide/enable

Example header:

Run: `/.recursive/run/<run-id>/`
Phase: `02 TO-BE plan`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/01-as-is.md`
- `/.recursive/run/<run-id>/addenda/01-as-is.addendum-01.md`
Outputs:
- `/.recursive/run/<run-id>/02-to-be-plan.md`
Scope note: This document defines the planned changes and how to validate them.

When Status is `LOCKED`, append these fields to the header:

- LockedAt: ISO8601 timestamp
- LockHash: SHA-256 of normalized artifact content at lock time (LF newlines; `LockHash:` line removed)

### Required audit fields for audited phases

Inside `## Audit Context`, record:

- `Audit Execution Mode: subagent` or `Audit Execution Mode: self-audit`
- `Subagent Availability: available` or `Subagent Availability: unavailable`
- `Subagent Capability Probe:`
- `Delegation Decision Basis:`
- `Delegation Override Reason:` when available subagents were not used
- `Audit Inputs Provided:` followed by explicit artifact paths, diff basis, changed files, and targeted code references

Inside `## Worktree Diff Audit`, record at minimum:

- `Baseline type:`
- `Baseline reference:`
- `Comparison reference:`
- `Normalized baseline:`
- `Normalized comparison:`
- `Normalized diff command:`
- `Planned or claimed changed files:`
- `Actual changed files reviewed:`
- `Unexplained drift:`

`00-worktree.md` is the source of truth for diff basis. `Baseline reference` records the human-facing source ref chosen in Phase 0. `Normalized baseline` records the exact commit that later audits execute against. `Comparison reference` records the intended comparison target, and `Normalized diff command` is the executable command string derived from those values.

`recursive-init` should prefill these fields from the current `HEAD` commit when possible, but Phase 0 remains responsible for correcting them if the real worktree context differs. Tooling must fail in Phase 0, not guess later, when the baseline type, references, or normalized command are missing, ambiguous, or inconsistent.

Inside `## Requirement Completion Status`, list every in-scope requirement or source-inventory ID using machine-checkable bullets such as:

- `R1 | Status: implemented | Changed Files: /path/to/file | Implementation Evidence: /path/to/file, /path/to/artifact`
- `R2 | Status: verified | Changed Files: /path/to/file | Implementation Evidence: /path/to/file | Verification Evidence: /path/to/test-summary.md`
- `R3 | Status: deferred | Rationale: [why] | Deferred By: /.recursive/run/<run-id>/addenda/...`
- `R4 | Status: out-of-scope | Rationale: [why] | Scope Decision: /.recursive/run/<run-id>/addenda/...`
- `R5 | Status: blocked | Rationale: [why] | Blocking Evidence: /path/to/log, /path/to/artifact`
- `R6 | Status: superseded by approved addendum | Addendum: /.recursive/run/<run-id>/addenda/...`

In `recursive-mode-audit-v2` Phase 2, use planning dispositions instead of implementation dispositions:

- `R1 | Status: planned | Implementation Surface: /path/to/file | Verification Surface: /path/to/test-or-artifact | QA Surface: /path/to/manual-qa-or-scenario`
- `SRC-001 | Status: planned-via-merge | Implementation Surface: /path/to/file | Verification Surface: /path/to/test-or-artifact | QA Surface: not-applicable-with-rationale | Rationale: [why the merge is lossless]`
- `SRC-002 | Status: planned-indirectly | Implementation Surface: /path/to/file | Verification Surface: /path/to/test-or-artifact | QA Surface: not-applicable-with-rationale | Rationale: [why the obligation is satisfied indirectly]`

Mentioning an `R#` only in Traceability is never sufficient for completion proof.

Status expectations:

- `implemented` requires `Changed Files` plus concrete implementation evidence paths.
- `verified` requires `Changed Files`, concrete implementation evidence, and concrete verification evidence.
- `deferred`, `out-of-scope`, and `superseded by approved addendum` require explicit approved rationale/decision references.
- `blocked` requires concrete blocking evidence, not only narrative prose.
- Requirement entries must not mix contradictory fields from other statuses.
- In product/worktree-diff phases, the requirement dispositions should collectively account for the diff-owned changed files rather than leaving changed implementation files unclaimed by any `R#`.
- Final closeout artifacts must not leave in-scope requirements at `implemented` or `blocked`.

### Phase-scoped diff ownership

The `## Worktree Diff Audit` section is phase-scoped, not a permanent promise that every earlier artifact must explain the repository's eventual end-state diff forever.

- Phase 2 owns planning completeness plus the expected product/worktree change surface.
- Phase 3, Phase 3.5, and Phase 4 own the actual product/worktree diff and must reconcile implementation drift there.
- Phase 6 owns `/.recursive/DECISIONS.md` plus the reviewed final product/worktree paths.
- Phase 7 owns `/.recursive/STATE.md` plus the reviewed final product/worktree paths.
- Phase 8 owns `/.recursive/memory/**` plus the reviewed final product/worktree paths.
- Late control-plane or memory churn must not retroactively invalidate an earlier locked planning artifact.
- If later phases discover a real upstream gap, record it via a current-phase upstream-gap addendum and compensate downstream instead of editing locked history.

### Required gate sections (end of file)

Every artifact must end with these two sections:

#### Coverage Gate

State whether the artifact covers everything relevant in the phase input docs. Coverage must be proven mechanically via requirement IDs:

- Phase 0 Requirements establishes stable requirement IDs (R1, R2, …) and Out of Scope IDs (OOS1, OOS2, …).
- Downstream artifacts must map each requirement ID to where it is addressed in that artifact and/or where evidence exists.
- If a requirement is intentionally deferred, say so explicitly and record the rationale.

The Coverage Gate must conclude with one of:

- Coverage: PASS
- Coverage: FAIL (and list what is missing and how it will be added before proceeding)

For audited phases:

- `Coverage: PASS` is invalid unless `Audit: PASS`.
- If any in-scope `R#` is unmapped, Coverage must be `FAIL`.
- If upstream reconciliation is incomplete, Coverage must be `FAIL`.

#### Approval Gate

State whether the artifact is ready to proceed to the next phase. The Approval Gate must be objective wherever possible (repro is unambiguous, plan includes runnable commands, tests pass, etc.).

Manual QA is the exception to purely document-driven progression, but the required sign-off depends on `QA Execution Mode`. Human and hybrid runs require explicit user sign-off. Agent-operated runs require explicit execution metadata and evidence instead.

The Approval Gate must conclude with one of:

- Approval: PASS
- Approval: FAIL (and list what must change before proceeding)

For audited phases:

- `Approval: PASS` is invalid unless `Audit: PASS`.
- Approval must be `FAIL` if unresolved in-scope gaps remain.
- Approval must be `FAIL` if unexplained diff drift remains.
- Approval must be `FAIL` if a required audit section is missing.

## Locking and immutability (phase advancement rules)

Recursive phases are one-way. Iteration is allowed within a phase, but after a phase advances, earlier artifacts must not be edited.

### DRAFT vs LOCKED

- While a phase is in progress, its output artifact status is `DRAFT`. The agent may revise it until both gates pass.
- When both gates pass, the agent must lock the artifact with `scripts/recursive-lock.py` or `scripts/recursive-lock.ps1`. The lock command is the primary supported path and must:
  1) verify the artifact is lockable,
  2) set Status to `LOCKED`,
  3) set `LockedAt`,
  4) compute `LockHash` (SHA-256),
  5) then allow the run to proceed to the next phase.

After an artifact is `LOCKED`, it must not be edited. If something is later discovered to be missing or wrong, use an addendum in the current phase (see Addenda policy).

### No backtracking rule

If the agent is in Phase N, it must not modify artifacts from Phase < N. If a Phase < N artifact is incomplete or incorrect, the agent must record the gap via a current-phase upstream-gap addendum and proceed forward without editing the locked earlier artifact.

### How to compute LockHash

When locking an artifact, compute the SHA-256 hash from a **normalized** representation of the
artifact text to avoid self-referential hashes and platform-specific newline differences.

**Canonical rule (this repo):** `LockHash` is the SHA-256 of the artifact content after:
1) normalizing newlines to `\n` (LF), and
2) removing the `LockHash:` line entirely (including its trailing newline, if present).

This makes `LockHash` stable across Windows/macOS/Linux and avoids the paradox of hashing a file
that contains its own hash.

#### Preferred: use the lock command

Use `scripts/recursive-lock.py` (cross-platform) or `scripts/recursive-lock.ps1` (PowerShell) to lock a draft artifact. Those commands validate lockability, write `Status: LOCKED`, write `LockedAt`, and compute `LockHash` using the canonical normalization rules.

#### Secondary: verify an existing lock

Use `scripts/verify-locks.py` (cross-platform) or `scripts/verify-locks.ps1` (PowerShell) to verify and (optionally) fix mismatched hashes on already locked artifacts.

#### Manual computation examples

**Bash (GNU coreutils):**

    sed '/^LockHash:/d' /.recursive/run/<run-id>/01-as-is.md | tr -d '\r' | sha256sum

**PowerShell (Windows PowerShell 5.1 / PowerShell 7+):**

    $p = "/.recursive/run/<run-id>/01-as-is.md"
    $t = Get-Content -LiteralPath $p -Raw -Encoding UTF8
    $n = ($t -replace "`r`n","`n") -replace "(?m)^LockHash:.*(?:`n|$)",""
    $b = [System.Text.Encoding]::UTF8.GetBytes($n)
    $h = [System.Security.Cryptography.SHA256]::Create().ComputeHash($b)
    ($h | ForEach-Object { $_.ToString("x2") }) -join ""

Record the resulting 64-character lowercase hex digest as `LockHash`.

## Addenda (mandatory)

Addenda are used to preserve immutability while allowing discovery, and to ensure "effective input" is not lost to context rot.

All addenda live under:

`/.recursive/run/<run-id>/addenda/`

### Stage-local addenda (same stage)

Stage-local addenda supplement a stage artifact without requiring destructive edits.

Naming:

- `<base-filename>.addendum-01.md`
- `<base-filename>.addendum-02.md`
- ... and so on

Examples:

- `01-as-is.addendum-01.md`
- `02-to-be-plan.addendum-01.md`

### Upstream-gap addenda (current stage records a gap in a locked earlier stage)

If, in Phase N, the agent discovers missing or incorrect information in a LOCKED Phase < N artifact, the agent must not edit the earlier artifact. Instead it must create a current-phase upstream-gap addendum.

Naming:

`<current-base>.upstream-gap.<prior-base>.addendum-01.md`

Examples (while in Phase 4, discovering a gap in Phase 2):

- `04-test-summary.upstream-gap.02-to-be-plan.addendum-01.md`

The upstream-gap addendum must:
- state the gap,
- explain how it was discovered (evidence),
- state the implications for the current and later phases,
- state how the current phase compensates (tests added, plan deviation recorded, etc.).

### Mandatory "effective input" read rule

When a phase declares an input artifact (for example `01-as-is.md`), the agent must treat the effective input as:

- the base file, plus
- all matching stage-local addenda in lexical order, plus
- any current-phase upstream-gap addenda that compensate for locked-history gaps relevant to that phase.

The agent must explicitly list all input addenda in the output artifact's header under Inputs.
If relevant addenda exist, the phase artifact must also re-read them in `## Effective Inputs Re-read` and reconcile them in `## Earlier Phase Reconciliation`.

### Meaningful diff only

Diff audit is about meaningful repository changes, not incidental runtime debris.
Transient byproducts such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/` are excluded from diff-audit enforcement unless the repository intentionally tracks them.

### Addenda locking

Addenda follow the same DRAFT/LOCKED rule:
- If an addendum is created during an active phase, it is `DRAFT` until the phase locks.
- When the phase locks, any stage-local addenda and upstream-gap addenda created in that phase must be locked as well.

## Requirement IDs and traceability (mandatory for Coverage Gate)

Recursive coverage must be mechanical. The Phase 0 requirements document must define stable IDs and acceptance criteria.

### Requirements document requirements (Phase 0)

`00-requirements.md` must include:

- Requirement IDs: R1, R2, …
- Out of Scope IDs: OOS1, OOS2, …
- Observable acceptance criteria for each R# (what a human can do/see)
- Constraints (if any) that are non-negotiable

### Downstream traceability rule

Every downstream artifact must include a short "Traceability" section that maps each R# to where it is addressed and what evidence exists.

- In analysis and plan phases, evidence may be code pointers, planned tests, and described verification steps.
- In implementation and validation phases, evidence should be concrete: file paths, diffs, logs, test results, and runtime observations.
- Vague statements such as "all requirements covered" are invalid unless each in-scope `R#` is mapped explicitly.

If a requirement is deferred, it must be explicitly marked as deferred with rationale and its impact on acceptance.

For `recursive-mode-audit-v1`, audited phases must also record:

- which upstream artifacts were re-read
- which prior recursive run docs were reviewed when relevant
- how current claims reconcile with the actual diff basis

## Formatting exception for Manual QA

This document prefers prose-first writing and discourages tables. Manual QA is the exception.

The Phase 5 Manual QA artifact (`05-manual-qa.md`) may use a compact table to present scenarios, expected outcomes, and observed outcomes if it materially improves clarity. Keep it small and focused.

## Minimum content expectations by recursive-mode phase

These are minimum expectations. Each artifact must still include the required header and gate sections.

Phase 0 — `00-requirements.md` (user-created first)
- Stable requirement IDs (R1…)
- Out of scope IDs (OOS1…)
- Acceptance criteria per R#
- Constraints and assumptions
- Traceability is not required here, but must be enabled by the IDs

Phase 1 — `01-as-is.md`
- Repro steps (novice-runnable)
- Current behavior description tied to requirement IDs
- Relevant code pointers by full path (files, functions/modules)
- Known unknowns (explicit)
- Evidence snippets where possible (logs, screenshots described, etc.)

Phase 2 — `02-to-be-plan.md` (ExecPlan-grade)
- Must comply with all ExecPlan requirements in this file
- Must include:
  - concrete edits by file path and location
  - commands to run
  - tests to add/run
  - manual QA scenarios
  - idempotence/recovery guidance
- Must include traceability mapping R# -> planned change + validation

Phase 6 — `06-decisions-update.md`
- Exact `DECISIONS.md` edits made for the run
- Rationale for any ledger structural changes
- Traceability back to the validated run artifacts

Phase 7 — `07-state-update.md`
- Exact `STATE.md` edits made for the run
- Current-state truths updated to match the validated implementation
- Rationale for any major interpretation changes

Phase 8 — `08-memory-impact.md`
- Final diff basis and changed-path analysis
- Affected memory docs and temporary/final statuses
- Explicit handling for uncovered changed paths
- Router/parent refresh notes when memory splits or summaries changed

## Large requirements: Implementation sub-phases (required when scope is large or risky)

Some requirements are too large or risky to implement safely as a single "Phase 3 then Phase 5" blob. In these cases, the work must be decomposed into ordered sub-phases. Each sub-phase has its own implementation steps, an implementation checklist, and an explicit set of tests that must be run and pass before proceeding.

This is not a new top-level recursive-mode phase. Sub-phases are a required structure inside Phase 2 planning and Phase 3/5 execution.

### When sub-phases are mandatory

Use sub-phases when any of the following are true:

- The change touches multiple subsystems (UI + state + persistence + backend, etc.).
- The change is expected to take more than one focused development session.
- The risk of regressions is non-trivial (touches critical flows, input handling, playback, persistence, auth, payments, etc.).
- The requirement includes multiple user-visible behaviors that can be delivered incrementally.

If sub-phases are not used for a large change, the Phase 2 Approval Gate must be FAIL unless the plan explicitly justifies why a single pass is safe.

### Where sub-phases live (Phase 2: `02-to-be-plan.md`)

When sub-phases are used, `02-to-be-plan.md` must include a section titled:

"Implementation Sub-phases"

Under it, define sub-phases as `SP1`, `SP2`, … in order. Each sub-phase must include:

1) Scope and purpose
- A short paragraph describing what will exist at the end of the sub-phase that does not exist before.
- Explicit mapping to requirement IDs (R#) covered by this sub-phase.

2) Implementation checklist (mandatory)
- A checkbox list of concrete edits/steps. This is allowed even if other narrative sections remain prose-first.
- Checklist items must name file paths and functions/modules where applicable.

3) Tests for this sub-phase (mandatory)
- A concrete list of tests to run before the sub-phase is considered complete.
- Include exact commands (repo-specific).
- Include Playwright scope rules:
  - Prefer a fast Tier A run for the sub-phase (new/changed tests + `@smoke` if applicable).
  - Specify any tags to use (e.g., `@recursive:<run-id>`, `@smoke`).
- State pass criteria (what "green" means).

4) Sub-phase acceptance (mandatory)
- Observable behavior a human can verify for this increment (even if the requirement is not fully complete yet).
- Any temporary limitations or feature flags must be stated explicitly.

5) Rollback / recovery notes (when relevant)
- If the sub-phase can leave the repo in a partially migrated state, describe how to recover.

Phase 2 Approval Gate must be FAIL unless sub-phases (when required) include checklists and test commands as described above.

### Execution rule (Phase 3 + Phase 4 are performed per sub-phase)

When implementing a plan with sub-phases, the agent must execute sub-phases sequentially:

For each sub-phase SPk:

1) Implement SPk according to the plan checklist.
2) Run the SPk test set exactly as specified in the plan.
3) If any SPk tests fail:
   - Do not proceed to the next sub-phase.
   - Iterate on implementation (and tests, if the plan requires test additions) until SPk tests pass.
4) Only after SPk tests pass may the agent proceed to SP(k+1).

This rule is non-negotiable. The agent must not "finish implementation first and test later" when sub-phases are defined.

### How to record progress and evidence (Phase 3 and Phase 4 artifacts)

Phase 3 output (`03-implementation-summary.md`) must include a section:

"Sub-phase Implementation Summary"

For each SPk, record:
- files touched (paths),
- key behavior changes,
- any deviations from the Phase 2 plan (with rationale and evidence pointers).

Phase 4 output (`04-test-summary.md`) must be organized by sub-phase when sub-phases exist:

- SP1: commands executed + results + artifact paths
- SP2: commands executed + results + artifact paths
- …

The Phase 4 Approval Gate must be FAIL unless every sub-phase's required tests have been executed and are passing (or an explicit decision with mitigation is recorded, and the requirement's constraints allow it).

### Plan amendments during implementation (without editing locked Phase 2)

Phase 2 artifacts are locked before Phase 3 begins. If, during Phase 3/5, the agent discovers that the locked plan is missing steps, missing tests, incorrect assumptions, or requires sequencing changes, the agent must not edit the locked `02-to-be-plan.md`.

Instead, the agent must create a current-phase upstream-gap addendum that functions as a "plan amendment" for the remaining work.

- Addendum location: `/.recursive/run/<run-id>/addenda/`
- Naming (examples):
  - `03-implementation-summary.upstream-gap.02-to-be-plan.addendum-01.md`
  - `04-test-summary.upstream-gap.02-to-be-plan.addendum-01.md`

Each plan-amendment addendum must:
- state what in the plan was missing/incorrect,
- provide evidence for why the amendment is needed,
- specify the amended steps/tests for the remaining sub-phases,
- state the impact on traceability (which R# are affected),
- and be treated as part of the effective plan input for the remainder of the run.

When plan amendments exist, subsequent sub-phases must follow the effective plan (base plan + relevant amendment addenda).

## Playwright tagging for recursive-mode runs and implementation sub-phases (required)

When recursive-mode uses implementation sub-phases (SP1, SP2, …), Playwright tests must be taggable so the agent can run fast, targeted Tier A validations per sub-phase and broader Tier B regressions at appropriate points.

### Required tags

All Playwright tests added or modified as part of a recursive-mode run must include the run tag:

- `@recursive:<run-id>`

When sub-phases exist, tests must also be tagged with the sub-phase tag:

- `@sp1`, `@sp2`, … corresponding to the sub-phase that introduced or modified the test

If the repository maintains a smoke tier, critical-path guardrail tests must also be tagged:

- `@smoke`

These tags may be applied at the `test.describe()` level or on individual tests, but they must be queryable via Playwright's `--grep` or equivalent mechanism used by the repository.

### Tagging examples (informative)

A test introduced in SP2 of run `01-example` should be discoverable by grepping for:

- `@recursive:01-example` and `@sp2`

A smoke guardrail test relevant to the run should be discoverable by:

- `@smoke` (and optionally also `@recursive:<run-id>` if it was changed in the run)

### Tier A / Tier B command requirements (must be specified in the plan)

When sub-phases exist, the TO-BE plan (`02-to-be-plan.md`) must specify Playwright commands for:

Tier A (per sub-phase, fast loop)

- Run the tests introduced/modified in the current sub-phase:
  - `@recursive:<run-id>` + `@spK`
- Plus any required smoke guardrails for affected flows:
  - `@smoke` (optionally scoped further if the repo supports it)

Tier B (broader regression)

- Run all tests for the run:
  - `@recursive:<run-id>` (all sub-phases)
- Optionally run the full suite, or all `@smoke`, or broader tags as required by constraints.

The plan must record the exact repo-specific commands (package manager, scripts, env vars) rather than generic placeholders.

### Execution rule (non-negotiable)

For each sub-phase SPk:

- The agent must run Tier A for SPk and require it to be green before starting SP(k+1).
- If Tier A fails, fix and rerun until green. Do not proceed.
- Tier B must be run before locking Phase 4 unless an explicit constraint in `00-requirements.md` allows a narrower run.

### Test summary rule (Phase 4)

When sub-phases exist, the test summary (`04-test-summary.md`) must record Playwright results by sub-phase:

- SPk Tier A command(s) + results + artifact paths
- Any Tier B run(s) + results + artifact paths

If a failure is flaky, the summary must record the rerun commands and outcomes, and the mitigation applied.

## Playwright test placement and naming conventions (required)

To keep recursive-mode runs discoverable, reviewable, and fast to validate per sub-phase, Playwright tests must follow a consistent placement and naming convention.

### Respect existing repository conventions first (non-negotiable)

Before creating new Playwright tests or moving existing ones, the agent must determine the repository's current Playwright layout by inspecting:

- Playwright config (e.g., `playwright.config.ts` / `.js`) for `testDir`, and
- package scripts that run Playwright (e.g., `package.json` scripts).

If the repo already has an established Playwright test directory and naming pattern, new tests must follow it. Do not introduce a second Playwright test tree.

If the repository does not have an established Playwright test directory, the agent may create one, but must record the decision and rationale in the Decision Log and keep the structure minimal.

### Standard test directory selection rule

When the repository already has a Playwright `testDir`, use it as the canonical location for new tests.

If `testDir` is not set and no obvious convention exists, use one of the following defaults (in this priority order), choosing the first that matches existing patterns in the repo:

1) `tests/e2e/`
2) `e2e/`
3) `playwright/tests/`

The Phase 2 plan must record the chosen directory path(s) explicitly.

### File naming (required)

Each new Playwright test file added for a recursive-mode run must include the run id and the sub-phase, and should be readable in file listings without opening the file.

Required format (kebab-case, TypeScript example):

- `recursive-<run-id>.sp<k>.<short-topic>.spec.ts`

Examples:

- `recursive-01-keyboard-controls-in-deck-settings.sp1.shortcut-discovery.spec.ts`
- `recursive-01-keyboard-controls-in-deck-settings.sp2.persistence-guardrail.spec.ts`

If the repo uses a different extension or suffix (e.g., `.test.ts`), match the repo convention, but keep the `recursive-<run-id>.sp<k>.` prefix.

### Test title and tag placement (required)

Tests must include tags in a way that is grep-able via the repo's chosen Playwright filtering mechanism (typically `--grep`).

Preferred pattern (apply tags at the `test.describe()` level):

- `test.describe('@recursive:<run-id> @sp<k> <topic>', () => { ... })`

If a test is part of a smoke tier, include `@smoke` in the same describe title:

- `test.describe('@smoke @recursive:<run-id> @sp<k> <topic>', () => { ... })`

Do not rely on brittle text selectors in tests. Prefer stable selectors (`data-testid` or equivalent). If the repo does not use stable selectors today, the plan may introduce `data-testid` additions as part of the requirement, and must record them as part of the implementation checklist.

### Requirement traceability inside tests (required)

At the top of each new Playwright test file, include a short comment block that ties the test back to the requirement IDs it covers.

Example:

- `// recursive run: <run-id>`
- `// Sub-phase: SP<k>`
- `// Covers: R1, R3`
- `// Guardrails: (if any) R2 (non-regression)`

This comment is not a substitute for the Traceability section in the recursive-mode artifacts, but it makes tests easier to audit during review.

### Fixtures and test data placement (recommended; required if new fixtures are added)

If tests require fixtures, seed data, or static assets, prefer colocating them under a dedicated folder near the test directory to avoid scattering run-specific artifacts across the repo.

Recommended pattern (adapt to repo conventions):

- `<playwright-test-dir>/fixtures/recursive/<run-id>/...`

If the repo already has a fixtures convention, follow it. Any new fixtures directories must be recorded in the Phase 2 plan and listed in Phase 4's touched files.

### Tier A discovery rule (required)

Tier A for a sub-phase must be able to target the sub-phase tests without manual selection. Therefore, either:

- tags must be present and filterable (preferred), or
- the plan must specify an equivalent deterministic selection mechanism used by the repo.

If the repo's Playwright setup cannot reliably filter by tags, the Phase 2 plan must define an alternative (for example, file glob patterns that correspond to `recursive-<run-id>.sp<k>.*`), and must use that alternative consistently throughout Phase 3/5 execution and reporting.


### Testing discipline (TDD + Playwright) - Phase 2 (TO-BE plan) must include a "Testing Strategy" section that specifies:

- New behavior tests to add (required for features).
- Regression-first tests that fail on current behavior (required for bug fixes).
- Non-regression guardrail tests for adjacent critical behavior (required whenever existing flows may be impacted).
- Exact test file paths and exact commands to run.
- Expected pass criteria.

Phase 3 — `03-implementation-summary.md`
- Files touched (repo-relative paths)
- What changed and why
- Traceability mapping R# -> implementation evidence

### Testing discipline (TDD + Playwright) - Phase 3 (Implementation) must begin with tests-first:

- Bug fixes: add a failing regression test first, then implement until it passes.
- Features: add tests for the new behavior first (may fail initially), then implement until they pass.

Phase 4 - `04-test-summary.md`
- Tests executed (commands)
- Results (pass/fail) with concise evidence
- If any required test is failing, the phase must not advance until fixed or explicitly decided with rationale and mitigation recorded

### Testing discipline (Playwright + validation) - Phase 4 (Tests/validation) must run:

- Tier A: the new/modified tests for this run plus relevant smoke tests.
- Tier B: the full Playwright suite (or a broader tagged set) before locking the phase, unless an explicit constraint in `00-requirements.md` permits a narrower run.

If Playwright coverage is infeasible or would be flaky for a specific behavior, the plan must explicitly record the exception and mitigation in the Approval Gate (e.g., unit test coverage + manual QA scenario).

### Playwright evidence capture and `04-test-summary.md` standard (required)

Playwright is the primary end-to-end regression safety net in this repository. To prevent regressions and make failures diagnosable, recursive-mode must standardize what is recorded in the Phase 4 artifact (`04-test-summary.md`) and how Playwright evidence is captured.

This section defines requirements for:

- Phase 2: the TO-BE plan must specify Playwright tests, tags, and how to run them.
- Phase 4: the test summary must capture exact commands, results, and where to find debugging artifacts.

#### Phase 2 requirements (plan must define this up front)

The ExecPlan-grade TO-BE plan (`02-to-be-plan.md`) must include a "Playwright Plan" subsection that specifies:

1) Which Playwright tests will be added or modified (file paths) and the intent of each test.
2) Tagging strategy for this run:
   - Tests added for the run must be tagged with `@recursive:<run-id>`.
   - If the repository uses a smoke tier, critical-path tests must also be tagged `@smoke`.
3) Exact commands to run Tier A (fast loop) and Tier B (broader regression), as they apply to this repo's toolchain.
4) How the app is started for E2E (or how requests are stubbed):
   - If a dev server is required, specify the exact start command, base URL, and readiness condition.
   - If stubbing network calls is required, specify what is stubbed and why.
5) Selector strategy: E2E tests must target stable selectors (prefer `data-testid` or equivalent), not brittle text selectors, unless explicitly justified.

The Phase 2 Approval Gate must be FAIL if the plan does not specify the above items with concrete, repo-specific details.

#### Phase 4 output requirements (`04-test-summary.md` must include these sections)

The Phase 4 artifact (`04-test-summary.md`) must be self-sufficient for diagnosing failures. It must contain the following sections in order.

1) Pre-test implementation audit

Before any test commands are executed, audit implementation correctness against intent:

- Compare `03-implementation-summary.md` against `00-requirements.md` and record per-requirement status (implemented / partial / missing) with evidence links.
- Compare `03-implementation-summary.md` against `02-to-be-plan.md` and record per step/sub-phase status (implemented / deviated / missing) with evidence links.
- For each mismatch, record remediation:
  - immediate fix in current phase, or
  - upstream-gap/stage-local addendum path with follow-up action.

2) Environment

Record enough environment detail to reproduce:

- Repo root (path) and run id
- Platform (OS) and Node/runtime version
- Playwright version
- Browser projects executed (e.g., chromium/firefox/webkit) and whether headed/headless
- Base URL used (if applicable)

3) Commands executed (exact)

List the exact commands actually executed (copy/paste exact shell lines), including:

- Any build commands
- Any dev server start command (and whether it ran in a separate terminal/process)
- Tier A Playwright command(s) executed
- Tier B Playwright command(s) executed (if required by the run's constraints)

If the repo uses scripts (e.g., `test:e2e`), record the script and the underlying Playwright invocation if available.

4) Results summary

Provide a compact pass/fail summary:

- Total tests run, passed, failed, skipped
- If failures occurred: list failing test titles and file paths
- Whether failures are deterministic or flaky (based on reruns described below)

5) Debugging artifacts (mandatory to locate)

The summary must state exactly where artifacts were written in this repo and how to open them.

At minimum, record paths for:

- Playwright HTML report directory (e.g., `playwright-report/`)
- Test results directory (e.g., `test-results/`)
- Trace files (if generated)
- Screenshots (if generated)
- Videos (if generated)

If the repository uses a custom Playwright config, explicitly cite the config file path that defines these output locations (e.g., `playwright.config.ts`).

6) Failure diagnosis notes (required when failures exist)

For each failing test:

- Failure symptom in one sentence (what did not happen)
- Primary suspected root cause (if known)
- The most relevant artifact to inspect (report/trace/screenshot/video path)
- Any immediate remediation step taken

7) Rerun policy and flake handling (required)

To prevent "green by accident," Phase 4 must follow this policy:

- On any Playwright failure, rerun the failing test(s) in isolation at least once.
- If the failure disappears on rerun, treat it as a potential flake and record:
  - how it was rerun,
  - whether it reproduced,
  - and what mitigation was applied (e.g., improved selector, proper waiting condition, deterministic state setup).

Do not mark Approval PASS if there are unresolved, newly introduced flakes without an explicit decision and mitigation.

#### Evidence capture policy (how Playwright should be configured/used for recursive-mode)

Playwright evidence must be sufficient to debug without guesswork.

- Prefer to have traces available for failures. If traces are not always-on, ensure they are captured on the first retry for failures (or equivalent policy supported by the repo).
- Screenshots on failure are strongly recommended.
- Videos on failure are recommended for interaction-heavy flows.

Standardize where evidence lives (per run):

- Store non-Markdown evidence artifacts under `/.recursive/run/<run-id>/evidence/`:
  - `evidence/screenshots/`
  - `evidence/logs/`
  - `evidence/perf/`
  - `evidence/traces/` (if applicable)
- Phase 4 and Phase 5 artifacts must reference concrete repo-relative paths under `evidence/`.
- If the repo generates artifacts elsewhere (e.g., Playwright `test-results/`), either configure output to point at the run folder (preferred) or copy/link the relevant files into the run's `evidence/` directory.

If the repo's Playwright configuration does not currently produce these artifacts, the plan may introduce minimal, non-invasive configuration changes to enable them (without changing product behavior). Such changes must be recorded in the Decision Log and reflected in the test summary.

#### Phase 4 Approval Gate requirements

Phase 4 Approval must be FAIL unless:

- The tests specified in the plan for Tier A have been run and are passing, or failures have been resolved.
- Any required Tier B run (as specified in the plan or constraints) has been completed and is passing, or an explicit decision with mitigation is recorded.
- The test summary contains the required sections above and points to concrete artifact paths for any failures that occurred during the phase.

Phase 5 — `05-manual-qa.md`
- Manual QA scenarios (from plan) and observed results
- `QA Execution Mode: human|agent-operated|hybrid`
- Human/hybrid: explicit user sign-off (name/handle + date + notes)
- Agent-operated/hybrid: execution record, tools used, and evidence paths
- If the selected mode's required approvals are not yet complete, iterate within this phase until complete or record an explicit abort decision

Phase 6 — update `/.recursive/DECISIONS.md`
- Append a new entry referencing:
  - the run folder path
  - all run artifacts (including addenda)
  - what changed (user-visible behavior)
  - why (tradeoffs)
  - how (high-level approach)
  - what was not done (OOS)
  - known issues / follow-ups
- Record the exact ledger changes in `06-decisions-update.md`

Phase 7 — update `/.recursive/STATE.md`
- Update current-state documentation to reflect the new reality:
  - features and flags/config
  - known limitations
  - operational notes
- Record the exact state changes in `07-state-update.md`

Phase 8 — update `/.recursive/memory/*`
- Compute final changed paths from the Phase 0 diff basis
- Match changed paths to memory owners/watchers
- Downgrade affected `CURRENT` docs to `SUSPECT` before semantic review
- Update/create/split/deprecate memory docs as needed
- Refresh parent/router docs when child docs changed materially
- Record uncovered changed paths explicitly
- Lock `08-memory-impact.md`
- Do not treat the run as complete before this phase passes

---

## Recursive worktree isolation (Phase 0)

### The Iron Law

```
NEVER WORK ON MAIN/MASTER BRANCH WITHOUT EXPLICIT CONSENT
```

### Why Isolation Matters

Working directly on main/master branch:
- Pollutes production history with WIP commits
- Prevents parallel requirement development
- Makes it harder to discard abandoned work
- Increases risk of accidental production changes

Git worktrees provide isolated workspaces that:
- Share the same repository (no duplicate clones)
- Allow parallel development on multiple requirements
- Keep main branch clean and linear
- Enable easy discard of abandoned work

### Directory Selection Priority

1. **Check existing directories** (priority order):
   - `.worktrees/` (preferred - hidden)
   - `worktrees/` (alternative)

2. **Check CLAUDE.md** for explicit preference

3. **Ask user** if no convention exists
   - Default: `.worktrees/` (project-local)
   - Alternative: `~/.config/recursive-mode/worktrees/<project>/` (global)

### Safety Verification

**MUST verify directory is git-ignored before creating project-local worktree:**

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

If NOT ignored:
1. Add to `.gitignore`: `.worktrees/`
2. Commit the change
3. Then create worktree

**Why critical:** Prevents committing worktree contents to repository.

### Worktree Creation Process

```bash
# Detect project name
project=$(basename "$(git rev-parse --show-toplevel)")
branch_name="recursive/${run_id}"

# Check current branch
current_branch=$(git branch --show-current)

if [ "$current_branch" = "main" ] || [ "$current_branch" = "master" ]; then
    # Require explicit consent or auto-create worktree
    echo "WARNING: On $current_branch branch. Creating worktree..."
fi

# Create worktree with new branch
git worktree add "$path" -b "$branch_name"
cd "$path"
```

### Main Branch Protection

When user invokes from main/master:

```
╔════════════════════════════════════════════════════════════╗
║  !   MAIN BRANCH PROTECTION                                ║
╠════════════════════════════════════════════════════════════╣
║  You are currently on the main/master branch.              ║
║                                                            ║
║  recursive-mode requires isolated worktrees to:          ║
║  • Prevent accidental commits to production               ║
║  • Enable parallel requirement development                ║
║  • Maintain clean main branch history                     ║
║                                                            ║
║  Default: Create worktree automatically                    ║
║  (press Ctrl+C to abort)                                   ║
╚════════════════════════════════════════════════════════════╝
```

### Project Setup Auto-Detection

After creating worktree, auto-detect and run setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi

# Java/Maven
if [ -f pom.xml ]; then mvn compile -q; fi

# Java/Gradle
if [ -f build.gradle ]; then ./gradlew compileJava --quiet; fi

# .NET
if [ -f *.csproj ]; then dotnet restore; fi
```

### Clean Test Baseline

Verify worktree starts with passing tests:

```bash
# Run appropriate test command
npm test        # Node.js
cargo test      # Rust
pytest -q       # Python
go test ./...   # Go
mvn test -q     # Maven
./gradlew test  # Gradle
dotnet test     # .NET
```

**If tests fail:**
- Document pre-existing failures in Phase 0 artifact
- Get explicit consent to proceed
- Or fix baseline issues first

### Worktree Context for All Phases

Once Phase 0 is complete:
- All subsequent phases execute in worktree directory
- Git operations target feature branch (`recursive/<run-id>`)
- Main branch remains untouched
- Development is fully isolated

### Windows path guidance for Node/Vite/Vitest

On Windows, prefer running Node-based toolchains from the real worktree path, not from:

- `subst` drive mappings
- Explorer-mapped drive letters
- ad hoc path aliases that rewrite the worktree root

This is especially important for:

- `vite`
- `vitest`
- Playwright helpers that resolve repo-relative assets

Short aliases may still be fine for manual file browsing or editing, but command execution and recorded evidence should use the real filesystem path so module resolution and evidence paths stay stable.

### Merging Completed Work

After Phase 8:
1. User reviews changes in worktree
2. User merges feature branch to main:
   ```bash
   git checkout main
   git merge recursive/<run-id>
   ```
3. Global artifacts (DECISIONS.md, STATE.md) are part of the merge
4. Worktree can be removed when no longer needed:
   ```bash
   git worktree remove .worktrees/<run-id>
   ```

---

## recursive-tdd (Phase 3)

### The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

### RED-GREEN-REFACTOR Cycle (Mandatory)

Phase 3 must declare `TDD Mode: strict|pragmatic`.

- `strict` is the default and requires actual failing-test evidence before implementation plus passing-test evidence after implementation.
- `pragmatic` is allowed only when the artifact records a concrete exception reason and compensating validation evidence.

Every requirement implemented in strict Phase 3 must follow RED-GREEN-REFACTOR discipline:

#### RED Phase
1. Write one minimal test showing what should happen
2. Run test, verify it fails for expected reason
3. Document failure output in Phase 3 artifact
4. **Never skip:** If test passes immediately, the test is wrong - fix it

#### GREEN Phase
1. Write simplest code to pass the test
2. Run test, verify it passes
3. No additional features, no "while I'm here" improvements
4. Document minimal implementation in Phase 3 artifact

#### REFACTOR Phase
1. Clean up: remove duplication, improve names, extract helpers
2. Keep tests green throughout
3. Never add behavior during refactor
4. Document cleanups in Phase 3 artifact

### Common Process Shortcuts (STOP)

| Excuse | Reality |
|--------|---------|
| "This is just a simple fix" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after confirming it works" | Tests passing immediately prove nothing. |
| "Tests after achieve same goals" | Tests-after = "what does this do?" Tests-first = "what should this do?" |
| "Deleting working code is wasteful" | Sunk cost fallacy. Keeping unverified code is technical debt. |
| "TDD is dogmatic, I'm being pragmatic" | TDD IS pragmatic. Finds bugs before commit. |

### TDD Compliance Log (Required in Phase 3 Artifact)

Every Phase 3 artifact must include:

```markdown
## TDD Compliance Log

TDD Mode: strict

RED Evidence:
- `/.recursive/run/<run-id>/evidence/logs/red/<file>.log`

GREEN Evidence:
- `/.recursive/run/<run-id>/evidence/logs/green/<file>.log`

### R1: [requirement description]

**Test:** `path/to/test.spec.ts` - "[test name]"

**RED Phase** ([ISO8601]):
- Command: [exact command]
- Expected failure: [what should fail]
- Actual failure: [paste output]
- RED verified: ✅

**GREEN Phase** ([ISO8601]):
- Implementation: [minimal change]
- Command: [exact command]
- Result: PASS
- GREEN verified: ✅

**REFACTOR Phase** ([ISO8601]):
- Cleanups: [description]
- All tests passing: ✅
```

If `TDD Mode: pragmatic` is used, the artifact must also contain:

```markdown
## Pragmatic TDD Exception

Exception reason: [why strict RED-first flow was not feasible here]
Compensating validation:
- [what was done instead]
- `/.recursive/run/<run-id>/evidence/<supporting-file>`
```

### Red Flags - DELETE CODE and Start Over

- Code written before test
- Test passes immediately (not testing what you think)
- "I'll add tests later"
- "This is too simple to test"

---

## recursive-debugging (Phase 1.5)

### When to Use Phase 1.5

**Mandatory when:**
- Requirement is a bug fix
- Investigating test failures
- Unexpected behavior reported
- Performance problems
- Integration issues

**Insert between Phase 1 and Phase 2:**
```
Phase 1 (AS-IS) -> Phase 1.5 (Root Cause) -> Phase 2 (TO-BE Plan)
```

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

### Four Phases of Systematic Debugging

#### Step 1: Root Cause Investigation
1. **Read Error Messages Carefully** - verbatim errors, stack traces, line numbers
2. **Reproduce Consistently** - exact steps, frequency, determinism
3. **Check Recent Changes** - git history, dependencies, environment
4. **Gather Evidence** - multi-layer diagnostics if applicable
5. **Trace Data Flow** - backward from error to source

#### Step 2: Pattern Analysis
- Find working examples in codebase
- Compare working vs broken
- Identify all differences
- Understand dependencies

#### Step 3: Hypothesis and Testing
- Form single, clear hypothesis
- Test with minimal change
- Verify before continuing
- If wrong, form NEW hypothesis (don't add more changes)

#### Step 4: Fix Summary for Phase 2 Planning
- Document confirmed root cause
- Define minimal fix strategy
- Create failing test case
- Handoff to Phase 2 for planning

### Common Process Shortcuts (STOP)

| Excuse | Reality |
|--------|---------|
| "I can see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "Quick fix first, investigate later" | "Later" never happens. Do it right from the start. |
| "Emergency, no time for process" | Systematic debugging is FASTER than thrashing. |
| "One fix attempt is enough" | First attempts often fail. The process anticipates iteration. |

### If 3+ Fix Attempts Failed

**STOP - Question Architecture:**
- Pattern indicating architectural problem
- Discuss with human partner
- Consider refactor vs. symptom fix
- Document in Phase 1.5 artifact

---

## Recursive Lock Verification

### The Lock Contract

Every locked artifact includes:
- `Status: LOCKED`
- `LockedAt: ISO8601 timestamp`
- `LockHash: SHA-256 hash of normalized artifact content (LF newlines; `LockHash:` line removed)`

### LockHash Computation

The LockHash is a SHA-256 hash of the normalized artifact content at lock time. See
"How to compute LockHash" above for the canonical normalization rules.

**Preferred:**
- use `scripts/verify-locks.py` for cross-platform verification (and optional fixing)
- use `scripts/verify-locks.ps1` when running in PowerShell environments

**PowerShell:**
```powershell
$p = "artifact.md"
$t = Get-Content -LiteralPath $p -Raw -Encoding UTF8
$n = ($t -replace "`r`n","`n") -replace "(?m)^LockHash:.*(?:`n|$)",""
$b = [System.Text.Encoding]::UTF8.GetBytes($n)
$h = [System.Security.Cryptography.SHA256]::Create().ComputeHash($b)
($h | ForEach-Object { $_.ToString("x2") }) -join ""
```

**Shell:**
```bash
sed '/^LockHash:/d' artifact.md | tr -d '\r' | sha256sum
```

### Lock Validity Rules

A phase artifact is **lock-valid** only when ALL of the following are true:

1. **File exists** at specified path
2. **Status is LOCKED** (not DRAFT)
3. **LockedAt is present** and is valid ISO8601 timestamp
4. **LockHash is present** and is 64-character hex string
5. **LockHash matches** SHA-256 of normalized artifact content (LF newlines; `LockHash:` line removed)
6. **If the artifact is an audited phase in `recursive-mode-audit-v1`, Audit Gate ends with:** `Audit: PASS`
7. **Coverage Gate ends with:** `Coverage: PASS`
8. **Approval Gate ends with:** `Approval: PASS`

### Automated Verification

Use the provided verifier scripts to verify all locks:

```bash
# Verify specific run
python ./.agents/skills/recursive-mode/scripts/verify-locks.py --run-id "<run-id>"

# Scan all runs
python ./.agents/skills/recursive-mode/scripts/verify-locks.py

# Fix incorrect hashes (use with caution)
python ./.agents/skills/recursive-mode/scripts/verify-locks.py --run-id "<run-id>" --fix
```

```powershell
# Verify specific run
.\.agents\skills\recursive-mode\scripts\verify-locks.ps1 -RunId "<run-id>"

# Scan all runs
.\.agents\skills\recursive-mode\scripts\verify-locks.ps1

# Fix incorrect hashes (use with caution)
.\.agents\skills\recursive-mode\scripts\verify-locks.ps1 -RunId "<run-id>" -Fix
```

### Tampering Detection

If LockHash doesn't match the canonical normalized content:

1. **File was modified after locking** (tampering)
2. **File encoding changed** (e.g., BOM added/removed)
3. **Line endings changed** (CRLF vs LF)

**Action:**
- If accidental: Use `verify-locks.py --fix` (or `verify-locks.ps1 -Fix`) to update hash
- If intentional modification: This is an anti-pattern. Use addenda instead.

### Phase Transition Lock Chain

Before starting Phase N, verify lock chain for all prior phases:

```
Phase 0 (Requirements) -> Phase 0 (Worktree) -> Phase 1 (AS-IS) -> ...
     LOCKED?               LOCKED?                  LOCKED?
```

**Hard stop:** Do NOT proceed if any prior phase is not lock-valid.

### Lock Chain Validation in Single-Command Mode

When user invokes "Implement requirement 'run-id'":

1. Scan all phases (0 through 6)
2. Check each locked artifact's hash
3. Identify earliest non-lock-valid phase
4. Resume from that phase

Example output:
```
Phase 0 Requirements: ✅ LOCKED (valid hash)
Phase 0 Worktree: ✅ LOCKED (valid hash)
Phase 1: ❌ DRAFT (incomplete)
Phase 1-5: ⏳ PENDING

Resuming Phase 2...
```

---

## recursive-mode skill priority

When a requirement involves multiple concerns, use this priority order to determine which skills/phases to apply first:

### Priority Order

| Priority | Concern | Action | Skill |
|----------|---------|--------|-------|
| 1 | **Debugging** (bug fixes) | Run Phase 1.5 Root Cause Analysis first | `recursive-debugging` |
| 2 | **Design** (new features) | Run full Phase 1 AS-IS Analysis | Core workflow |
| 3 | **Implementation** | Proceed to Phase 2+ after analysis complete | Core workflow |
| 4 | **Testing** | Use TDD discipline in Phase 3 | `recursive-tdd` |
| 5 | **Review** | Run Phase 3.5 Code Review before Phase 4 | `recursive-subagent` (optional) |

### Decision Rules

**Rule 1: Debugging First**
When requirement mentions bug, crash, test failure, or unexpected behavior:
- MUST run Phase 1.5 before Phase 2
- Root cause analysis is prerequisite to planning
- Exception: None. Never plan a fix without understanding root cause.

**Rule 2: Design Before Implementation**
When requirement is a new feature or enhancement:
- MUST complete Phase 1 (AS-IS) before Phase 2
- Understanding current state is prerequisite to defining future state
- Exception: None. Never plan changes without knowing current state.

**Rule 3: Testing During Implementation**
For all implementation work:
- MUST use TDD discipline (RED-GREEN-REFACTOR)
- Tests validate implementation against requirements
- Exception: None. The Iron Law has no exceptions.

**Rule 4: Review Before Final Validation**
After implementation but before final testing:
- Optional Phase 3.5 Code Review
- Catch issues early, before manual QA
- Exception: User can skip, but must document decision

### Examples

Notation:
- `0R` = Phase 0 Requirements (`00-requirements.md`)
- `0W` = Phase 0 Worktree Isolation (`00-worktree.md`)
- `3.5?` = optional Phase 3.5 Code Review (`03.5-code-review.md`)

| Requirement | Type | Phase Sequence |
|-------------|------|----------------|
| "Fix login crash" | Bug fix | 0R -> 0W -> 1 -> 1.5 -> 2 -> 3 -> 3.5? -> 4 -> 5 -> 6 -> 7 -> 8 |
| "Add dark mode" | Feature | 0R -> 0W -> 1 -> 2 -> 3 -> 3.5? -> 4 -> 5 -> 6 -> 7 -> 8 |
| "API returns wrong data" | Bug fix | 0R -> 0W -> 1 -> 1.5 -> 2 -> 3 -> 3.5? -> 4 -> 5 -> 6 -> 7 -> 8 |
| "Refactor auth module" | Refactoring | 0R -> 0W -> 1 -> 2 -> 3 -> 3.5? -> 4 -> 5 -> 6 -> 7 -> 8 |

---

## recursive-mode hard gates

Hard gates are non-negotiable checkpoints. Violating a hard gate is a process failure.

### What is a Hard Gate?

<HG>
A hard gate is a mandatory condition that MUST be satisfied before proceeding.
Hard gates are marked with <HG> tags and use absolute language:
- "Do NOT proceed until..."
- "MUST be..."
- "Exception: None"
</HG>

### Universal Hard Gates

<HG>
Do NOT proceed to next phase until:
- Current phase artifact is complete
- If the phase is audited, `Audit: PASS`
- Coverage Gate: PASS
- Approval Gate: PASS
- Status: LOCKED with LockedAt and LockHash
</HG>

<HG>
Do NOT edit locked prior-phase artifacts.
If gap discovered, create addendum in current phase.
</HG>

<HG>
Do NOT skip or weaken an audit because subagents are unavailable.
If delegation is unavailable or the context bundle is incomplete:
- record `Audit Execution Mode: self-audit`
- perform the full audit locally
- repair and re-audit before lock
</HG>

<HG>
Do NOT write implementation code before failing test.
If code written before test: DELETE IT. Start over.
</HG>

### HG-0: Phase 0 (Worktree) Hard Gate

<HG>
Do NOT proceed to Phase 1 or 2 until Phase 0 is LOCKED with:
- Isolated worktree created
- Git-ignore verified (if project-local)
- Clean test baseline confirmed
- LockedAt and LockHash populated

**Exception:** None. Phase 0 is REQUIRED.
</HG>

### HG-1: Phase 1 -> 2 Hard Gate

<HG>
Do NOT create 02-to-be-plan.md until 01-as-is.md is LOCKED with:
- Audit: PASS
- Coverage: PASS
- Approval: PASS
- LockedAt and LockHash populated

**Exception:** If Phase 1.5 exists, it must ALSO be locked before Phase 2.
</HG>

### HG-2: Phase 1.5 (Debug Mode) Hard Gate

<HG>
Do NOT create TO-BE plan until root cause analysis is complete:
- Phase 1.5 artifact is LOCKED
- Root cause identified (not just symptom)
- Fix strategy defined
- Audit: PASS
- Coverage: PASS
- Approval: PASS

**Exception:** None. Debug mode requires completion before planning.
</HG>

### HG-3: Phase 3 TDD Hard Gate

<HG>
Do NOT write implementation code until:
- Failing test exists and has been run
- Test failure is documented in Phase 3 artifact TDD Compliance Log
- `TDD Mode` is declared
- In `strict` mode, RED phase is verified with actual test output and referenced RED evidence
- In `pragmatic` mode, the exception and compensating validation are explicitly recorded

**Exception:** `TDD Mode: pragmatic` is allowed only when the artifact explicitly records a concrete exception rationale plus compensating validation evidence.
</HG>

### HG-4: Phase 4 -> 5 Hard Gate

<HG>
Do NOT proceed to Manual QA until:
- Implementation audit is documented in Phase 4 artifact (against `00-requirements.md` and `02-to-be-plan.md`)
- Phase 4 audit verdict is PASS
- All tests from Phase 3 are passing
- TDD Compliance is verified
- Test evidence is documented in Phase 4 artifact
- Phase 4 is LOCKED

**Exception:** None. QA requires complete test evidence.
</HG>

### HG-5: Phase 5 Manual QA Hard Gate

<HG>
Do NOT update DECISIONS.md until:
- `QA Execution Mode` is declared in `05-manual-qa.md`
- 05-manual-qa.md contains observed results for all scenarios
- If mode is `human`, user has explicitly signed off on QA scenarios
- If mode is `agent-operated`, execution record, tools used, and evidence paths are recorded
- If mode is `hybrid`, both the execution record/evidence and user sign-off are recorded
- Approval: PASS is consistent with the declared QA mode
- Phase 5 is LOCKED with LockHash matching content

**Exception:** None. Phase 6 requires QA completion.
</HG>

### HG-6: Phase 6 -> 7 Hard Gate

<HG>
Do NOT update STATE.md until:
- `06-decisions-update.md` is lock-valid
- `/.recursive/DECISIONS.md` has been updated for the run
- the Phase 6 receipt records the exact ledger changes made
- the Phase 6 audit confirms the receipt matches final run reality

**Exception:** None.
</HG>

### HG-7: Phase 7 -> 8 Hard Gate

<HG>
Do NOT begin memory maintenance until:
- `07-state-update.md` is lock-valid
- `/.recursive/STATE.md` has been updated for the run
- `00-worktree.md` records the diff basis for late-phase review
- the Phase 7 audit confirms the state summary matches final code reality

**Exception:** None.
</HG>

### HG-8: Phase 8 Completion Hard Gate

<HG>
Do NOT consider a `recursive-mode-audit-v1` run complete until:
- `08-memory-impact.md` is lock-valid
- affected memory docs were reviewed or explicitly left `SUSPECT` / `STALE`
- uncovered changed paths were handled explicitly
- run-local skill usage was captured and any durable promotion decision was recorded when skill usage was relevant
- Phase 8 ends with `Audit: PASS`

**Exception:** Compatibility profiles may remain complete under their own documented contract.
</HG>

### HG-9: Lock Chain Hard Gate (Universal)

<HG>
Do NOT start Phase N unless ALL prior phases (0 through N-1) are lock-valid:
- Status: LOCKED
- LockedAt: populated
- LockHash: matches SHA-256 of content
- Audited prior phases end with `Audit: PASS`
- Coverage: PASS
- Approval: PASS

**Exception:** None. The lock chain is absolute.
</HG>

### HG-10: Main Branch Protection Hard Gate

<HG>
Do NOT work on main/master branch without:
- Explicit user consent
- Documentation of risks acknowledged
- Recorded reason for exception

**Default behavior:** Create isolated worktree automatically.
</HG>

### HG-11: TODO Completion Hard Gate (Universal)

<HG>
Do NOT lock any phase artifact or proceed to next phase until:
- `## TODO` section exists in current phase artifact
- ALL TODO items are checked off ([x])
- NO unchecked items remain ([ ] or empty boxes)
- No "deferred" or "WIP" items

**Verification:**
1. Search artifact for `[ ]` (unchecked boxes)
2. If found: complete the work OR create addendum
3. Only proceed when ALL boxes are `[x]`

**Exception:** None. Complete all todos before locking.
</HG>

### Hard Gate Violations

If a hard gate is violated:

1. **STOP** immediately
2. **Document** the violation in current phase artifact
3. **Return** to the phase that should have been completed
4. **Complete** that phase properly
5. **Lock** that phase
6. **Resume** from where you should have been

**Never** proceed after a hard gate violation without correcting it.

---

## recursive-mode single-command orchestration ("Implement requirement '<run-id>'")

recursive-mode must be operable via a single short prompt. When the user says:

- Implement requirement '<run-id>'

…the agent must execute the recursive-mode workflow end-to-end by reading repo documents, generating missing phase artifacts, enforcing gates, locking artifacts, updating global documents, and maintaining durable memory, without requiring the user to provide long prompts.

### Accepted invocation forms

The user does not need to use only one exact phrase. Agents should treat the following as valid recursive-mode entry commands when repo docs provide the actual requirements or plan:

- `Implement the run`
- `Implement run 75`
- `Implement requirement '75'`
- `Implement the plan`
- `Create a new run based on the plan`
- `Start a recursive run`

These are commands, not specifications. The agent must still read the repository documents that define the run inputs before proceeding.

### Invocation resolution rules

When the user gives a short invocation command, resolve it like this:

1. If the command includes an explicit run id, use that run id.
2. If the command says `Implement the run` and there is exactly one active or incomplete run under `/.recursive/run/`, use that run.
3. If the command says `Implement the plan`, `Create a new run based on the plan`, or `Start a recursive run`, create a new run only when a unique source plan/requirements artifact can be identified from repo docs or from the immediate task context.
4. If multiple candidate runs exist and no run id is given, stop and ask the user which run to use.
5. If no run exists and no unique source plan/requirements artifact can be identified, stop and ask the user for the plan or requirements path. Do not invent requirements from chat alone.

### Run folder resolution

Given `<run-id>`, the agent must locate the run folder at:

- `/.recursive/run/<run-id>/`

A valid run folder must contain at minimum:

- `/.recursive/run/<run-id>/00-requirements.md`

If the run folder or `00-requirements.md` does not exist, the agent must stop and instruct the user to create it (the agent must not invent requirements).

### Phase auto-resume and phase selection

The single-command orchestrator must be idempotent and resumable. On every invocation of "Implement requirement '<run-id>'" the agent must:

1) Determine the current phase by inspecting which phase outputs exist and whether they are LOCKED.
2) If a phase output exists but is DRAFT (or gates are FAIL), resume that phase and iterate until PASS and then lock.
3) If a phase output does not exist, start that phase by creating its output artifact (and addenda if needed).
4) Never edit artifacts from earlier phases once they are LOCKED. If an earlier phase is missing something, use the Addenda policy (below) to record the gap in the current phase.

The orchestrator proceeds in order:

Phase 1: create/lock `01-as-is.md`  
Phase 2: create/lock `02-to-be-plan.md` (ExecPlan-grade)  
Phase 3: implement and create/lock `03-implementation-summary.md`  
Phase 4: run tests and create/lock `04-test-summary.md`  
Phase 5: create `05-manual-qa.md`, satisfy the selected QA execution mode requirements, and then lock it  
Phase 6: update global `/.recursive/DECISIONS.md` and create/lock `06-decisions-update.md`
Phase 7: update global `/.recursive/STATE.md` and create/lock `07-state-update.md`
Phase 8: update `/.recursive/memory/*` and create/lock `08-memory-impact.md`

### Mandatory "effective input" rule (base + addenda)

Whenever the orchestrator reads a phase input artifact, it must treat the effective input as:

- the base artifact, plus
- all matching stage-local addenda in `/.recursive/run/<run-id>/addenda/` in lexical order, plus
- any current-phase upstream-gap addenda relevant to the locked artifact being compensated.

The orchestrator must list all effective inputs in the header of each output artifact under Inputs.
When relevant addenda exist, the orchestrator must also re-read and reconcile them explicitly in the audited phase body.

### Phase transition hard-stop lock chain (required)

Before the orchestrator starts or resumes Phase `N` (`N >= 3`), it must validate that every required prior phase is lock-valid.

Required prior artifacts by phase:

- Phase 2: `01-as-is.md`
- Phase 2: `02-to-be-plan.md`
- Phase 3: `03-implementation-summary.md`
- Phase 4: `04-test-summary.md`
- Phase 5: `05-manual-qa.md`
- Phase 6: `06-decisions-update.md`
- Phase 7: `07-state-update.md`
- Phase 8: `08-memory-impact.md`

A phase artifact is lock-valid only if all checks pass:

1) The base artifact file exists.
2) The header contains `Status: LOCKED`.
3) The header contains non-empty `LockedAt`.
4) The header contains non-empty `LockHash`.
5) If the artifact is an audited phase in `recursive-mode-audit-v1`, it ends with `Audit: PASS`.
6) The artifact ends with `Coverage: PASS` and `Approval: PASS`.
7) Any stage-local addenda for that phase (`addenda/<base>.addendum-*.md`) also satisfy the same required checks for that phase.

If any lock-valid check fails for a required prior phase:

- Do not create, edit, or lock any later-phase artifact.
- Resume the earliest failing phase and iterate until it is lock-valid.
- Report the blocking file path(s) and failed check(s) in the phase notes/output.

Forbidden phase transitions:

- Do not create `02-to-be-plan.md` unless `01-as-is.md` is lock-valid.
- Do not create `03-implementation-summary.md` unless `02-to-be-plan.md` is lock-valid.
- Do not create `04-test-summary.md` unless `03-implementation-summary.md` is lock-valid.
- Do not create or complete `05-manual-qa.md` unless `04-test-summary.md` is lock-valid.
- Do not start Phase 6 unless `05-manual-qa.md` is lock-valid.
- Do not start Phase 7 unless `06-decisions-update.md` is lock-valid.
- Do not start Phase 8 unless `07-state-update.md` is lock-valid.

This hard-stop chain applies in single-command mode and single-phase mode.

### Strict sequential phase execution (no parallel phase work)

Recursive phase execution is strictly sequential within a run. Parallel phase work is forbidden.

Rules:

1) Exactly one active phase per run at any time.
2) The active phase is the earliest phase whose base artifact is missing or not lock-valid.
3) While the active phase is unresolved, the agent must not create, edit, or lock artifacts for later phases.
4) There must never be more than one phase base artifact in `DRAFT` simultaneously.

If multiple phase artifacts are found in `DRAFT`:

- Treat the earliest `DRAFT` phase as the only active phase.
- Treat later `DRAFT` phase artifacts as invalid parallel prework.
- Do not continue later `DRAFT` artifacts until the active phase becomes lock-valid.
- Once the active phase locks, proceed in sequence and recreate/overwrite invalid later-phase `DRAFT` artifacts only when each phase becomes active.

This rule applies to single-command orchestration and explicit single-phase invocations.

Scoped exception:

- read-only audit/review delegation and independent test execution may happen inside the active phase
- write-capable subagent work is allowed only for explicitly independent sub-phases with disjoint write scopes
- none of these exceptions allow parallel phase advancement or audit-free locking

### Mandatory gates

For each phase artifact created or updated, the orchestrator must enforce:

- Audit Gate: required for audited phases. The artifact must end with `Audit: PASS` or `Audit: FAIL`.
- Coverage Gate: PASS only if the output covers everything relevant in the effective inputs (including addenda), proven via Requirement IDs (R1, R2, …).
- Approval Gate: PASS only if phase readiness criteria are met.

For audited phases:

- run the audit after drafting the phase
- if audit finds gaps or drift, repair inside the same phase
- rerun the audit
- do not allow `Coverage: PASS` or `Approval: PASS` unless `Audit: PASS`

If any required gate is FAIL, the orchestrator must iterate within the same phase until the phase is truly ready, then lock and proceed.

### Manual QA execution modes

Phase 5 must declare `QA Execution Mode: human|agent-operated|hybrid` in `05-manual-qa.md`.

When the orchestrator reaches Phase 5, it must:

1) Ensure the plan's QA scenarios are present (from `02-to-be-plan.md` effective content). If missing, create a Phase 5 upstream-gap addendum and include the missing scenarios in `05-manual-qa.md`.
2) If mode is `human` or `hybrid`, ask the user to execute the relevant QA scenarios and report results.
3) If mode is `agent-operated` or `hybrid`, record the execution agent, tools used, and concrete evidence paths.
4) Stop only when user input is still required for the selected mode.

On the next invocation of "Implement requirement '<run-id>'", if the required QA results or sign-off have been provided, the agent must record them into `05-manual-qa.md`, pass gates, lock Phase 5, and proceed through Phase 6, Phase 7, and Phase 8.

### Locking rules for single-command execution

Within a phase, the agent may iterate on that phase's output artifact and create phase-local addenda. For audited phases, iteration must follow `draft -> audit -> repair -> re-audit`. Once all required gates are PASS for a phase, the agent must set Status to LOCKED and record LockedAt and LockHash.

After locking a phase, the orchestrator must not edit that phase's base artifact or its stage-local addenda.

### Addenda integration for single-command execution

If the orchestrator discovers missing or incorrect information in a LOCKED earlier phase, it must not modify that earlier phase. It must create an upstream-gap addendum in the current phase (as defined in the Addenda section) and proceed forward using the current phase's addendum to compensate.

## recursive-mode operator contract (what the user does)

To start a recursive-mode run:

1) Create `/.recursive/run/<run-id>/00-requirements.md` and ensure it contains requirement IDs (R1, R2, …) and acceptance criteria.
   - New runs should also include `Workflow version: recursive-mode-audit-v2`.
2) Invoke: Implement requirement '<run-id>'

Equivalent short commands are also valid when the repository already contains enough information to resolve the run or source plan:

- `Implement the run`
- `Implement run <run-id>`
- `Implement the plan`
- `Create a new run based on the plan`
- `Start a recursive run`

If the command is ambiguous, the agent should ask for the run id or the repo path of the source plan/requirements artifact.

To continue after Manual QA:

1) Run the requested QA scenarios.
2) Provide results in chat (pass/fail notes per scenario).
3) Invoke again: Implement requirement '<run-id>' and complete through Phase 8.

## Legacy compatibility

Older runs are not blindly retrofitted.

- Runs with `Workflow version: recursive-mode-audit-v1` in `00-requirements.md` use the strict audit-loop workflow and must satisfy the audited-phase rules in this document.
- Runs with `Workflow version: memory-phase8` in `00-requirements.md` are phase8-aware compatibility runs and must complete through `06-decisions-update.md`, `07-state-update.md`, and `08-memory-impact.md`.
- Runs that already contain any of the `06/07/08` receipt artifacts are also treated as phase8-aware runs.
- Runs with no phase8 marker and no late-phase receipts may be treated as legacy runs by tooling and are not required to backfill the new receipt artifacts automatically.
- When a legacy run is explicitly resumed under the new strict workflow, add `Workflow version: recursive-mode-audit-v2` to `00-requirements.md` so tools can enforce the stronger contract.

<!-- RECURSIVE-MODE-SKILL:START -->
## recursive-mode skill integration

The recursive-mode skill operationalizes this document's workflow rules during execution.
Use it for recursive-mode prompts such as Implement requirement 'run-id' and phase-specific commands.
<!-- RECURSIVE-MODE-SKILL:END -->
