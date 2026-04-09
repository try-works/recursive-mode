# recursive-mode Maintainer Notes

This file is for maintainers of the `recursive-mode` repository itself.

It is not the canonical workflow spec. The canonical workflow remains:

- `/.recursive/RECURSIVE.md`

It is also not the public package landing page. The GitHub-facing overview remains:

- `/README.md`

Use this file for maintainer-oriented commands, smoke-harness notes, and repo-internal packaging guidance.

If you just need a lightweight routing/index doc for what to read under `/.recursive/`, start with:

- `/.recursive/AGENTS.md`

## Package Surface

Installable entrypoints:

- `/SKILL.md`
- `/skills/recursive-worktree/SKILL.md`
- `/skills/recursive-debugging/SKILL.md`
- `/skills/recursive-tdd/SKILL.md`
- `/skills/recursive-review-bundle/SKILL.md`
- `/skills/recursive-subagent/SKILL.md`

## Bootstrap Layout

The installer bootstraps the canonical layout in a target repo:

```text
.recursive/
  AGENTS.md
  RECURSIVE.md
  STATE.md
  DECISIONS.md
  memory/
    MEMORY.md
    domains/
    patterns/
    incidents/
    episodes/
    skills/
      SKILLS.md
      availability/
      usage/
        skill-discovery-and-evaluation.md
      issues/
      patterns/
        delegated-verification-and-refresh.md
        phase8-skill-memory-promotion.md
    archive/
  run/
    <run-id>/
.codex/AGENTS.md
.agent/PLANS.md
/AGENTS.md (optional mirror only)
```

- `/.recursive/AGENTS.md` is a lightweight internal router/index
- `/.recursive/RECURSIVE.md` remains the only workflow source of truth
- `references/bootstrap/RECURSIVE.md` is the packaged non-hidden bootstrap copy that installers use from installed skill directories; keep it byte-for-byte aligned with `/.recursive/RECURSIVE.md`

## Main Maintainer Commands

Bootstrap a target repo:

```bash
python "<SKILL_DIR>/scripts/install-recursive-mode.py" --repo-root .
bash "<SKILL_DIR>/scripts/install-recursive-mode.sh" --repo-root .
pwsh -NoProfile -File "<SKILL_DIR>/scripts/install-recursive-mode.ps1" -RepoRoot .
```

Notes:

- Python and Bash are the primary cross-platform bootstrap paths.
- PowerShell is optional and mainly relevant on Windows.

Scaffold a run:

```bash
python "<SKILL_DIR>/scripts/recursive-init.py" --repo-root . --run-id "<run-id>" --template feature
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-init.ps1" -RepoRoot . -RunId "<run-id>" -Template feature
```

Check status:

```bash
python "<SKILL_DIR>/scripts/recursive-status.py" --repo-root . --run-id "<run-id>"
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-status.ps1" -RepoRoot . -RunId "<run-id>"
```

Lint a run:

```bash
python "<SKILL_DIR>/scripts/lint-recursive-run.py" --repo-root . --run-id "<run-id>" --strict
pwsh -NoProfile -File "<SKILL_DIR>/scripts/lint-recursive-run.ps1" -RepoRoot . -RunId "<run-id>"
```

Generate a delegated review bundle:

```bash
python "<SKILL_DIR>/scripts/recursive-review-bundle.py" --repo-root . --run-id "<run-id>" --phase "03.5 Code Review" --role code-reviewer --artifact-path "/.recursive/run/<run-id>/03.5-code-review.md" --upstream-artifact "/.recursive/run/<run-id>/00-requirements.md" --upstream-artifact "/.recursive/run/<run-id>/02-to-be-plan.md" --audit-question "Which R# remain incomplete?" --required-output "Findings ordered by severity"
```

Lock an artifact:

```bash
python "<SKILL_DIR>/scripts/recursive-lock.py" --repo-root . --run-id "<run-id>" --artifact "<artifact>.md"
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-lock.ps1" -RepoRoot . -RunId "<run-id>" -Artifact "<artifact>.md"
```

Check reusable-repo hygiene:

```bash
python "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.py" --repo-root .
pwsh -NoProfile -File "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.ps1" -RepoRoot .
```

## Maintainer Smoke Harness

Run disposable regression coverage when changing this repo itself:

```bash
python "<SKILL_DIR>/scripts/test-recursive-mode-smoke.py" --scenario quick --toolchain mixed
python "<SKILL_DIR>/scripts/test-recursive-mode-smoke.py" --scenario full --toolchain python --keep-temp
python "<SKILL_DIR>/scripts/test-recursive-mode-smoke.py" --scenario subagent --toolchain mixed

pwsh -NoProfile -File "<SKILL_DIR>/scripts/test-recursive-mode-smoke.ps1" -Scenario quick -Toolchain mixed
pwsh -NoProfile -File "<SKILL_DIR>/scripts/test-recursive-mode-smoke.ps1" -Scenario subagent -Toolchain mixed
```

Notes:

- the harness uses disposable repos only
- `--toolchain python` must work without PowerShell
- `mixed` should skip PowerShell clearly when unavailable
- full mode exercises negative regressions as well as the positive path

## Delegation And Review

- prefer `recursive-review-bundle` for delegated Phase 3.5 review
- record `Review Bundle Path`
- use `recursive-subagent-action` for durable delegated work records
- verify delegated claims against actual files, diffs, bundles, and recursive artifacts before acceptance

## Reusable-Repo Boundary

When improving this repository itself:

- do not commit concrete `/.recursive/run/<run-id>/` folders
- do not commit run-local evidence logs, review bundles, or subagent action records
- do not commit temp-directory residue
- do not update `STATE.md` or `DECISIONS.md` with current-session implementation history
- keep only reusable product changes in the final diff

Run the hygiene checker before treating the repo as clean.
For final handoff of this repo itself, prefer the strict form:

```bash
python "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.py" --repo-root . --require-clean-git
pwsh -NoProfile -File "<SKILL_DIR>/scripts/check-reusable-repo-hygiene.ps1" -RepoRoot . -RequireCleanGit
```

That final check should pass only when there is no run contamination, no generated local residue, and no dirty worktree state left to hand off.
