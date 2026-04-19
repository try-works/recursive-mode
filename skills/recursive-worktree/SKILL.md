---
name: recursive-worktree
description: 'Use when starting any recursive-mode requirement to set up an isolated git worktree. Required before implementation phases: create an isolated workspace, verify a clean baseline, and keep main/master clean.'
---

# recursive-worktree

## Purpose

Use this skill at the start of a recursive-mode run to set up an isolated worktree before Phase 1+ work begins.

The canonical overall workflow still lives in `/.recursive/RECURSIVE.md`. This skill covers only the worktree-isolation discipline for `00-worktree.md`.

## Hard Rule

Do not proceed with recursive-mode phase work until:

1. A feature-branch worktree exists.
2. The worktree directory is git-ignored if it lives inside the repo.
3. Project setup has completed.
4. A clean or explicitly acknowledged baseline test state has been recorded.

## Default Location Order

Use this priority:

1. Existing `.worktrees/`
2. Existing `worktrees/`
3. A preference documented in repo instructions
4. Ask the user
5. Default to `.worktrees/`

Global fallback location:

- `~/.config/recursive-mode/worktrees/<project-name>/`

## Main Branch Protection

If the current branch is `main` or `master`, default to creating a worktree on a feature branch:

```bash
git worktree add .worktrees/<run-id> -b recursive/<run-id>
cd .worktrees/<run-id>
```

If the user explicitly insists on main-branch work, record that exception in `00-worktree.md`.

## Minimum Phase 0 Checklist

`00-worktree.md` must cover:

- selected worktree location
- git-ignore verification
- branch name and worktree path
- setup commands executed
- baseline test command and result
- normalized diff basis fields including `Baseline type`, `Baseline reference`, `Comparison reference`, `Normalized baseline`, `Normalized comparison`, and `Normalized diff command`
- explicit note that subsequent phases run from the worktree
- the required `## TODO` heading from the scaffold

## Suggested Commands

Check branch:

```bash
git branch --show-current
```

Check ignore status:

```bash
git check-ignore -q .worktrees || git check-ignore -q worktrees
```

Create worktree:

```bash
git worktree add .worktrees/<run-id> -b recursive/<run-id>
```

## Setup Guidance

Run the setup command that matches the repo:

- Node.js: `npm install`
- Rust: `cargo build`
- Python: `pip install -r requirements.txt` or project-specific install
- Go: `go mod download`
- Maven: `mvn compile -q`
- Gradle: `./gradlew compileJava`
- .NET: `dotnet restore`

Then run the baseline test command appropriate to the project and record the result in `00-worktree.md`.

## Output Contract

Write the artifact to:

- `/.recursive/run/<run-id>/00-worktree.md`

Use feature branches named:

- `recursive/<run-id>`

## Routing Awareness

If this skill uses delegated review or any other routed external model to validate worktree setup, baseline verification, or branch safety, re-read:

- `/.recursive/config/recursive-router.json`
- `/.recursive/config/recursive-router-discovered.json`

immediately before choosing that CLI/model, and honor the routed policy or explicit fallback instead of hardcoding a reviewer model.

## Integration

- Invoke this skill before AS-IS analysis and planning.
- After Phase 0 is lock-valid, continue the run from the worktree context.
- Keep later phases, including `STATE.md`, `DECISIONS.md`, and memory updates, on the same feature branch until merge time.
