# PLANS.md

<!-- RECURSIVE-MODE-PLANS-BRIDGE:START -->
## recursive-mode plans bridge

This file exists only for tools that expect the Codex plans bridge at `/.agent/PLANS.md`.

The canonical workflow specification lives in `/.recursive/RECURSIVE.md`.
Do not maintain a second authoritative workflow here.

If this bridge conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

Short user commands that should trigger recursive-mode orchestration include:

- `Implement the run`
- `Implement run <run-id>`
- `Implement requirement '<run-id>'`
- `Implement the plan`
- `Create a new run based on the plan`
- `Start a recursive run`

Resolution rule:

- If a run id is explicit, use that run.
- If exactly one active/incomplete run exists and no run id is given, resume it.
- If the user refers to a plan, create a new run only when a unique source plan/requirements artifact can be identified from repo docs or immediate task context.
- If the command is ambiguous, ask for the run id or the repo path of the source plan/requirements artifact.
<!-- RECURSIVE-MODE-PLANS-BRIDGE:END -->
