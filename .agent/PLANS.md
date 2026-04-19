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

Spec-authoring rule:

- If the user asks to create a plan, help plan, create a spec, or write requirements for a new recursive run, prefer `recursive-spec` before orchestration.
- `recursive-spec` should confirm the user wants spec help, ask what they want to do, read `STATE.md`, `DECISIONS.md`, `MEMORY.md`, and relevant code/tests, keep the draft in temporary non-repo storage, then create the new run only after the requirements are approved.

Benchmark rule:

- If the user asks to benchmark recursive-mode, compare recursive vs non-recursive execution, or generate a recursive-mode benchmark report, install and use the separate optional `recursive-benchmark` add-on on demand instead of assuming benchmark fixtures ship with the default recursive-mode package.
- Prefer `find-skills` when available. Otherwise use `npx skills add <recursive-benchmark-package-or-repo> --full-depth`.

Audit delegation rule:

- If subagents are available and the audit/review context bundle is complete, delegated audit/review is the default path.
- If the controller still chooses `self-audit`, record a concrete `Delegation Override Reason` in the audited phase artifact.

Router rule:

- If the user asks to route delegated work through another transport/model, configure or inspect `/.recursive/config/recursive-router.json`, refresh `/.recursive/config/recursive-router-discovered.json`, re-read both immediately before choosing the delegated CLI/model, and use `recursive-router` before dispatching the delegated role.
<!-- RECURSIVE-MODE-PLANS-BRIDGE:END -->
