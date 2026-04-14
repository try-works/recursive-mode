# Release Readiness Dashboard benchmark

Tier: **hard**

This packaged benchmark scenario pushes beyond a basic planner into a local release-operations workspace with multi-release modeling, approval gates, blockers, dependencies, incident/risk tracking, exception queues, detail drill-down, and local audit or snapshot behavior.

## Scenario goals

- realistic multi-file React + TypeScript + Vite work
- local-browser execution from a temp folder
- no external database or service dependencies
- enough scope to require non-trivial state modeling, derived readiness calculations, exception handling, richer filters, detail inspection, and visual evidence

## Included files

- `00-requirements.md` - canonical project requirements used for both benchmark arms
- `scoring-rubric.md` - transparent scoring weights
- `prompt-recursive-off.md` - prompt template for the non-recursive arm
- `prompt-recursive-on.md` - prompt template for the recursive arm
- `starter/` - starter repository copied into disposable benchmark repos

If a benchmark agent takes browser or validation screenshots, it should store them under `benchmark/screenshots/` so the harness can include them in the final report.
