---
name: recursive-subagent
description: 'Use when recursive-mode work may benefit from delegated audit, review, or bounded implementation support. This skill prioritizes phase-auditor, traceability-auditor, code-reviewer, memory-auditor, and test-reviewer roles, with mandatory self-audit fallback when subagents are unavailable.'
---

# recursive-subagent

Use this skill to decide whether subagents help a recursive-mode phase and to enforce the handoff contract when they do.

This skill does not relax the canonical workflow. The main agent remains responsible for:

- one active recursive phase at a time
- full audit rigor before lock
- rejecting incomplete or context-free subagent output
- falling back to `self-audit` when subagents are unavailable

## Priority Of Use

Use subagents in this order of value:

1. phase auditor
2. traceability auditor
3. code reviewer
4. memory auditor
5. test reviewer
6. bounded implementer for truly disjoint write scopes

Do not treat subagents as required infrastructure. They are optional infrastructure, but delegated audit/review is the preferred default when subagents are available and the context bundle is complete.

## Capability Detection Is A Hard Control Point

At the start of a phase where delegation is being considered, determine whether the environment actually supports subagents/tasks.

If subagents are unavailable:

- record `Subagent Availability: unavailable`
- record `Audit Execution Mode: self-audit`
- perform the same audit locally

If subagents are available:

- record `Subagent Availability: available`
- delegate by default for audit/review work when the context bundle is complete
- if the controller still chooses `self-audit`, record a concrete `Delegation Override Reason`
- keep the same audit checklist and acceptance standard

Before delegating, read `/.recursive/memory/skills/SKILLS.md` plus the relevant skill-memory shards for delegated review, review-bundle fit, and stale-context risks.

Never skip or weaken an audit because delegation is unavailable.

## Canonical Constraints

- Recursive phases stay sequential. There is exactly one active phase per run.
- Subagents may help inside the active phase; they do not authorize parallel phase work.
- Parallel write-capable implementation is allowed only for explicitly independent sub-phases with disjoint write scopes and no blocking dependency chain.
- Audit, review, and read-only verification are the safest default delegation modes.

## Delegated Audit Contract

A delegated audit is valid only when the controller passes a complete context bundle. Prefer a canonical review bundle file under `/.recursive/run/<run-id>/evidence/review-bundles/` so the handoff is durable and repeatable.

The controller must pass all of:

1. phase name and artifact path
2. current phase draft
3. exact upstream artifact paths that must be reread
4. relevant addendum paths
5. relevant prior recursive evidence and memory refs
6. diff basis from `00-worktree.md`
7. changed file list
8. targeted code file paths or file groups to inspect
9. relevant control-plane docs when needed
10. exact audit questions/checklist for the phase
11. required output shape including findings and verdict

Vague delegation such as "review this phase" or "audit implementation" is invalid.

If any required item is missing, do not delegate. Perform the audit yourself.

If repairs materially change reviewed scope, changed files, or evidence, refresh the bundle before re-audit.

## Controller Checklist

Before dispatch:

- [ ] Confirm delegation is optional, not required
- [ ] Confirm the phase is still the single active phase
- [ ] Confirm the handoff bundle is complete
- [ ] Confirm the canonical review bundle path exists when delegation is being recorded in a phase artifact
- [ ] Confirm a durable subagent action record will be written under `/.recursive/run/<run-id>/subagents/`
- [ ] Confirm the target subagent role matches the task
- [ ] Confirm write scopes are disjoint before any write-capable delegation

Before accepting a result:

- [ ] Verify the subagent read the named upstream artifacts
- [ ] Verify the subagent read the review bundle or its full equivalent
- [ ] Verify the subagent returned enough detail to populate the action record fields
- [ ] Verify `Current Artifact` points at a stable reviewed artifact or refresh the record after any material draft edits
- [ ] Verify the output cites the diff basis and changed files
- [ ] Verify the bundle still matches the current artifact hash after any repairs
- [ ] Verify the output contains concrete findings or an explicit no-findings conclusion
- [ ] Verify the output includes requirement/plan alignment comments where relevant
- [ ] Verify the output ends with a clear verdict
- [ ] Verify any claimed file impact, artifact impact, or findings against the actual worktree diff, actual artifacts, and earlier locked recursive docs before acceptance
- [ ] Verify the phase artifact records `Reviewed Action Records`, `Main-Agent Verification Performed`, `Acceptance Decision`, `Refresh Handling`, and `Repair Performed After Verification`
- [ ] Reject action records that leave claimed file impact or claimed artifact impact as `none` for materially contributing work
- [ ] Reject the output if it is context-free, hand-wavy, or missing required checks

