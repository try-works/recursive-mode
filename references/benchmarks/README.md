# Packaged benchmark scenarios

These fixtures are the packaged benchmark projects used by `scripts/run-recursive-benchmark.py`.

| Scenario | Tier | Purpose |
| --- | --- | --- |
| `local-first-planner` | easy | Local-first work-item planner with CRUD, filters, summary metrics, import/export, and screenshot-friendly UI validation. |
| `team-capacity-board` | medium | Team planning board with owners, capacity points, dependency awareness, risk/blocked states, and broader planning summaries. |
| `release-readiness-dashboard` | hard | Local release-control dashboard with milestones, blockers, incidents, readiness scoring, and richer derived views. |
| `scientific-calculator-rust` | xhard | Browser-hosted Rust/WASM scientific calculator that starts from a bootstrap-only dependency scaffold so the agent must author the real expression engine, UI, and browser behavior from near-zero product code. |

All packaged scenarios stay browser-local, runnable from disposable folders, and free of external databases or services.

Current packaged stacks:

- React + TypeScript + Vite for the easy/medium/hard fixtures
- Rust + WebAssembly with Trunk for the xhard fixture

Benchmark reports combine:

- heuristic rubric coverage
- the mandatory controller-side judge metric

The default combined benchmark score weights heuristic coverage at 70% and judge review at 30%, while still reporting raw build/test/preview outcomes, recursive-on worktree isolation status, and the underlying component scores separately.
