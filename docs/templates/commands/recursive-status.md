# recursive-status (prompt template)

> Paste this into chat if your agent does not support custom slash commands.

## Usage Pattern

```text
Check recursive-mode status: [run-id]
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/recursive-status.py" --repo-root . --run-id "<run-id>"
python "<SKILL_DIR>/scripts/recursive-status.py" --repo-root .
python3 "<SKILL_DIR>/scripts/recursive-status.py" --repo-root . --run-id "<run-id>"

powershell -ExecutionPolicy Bypass -File "<SKILL_DIR>/scripts/recursive-status.ps1" -RepoRoot . -RunId "<run-id>"
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-status.ps1" -RepoRoot . -RunId "<run-id>"
```

## What It Shows

- Current phase and lock state
- Audit blockers for the active phase
- Workflow profile
- Lock-chain status
- Evidence directory summary
- Phase-scoped diff-audit readiness and next steps through Phase 8
- Phase 3 TDD blockers such as missing RED/GREEN evidence or an invalid pragmatic exception
- Phase 3.5 review-bundle blockers such as missing `Review Bundle Path` or a bundle file that does not exist
- Phase 5 QA-mode blockers such as missing human sign-off or missing agent execution evidence

## Example Output Shape

```text
Recursive Run: <run-id>
===================================

Workflow Profile: recursive-mode-audit-v2

Phase Status:
  Phase 0 (Requirements)     [LOCKED]
  Phase 0 (Worktree)         [LOCKED]
  Phase 1 (AS-IS)            [LOCKED]
  Phase 2 (TO-BE Plan)       [DRAFT]
  Phase 8 (Memory)           [PENDING]

Current Phase: 2 (TO-BE Plan)
Status: DRAFT
```

## Implementation

1. Scan `/.recursive/run/<run-id>/`
2. Check each artifact for existence, lock status, audit status, and gate status
3. Determine the current active phase
4. Print next-step guidance using the recursive-mode path layout
5. Attribute diff blockers to the phase that owns them instead of retroactively blaming earlier locked phases for late control-plane or memory files
6. For Phase 3.5, report missing or invalid `Review Bundle Path` before lock time
