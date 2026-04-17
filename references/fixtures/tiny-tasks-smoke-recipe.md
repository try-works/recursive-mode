# Tiny Tasks Smoke Recipe

Use this fixture for disposable maintainer smoke tests of `recursive-mode`.

It is intentionally small, deterministic, and standard-library only.

## Fixture App

- Language: Python
- Test runner: `python -m unittest -q`
- Product files:
  - `tiny_tasks.py`
  - `test_tiny_tasks.py`

## Base Behavior

The base commit contains a tiny summary helper that reports only the total task count.

Expected base output:

```text
2 total
```

## Feature Change Under Test

Add completed and active counts to the summary output.

Expected post-change output:

```text
2 total, 1 completed, 1 active
```

Expected changed product files:

- `tiny_tasks.py`
- `test_tiny_tasks.py`

## Required Run Evidence

Expected RED evidence path:

- `/.recursive/run/<run-id>/evidence/logs/red/red-cycle-01.log`

Expected GREEN evidence path:

- `/.recursive/run/<run-id>/evidence/logs/green/green-cycle-01.log`

Expected manual QA evidence path:

- `/.recursive/run/<run-id>/evidence/logs/manual-qa-agent.log`

Expected preview log path used for Phase 5 scaffolding:

- `/.recursive/run/<run-id>/evidence/logs/preview-server.log`

Expected review bundle path:

- `/.recursive/run/<run-id>/evidence/review-bundles/03-5-code-review-code-reviewer.md`

Expected delegated-review action-record path for the dedicated subagent scenario:

- `/.recursive/run/<run-id>/subagents/delegated-review-action-record.md`

## Expected Workflow Shape

- Workflow profile: `recursive-mode-audit-v2`
- TDD mode: `strict`
- QA execution mode: `agent-operated`
- Optional review phase present: `03.5-code-review.md`
- Late receipts are compact delta receipts:
  - `06-decisions-update.md`
  - `07-state-update.md`
  - `08-memory-impact.md`

## Late-Phase Control-Plane Changes

The smoke run should update:

- `/.recursive/DECISIONS.md`
- `/.recursive/STATE.md`
- `/.recursive/memory/MEMORY.md`
- `/.recursive/memory/domains/TINY-TASKS.md`

## Positive Assertions

- The run reaches locked Phase 8 without custom lock helpers.
- Python `lint`, `status`, and `verify-locks` succeed.
- PowerShell `lint`, `status`, and `verify-locks` succeed on the same completed disposable repo.
- In the dedicated `subagent` scenario, `03.5-code-review.md` remains `Audit Execution Mode: subagent` through lock and final completion, and the canonical action record remains present under `subagents/`.

## Negative Assertions For Full Smoke

- Removing RED evidence causes strict Phase 3 lint and lock failure.
- Breaking `Review Bundle Path` causes Phase 3.5 lint and status failure.
- A malformed delegated-review action record causes both toolchains to fail clearly.
- Switching Phase 5 to `human` without sign-off causes lock failure.
