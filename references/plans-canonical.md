# plans-canonical bridge

The single canonical workflow specification lives in `/.recursive/RECURSIVE.md`.

This file remains a compatibility locator plus a compact mirror of the hard requirements so older references still point at the right behavior without maintaining a second full workflow spec.

## Current Workflow Profile

New runs should use:

- `Workflow version: recursive-mode-audit-v2`

Compatibility aliases still recognized by tooling:

- `recursive-mode-audit-v1`
- `memory-phase8`
- legacy runs with no late-phase marker

## Workflow Mirror

The current strict workflow requires:

- audited phases use `draft -> audit -> repair -> re-audit -> pass -> lock`
- audited phases are: Phase 1, Phase 1.5 when present, Phase 2, Phase 3, Phase 3.5 when present, Phase 4, Phase 6, Phase 7, and Phase 8
- exactly one active phase may exist in a run at a time; later-phase draft work is invalid while an earlier phase remains unresolved
- subagents are still optional infrastructure, but delegated audit/review is the default inside the active phase when subagents are available and the context bundle is complete; they do not permit parallel phase advancement
- read-only review/audit delegation and independent test execution are allowed only inside the active phase
- write-capable subagent work is allowed only for explicitly independent sub-phases with disjoint write scopes
- meaningful subagent work must leave durable action records under `/.recursive/run/<run-id>/subagents/` and the controller must verify them against actual files and artifacts before acceptance
- reusable skill or workflow repos should keep shipped history clean; do not treat current-session run artifacts as durable repo content unless they are intentional fixtures

## Audit Context Mirror

Every audited phase must record:

- `Audit Execution Mode: subagent` or `Audit Execution Mode: self-audit`
- `Subagent Availability: available` or `Subagent Availability: unavailable`
- `Subagent Capability Probe`
- `Delegation Decision Basis`
- `Delegation Override Reason` when available subagents were not used
- `Audit Inputs Provided:` with exact artifact paths, diff basis, changed files, and targeted code references

Delegation rules:

- self-audit is mandatory when subagents are unavailable
- delegated audit/review is the preferred default when subagents are available and the context bundle is complete
- if available subagents are not used, the artifact should record an explicit `Delegation Override Reason`
- delegated audits are invalid unless the subagent receives the full context bundle
- the required context bundle includes the current phase draft, exact upstream artifacts, relevant addenda, diff basis from `00-worktree.md`, changed file list, targeted code paths, relevant control-plane docs, and phase-specific audit questions
- if the context bundle is incomplete, do not delegate; perform the audit locally and record `Audit Execution Mode: self-audit`
- for Phase 3.5 and similar delegated review work, prefer a canonical review bundle under `/.recursive/run/<run-id>/evidence/review-bundles/` and record `Review Bundle Path` in the phase artifact
- review bundles should auto-include relevant addenda by default, and the written review narrative must cite the bundle path plus bundle-grounded upstream artifacts, addenda, prior recursive evidence, and changed files or code refs
- delegated acceptance must record any repair performed after verification when main-agent checks found issues or stale delegated context
- if a run needs a missing specialized capability, prefer `find-skills` when available; otherwise use the Skills CLI (`npx skills find`, `npx skills add`, `npx skills check`, `npx skills update`) and record the result in Phase 8 when skill usage is relevant

## Audit Evidence Mirror

Every audited artifact must contain, before Coverage and Approval:

- `## Audit Context`
- `## Effective Inputs Re-read`
- `## Earlier Phase Reconciliation`
- `## Subagent Contribution Verification`
- `## Worktree Diff Audit`
- `## Gaps Found`
- `## Repair Work Performed`
- `## Requirement Completion Status`
- `## Audit Verdict`

The following audited phases must also contain `## Prior Recursive Evidence Reviewed`:

- Phase 1
- Phase 2
- Phase 4
- Phase 7
- Phase 8

The artifact must end with:

- `Audit: PASS` or `Audit: FAIL`
- `Coverage: PASS` or `Coverage: FAIL`
- `Approval: PASS` or `Approval: FAIL`

## Reconciliation Mirror

Audited phases must reconcile against:

- `00-requirements.md`
- `00-worktree.md`
- the immediately previous locked phase artifact
- relevant addenda
- relevant sub-phase artifacts where applicable
- any phase-specific earlier artifacts
- relevant prior recursive-mode run docs when they matter to the same subsystem, workflow, or architecture area
- relevant stage-local addenda and current-phase upstream-gap addenda that change the effective input set

Diff reconciliation must reuse the baseline recorded in `00-worktree.md`, including:

- baseline type
- baseline reference
- comparison reference
- normalized baseline
- normalized comparison
- normalized diff command

Audited phases that rely on implementation reality must explicitly compare:

- planned or claimed changed files
- actual changed files reviewed
- claimed completion vs actual code and tests
- unexplained drift or omissions

No audited phase may pass or lock if upstream reconciliation is incomplete, in-scope gaps remain, or unexplained diff drift remains.

Phase-scoped diff ownership:

