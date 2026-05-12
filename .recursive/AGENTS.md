# AGENTS.md

<!-- RECURSIVE-MODE-AGENTS:START -->
## .recursive AGENTS Router

This file is a lightweight routing/index doc for agents already working inside the repository.
It exists to reduce blind doc-by-doc scanning. It is not a second workflow spec.

## Canonical Rule

- Treat `/.recursive/RECURSIVE.md` as the single workflow source of truth.
- If this file conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

## Suggested Read Order

1. Read `/.recursive/RECURSIVE.md` first for workflow rules and required behavior.
2. Read `/.recursive/STATE.md` when the current repo state matters.
3. Read `/.recursive/DECISIONS.md` when prior rationale or relevant earlier work matters.
4. Read `/.recursive/memory/MEMORY.md` when task context may depend on durable memory.
5. Read `/.recursive/memory/skills/SKILLS.md` when the task may use delegated review, subagents, review bundles, smoke-harness portability work, or other capability-sensitive execution.
6. Read `/.recursive/README.md` for repo-maintainer/bootstrap notes when changing the package itself.

## Task Routing

- Starting or resuming a recursive-mode run:
  - `/.recursive/RECURSIVE.md`
  - `/.recursive/STATE.md`
  - `/.recursive/DECISIONS.md`
  - `/.recursive/memory/MEMORY.md`
- Authoring a new recursive-mode spec or `00-requirements.md`:
  - `/.recursive/STATE.md`
  - `/.recursive/DECISIONS.md`
  - `/.recursive/memory/MEMORY.md`
  - `/skills/recursive-spec/SKILL.md`
  - relevant code and tests for the requested area
- Benchmarking recursive-mode against a non-recursive baseline:
  - Install the separate optional `recursive-benchmark` add-on only when the user explicitly asks for benchmarking.
  - Prefer `find-skills` when available; otherwise use `npx skills add <recursive-benchmark-package-or-repo> --full-depth`.
  - The default exported `recursive-mode` package intentionally excludes benchmark fixtures and benchmark skill files.
  - After the benchmark add-on is installed, follow its packaged fixture and harness docs.
- Working on reusable package/bootstrap/docs for this repo:
  - `/.recursive/README.md`
  - `/README.md`
  - `/scripts/install-recursive-mode.py`
  - `/scripts/install-recursive-mode.ps1`
- Working on phase artifact structure or lint expectations:
  - `/references/artifact-template.md`
  - `/scripts/lint-recursive-run.py`
  - `/scripts/recursive-status.py`
- Working on delegated review, subagent behavior, or routed CLI delegation:
  - `/.recursive/memory/skills/SKILLS.md`
  - `/.recursive/config/recursive-router.json`
  - `/.recursive/config/recursive-router-discovered.json`
  - `/skills/recursive-router/SKILL.md`
  - `/skills/recursive-subagent/SKILL.md`
  - `/skills/recursive-review-bundle/SKILL.md`
- Working on memory behavior:
  - `/.recursive/memory/MEMORY.md`
  - `/skills/recursive-training/SKILL.md`
  - `/.recursive/scripts/recursive-training-loader.py`
  - `/.recursive/memory/training/`
  - `/.recursive/memory/skills/SKILLS.md`

## Non-Canonical Bridges

These are adapters, not second specs:

- `/.codex/AGENTS.md`
- `/AGENTS.md`
- `/.agent/PLANS.md`

Read them only when the tool or host expects those entrypoints.
<!-- RECURSIVE-MODE-AGENTS:END -->
