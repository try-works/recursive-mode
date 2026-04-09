# test-recursive-mode-smoke (maintainer command)

> Maintainer-facing regression harness for disposable recursive-mode validation.

## Usage Pattern

```text
Run recursive-mode smoke tests [quick|full|subagent] [python|powershell|mixed]
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/test-recursive-mode-smoke.py" --scenario quick --toolchain mixed
python "<SKILL_DIR>/scripts/test-recursive-mode-smoke.py" --scenario full --toolchain python --keep-temp
python "<SKILL_DIR>/scripts/test-recursive-mode-smoke.py" --scenario subagent --toolchain mixed

pwsh -NoProfile -File "<SKILL_DIR>/scripts/test-recursive-mode-smoke.ps1" -Scenario quick -Toolchain mixed
pwsh -NoProfile -File "<SKILL_DIR>/scripts/test-recursive-mode-smoke.ps1" -Scenario full -Toolchain powershell -KeepTemp
pwsh -NoProfile -File "<SKILL_DIR>/scripts/test-recursive-mode-smoke.ps1" -Scenario subagent -Toolchain mixed
```

## What It Does

- Creates a disposable temp git repo
- Bootstraps recursive-mode into that repo
- Creates a tiny Python fixture app and a small feature change
- Captures RED and GREEN evidence logs
- Records preflight toolchain decisions, detected executables, and skipped parity paths when applicable
- Scaffolds Phases 4-8 through `recursive-closeout` so late-phase receipts start from the supported helper path
- Generates a canonical review bundle
- Locks artifacts through Phase 8 using the supported lock command
- Runs `lint`, `status`, and `verify-locks`
- In `full` mode, runs targeted negative regressions for strict TDD, review bundle validity, context-free reviews, effective-input addenda handling, and QA sign-off requirements
- In `subagent` mode, proves the dedicated delegated-review path end to end by keeping `03.5-code-review.md` bundle-backed and `Audit Execution Mode: subagent` through lock and final closeout
- Proves diff audit ignores transient runtime noise such as `__pycache__/` and common test caches

## Important Safety Property

Every external command is run with an explicit timeout so the harness fails fast instead of hanging indefinitely.
On Windows, run the harness from the real filesystem path rather than from `subst` or mapped-drive aliases, especially if the evaluated project uses Vite or Vitest.

## Useful Flags

- `--scenario quick|full|subagent`
- `--toolchain python|powershell|mixed`
- `--temp-root <dir>`
- `--keep-temp`
- `--command-timeout <seconds>`

`both` remains accepted as a backward-compatible alias for `mixed`, but maintainers should prefer `mixed` in docs and scripts.

Toolchain behavior:

- `python` -> Python path only; works even when PowerShell is unavailable
- `powershell` -> requires a PowerShell executable
- `mixed` -> always runs the Python path and adds PowerShell parity checks only when PowerShell is available

Success interpretation:

- preflight success -> toolchain selection, executable discovery, and skip/fallback decisions were recorded
- bootstrap success -> the disposable repo was created and `install-recursive-mode` completed
- quick smoke success -> the positive end-to-end path completed
- full smoke success -> the positive path plus the negative regression suite completed
- mixed partial success -> Python completed and PowerShell parity was skipped explicitly because PowerShell was unavailable

## Fixture Reference

The checked-in fixture recipe is:

- `references/fixtures/tiny-tasks-smoke-recipe.md`

For richer browser-local evaluations, also consult:

- `references/local-first-web-app-checklist.md`
