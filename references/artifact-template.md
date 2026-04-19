# recursive-mode Artifact Writing Guide and Templates

Use this file when writing any per-run artifact in:
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/01-as-is.md`
- `/.recursive/run/<run-id>/01.5-root-cause.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- `/.recursive/run/<run-id>/03.5-code-review.md`
- `/.recursive/run/<run-id>/04-test-summary.md`
- `/.recursive/run/<run-id>/05-manual-qa.md`
- `/.recursive/run/<run-id>/06-decisions-update.md`
- `/.recursive/run/<run-id>/07-state-update.md`
- `/.recursive/run/<run-id>/08-memory-impact.md`
- `/.recursive/run/<run-id>/addenda/*.md`

This guide is intentionally prescriptive so two different agents produce equivalent artifacts.

## Table of Contents

- [Quick Start Checklist](#quick-start-checklist)
- [Required Header (All Artifacts)](#required-header-all-artifacts)
- [Universal Sections (All Artifacts Except `00-requirements.md`)](#universal-sections-all-artifacts-except-00-requirementsmd)
- [Memory Metadata Block (Durable Memory Docs)](#memory-metadata-block-durable-memory-docs)
- [Evidence Directory (Per Run)](#evidence-directory-per-run)
- [Review Bundle Template](#review-bundle-template)
- [Subagent Action Record Template](#subagent-action-record-template)
- [Phase-by-Phase Authoring Templates](#phase-by-phase-authoring-templates)
- [Phase 0 Template (`00-worktree.md`) - Isolation REQUIRED](#phase-0-template-00-worktreemd---isolation-required)
- [Phase 0 Requirements Template (`00-requirements.md`)](#phase-0-requirements-template-00-requirementsmd)
- [Phase 1 Template (`01-as-is.md`)](#phase-1-template-01-as-ismd)
- [Phase 1.5 Template (`01.5-root-cause.md`) - Debug Mode Only](#phase-15-template-015-root-causemd---debug-mode-only)
- [Phase 2 Template (`02-to-be-plan.md`, ExecPlan Grade)](#phase-2-template-02-to-be-planmd-execplan-grade)
- [Phase 3 Template (`03-implementation-summary.md`)](#phase-3-template-03-implementation-summarymd)
- [Phase 3.5 Template (`03.5-code-review.md`) - Optional](#phase-35-template-035-code-reviewmd---optional)
- [Phase 4 Template (`04-test-summary.md`)](#phase-4-template-04-test-summarymd)
- [Phase 5 Template (`05-manual-qa.md`)](#phase-5-template-05-manual-qamd)
- [Phase 6 Template (`06-decisions-update.md`)](#phase-6-template-06-decisions-updatemd)
- [Phase 7 Template (`07-state-update.md`)](#phase-7-template-07-state-updatemd)
- [Phase 8 Template (`08-memory-impact.md`)](#phase-8-template-08-memory-impactmd)
- [Addenda Templates](#addenda-templates)
- [Stage-Local Addendum](#stage-local-addendum)
- [Upstream-Gap Addendum](#upstream-gap-addendum)
- [Artifact Linting (Structure + TODO Discipline)](#artifact-linting-structure--todo-discipline)
- [Locking Commands](#locking-commands)
- [Common Failure Modes (Use as Pre-Lock Checklist)](#common-failure-modes-use-as-pre-lock-checklist)
- [Lock Verification](#lock-verification)

## Quick Start Checklist

1. Resolve the run id and exact output path.
2. **Ensure `00-requirements.md` exists, then create/lock Phase 0 worktree (`00-worktree.md`) before Phase 1+ (isolated workspace setup).**
3. **If writing Phase 3 or later, verify all prior phase artifacts are lock-valid before proceeding.**
4. Verify phase isolation: only the current phase may be `DRAFT`; do not proceed if a prior phase is unresolved.
5. Determine effective inputs:
   - base input files for this phase
   - plus stage-local addenda for each base input, lexical order
   - plus current-phase upstream-gap addenda when they compensate for locked-history gaps you must account for now
6. Write the required header with exact input/output paths.
7. Write phase-specific content sections from this guide.
8. For audited phases, write the audit sections and complete the `draft -> audit -> repair -> re-audit` loop.
9. Write `Traceability`, `Coverage Gate`, and `Approval Gate`.
10. Perform a pre-lock completeness check using this template's required sections and gates.
11. Verify LockHash matches SHA-256 of content before locking.
12. Lock only after all required gates pass (`Status`, `LockedAt`, `LockHash`).

## Required Header (All Artifacts)

```md
Run: `/.recursive/run/<run-id>/`
Phase: `0N <phase-name>`
Status: `DRAFT`
Inputs:
- `/<path-to-input-1>`
- `/<path-to-input-2>`
Outputs:
- `/<path-to-this-output>`
Scope note: One short paragraph describing what this artifact decides or enables.
```

When locking, append:

```md
LockedAt: `YYYY-MM-DDTHH:MM:SSZ`
LockHash: `<sha256-hex>`
```

## Universal Sections (All Artifacts Except `00-requirements.md`)

Traceability is not required in `00-requirements.md`, but every downstream artifact (Phase 1+) must include it.

```md
## Traceability

- `R1` -> [where this artifact addresses it] | Evidence: [files, commands, observations]
- `R2` -> [where this artifact addresses it] | Evidence: [files, commands, observations]
- `R3` -> Deferred in this phase | Rationale: [...] | Impact: [...]
```

```md
## Coverage Gate

- Effective inputs reviewed:
  - `/<base-input-1>`
  - `/<matching-addendum-1>`
  - `/<matching-addendum-2>`
- Requirement coverage check:
  - `R1`: Covered at [section]
  - `R2`: Covered at [section]
  - `R3`: Deferred [why]
- Out-of-scope confirmation:
  - `OOS1`: unchanged
  - `OOS2`: unchanged

Coverage: PASS
```

```md
## Approval Gate

- Objective readiness checks:
  - [artifact is internally consistent]
  - [commands are runnable and specific]
  - [tests/QA expectations are explicit for this phase]
  - [no required section is missing]
- Remaining blockers:
  - none

Approval: PASS
```

If either gate fails, set `FAIL` and list exact fixes required before proceeding.

## Universal Audit Sections (Audited Phases)

Use this block in every audited phase for `recursive-mode-audit-v1` and `recursive-mode-audit-v2`:

```md
## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Subagent Capability Probe: [what proved availability or unavailability]
Delegation Decision Basis: [why self-audit or delegation was chosen]
Delegation Override Reason: [required when subagents were available but self-audit was still chosen]
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- [other upstream artifacts]
- Changed files:
  - `path/to/file`
- Targeted code references:
  - `path/to/file`

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/...`

## Earlier Phase Reconciliation

- Upstream artifact:
  - Claim carried forward:
  - Current reconciliation:

## Subagent Contribution Verification

- Reviewed Action Records: `none` / `/.recursive/run/<run-id>/subagents/<record>.md`
- Main-Agent Verification Performed: `path/to/file`, `/.recursive/run/<run-id>/artifact.md`, diff-owned paths actually checked by the controller
- Acceptance Decision: `accepted|partially accepted|rejected`
- Refresh Handling: [whether the bundle/action record was refreshed after repairs or why no refresh was needed]
- Repair Performed After Verification: `none` / [concrete repair paths or artifact updates performed after checking delegated work]

Controller verification rule:

- `Main-Agent Verification Performed` should cite real files or recursive artifacts that exist, not placeholder prose
- if `Repair Performed After Verification` cites paths, those paths should also exist
- if `Subagent Availability` is `available` and `Audit Execution Mode` is `self-audit`, `Delegation Override Reason` should state the concrete reason the controller chose not to delegate
- these fields may be written inline or as multi-line bullet lists; lint/status should accept either form as long as the cited paths and decisions are concrete

## Worktree Diff Audit

- Baseline type: `local commit|local branch|remote ref|merge-base derived`
- Baseline reference: `origin/main` / `main` / `<commit>`
- Comparison reference: `working-tree` / `HEAD` / `<branch-or-ref>`
- Normalized baseline: `<commit-sha>`
- Normalized comparison: `working-tree` / `<commit-sha>`
- Normalized diff command: `git diff --name-only <normalized-basis>`
- Planned or claimed changed files:
  - `path/to/file`
- Actual changed files reviewed:
  - `path/to/file`
- Unexplained drift:
  - none / [explain]

Incidental runtime noise such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/` is excluded from meaningful diff audit unless the repo intentionally tracks it.

For Phase 0 specifically, `recursive-init` should prefill a safe executable default from the current `HEAD` commit when possible. If you later choose a different baseline, update `Baseline reference`, `Normalized baseline`, `Comparison reference`, `Normalized comparison`, and `Normalized diff command` together and rerun lint before locking.

## Phase-Scoped Diff Ownership

Treat `## Worktree Diff Audit` as phase-scoped, not as a permanent obligation for every earlier artifact to explain the eventual end-state diff forever.

- Phase 2 owns planning completeness plus the expected product/worktree change surface.
- Phase 3, Phase 3.5, and Phase 4 own the actual product/worktree diff.
- Phase 6 owns `/.recursive/DECISIONS.md` plus the reviewed final product/worktree paths.
- Phase 7 owns `/.recursive/STATE.md` plus the reviewed final product/worktree paths.
- Phase 8 owns `/.recursive/memory/**` plus the reviewed final product/worktree paths.
- Late control-plane or memory churn must not retroactively invalidate an earlier locked planning artifact.
- If a later phase discovers a real upstream gap, create a current-phase upstream-gap addendum and compensate there instead of editing locked history.

## Gaps Found

- none / [list in-scope gaps, missing evidence, or drift]

## Repair Work Performed

- none / [list repairs made before re-audit]

## Requirement Completion Status

- `R1 | Status: implemented | Changed Files: /path/to/file | Implementation Evidence: /path/to/file, /path/to/artifact`
- `R2 | Status: verified | Changed Files: /path/to/file | Implementation Evidence: /path/to/file | Verification Evidence: /path/to/test-summary.md`
- `R3 | Status: deferred | Rationale: [why] | Deferred By: /.recursive/run/<run-id>/addenda/...`
- `R4 | Status: out-of-scope | Rationale: [why] | Scope Decision: /.recursive/run/<run-id>/addenda/...`
- `R5 | Status: blocked | Rationale: [why] | Blocking Evidence: /path/to/log, /path/to/artifact`
- `R6 | Status: superseded by approved addendum | Addendum: /.recursive/run/<run-id>/addenda/...`

Use status-specific evidence fields rather than a generic `Evidence:` field:

- `implemented` -> `Changed Files` and `Implementation Evidence`
- `verified` -> `Changed Files`, `Implementation Evidence`, and `Verification Evidence`
- `deferred` -> `Deferred By` or `Addendum`
- `out-of-scope` -> `Scope Decision` or `Addendum`
- `blocked` -> `Blocking Evidence`

Contradiction rule:

- do not mix fields from conflicting statuses in one `R#` entry
- do not mark a requirement `implemented` or `verified` without concrete changed-file refs
- do not mark a requirement `verified` without verification evidence that is stronger than merely restating implementation evidence
- in phases that own product/worktree diff, every diff-owned changed file should appear under some in-scope requirement's `Changed Files`

## Audit Verdict

- Audit summary:
- Follow-up required before lock:
- Audit: FAIL
```

Additional audited-phase requirement:

- Phase 1, Phase 2, Phase 4, Phase 7, and Phase 8 must also include `## Prior Recursive Evidence Reviewed`.
- Do not set `Coverage: PASS` or `Approval: PASS` unless `Audit: PASS`.
- Phase 8 must also include `## Run-Local Skill Usage Capture` and `## Skill Memory Promotion Review`.

## Memory Metadata Block (Durable Memory Docs)

Every durable memory doc under `/.recursive/memory/` except `MEMORY.md` must include this metadata block near the top.

```md
Type: `domain|pattern|incident|episode`
Status: `CURRENT|SUSPECT|STALE|DEPRECATED|DRAFT`
Scope: `<what this memory doc covers>`
Owns-Paths:
- `path/or/glob/**`
Watch-Paths:
- `path/or/glob/**`
Source-Runs:
- `/.recursive/run/<run-id>/`
Validated-At-Commit: `<git-sha>`
Last-Validated: `YYYY-MM-DDTHH:MM:SSZ`
Tags:
- `tag-one`
- `tag-two`
Parent: `<optional parent memory doc path>`
Children:
- `<optional child memory doc path>`
Supersedes:
- `<optional older memory doc path>`
Superseded-By:
- `<optional newer memory doc path>`
```

Notes:
- `MEMORY.md` is the router/index and does not require the metadata block.
- `SKILLS.md` is the skill-memory router/index and does not require the metadata block.
- `Owns-Paths` may be empty for non-domain docs, but the field must exist.
- `Watch-Paths` may be empty, but the field must exist.
- Phase 8 should downgrade affected `CURRENT` docs to `SUSPECT` until semantic revalidation is complete.

## Evidence Directory (Per Run)

To keep Phase 4/5 fast and reproducible, store all non-Markdown evidence artifacts under a standard folder:

- `/.recursive/run/<run-id>/evidence/`
  - `screenshots/` (UI screenshots, failure screenshots)
  - `logs/` (console/server/CI excerpts)
  - `perf/` (profiles, measurements, benchmarks)
  - `traces/` (Playwright traces, HARs; if applicable)
  - `review-bundles/` (canonical delegated review handoff files)
  - `other/` (fallback)

Per-run delegated work records live under:

- `/.recursive/run/<run-id>/subagents/`

Reference these artifacts in Phase 3/4/5 using repo-relative paths.

## Review Bundle Template

Use this when delegating a Phase 3.5 review or any other review/audit that needs a reproducible context handoff. Prefer generating it with `recursive-review-bundle`.
The helper auto-discovers relevant addenda by default; do not trim them out unless you are deliberately debugging bundle generation.

```md
Run: `/.recursive/run/<run-id>/`
Bundle Type: `review-bundle`
Phase: `03.5 Code Review`
Role: `code-reviewer`
Artifact path: `/.recursive/run/<run-id>/03.5-code-review.md`
Artifact Content Hash: `<sha256>`

## Routing

- Routed CLI: `none`
- Routed Model: `none`
- Routing Config Path: `none`
- Routing Discovery Path: `none`

## Upstream Artifacts

- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`

## Addenda

- none / `/.recursive/run/<run-id>/addenda/...`

## Prior Recursive Evidence

- none / `/.recursive/run/<run-id>/...`
- none / `/.recursive/memory/...`

## Control-Plane Docs

- none / `/.recursive/DECISIONS.md`
- none / `/.recursive/STATE.md`

## Diff Basis

- Baseline type:
- Baseline reference:
- Comparison reference:
- Normalized baseline:
- Normalized comparison:
- Normalized diff command:

## Changed Files

- `path/to/file`

## Targeted Code References

- `path/to/file`

## Evidence References

- `/.recursive/run/<run-id>/evidence/logs/...`

## Audit Questions

- Which `R#` remain incomplete or weakly evidenced?
- Which changed files drift from the plan or implementation claims?
- Is TDD and test evidence sufficient for this phase?
- What must be repaired before lock?

## Required Output

- Findings ordered by severity
- Missing evidence or traceability gaps
- Concrete repair recommendations
- Final verdict suitable for `Audit: PASS` or `Audit: FAIL`
```

Review-artifact expectation:

- The written review narrative should cite the `Review Bundle Path`, at least one upstream artifact from the bundle, relevant addenda when present, and changed files or code refs from the bundle.
- Relevant addenda should appear in the bundle automatically unless auto-discovery is intentionally disabled for debugging.
- `## Changed Files Reviewed` and `## Targeted Code References` should be concrete, non-empty, and grounded in the changed-file scope being reviewed.
- Main-agent acceptance should record how delegated claims were checked against actual files, actual recursive artifacts, actual diff scope, and any repairs performed after verification.

## Subagent Action Record Template

Use this when a meaningful subagent invocation contributes to a phase outcome. The record is a durable claim log that the main agent must verify before accepting the work.

```md
# Subagent Action Record

## Metadata
- Subagent ID:
- Run ID:
- Phase:
- Purpose:
- Execution Mode:
- Timestamp:
- Action Record Path:

## Inputs Provided
- Current Artifact:
- Artifact Content Hash:
- Upstream Artifacts:
- Addenda:
- Review Bundle:
- Diff Basis:
- Code Refs:
- Memory Refs:
- Audit / Task Questions:

## Routing
- Router Used:
- Routed Role:
- Routed CLI:
- Routed Model:
- Routing Config Path:
- Routing Discovery Path:
- Routing Resolution Basis:
- Routing Fallback Reason:
- CLI Probe Summary:
- Prompt Bundle Path:
- Invocation Exit Code:
- Output Capture Paths:

## Claimed Actions Taken
- [bullet list]

## Claimed File Impact
### Created
- path
### Modified
- path
### Reviewed
- path
### Relevant but Untouched
- path

## Claimed Artifact Impact
### Read
- artifact path
### Updated
- artifact path
### Evidence Used
- evidence path

## Claimed Findings
- [bullet list]

## Verification Handoff
- Inspect these files first:
- Reconcile these diffs:
- Cross-check these artifacts:
- Known uncertainties:
```

Meaningfulness rule:

- For materially contributing delegated work, `## Claimed Actions Taken` cannot be `none`.
- `## Claimed File Impact` should cite concrete created, modified, reviewed, or relevant untouched files.
- `## Claimed Artifact Impact` should cite recursive artifacts or evidence paths actually used.
- `Artifact Content Hash` should match the current artifact content at the time the controller accepts the record.
- For delegated review or audit, prefer a stable reviewed artifact for `Current Artifact` instead of a mutable controller-authored phase receipt draft. If that artifact changes materially, refresh the action record.
- The controller should verify the record against actual changed files, actual recursive artifacts, the review bundle when present, and earlier locked recursive docs before acceptance.

## Phase-by-Phase Authoring Templates

For Phases 4-8, prefer starting from `recursive-closeout` rather than hand-authoring a blank markdown file. The helper scaffolds the required headings, audited sections, and late-phase input/output lists before you fill in the final receipt content.

## Phase 0 Template (`00-worktree.md`) - Isolation REQUIRED

Required outcome:
- Isolated git worktree created on feature branch
- Worktree directory verified as git-ignored
- Project setup completed
- Clean test baseline verified
- Main branch protection confirmed

```md
Run: `/.recursive/run/<run-id>/`
Phase: `00 Worktree Setup`
Status: `DRAFT`
Inputs:
- Current git repository state
- User preference (for worktree location)
Outputs:
- `/.recursive/run/<run-id>/00-worktree.md`
- Isolated worktree at `[location]`
Scope note: This document records isolated workspace setup and verifies clean test baseline.

## TODO

- [ ] Verify current branch (main/master protection check)
- [ ] Select worktree location (`.worktrees/<run-id>/` preferred)
- [ ] Verify worktree directory is git-ignored
- [ ] Create git worktree with feature branch
- [ ] Run project setup (npm install, cargo build, etc.)
- [ ] Verify clean test baseline (all tests passing)
- [ ] Document worktree location and branch name
- [ ] Record baseline commit SHA
- [ ] Record reusable diff basis for later audited phases

## Directory Selection

**Convention checked:**
- [ ] `.worktrees/` exists
- [ ] `worktrees/` exists
- [ ] CLAUDE.md preference found
- [ ] User preference obtained

**Selected location:** `.worktrees/` (project-local, hidden)
**Rationale:** [why this location]

## Safety Verification

**Gitignore check:**
```bash
$ git check-ignore -q .worktrees && echo "IGNORED" || echo "NOT IGNORED"
IGNORED
```

**Result:** ? Directory is properly ignored

(If NOT ignored: added to .gitignore and committed before proceeding)

## Worktree Creation

**Current branch before:** `main` (or `master`)

**Command:**
```bash
git worktree add .worktrees/<run-id> -b recursive/<run-id>
```

**Output:**
```
Preparing worktree (new branch 'recursive/<run-id>')
HEAD is now at abc1234 Previous commit message
```

**Branch created:** `recursive/<run-id>`
**Worktree location:** `/full/path/to/project/.worktrees/<run-id>`

## Main Branch Protection

**Original branch:** `main`
**Action:** Created worktree (default behavior)
**Isolation:** ? Working in isolated worktree

(If on main and user insisted: document explicit consent here)

## Project Setup

**Detected project type:** [Node.js/Rust/Python/Go/etc.]

**Commands executed:**
```bash
cd .worktrees/<run-id>
[npm install / cargo build / pip install / etc.]
```

**Output:**
```
[setup output]
```

**Setup status:** ? Complete / ? Issues noted

## Test Baseline Verification

**Command:**
```bash
[npm test / cargo test / pytest / etc.]
```

**Results:**
- Total: [N] tests
- Passed: [N]
- Failed: [N]
- Skipped: [N]

**Baseline:** ? Clean (all tests passing) / ? Pre-existing failures noted

(If failures exist, document and get explicit consent to proceed)

## Worktree Context

**All subsequent phases will execute in:**
- Directory: `.worktrees/<run-id>/`
- Branch: `recursive/<run-id>`
- Base commit: `abc1234`

## Diff Basis For Later Audits

- Baseline type: `local commit|local branch|remote ref|merge-base derived`
- Baseline reference: `main` / `origin/main` / `abc1234`
- Comparison reference: `working-tree` / `HEAD` / `<branch-or-ref>`
- Normalized baseline: `abc1234`
- Normalized comparison: `working-tree` / `def5678`
- Normalized diff command: `git diff --name-only abc1234`
- Base branch: `main`
- Worktree branch: `recursive/<run-id>`
- Diff basis notes: [why this non-default basis was chosen, if applicable]

`recursive-init` should prefill this block from the current `HEAD` commit when possible. The executable source of truth is the combination of `Normalized baseline`, `Normalized comparison`, and `Normalized diff command`; Phase 0 lock must fail if those values do not match live git state.

## Traceability

- recursive-mode process -> Isolated workspace established | Evidence: worktree at `.worktrees/<run-id>`

## Coverage Gate

- [ ] Worktree location selected following priority rules
- [ ] Directory verified as git-ignored (if project-local)
- [ ] Worktree created successfully on feature branch
- [ ] Project setup completed without errors
- [ ] Clean test baseline verified (all tests passing, or failures documented)
- [ ] Main branch protection confirmed (working in isolation, or consent documented)

Coverage: PASS / FAIL

## Approval Gate

- [ ] Isolated workspace ready for development
- [ ] No pending setup issues
- [ ] Ready to proceed to Phase 1/2
- [ ] LockHash matches SHA-256 of content (verified)

Approval: PASS / FAIL

LockedAt: `YYYY-MM-DDTHH:MM:SSZ`
LockHash: `<sha256-hex>`
```

## Phase 0 Requirements Template (`00-requirements.md`)

Required outcome:
- stable requirement IDs (`R1`, `R2`, ...)
- out-of-scope IDs (`OOS1`, `OOS2`, ...)
- observable acceptance criteria per requirement
- constraints/assumptions

```md
Run: `/.recursive/run/<run-id>/`
Phase: `00 Requirements`
Status: `DRAFT`
Workflow version: `recursive-mode-audit-v2`
Inputs:
- [chat summary or source notes if captured in repo]
Outputs:
- `/.recursive/run/<run-id>/00-requirements.md`
Scope note: This document defines stable requirement identifiers and acceptance criteria.

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

### `R2` <short title>
Description:
Acceptance criteria:
- [...]

## Out of Scope

- `OOS1`: ...
- `OOS2`: ...

## Constraints

- ...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Phase 1 Template (`01-as-is.md`)

Required outcome:
- novice-runnable repro
- current behavior tied to `R#`
- concrete code pointers
- known unknowns

```md
Run: `/.recursive/run/<run-id>/`
Phase: `01 AS-IS`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/addenda/00-requirements.addendum-01.md` [if present]
Outputs:
- `/.recursive/run/<run-id>/01-as-is.md`
Scope note: This document captures current behavior and evidence before changes.

## TODO

- [ ] Read and understand requirements from Phase 1
- [ ] Read and understand requirements from Phase 0
- [ ] Create novice-runnable reproduction steps
- [ ] Document current behavior for each requirement (R1, R2, ...)
- [ ] Identify and record relevant code pointers
- [ ] List known unknowns
- [ ] Gather evidence (logs, screenshots, outputs)
- [ ] Review relevant prior recursive evidence for the affected area
- [ ] Assemble audit context bundle
- [ ] Run phase audit
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Create traceability mapping
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Reproduction Steps (Novice-Runnable)

1. ...
2. ...
3. ...

## Current Behavior by Requirement

- `R1`: [what currently happens]
- `R2`: [what currently happens]

## Relevant Code Pointers

- `path/to/file.ext`: [why relevant]
- `path/to/other.ext`: [why relevant]

## Known Unknowns

- ...

## Evidence

- Command output: ...
- Log snippet: ...
- UI observation: ...

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- Changed files:
  - none yet / `path`
- Targeted code references:
  - `path/to/file`

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/00-requirements.md`
- [phase-local addenda]

## Prior Recursive Evidence Reviewed

- Prior run id:
  - Docs read:
  - Reused insight:
  - Superseded or contradicted:

## Earlier Phase Reconciliation

- `00-requirements.md`:
  - Requirement coverage status:
  - Unknowns carried forward:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - none yet / `path`
- Actual changed files reviewed:
  - none yet / `path`
- Unexplained drift:
  - none

## Gaps Found

- none / [list gaps]

## Repair Work Performed

- none / [list repairs]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Phase 1.5 Template (`01.5-root-cause.md`) - Debug Mode Only

Required outcome:
- systematic root cause analysis for bug fixes
- error analysis, reproduction verification, data flow tracing
- documented hypothesis testing
- root cause summary for Phase 2 planning

**Use when:** Requirement involves fixing a bug, test failure, or investigating unexpected behavior.

```md
Run: `/.recursive/run/<run-id>/`
Phase: `01.5 Root Cause Analysis`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/01-as-is.md`
- [relevant addenda]
Outputs:
- `/.recursive/run/<run-id>/01.5-root-cause.md`
Scope note: This document records systematic debugging process and identified root cause before any fix is attempted.

## TODO

- [ ] Analyze error messages and stack traces
- [ ] Verify reproduction (confirm bug is reproducible)
- [ ] Review recent changes (git history, dependencies)
- [ ] Gather evidence (logs, data flow, state inspection)
- [ ] Trace data flow to identify source
- [ ] Analyze patterns (working vs broken comparisons)
- [ ] Form and test hypotheses
- [ ] Confirm root cause (not just symptom)
- [ ] Define fix strategy for Phase 2
- [ ] Assemble audit context bundle
- [ ] Run phase audit
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Error Analysis

**Error Message:** [verbatim]
**Stack Trace:** [key frames]
**File:Line:** [locations]
**Key Insight:** [what the error is telling you]

## Reproduction Verification

**Steps:**
1. [exact step]
2. [exact step]
3. [exact step]

**Reproducible:** Yes / No / Intermittent
**Frequency:** [X out of Y attempts]
**Deterministic:** Yes / No

## Recent Changes Analysis

**Git History:** [relevant commits]
**Dependency Changes:** [if applicable]
**Environment:** [OS, runtime versions]
**Likely Culprit:** [most suspicious change]

## Evidence Gathering (Multi-Layer if applicable)

**Layer 1: [Component]**
- Input: [data]
- Output: [data]
- Status: ? Working / ? Broken

**Failure Boundary:** [where it breaks]

## Data Flow Trace

**Error Location:** [file:line - function]
**Bad Value:** [what was wrong]

**Call Stack (backward):**
1. `functionA()` at fileA:line - received [value]
2. `functionB()` at fileB:line - passed [value]
3. [source] `functionC()` at fileC:line - ORIGIN

## Pattern Analysis

**Working Example:** [file:location]
**Broken Code:** [file:location]

**Key Differences:**
| Aspect | Working | Broken |
|--------|---------|--------|
| [X] | [value] | [value] |

## Hypothesis Testing

### Hypothesis 1
**Statement:** [clear hypothesis]
**Test:** [minimal change]
**Result:** [confirmed/rejected]

### Hypothesis 2 (if needed)
[...]

**Confirmed Root Cause:** [final hypothesis]

## Root Cause Summary

**Root Cause:** [one sentence]
**Location:** [file:line]
**Detailed Explanation:** [paragraph]
**Fix Strategy:** [approach for Phase 2]
**Test Strategy:** [how to verify fix]

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/01-as-is.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- Changed files:
  - `path/to/file`
- Targeted code references:
  - `path/to/file`

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/01-as-is.md`
- [phase-local addenda]

## Earlier Phase Reconciliation

- `01-as-is.md`:
  - Reproduction status:
  - Evidence carried forward:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `path/to/file`
- Actual changed files reviewed:
  - `path/to/file`
- Unexplained drift:
  - none

## Gaps Found

- none / [list unresolved gaps]

## Repair Work Performed

- none / [list repairs]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability

- R# (Bug fix requirement) -> Root cause identified at [location] | Evidence: [section]

## Coverage Gate

- [ ] Error messages analyzed
- [ ] Reproduction verified
- [ ] Recent changes reviewed
- [ ] Data flow traced to source
- [ ] Pattern analysis completed
- [ ] Hypothesis tested and confirmed
- [ ] Root cause documented (not just symptom)
- [ ] Fix strategy defined

Coverage: PASS / FAIL

## Approval Gate

- [ ] Root cause identified at source (not just symptom location)
- [ ] Fix approach clear and minimal
- [ ] Test strategy defined
- [ ] No "quick fix" attempts made
- [ ] Ready to proceed to Phase 2 with fix plan

Approval: PASS / FAIL
```

## Phase 2 Template (`02-to-be-plan.md`, ExecPlan Grade)

Required outcome:
- concrete edits by file and location
- exact commands
- tests to add/run
- manual QA scenarios
- recovery/idempotence
- traceability mapping `R# -> planned change + validation`
- sub-phases (`SP1`, `SP2`, ...) when scope/risk is large

```md
Run: `/.recursive/run/<run-id>/`
Phase: `02 TO-BE plan`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/01-as-is.md`
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/addenda/01-as-is.addendum-01.md` [if present]
Outputs:
- `/.recursive/run/<run-id>/02-to-be-plan.md`
Scope note: This document defines the implementation and validation plan.

## TODO

- [ ] Read Phase 1 (AS-IS) and Phase 0 (Requirements) artifacts
- [ ] If Phase 1.5 exists: incorporate root cause findings
- [ ] Define sub-phases (SP1, SP2, ...) if scope/risk is large
- [ ] Specify concrete file changes (what, where, how)
- [ ] Define implementation steps in sequence
- [ ] Design testing strategy (new + regression + guardrail)
- [ ] Document Playwright test plan (if applicable)
- [ ] Define manual QA scenarios
- [ ] Review relevant prior recursive evidence for the affected area
- [ ] Assemble audit context bundle
- [ ] Run phase audit
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Create traceability mapping (R# -> changes -> validation)
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Planned Changes by File

- `path/to/file.ext`: [exact change]
- `path/to/file2.ext`: [exact change]

## Implementation Steps

1. ...
2. ...
3. ...

## Testing Strategy

- New behavior tests: ...
- Regression tests: ...
- Guardrail tests: ...
- Commands:
  - `...`
  - `...`

## Playwright Plan (if applicable)

- Tags: `@recursive:<run-id>`, `@sp1`, `@smoke`
- Tier A command(s): `...`
- Tier B command(s): `...`
- Evidence outputs: `playwright-report/`, `test-results/`

## Manual QA Scenarios

1. Scenario:
   - Steps:
   - Expected:

2. Scenario:
   - Steps:
   - Expected:

## Idempotence and Recovery

- Re-run safety notes:
- Rollback notes:

## Implementation Sub-phases

### `SP1` <name>
Scope and requirement mapping:
- Covers: `R1`, `R3`

Implementation checklist:
- [ ] edit `path/to/file.ext` ...
- [ ] add test `path/to/test.spec.ts` ...

Tests for this sub-phase:
- `...`
- Pass criteria: ...

Sub-phase acceptance:
- ...

### `SP2` <name>
[same structure]

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/01-as-is.md`
- [relevant addenda]
- Changed files:
  - anticipated `path/to/file`
- Targeted code references:
  - `path/to/file`

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/01-as-is.md`
- [phase-local addenda]

## Prior Recursive Evidence Reviewed

- Prior run id:
  - Docs read:
  - Reused insight:
  - Superseded or contradicted:

## Earlier Phase Reconciliation

- `00-requirements.md`:
  - each in-scope `R#` planned:
- `01-as-is.md`:
  - current behavior reconciled:
- `01.5-root-cause.md`:
  - fix strategy incorporated:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `path/to/file`
- Actual changed files reviewed:
  - none yet / `path/to/file`
- Unexplained drift:
  - none

Note: incidental runtime byproducts such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/` are excluded from meaningful diff audit unless the repository intentionally tracks them.

## Gaps Found

- none / [list planning gaps or missing concreteness]

## Repair Work Performed

- none / [list plan repairs made before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Phase 3 Template (`03-implementation-summary.md`)

Required outcome:
- what changed, where, why
- implementation evidence
- **TDD compliance log (RED-GREEN-REFACTOR for each requirement)**
- deviations from plan (if any)

```md
Run: `/.recursive/run/<run-id>/`
Phase: `03 Implementation`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/addenda/02-to-be-plan.addendum-01.md` [if present]
Outputs:
- `/.recursive/run/<run-id>/03-implementation-summary.md`
Scope note: This document records completed code changes, TDD compliance, and implementation evidence.

## TODO

- [ ] Read locked Phase 2 (TO-BE) plan
- [ ] Determine execution mode (Parallel vs Sequential)
- [ ] For each sub-phase (SP1, SP2, ...):
  - [ ] Implement per plan (TDD discipline)
  - [ ] Write tests BEFORE code (RED phase)
  - [ ] Make tests pass (GREEN phase)
  - [ ] Refactor while keeping tests green
  - [ ] Self-review / subagent review
  - [ ] Run integration tests
- [ ] Complete TDD Compliance Log for all requirements
- [ ] Document any plan deviations
- [ ] Record implementation evidence (diffs, logs)
- [ ] Assemble audit context bundle
- [ ] Run implementation audit against requirements, plan, and actual diff
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Changes Applied

- `path/to/file.ext`: [change summary]
- `path/to/file2.ext`: [change summary]

## Sub-phase Implementation Summary

- `SP1`: [what shipped, files touched, notes]
- `SP2`: [what shipped, files touched, notes]

## TDD Compliance Log

**The Iron Law:** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.

TDD Mode: strict / pragmatic

RED Evidence:
- `/.recursive/run/<run-id>/evidence/logs/red/<file>.log`

GREEN Evidence:
- `/.recursive/run/<run-id>/evidence/logs/green/<file>.log`

### Requirement R1 ([description])

**Test:** `path/to/test.spec.ts` - "[test name]"

**RED Phase** ([ISO8601 timestamp]):
```bash
[exact command run]
[test failure output - showing it failed correctly]
```
- Expected failure: [what should fail]
- Actual failure: [what actually failed]
- RED verified: ? / ?

**GREEN Phase** ([ISO8601 timestamp]):
- Implementation: [minimal change made]
```bash
[exact command run]
[test pass output]
```
- GREEN verified: ? / ?

**REFACTOR Phase** ([ISO8601 timestamp]):
- Cleanups: [description of improvements]
- All tests still passing: ? / ?

**Final State:** [All tests passing / Issues noted]

### Requirement R2 (Bug Fix - Regression Test)

**Regression Test:** `path/to/regression.test.ts` - "[test name]"

**RED Phase** ([ISO8601 timestamp]):
- Bug reproduced: [evidence]
- RED verified: ? / ?

**GREEN Phase** ([ISO8601 timestamp]):
- Fix applied: [minimal change]
- GREEN verified: ? / ?

**REFACTOR:** [N/A or description]

**Final State:** [Test passes, bug fixed]

### TDD Red Flags Check

- [ ] No code written before failing test
- [ ] All RED phases documented with failure output
- [ ] All GREEN phases documented with minimal implementation
- [ ] No tests passing immediately (would indicate wrong test)
- [ ] No "tests to be added later"

## Pragmatic TDD Exception

Only include this section when `TDD Mode: pragmatic`.

Exception reason:
Compensating validation:
- `/.recursive/run/<run-id>/evidence/<supporting-file>`

## Plan Deviations

- Deviation:
  - Why:
  - Impact:
  - Evidence:

## Implementation Evidence

- Diff pointers:
- Runtime evidence:
- Build/lint results:

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- [relevant addenda]
- Changed files:
  - `path/to/file`
- Targeted code references:
  - `path/to/file`
- Review inputs:
  - failing tests
  - changed code
  - build/test evidence

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- [phase-local addenda]

## Earlier Phase Reconciliation

- `00-requirements.md`:
  - in-scope `R#` implemented:
- `02-to-be-plan.md`:
  - planned steps/sub-phases completed:
  - deviations explained:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `path/to/file`
- Actual changed files reviewed:
  - `path/to/file`
- Unexplained drift:
  - none / [explain]

## Gaps Found

- none / [list unfinished requirements, drift, or missing evidence]

## Repair Work Performed

- none / [list repairs completed before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate

- [ ] All requirements (R1..Rn) have implementation
- [ ] All sub-phases completed
- [ ] TDD Compliance Log complete for all requirements
- [ ] No production code without preceding failing test
- [ ] Plan deviations documented (if any)
- [ ] Implementation evidence recorded

TDD Compliance: PASS / FAIL
Coverage: PASS / FAIL

## Approval Gate

- [ ] Implementation matches Phase 2 TO-BE plan (or deviations documented)
- [ ] All tests passing
- [ ] Build/lint clean
- [ ] TDD Iron Law followed (no code before tests)
- [ ] `Audit: PASS` recorded before phase lock

Approval: PASS / FAIL
```

## Phase 3.5 Template (`03.5-code-review.md`) - Optional

Required outcome:
- Independent review of Phase 3 implementation against plan
- Code quality assessment
- Issue classification (Critical/Important/Minor)
- Clear verdict (Approved / Changes Required)

```md
Run: `/.recursive/run/<run-id>/`
Phase: `03.5 Code Review`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- Git range: BASE_SHA..HEAD_SHA
Outputs:
- `/.recursive/run/<run-id>/03.5-code-review.md`
Scope note: This document records independent review of implementation against plan and coding standards.

## TODO

- [ ] Read Phase 2 plan and Phase 3 implementation summary
- [ ] Review git diff (BASE_SHA..HEAD_SHA)
- [ ] Assess plan alignment for each requirement (R1, R2, ...)
- [ ] Assess plan alignment for each sub-phase (SP1, SP2, ...)
- [ ] Evaluate code quality (architecture, naming, error handling)
- [ ] Evaluate test quality (coverage, edge cases)
- [ ] Verify TDD compliance
- [ ] Categorize issues (Critical/Important/Minor)
- [ ] Document positive findings
- [ ] Record recommendations
- [ ] Render verdict (Approved / Changes Required)
- [ ] Generate or refresh the canonical review bundle
- [ ] Run review audit against requirements, plan, and actual diff
- [ ] Repair issues and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Review Scope

- Sub-phases reviewed: SP1, SP2, ...
- Git range reviewed: [BASE_SHA]..[HEAD_SHA]

## Plan Alignment Assessment

- **R1**: [description]
  - Plan requirement: [what was planned]
  - Implementation: [what was done]
  - Aligned: OK / WARN / FAIL
  - Notes: [deviations if any]

- **SP1**: [description]
  - Plan specification: [what was specified]
  - Implementation: [what was done]
  - Aligned: OK / WARN / FAIL
  - Notes: [deviations if any]

## Code Quality Assessment

### Architecture & Design
- SOLID principles: OK / WARN / FAIL
- Separation of concerns: OK / WARN / FAIL
- Integration with existing code: OK / WARN / FAIL

### Code Quality
- Naming conventions: OK / WARN / FAIL
- Error handling: OK / WARN / FAIL
- Type safety: OK / WARN / FAIL
- Maintainability: OK / WARN / FAIL

### Test Quality
- Test coverage adequate: OK / WARN / FAIL
- Test quality: OK / WARN / FAIL
- Edge cases covered: OK / WARN / FAIL

### TDD Compliance
- All production code preceded by failing tests: OK / WARN / FAIL
- TDD cycles documented: OK / WARN / FAIL
- Strict mode includes concrete RED and GREEN evidence paths: OK / WARN / FAIL
- Pragmatic mode has explicit exception rationale and compensating evidence: OK / WARN / FAIL
- No evidence of "code first, test later": OK / WARN / FAIL

## Issues Found

### Critical (must fix before proceeding)
1. **[Issue name]**
   - **Location:** `file:line`
   - **Problem:** [description]
   - **Recommendation:** [specific fix]

### Important (should fix)
1. **[Issue name]**
   - **Location:** `file:line`
   - **Problem:** [description]
   - **Recommendation:** [specific fix]

### Minor (suggestions)
1. **[Issue name]**
   - **Suggestion:** [description]

## Positive Findings

- [What was done well]

## Recommendations

- **Immediate:** [what to fix now]
- **Future:** [improvements for later]

## Verdict

- [ ] **APPROVED** - Ready to proceed to Phase 4
- [ ] **APPROVED WITH NOTES** - Minor issues, can proceed
- [ ] **CHANGES REQUIRED** - Fix issues, then re-review

## Review Metadata

- Reviewer: [agent name / self-review]
- Review Execution Mode: subagent / self-audit
- Review Bundle Path: `/.recursive/run/<run-id>/evidence/review-bundles/<bundle>.md`
- Bundle Scope Summary: [what the bundle covered]
- Reviewer Receipt: [review comment id / local note / n/a]
- Review duration: [time spent]
- Files reviewed: [count]
- Lines of code reviewed: [count]

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- Changed files:
  - `path/to/file`
- Targeted code references:
  - `path/to/file`

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- [phase-local addenda]

## Earlier Phase Reconciliation

- Requirements vs implementation:
- Plan vs implementation:
- Prior fixes vs remaining issues:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `path/to/file`
- Actual changed files reviewed:
  - `path/to/file`
- Unexplained drift:
  - none / [explain]

## Gaps Found

- none / [list blocking issues, drift, or missing evidence]

## Repair Work Performed

- none / [list repairs completed before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate

- [ ] All sub-phases reviewed
- [ ] Plan alignment verified for all requirements
- [ ] Code quality assessed
- [ ] Issues categorized by severity
- [ ] Verdict recorded
- [ ] `Audit: PASS` recorded before phase lock

Coverage: PASS / FAIL

## Approval Gate

- [ ] Review completed objectively
- [ ] Issues clearly documented
- [ ] Verdict justified
- [ ] Ready for Phase 4 (if approved)

Approval: PASS / FAIL
```

## Phase 4 Template (`04-test-summary.md`)

Required outcome:
- pre-test implementation audit against requirements and TO-BE plan
- exact commands executed
- pass/fail outcomes
- evidence artifact locations (standardized under `/.recursive/run/<run-id>/evidence/`)
- flake/retry notes
- parallel test execution summary (if applicable)

```md
Run: `/.recursive/run/<run-id>/`
Phase: `04 Test Summary`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- `/.recursive/run/<run-id>/03.5-code-review.md` [if present]
- [relevant addenda]
Outputs:
- `/.recursive/run/<run-id>/04-test-summary.md`
Scope note: This document records test execution evidence and readiness.

## TODO

- [ ] Read Phase 2 plan and Phase 3 implementation summary
- [ ] Audit implementation summary against `00-requirements.md` and `02-to-be-plan.md`
- [ ] Determine test execution mode (Parallel vs Sequential)
- [ ] Execute unit tests (document commands and results)
- [ ] Execute integration tests (document commands and results)
- [ ] Execute E2E Tier A tests (document commands and results)
- [ ] Execute Tier B regression tests (if applicable)
- [ ] Document any failures and diagnostics
- [ ] Note any flake/retry occurrences
- [ ] Verify TDD compliance (all Phase 3 tests passing)
- [ ] Review relevant prior recursive evidence for the affected area
- [ ] Assemble audit context bundle
- [ ] Run pre-test audit and post-test audit
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Pre-Test Implementation Audit

- Requirement alignment (`00-requirements.md`): list each requirement and confirm implemented/not implemented with evidence.
- Plan alignment (`02-to-be-plan.md`): list planned steps/sub-phases and confirm implemented/not implemented with evidence.
- Mismatches found:
  - [ ] None
  - [ ] Yes (document each mismatch and required addendum or fix before proceeding)

## Environment

- OS:
- Runtime versions:
- Test framework versions:
- Base URL / server mode:

## Execution Mode

- **Mode:** Parallel / Sequential
- **Subagent Usage:**
  - Unit tests: [subagent name] / Main agent
  - Integration tests: [subagent name] / Main agent
  - E2E tests: [subagent name] / Main agent
- **Parallel execution time:** [X] minutes (vs [Y] estimated sequential)

## Commands Executed (Exact)

- `...`
- `...`

## Results Summary

- Total:
- Passed:
- Failed:
- Skipped:

## Evidence and Artifacts

Store and reference artifacts under:
- `/.recursive/run/<run-id>/evidence/`
  - `evidence/screenshots/`
  - `evidence/logs/`
  - `evidence/perf/`
  - `evidence/traces/` (if applicable)

## By Sub-phase

- `SP1`:
  - Tier A command(s):
  - Result:
  - Evidence path(s):
- `SP2`:
  - Tier A command(s):
  - Result:
  - Evidence path(s):

## Tier B / Broader Regression

- Command(s):
- Result:
- Evidence path(s):

## Failures and Diagnostics (if any)

- Failing test:
  - Symptom:
  - Suspected cause:
  - Artifact path:
  - Mitigation:

## Flake/Rerun Notes

- Rerun command:
- Outcome:
- Deterministic or flaky:

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- `/.recursive/run/<run-id>/03.5-code-review.md` [if present]
- Changed files:
  - `path/to/file`
- Targeted code references:
  - `path/to/file`
- Test file references:
  - `path/to/test`

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- `/.recursive/run/<run-id>/03.5-code-review.md` [if present]
- [phase-local addenda]

## Prior Recursive Evidence Reviewed

- Prior run id:
  - Docs read:
  - Reused insight:
  - Superseded or contradicted:

## Earlier Phase Reconciliation

- Requirements vs implementation:
- Plan vs implementation:
- Review findings vs repairs:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `path/to/file`
- Actual changed files reviewed:
  - `path/to/file`
- Unexplained drift:
  - none / [explain]

## Gaps Found

- none / [list unfinished work, drift, or missing tests]

## Repair Work Performed

- none / [list repairs completed before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Phase 5 Template (`05-manual-qa.md`)

Required outcome:
- plan scenarios executed according to the selected QA mode
- observed outcomes
- explicit `QA Execution Mode`
- required sign-off and/or execution evidence for that mode

Compact table is allowed in this phase.

```md
Run: `/.recursive/run/<run-id>/`
Phase: `05 Manual QA`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- [relevant addenda]
Outputs:
- `/.recursive/run/<run-id>/05-manual-qa.md`
Scope note: This document records QA outcomes, the execution mode used, and the required evidence/sign-off for that mode.
QA Execution Mode: human / agent-operated / hybrid

## TODO

- [ ] Read Phase 2 plan (QA scenarios)
- [ ] Declare QA execution mode
- [ ] Present QA scenarios to the user if human input is required
- [ ] **PAUSE if needed:** Wait for user execution/sign-off when the selected mode requires it
- [ ] Record observed outcomes for each scenario
- [ ] Document pass/fail status
- [ ] Record QA execution metadata and evidence
- [ ] Record user sign-off if the selected mode requires it
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## QA Scenarios and Results

| Scenario | Expected | Observed | Pass/Fail | Notes |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |

## Evidence and Artifacts

Store and reference artifacts under:
- `/.recursive/run/<run-id>/evidence/`
  - `evidence/screenshots/` (screenshots, videos-as-files)
  - `evidence/logs/` (console/server output excerpts)
  - `evidence/perf/` (if QA included perf checks)

## QA Execution Record

QA Execution Mode: human / agent-operated / hybrid
- Agent Executor:
- Tools Used:
- Evidence:
  - `/.recursive/run/<run-id>/evidence/<file>`

## User Sign-Off

- Approved by:
- Date:
- Notes:

## Traceability
...

## Coverage Gate

- [ ] QA scenarios from Phase 2 are represented
- [ ] Observed results are recorded for all executed scenarios
- [ ] QA execution mode is declared
- [ ] Required execution metadata/evidence for that mode is present

Coverage: PASS / FAIL

## Approval Gate

- [ ] The selected QA mode's completion requirements are satisfied
- [ ] Human sign-off is present if mode is `human` or `hybrid`
- [ ] Agent execution evidence is present if mode is `agent-operated` or `hybrid`

Approval: PASS / FAIL
```

If the selected QA mode is not yet complete, keep `Approval: FAIL` and list what is pending.

## Phase 6 Template (`06-decisions-update.md`)

Required outcome:
- `/.recursive/DECISIONS.md` updated for the run
- exact ledger delta recorded in a lockable receipt
- rationale for any ledger structure changes documented

```md
Run: `/.recursive/run/<run-id>/`
Phase: `06 Decisions Update`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/05-manual-qa.md`
- `/.recursive/DECISIONS.md`
- [relevant addenda]
Outputs:
- `/.recursive/DECISIONS.md`
- `/.recursive/run/<run-id>/06-decisions-update.md`
Scope note: This document records the exact `DECISIONS.md` updates made for the completed run.

## TODO

- [ ] Read locked Phase 5 manual QA artifact
- [ ] Update `/.recursive/DECISIONS.md` with the run outcome
- [ ] Record a concise delta summary of the `DECISIONS.md` edits
- [ ] Document rationale for any structural ledger changes
- [ ] Verify run references and late-phase links are correct
- [ ] Assemble audit context bundle
- [ ] Audit receipt against final run folder and actual repo state
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Decisions Changes Applied

- Updated path or section:
- Run entry added or edited:
- Structural edits:

## Rationale

- Why these ledger changes were needed:
- Why this run belongs in this section/index:

## Resulting Decision Entry

```md
[quote or summarize only the final run entry excerpt needed for audit; prefer a short excerpt plus path over pasting large ledger sections]
```

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/05-manual-qa.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/DECISIONS.md`
- Changed files:
  - `/.recursive/DECISIONS.md`
  - final product paths reviewed

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/05-manual-qa.md`
- [relevant addenda]
- `/.recursive/DECISIONS.md`

## Earlier Phase Reconciliation

- Manual QA outcome reflected:
- Run outcome and scope reflected:
- Follow-ups and OOS reflected:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `/.recursive/DECISIONS.md`
- Actual changed files reviewed:
  - `/.recursive/DECISIONS.md`
  - final product paths reviewed
- Unexplained drift:
  - none / [explain]

## Gaps Found

- none / [list receipt or ledger gaps]

## Repair Work Performed

- none / [list repairs completed before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Phase 7 Template (`07-state-update.md`)

Required outcome:
- `/.recursive/STATE.md` updated to reflect post-change reality
- exact state delta recorded in a lockable receipt
- rationale for any interpretation changes documented

```md
Run: `/.recursive/run/<run-id>/`
Phase: `07 State Update`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/06-decisions-update.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- [relevant addenda]
Outputs:
- `/.recursive/STATE.md`
- `/.recursive/run/<run-id>/07-state-update.md`
Scope note: This document records the exact `STATE.md` changes made after the run was validated.

## TODO

- [ ] Read locked Phase 6 decisions receipt
- [ ] Update `/.recursive/STATE.md` with current truths from the validated implementation
- [ ] Record a concise delta summary of the `STATE.md` edits
- [ ] Document any major interpretation changes
- [ ] Verify the updated state matches the implemented system
- [ ] Review relevant prior recursive evidence for the affected area
- [ ] Assemble audit context bundle
- [ ] Audit receipt against final code reality and state truth
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## State Changes Applied

- Updated path or section:
- Current truth changed:
- Removed or superseded statement:

## Rationale

- Why these state changes were needed:
- Why any interpretation changed:

## Resulting State Summary

- Link or section updated: `/.recursive/STATE.md#[section]`
- Current behavior delta:
- Current limitations delta:
- Operational notes delta:

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/06-decisions-update.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- Changed files:
  - `/.recursive/STATE.md`
  - final product paths reviewed

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/06-decisions-update.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- [relevant addenda]

## Prior Recursive Evidence Reviewed

- Prior run id:
  - Docs read:
  - Reused insight:
  - Superseded or contradicted:

## Earlier Phase Reconciliation

- Decisions receipt reflected:
- Current product truths reflected:
- Known limitations reflected:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - `/.recursive/STATE.md`
- Actual changed files reviewed:
  - `/.recursive/STATE.md`
  - final product paths reviewed
- Unexplained drift:
  - none / [explain]

## Gaps Found

- none / [list missing or inaccurate state claims]

## Repair Work Performed

- none / [list repairs completed before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Phase 8 Template (`08-memory-impact.md`)

Required outcome:
- changed paths analyzed against the memory plane
- affected memory docs reviewed and updated
- uncovered changed paths handled explicitly
- final memory statuses recorded
- run-local skill usage captured before durable promotion decisions
- durable skill-memory promotions justified explicitly
- receipt remains a concise delta summary that points to final memory docs rather than duplicating them

```md
Run: `/.recursive/run/<run-id>/`
Phase: `08 Memory Impact`
Status: `DRAFT`
Inputs:
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/01-as-is.md`
- `/.recursive/run/<run-id>/02-to-be-plan.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- `/.recursive/run/<run-id>/04-test-summary.md`
- `/.recursive/run/<run-id>/05-manual-qa.md`
- `/.recursive/run/<run-id>/06-decisions-update.md`
- `/.recursive/run/<run-id>/07-state-update.md`
- `/.recursive/DECISIONS.md`
- `/.recursive/STATE.md`
- `/.recursive/memory/MEMORY.md`
- `/.recursive/memory/skills/SKILLS.md`
- [affected memory docs]
- [relevant addenda]
Outputs:
- `/.recursive/run/<run-id>/08-memory-impact.md`
- [updated memory docs]
Scope note: This document records memory freshness review and durable memory maintenance after the run is fully validated.

## TODO

- [ ] Read diff basis from `00-worktree.md`
- [ ] Compute final changed paths
- [ ] Exclude run-artifact churn unless explicitly relevant
- [ ] Match changed paths to memory doc owners/watchers
- [ ] Identify uncovered changed paths
- [ ] Downgrade affected `CURRENT` docs to `SUSPECT` before review
- [ ] Semantically review affected docs against final code + `STATE.md` + `DECISIONS.md`
- [ ] Update/create/split/deprecate memory docs as needed
- [ ] Promote durable skill lessons into `/.recursive/memory/skills/` or record why no promotion was needed
- [ ] Refresh parent/router docs if child memory changed materially
- [ ] Record final memory statuses
- [ ] Review relevant prior recursive evidence for the affected area
- [ ] Assemble audit context bundle
- [ ] Audit memory updates against diff, state, decisions, and prior memory truth
- [ ] Repair gaps and re-audit until `Audit: PASS`
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Diff Basis

- Base commit / anchor:
- Head commit / comparison target:
- Exclusions applied:

## Changed Paths Review

- Changed path:
  - Owning doc(s):
  - Watching doc(s):
  - Review result:

## Affected Memory Docs

- `/.recursive/memory/domains/<doc>.md`
  - Prior status:
  - Temporary downgrade:
  - Final status:
  - Change summary:
  - Final doc path to review:
- `/.recursive/memory/skills/<category>/<doc>.md`
  - Prior status:
  - Final status:
  - Skill lesson captured:

## Uncovered Paths

- Changed path without owner:
  - Action: [created new domain doc / explicit follow-up]
  - Follow-up path or note:

## Router and Parent Refresh

- `/.recursive/memory/MEMORY.md` changes:
- `/.recursive/memory/skills/SKILLS.md` changes:
- Parent doc updates:

## Final Status Summary

- Restored to `CURRENT`:
- Left as `SUSPECT`:
- Marked `STALE`:
- Deprecated / archived:

## Run-Local Skill Usage Capture

- Skill Usage Relevance: `relevant|not-relevant`
- Available Skills:
- Skills Sought:
- Skills Attempted:
- Skills Used:
- Worked Well:
- Issues Encountered:
- Future Guidance:
- Promotion Candidates:

## Skill Memory Promotion Review

- Durable Skill Lessons Promoted:
- Generalized Guidance Updated:
- Run-Local Observations Left Unpromoted:
- Promotion Decision Rationale:

## Audit Context

Audit Execution Mode: self-audit / subagent
Subagent Availability: available / unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/00-worktree.md`
- final validated run artifacts
- `/.recursive/DECISIONS.md`
- `/.recursive/STATE.md`
- `/.recursive/memory/MEMORY.md`
- `/.recursive/memory/skills/SKILLS.md`
- affected memory docs
- Changed files:
  - final product paths reviewed
  - memory doc paths reviewed

## Effective Inputs Re-read

- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/03-implementation-summary.md`
- `/.recursive/run/<run-id>/04-test-summary.md`
- `/.recursive/run/<run-id>/06-decisions-update.md`
- `/.recursive/run/<run-id>/07-state-update.md`
- `/.recursive/DECISIONS.md`
- `/.recursive/STATE.md`
- `/.recursive/memory/MEMORY.md`
- affected memory docs
- [relevant addenda]

## Prior Recursive Evidence Reviewed

- Prior run id:
  - Docs read:
  - Reused insight:
  - Superseded or contradicted:

## Earlier Phase Reconciliation

- Final diff vs memory ownership:
- State update vs memory truth:
- Decisions update vs memory truth:

## Worktree Diff Audit

- Diff basis used: `git diff --name-only <base-commit>..HEAD`
- Base branch:
- Worktree branch:
- Base commit:
- Planned or claimed changed files:
  - memory-impact targets
- Actual changed files reviewed:
  - final product paths reviewed
  - memory doc paths reviewed
- Unexplained drift:
  - none / [explain]

## Gaps Found

- none / [list uncovered paths, stale memory, or unresolved status transitions]

## Repair Work Performed

- none / [list repairs completed before re-audit]

## Audit Verdict

- Summary:
- Audit: FAIL / PASS

## Traceability
...

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Addenda Templates

## Stage-Local Addendum

File name:
- `<base>.addendum-01.md`

```md
Run: `/.recursive/run/<run-id>/`
Phase: `<current phase>`
Status: `DRAFT`
Inputs:
- `<base artifact>`
Outputs:
- `/.recursive/run/<run-id>/addenda/<base>.addendum-01.md`
Scope note: This addendum supplements phase-local content without changing locked history.

## TODO

- [ ] Add the missing information
- [ ] Update Traceability/Coverage implications in the current phase artifact (if needed)
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Addendum Content

- Added/clarified information:
- Rationale:
- Impact on phase output:

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Upstream-Gap Addendum

File name:
- `<current>.upstream-gap.<prior>.addendum-01.md`

```md
Run: `/.recursive/run/<run-id>/`
Phase: `<current phase>`
Status: `DRAFT`
Inputs:
- `<current phase inputs>`
- `<locked prior artifact>`
Outputs:
- `/.recursive/run/<run-id>/addenda/<current>.upstream-gap.<prior>.addendum-01.md`
Scope note: This addendum records a discovered gap in a locked upstream artifact.

## TODO

- [ ] Record the upstream gap precisely
- [ ] Add discovery evidence (commands, files, outputs)
- [ ] State impact and compensation plan
- [ ] Update current-phase planning/implementation accordingly
- [ ] Complete Coverage Gate checklist
- [ ] Complete Approval Gate checklist

## Gap Statement

- Missing or incorrect upstream content:

## Discovery Evidence

- How the gap was found:
- Supporting evidence:

## Impact

- Impact on current phase:
- Impact on later phases:

## Compensation Plan

- Tests, validation, or process compensations applied now:

## Traceability Impact

- Affected requirements: `R#`, `R#`

## Coverage Gate
...
Coverage: PASS

## Approval Gate
...
Approval: PASS
```

## Artifact Linting (Structure + TODO Discipline)

Before locking (or when a lock verification fails unexpectedly), lint the run artifacts for required header fields, required section headings, and TODO completion rules:

```powershell
# Python (cross-platform):
python ./.agents/skills/recursive-mode/scripts/lint-recursive-run.py --run-id "<run-id>"
# Or, when running from this repo:
python ./scripts/lint-recursive-run.py --run-id "<run-id>"
python3 ./.agents/skills/recursive-mode/scripts/lint-recursive-run.py --run-id "<run-id>"
python3 ./scripts/lint-recursive-run.py --run-id "<run-id>"

# Treat WARN as FAIL
python ./.agents/skills/recursive-mode/scripts/lint-recursive-run.py --run-id "<run-id>" --strict
python ./scripts/lint-recursive-run.py --run-id "<run-id>" --strict
python3 ./.agents/skills/recursive-mode/scripts/lint-recursive-run.py --run-id "<run-id>" --strict
python3 ./scripts/lint-recursive-run.py --run-id "<run-id>" --strict

# Lint specific run
.\.agents\skills\recursive-mode\scripts\lint-recursive-run.ps1 -RunId "<run-id>"
# Or, when running from this repo:
.\scripts\lint-recursive-run.ps1 -RunId "<run-id>"

# Treat WARN as FAIL
.\.agents\skills\recursive-mode\scripts\lint-recursive-run.ps1 -RunId "<run-id>" -Strict
.\scripts\lint-recursive-run.ps1 -RunId "<run-id>" -Strict
```

## Locking Commands

Preferred:

```powershell
# Python (cross-platform)
python ./.agents/skills/recursive-mode/scripts/recursive-lock.py --run-id "<run-id>" --artifact "<artifact>.md"
# Or, when running from this repo:
python ./scripts/recursive-lock.py --run-id "<run-id>" --artifact "<artifact>.md"
python3 ./.agents/skills/recursive-mode/scripts/recursive-lock.py --run-id "<run-id>" --artifact "<artifact>.md"
python3 ./scripts/recursive-lock.py --run-id "<run-id>" --artifact "<artifact>.md"

# PowerShell
.\.agents\skills\recursive-mode\scripts\recursive-lock.ps1 -RunId "<run-id>" -Artifact "<artifact>.md"
# Or, when running from this repo:
.\scripts\recursive-lock.ps1 -RunId "<run-id>" -Artifact "<artifact>.md"
```

The lock command is the primary supported path. It must refuse to lock artifacts whose required gates or lint-critical structure are still invalid.

Manual fallback for hash computation only:

PowerShell:

```powershell
$p = '.recursive/run/<run-id>/<artifact>.md'
$t = Get-Content -LiteralPath $p -Raw -Encoding UTF8
$n = ($t -replace "`r`n","`n") -replace "(?m)^LockHash:.*(?:`n|$)",""
$b = [System.Text.Encoding]::UTF8.GetBytes($n)
$h = [System.Security.Cryptography.SHA256]::Create().ComputeHash($b)
($h | ForEach-Object { $_.ToString("x2") }) -join ""
```

Shell:

```bash
sed '/^LockHash:/d' .recursive/run/<run-id>/<artifact>.md | tr -d '\r' | sha256sum
```

## Common Failure Modes (Use as Pre-Lock Checklist)

- Missing one or more effective-input addenda under `Inputs`.
- Relevant addenda exist but are not re-read in `## Effective Inputs Re-read`.
- Relevant addenda exist but are not reconciled in `## Earlier Phase Reconciliation`.
- Coverage Gate says PASS but does not map every `R#`.
- Approval Gate says PASS with unresolved blockers.
- `Traceability` references vague evidence instead of concrete files/commands.
- Artifact locked without `LockedAt` and `LockHash`.
- **LockHash does not match SHA-256 of normalized content (tampering detected).**
- Editing locked prior-phase artifacts instead of writing addenda.
- Delegated review has a bundle file but the written review does not cite upstream artifacts, relevant addenda, or changed files/code refs from that bundle.
- Diff audit is failing on transient runtime noise because incidental cache files were mistaken for meaningful repo changes.
- Working on main/master branch without explicit consent documented.
- Worktree directory not git-ignored (project-local worktrees).
- Baseline tests failing (pre-existing issues not documented).

## Lock Verification

### Automated Verification

Use the provided script to verify all locks in a run:

```bash
# Verify specific run
python ./.agents/skills/recursive-mode/scripts/verify-locks.py --run-id "<run-id>"
# Or, when running from this repo:
python ./scripts/verify-locks.py --run-id "<run-id>"
python3 ./.agents/skills/recursive-mode/scripts/verify-locks.py --run-id "<run-id>"
python3 ./scripts/verify-locks.py --run-id "<run-id>"

# Fix incorrect hashes (use with caution)
python ./.agents/skills/recursive-mode/scripts/verify-locks.py --run-id "<run-id>" --fix
# Or, when running from this repo:
python ./scripts/verify-locks.py --run-id "<run-id>" --fix
python3 ./.agents/skills/recursive-mode/scripts/verify-locks.py --run-id "<run-id>" --fix
python3 ./scripts/verify-locks.py --run-id "<run-id>" --fix
```

```powershell
# Verify specific run
.\.agents\skills\recursive-mode\scripts\verify-locks.ps1 -RunId "<run-id>"
# Or, when running from this repo:
.\scripts\verify-locks.ps1 -RunId "<run-id>"

# Fix incorrect hashes (use with caution)
.\.agents\skills\recursive-mode\scripts\verify-locks.ps1 -RunId "<run-id>" -Fix
# Or, when running from this repo:
.\scripts\verify-locks.ps1 -RunId "<run-id>" -Fix
```

### Manual Verification

Compute SHA-256 hash:

**PowerShell:**
```powershell
$p = '.recursive/run/<run-id>/<artifact>.md'
$t = Get-Content -LiteralPath $p -Raw -Encoding UTF8
$n = ($t -replace "`r`n","`n") -replace "(?m)^LockHash:.*(?:`n|$)",""
$b = [System.Text.Encoding]::UTF8.GetBytes($n)
$h = [System.Security.Cryptography.SHA256]::Create().ComputeHash($b)
($h | ForEach-Object { $_.ToString("x2") }) -join ""
```

**Shell:**
```bash
sed '/^LockHash:/d' .recursive/run/<run-id>/<artifact>.md | tr -d '\r' | sha256sum
```

Compare computed hash with `LockHash` in artifact header. They must match exactly.


