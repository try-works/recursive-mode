---
name: recursive-spec
description: 'Approval-gated, repo-aware requirements/spec authoring for new recursive-mode runs. Use when the user wants help creating a plan, spec, scope, or requirements for work that does not yet have a run, especially prompts like "create a plan", "help me plan", "create a spec", "write requirements", or similar derivatives.'
---

# recursive-spec

Use this skill to co-author a repo-aware `00-requirements.md` for a new recursive-mode run.

This skill is for **requirements/spec authoring before implementation starts**. It does not replace `/.recursive/RECURSIVE.md`, and it should not skip ahead to Phase 2 planning or Phase 3 implementation.

## Primary Use Case

Use `recursive-spec` when the user wants help shaping work before a run exists, especially with prompts like:

- `create a plan`
- `help me plan`
- `create a spec`
- `write requirements`
- `spec this out`
- `scope this`

The important signal is **plan/spec language for a new run**, not implementation of an existing run.

## Conversation Contract

When the trigger is detected:

1. First ask whether the user wants help creating a spec for a recursive run.
2. If the user replies positively, ask: `What do you want to do?`
3. Then gather context, read the repo, and co-author the requirements.

Do not jump straight into writing `00-requirements.md` before the user confirms they want spec help.

## Draft Handling Before Approval

Until the user explicitly approves the spec:

- keep the draft outside the repository worktree
- prefer a temporary session artifact or scratch file
- do **not** create `/.recursive/run/<run-id>/`
- do **not** write `00-requirements.md`

If the user rejects the draft, revise it or discard the temporary draft artifact. Do not leave behind a half-approved run folder.

## Required Read Behavior

Before drafting requirements, read:

1. `/.recursive/STATE.md`
2. `/.recursive/DECISIONS.md`
3. `/.recursive/memory/MEMORY.md`
4. relevant memory shards only when they actually matter
5. the most relevant code and tests for the requested area

The skill should be **repo-aware**, not a blind questionnaire. Use the control-plane docs to understand current truth and the codebase to understand actual surfaces, coupled modules, existing tests, and likely boundaries.

## Authoring Flow

Use a guided interview. Ask one focused question at a time when the answer is not already grounded by repo docs or code.

Recommended sequence:

1. Goal and user outcome
2. Task type: feature, bugfix, refactor, migration, investigation
3. Affected subsystem or files
4. In-scope requirements (`R#`)
5. Observable acceptance criteria for each requirement
6. Edge cases, failure paths, and exclusions
7. Constraints, fixed decisions, and boundaries
8. Assumptions or open unknowns

Prefer proposing draft wording and asking the user to confirm or correct it rather than asking the user to author the whole document from scratch.

## Quality Rules

Borrow the strongest authoring ideas from contract-first workflows, but keep the output native to recursive-mode:

- start with user intent and desired outcome
- separate fixed decisions from open questions
- define deterministic, observable acceptance criteria
- include exception and failure-path thinking instead of only the happy path
- make boundaries concrete enough to guide later AS-IS analysis and planning
- keep out-of-scope items explicit

Do **not** introduce a separate `.spec` DSL or a second workflow format.

## Output Contract

The finished output should become:

- `/.recursive/run/<run-id>/00-requirements.md`

Use the repository's native Phase 0 requirements structure:

- `## Requirements`
- `## Out of Scope`
- `## Constraints`
- `## Assumptions`

Within `## Requirements`, each `R#` should include:

- a short title
- a clear description
- observable acceptance criteria bullets

## Run Creation Rule

Do not create the run folder immediately.

1. Draft and refine the requirements with the user first.
2. Keep the draft in a temporary non-repo artifact until approval.
3. Confirm the user approves the spec and that it is complete enough to proceed.
4. Create the run with `scripts/recursive-init.py` or `scripts/recursive-init.ps1`.
5. Replace the scaffolded `00-requirements.md` with the approved requirements content.

This keeps the run artifact grounded in user-approved requirements instead of half-formed notes.

## Boundaries

- Stay focused on `00-requirements.md` authoring for a new run.
- Do not silently convert this into Phase 2 planning.
- Do not start implementation just because the requirements became clear.
- Do not skip code reading when repository structure matters to scope or constraints.
- Do not create a run until the user-approved spec is ready to write.
- Do not write repository requirements artifacts from an unapproved draft.

## References

- `/.recursive/RECURSIVE.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- `/.recursive/memory/MEMORY.md`
- `../../references/artifact-template.md`
- `./references/patterns.md`
