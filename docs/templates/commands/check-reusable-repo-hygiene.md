# check-reusable-repo-hygiene

> Maintainer-facing check for reusable workflow/skill repos that should not ship recursive run residue.

## Usage

```powershell
python "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.py" --repo-root .
pwsh -NoProfile -File "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.ps1" -RepoRoot .
```

Optional strict cleanliness check:

```powershell
python "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.py" --repo-root . --require-clean-git
pwsh -NoProfile -File "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.ps1" -RepoRoot . -RequireCleanGit
```

## What It Checks

- `/.recursive/run/` contains only `.gitkeep`
- no concrete `/.recursive/run/<run-id>/` references remain in committed text files
- no concrete temp-directory residue remains in committed text files
- no generated local residue such as `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, or `.ruff_cache/` remains in the repo tree
- optional `git status --porcelain` cleanliness when `--require-clean-git` is selected

Interpretation:

- default mode: repo-content hygiene only
- `--require-clean-git`: final handoff check for a reusable skill/workflow repo snapshot

Use this before calling a reusable skill/workflow repo clean.
