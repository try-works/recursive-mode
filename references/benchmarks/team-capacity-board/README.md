# Team Capacity Board benchmark

Tier: **medium**

This packaged benchmark scenario expands beyond the easy planner into a small planning tool that requires stronger state modeling, more derived UI, and richer validation.

## Scenario goals

- realistic multi-file React + TypeScript + Vite work
- local-browser execution from a temp folder
- no external database or service dependencies
- enough scope to require work-item modeling, dependency handling, summary logic, and visible risk states

## Included files

- `00-requirements.md` - canonical project requirements used for both benchmark arms
- `scoring-rubric.md` - transparent scoring weights
- `prompt-recursive-off.md` - prompt template for the non-recursive arm
- `prompt-recursive-on.md` - prompt template for the recursive arm
- `starter/` - starter repository copied into disposable benchmark repos

If a benchmark agent takes browser or validation screenshots, it should store them under `benchmark/screenshots/` so the harness can include them in the final report.
