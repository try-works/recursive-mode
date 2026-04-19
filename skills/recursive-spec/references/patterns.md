# recursive-spec authoring patterns

## Table of Contents

- [Purpose](#purpose)
- [Interaction Pattern](#interaction-pattern)
- [Temporary Draft Rule](#temporary-draft-rule)
- [Required Inputs To Gather](#required-inputs-to-gather)
- [Repo-Aware Reading Heuristics](#repo-aware-reading-heuristics)
- [Requirement Writing Rules](#requirement-writing-rules)
- [Edge-Case Rule](#edge-case-rule)
- [Mapping To `00-requirements.md`](#mapping-to-00-requirementsmd)
- [Run Creation Rule](#run-creation-rule)

## Purpose

Use this reference when helping a user turn a vague request into a strong `00-requirements.md` for a new recursive-mode run.

The output stays native to recursive-mode. Do not switch into a separate `.spec` DSL.

## Interaction Pattern

1. Detect plan/spec wording.
2. Ask whether the user wants help creating a spec for a recursive run.
3. If yes, ask what they want to do.
4. Read recursive control docs and the relevant code/tests.
5. Ask only the missing questions needed to finish the requirements.
6. Draft the requirements in repo-native format in a temporary non-repo artifact.
7. Create the run only after the user approves the final spec.

## Temporary Draft Rule

Before approval:

- keep the draft in session state or another temporary artifact outside the repo
- do not create `/.recursive/run/<run-id>/`
- do not write `00-requirements.md`

If the user does not approve the draft, revise or discard the temporary artifact.

## Required Inputs To Gather

Minimum authoring inputs:

- desired outcome
- task type
- in-scope changes
- acceptance criteria
- out-of-scope items
- constraints and fixed decisions
- assumptions or open unknowns

## Repo-Aware Reading Heuristics

Before drafting, prefer reading:

- current state and decisions docs
- existing tests for the affected area
- code paths most likely to change
- nearby README or reference docs when the subsystem has them

If the request is broad, read enough code to identify realistic boundaries before proposing `R#`.

## Requirement Writing Rules

Good `R#` entries are:

- specific
- observable
- implementation-neutral unless a decision is already fixed
- testable later in AS-IS, plan, implementation, and verification phases

Weak:

```md
### `R1` Better reporting

Description: Improve reporting.
Acceptance criteria:
- Reporting is better.
```

Strong:

```md
### `R1` CSV export for weekly summary

Description: Add a weekly summary export so users can download the currently displayed report as CSV without changing the on-screen view.
Acceptance criteria:
- User can export the weekly summary from the existing report page.
- Export includes the same date range currently selected in the UI.
- Export preserves the existing report page behavior when the export action is not used.
```

## Edge-Case Rule

Do not stop at one happy path requirement.

If the request implies validation, errors, empty states, fallback behavior, migration risk, or backward compatibility constraints, surface them explicitly in:

- requirement acceptance criteria
- out-of-scope items
- constraints
- assumptions

## Mapping To `00-requirements.md`

Use this shape:

```md
## Requirements

### `R1` <short title>

Description:
Acceptance criteria:
- ...

## Out of Scope

- `OOS1`: ...

## Constraints

- ...
```

Useful adaptation patterns:

- fixed architecture choice -> `## Constraints`
- forbidden change area -> `## Constraints`
- user explicitly defers a follow-up -> `## Out of Scope`
- uncertainty that must be resolved before locking -> confirm it or convert it into a concrete requirement, constraint, or out-of-scope note

## Run Creation Rule

After the user approves the finished spec:

1. create a new run with `recursive-init`
2. replace the scaffolded `00-requirements.md`
3. leave the run ready for Phase 0 / Phase 1 handoff

Before approval, the draft belongs in temporary session storage rather than the repository.