- Phase 2 owns the planned product/worktree surface, not the eventual full repo diff forever.
- Phase 3, Phase 3.5, and Phase 4 own actual product/worktree drift reconciliation.
- Phase 6 owns `/.recursive/DECISIONS.md` plus reviewed final product/worktree paths.
- Phase 7 owns `/.recursive/STATE.md` plus reviewed final product/worktree paths.
- Phase 8 owns `/.recursive/memory/**` plus reviewed final product/worktree paths.
- Later control-plane or memory churn must not retroactively invalidate earlier locked planning artifacts.
- If a locked earlier phase omitted something material, the owning downstream phase must compensate via its artifact or addenda instead of rewriting locked history.
- Effective inputs are base artifact plus relevant addenda; downstream audited phases must list, re-read, and reconcile them explicitly.
- Diff audit excludes incidental runtime byproducts such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/` unless the repo intentionally tracks them.
- Requirement completion is not proven by Traceability alone. Audited phases must include machine-checkable `Requirement Completion Status` entries for every in-scope requirement or Phase 1 source-inventory ID.
- `implemented` and `verified` requirement dispositions must cite concrete `Changed Files`; `verified` also requires distinct verification evidence.
- Prior recursive evidence must cite actual run or memory paths, or explicitly state that none is relevant with justification.

## Phase-Specific Audit Mirror

Phase 2 must fail unless:

- every in-scope `R#` is planned in v1, and every Phase 1 source-inventory item is accounted for in v2
- targeted files/modules are concrete enough for later comparison
- tests and QA coverage are concrete
- expected change surface is concrete enough for later diff reconciliation
- v2 plans include `## Requirement Mapping`, `## Plan Drift Check`, and plan-stage `## Requirement Completion Status`

Phase 3 must audit implementation claims against:

- `00-requirements.md`
- `02-to-be-plan.md`
- current diff and actual changed files
- required implementation and test evidence
- declared `TDD Mode: strict|pragmatic`
- strict-mode RED and GREEN evidence paths under `/.recursive/run/<run-id>/evidence/logs/`
- pragmatic-mode exception rationale plus compensating validation evidence when strict mode is not used

Phase 3.5, when present, must explicitly review:

- implementation vs requirements
- implementation vs plan
- git diff vs claimed scope
- code quality and maintainability
- test adequacy and TDD compliance
- the review bundle path and bundle contents when delegation is used

Phase 4 must perform a pre-test implementation audit and fail back to Phase 3 repair if unfinished in-scope work remains.

Phase 5 must declare `QA Execution Mode: human|agent-operated|hybrid` and satisfy the matching requirements:

- `human`: observed results plus explicit user sign-off
- `agent-operated`: observed results plus execution record, tools used, and evidence paths
- `hybrid`: both execution evidence and explicit user sign-off

Phase 6, Phase 7, and Phase 8 must reconcile their control-plane updates against final validated repo state:

- Phase 6 verifies `DECISIONS.md`
- Phase 7 verifies `STATE.md`
- Phase 8 verifies memory updates and status transitions against touched paths, prior memory truth, `STATE.md`, `DECISIONS.md`, and final code
- Phase 6, Phase 7, and Phase 8 receipts should be concise delta receipts that point to the final control-plane docs instead of restating large sections of them
- Phase 8 must record run-local skill usage, promotion decisions, and why observations were or were not promoted into durable skill memory

## Gate And Tooling Mirror

For audited phases:

- `Coverage: PASS` is invalid unless `Audit: PASS`
- `Approval: PASS` is invalid unless `Audit: PASS`
- no lock is valid without required audit sections, traceability, and audit success
- downstream artifacts must explicitly map every in-scope `R#`; vague traceability is invalid

Repo tooling should stay aligned with these rules:

- `lint-recursive-run.*` rejects missing audit structure, missing `Audit: PASS|FAIL`, missing required `R#` coverage, missing prior recursive evidence where required, and missing diff-basis usage where required
- `recursive-status.*` reports audit blockers, diff-audit deficiencies, missing reconciliation, missing prior recursive evidence, traceability gaps, and lock ineligibility reasons
- `recursive-status.*` and `lint-recursive-run.*` must fail delegated review records that only point at a bundle file without citing bundle-grounded upstream artifacts, addenda, prior recursive evidence, and changed files/code refs
- `recursive-status.*` also reports missing RED/GREEN evidence, invalid pragmatic TDD exceptions, and QA-mode-specific blockers
- `verify-locks.*` remains primarily structural/cryptographic, but audited-phase lock validity must stay consistent with the strict audit gates
- `recursive-lock.*` is the primary supported locking path and must refuse to lock artifacts whose required gates, TDD evidence requirements, QA-mode requirements, or lint-critical structure are not yet valid

## Canonical Locations

- Canonical workflow: `/.recursive/RECURSIVE.md`
- Primary Codex AGENTS bridge: `/.codex/AGENTS.md`
- Primary Codex PLANS bridge: `/.agent/PLANS.md`
- Canonical run root: `/.recursive/run/<run-id>/`
- Durable memory root: `/.recursive/memory/`
- Skill-memory router: `/.recursive/memory/skills/SKILLS.md`