## Recommended Roles

### Phase Auditor

Use for audited phases that need an independent pass over:

- current draft
- upstream locked artifacts
- git diff vs recorded baseline
- requirement coverage
- gaps, drift, and repair needs

### Traceability Auditor

Use when checking that downstream artifacts explicitly cover every in-scope `R#` and do not hide behind vague summaries.

### Code Reviewer

Use for Phase 3.5 or high-risk Phase 3/4 audits.

Expected checks:

- requirements vs implementation
- plan vs implementation
- git diff vs claimed scope
- code quality and maintainability
- test adequacy and TDD compliance

### Memory Auditor

Use in Phase 8 to verify that touched paths, memory status transitions, and router updates match the final validated repo state.

### Test Reviewer

Use in Phase 4 to audit test adequacy, exact commands, evidence capture, and whether the implementation is truly complete before test results are trusted.

### Implementer

Use only when Phase 2 defines truly independent sub-phases with concrete file ownership.

The controller must assign ownership explicitly and must not present this as broad "parallel mode" by default.

## Handoff Template

Use this structure whenever you delegate an audit or review. Prefer generating the bundle with `recursive-review-bundle` and then passing the bundle path plus any phase-specific instructions:

```md
Review Bundle Path: `/.recursive/run/<run-id>/evidence/review-bundles/<bundle>.md`
Phase: `03.5 Code Review`
Artifact path: `/.recursive/run/<run-id>/03.5-code-review.md`
Role: `phase-auditor`
Audit execution expectation: return findings plus `Audit: PASS` or `Audit: FAIL`

Bundle freshness check:
- confirm changed files, evidence refs, and audit questions still match the latest repaired draft
- confirm relevant addenda are included; do not hand-wave plan or requirement amendments that live in addenda

Additional audit questions:
- Which `R#` are still incomplete?
- Which changed files drift from the plan?
- Is required evidence missing?
- Is repair required before lock?

Action-record expectation:
- return enough structured detail for `recursive-subagent-action`
- prefer the stable reviewed artifact for `Current Artifact` when recording review/audit work
- cite upstream artifacts reread, relevant addenda, prior recursive evidence, changed files or code refs reviewed, claimed findings, and verification handoff items
```

## Self-Audit Fallback Pattern

When subagents are unavailable, reuse the same checklist in the phase artifact and record:

```md
## Audit Context

Audit Execution Mode: self-audit
Subagent Availability: unavailable
Audit Inputs Provided:
- `/.recursive/run/<run-id>/...`
```

Then complete the full audit loop locally:

1. draft or revise the phase artifact
2. reread upstream artifacts
3. reconcile against the recorded diff basis and changed files
4. record gaps
5. repair the work
6. rerun the audit
7. set `Audit: PASS` only when the phase is actually ready to lock

## Output Rejection Rules

Reject a delegated result if any of the following are true:

- it does not cite the artifact path or phase name
- it does not cite the review bundle path or clearly restate the same bundle contents
- it does not mention the upstream artifacts reread
- it ignores relevant addenda that were part of the effective input set
- it ignores relevant prior recursive evidence or memory refs that were part of the bundle
- it does not review the diff basis or changed files
- it does not cite changed files or code refs in the review narrative
- it claims delegated success but the controller did not verify those claims against actual files, actual artifacts, and the actual diff-owned scope
- it cannot be translated into a durable subagent action record without guessing
- it does not address requirement or plan alignment where required
- it gives only generic praise with no grounded findings
- it has no explicit verdict

## References

- Canonical workflow: `/.recursive/RECURSIVE.md`
- Artifact templates: `references/artifact-template.md`
- Code reviewer prompt: `agents/code-reviewer.md`
- Implementer prompt: `agents/implementer.md`
