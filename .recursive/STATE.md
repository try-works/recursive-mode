# STATE.md

## Current State

- The repository now uses `/.recursive/RECURSIVE.md` as the single canonical workflow specification.
- The workflow profile in active use is `recursive-mode-audit-v1`.
- Executable diff-basis normalization is implemented across lint, status, review-bundle generation, and lock-time validation.
- Audited phases now require status-specific, machine-checkable `Requirement Completion Status` entries rather than traceability-only completion claims.
- Delegated review is grounded by canonical review bundles, prior recursive evidence, and durable subagent action records under `/.recursive/run/<run-id>/subagents/`, with explicit main-agent verification recorded in the phase artifact.
- Skill memory is available as an optional durable part of the memory plane via `/.recursive/memory/skills/`, with generic router/index support and category directories for intentionally promoted reusable guidance.
- The maintained smoke harness lives in `scripts/test-recursive-mode-smoke.py` and `scripts/test-recursive-mode-smoke.ps1`, supports `python`, `powershell`, and `mixed` toolchain modes, and records lazy PowerShell fallback/skip behavior.
- `scripts/install-recursive-mode.py` and `scripts/install-recursive-mode.ps1` scaffold the skill-memory router and category directories, and late closeout uses `scripts/recursive-closeout.py` / `.ps1` to seed audited Phase 4-8 receipts with machine-checkable requirement fields.

## Notes

- Reusable workflow docs in this repository should remain generic. Do not check in self-run control-plane history, run artifacts, or run-derived memory unless that is an intentional product requirement.
