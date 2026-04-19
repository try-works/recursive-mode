# recursive-init (prompt template)

> Paste this into chat if your agent does not support custom slash commands.

## Usage Pattern

```text
Initialize recursive run: <run-id> [options]
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/recursive-init.py" --repo-root . --run-id "<run-id>" --template feature
python "<SKILL_DIR>/scripts/recursive-init.py" --repo-root . --run-id "<run-id>" --template bugfix --from-issue "#123"
python3 "<SKILL_DIR>/scripts/recursive-init.py" --repo-root . --run-id "<run-id>" --template feature

powershell -ExecutionPolicy Bypass -File "<SKILL_DIR>/scripts/recursive-init.ps1" -RepoRoot . -RunId "<run-id>" -Template feature
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-init.ps1" -RepoRoot . -RunId "<run-id>" -Template feature
```

## What It Does

1. Creates `/.recursive/run/<run-id>/`
2. Generates `00-requirements.md`
3. Generates a prefilled `00-worktree.md` scaffold with executable Phase 0 diff-basis fields when git state can be resolved
4. Validates that the recorded Phase 0 diff basis is executable against live git state before returning success
5. Creates `addenda/`, `subagents/`, `router-prompts/`, and `evidence/` subfolders
6. Creates canonical evidence subfolders including `review-bundles/` and `router/`
7. Marks the run as `recursive-mode-audit-v2`

## Output

- `/.recursive/run/<run-id>/00-requirements.md`
- `/.recursive/run/<run-id>/00-worktree.md`
- `/.recursive/run/<run-id>/addenda/`
- `/.recursive/run/<run-id>/subagents/`
- `/.recursive/run/<run-id>/router-prompts/`
- `/.recursive/run/<run-id>/evidence/{screenshots,logs,perf,traces,review-bundles,router,other}/`

## Diff Basis Notes

- The generated `00-worktree.md` uses the current `HEAD` commit as the safe default baseline when possible.
- `Normalized baseline`, `Normalized comparison`, and `Normalized diff command` are treated as executable source-of-truth fields.
- If you later change the baseline reference during Phase 0, update every diff-basis field and rerun lint before locking.

## Next Step

```text
Implement requirement '<run-id>'
```
