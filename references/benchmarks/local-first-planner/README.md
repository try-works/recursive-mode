# Local First Planner benchmark

This packaged benchmark scenario is the first canonical project used to compare coding-agent performance with recursive-mode off and on.

Tier: **easy**

## Scenario goals

- realistic multi-file React + TypeScript + Vite work
- local-browser execution from a temp folder
- no external database or service dependencies
- enough product scope to require planning, state modeling, UI work, and quality checks

## Included files

- `00-requirements.md` - canonical project requirements used for both benchmark arms
- `scoring-rubric.md` - transparent scoring weights
- `prompt-recursive-off.md` - prompt template for the non-recursive arm
- `prompt-recursive-on.md` - prompt template for the recursive arm
- `starter/` - starter repository copied into disposable benchmark repos

The benchmark harness copies the same scenario into both disposable repos, then adds recursive-mode scaffolding only to the recursive-on arm.

If a benchmark agent takes browser or validation screenshots, it should store them under `benchmark/screenshots/` so the harness can include them in the final report.
