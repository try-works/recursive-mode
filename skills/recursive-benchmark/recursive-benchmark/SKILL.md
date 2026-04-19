---
name: recursive-benchmark
description: 'Paired benchmark orchestration for comparing coding-agent performance with recursive-mode off and on. Use when the user wants to benchmark recursive-mode, compare recursive vs non-recursive execution on the same project, generate disposable benchmark repos, capture timing/build-test logs, or write a benchmark report.'
---

# recursive-benchmark

Use this skill to run a fair benchmark that compares the same coding agent with **recursive-mode off** and **recursive-mode on**.

The benchmark should use the same project requirements, the same model family, and the same success criteria for both arms. The recursive-on arm should additionally start from a bootstrapped recursive-mode scaffold, a run-local `00-requirements.md`, and a command-style prompt that explicitly tells the agent to use the bootstrapped recursive control-plane files as the recursive-mode skill before implementing the run end to end.

For fairness, the recursive-off arm should receive controller guidance only in the chat prompt, not as benchmark requirement, rubric, or prompt documents inside its repo or benchmark workspace.

Current maintained benchmark runners are Codex CLI, Kimi CLI, and OpenCode CLI. For OpenCode, prefer provider-qualified model ids and use the dedicated CLI binary rather than the desktop wrapper.

## Primary Use Case

Use `recursive-benchmark` when the user wants to:

- compare recursive-mode against a non-recursive baseline
- measure whether recursive-mode improves implementation quality, reliability, or completion rate
- run disposable benchmark repos in temp folders
- capture build/test/preview outcomes, timings, issues, and final scores
- capture and report screenshot artifacts produced during the benchmark
- generate a markdown benchmark report or dashboard
- choose among packaged easy, medium, hard, and xhard benchmark scenarios
- optionally run the paired arms in parallel when the runtime/provider can tolerate it; unstable runners should fall back to sequential execution and record that downgrade in the report

## Benchmark Contract

For each benchmark run:

1. Create paired disposable repos for `recursive-off` and `recursive-on`.
2. Give both repos the same benchmark project requirements.
3. Bootstrap recursive-mode only in the recursive-on repo and place the benchmark requirements in a run-local, recursive-compliant `00-requirements.md`.
4. Prompt the recursive-on arm to read `/.recursive/RECURSIVE.md`, the bridge docs, the router config files, and the run requirements before implementing the run.
5. Record the runner, provider family, model string, and timeout budget.
6. Execute the selected agent runtime non-interactively for both arms.
7. Run a mandatory controller-side judge review for every completed arm, preferring `gpt-5.4` and falling back to a fresh instance of the benchmarked model when needed.
8. Capture logs, durations, issues, screenshot artifacts, live progress artifacts, and evaluation outcomes, including whether the recursive-on arm produced the expected run artifacts through `08-memory-impact.md`, passed controller-side recursive run lint, and required an isolated product snapshot for Rust build/test/preview evaluation.
9. Keep repo-local benchmark workspaces such as `.benchmark-workspaces/` ignored when the harness runs inside the packaged repo.
10. Produce a final markdown report that compares the two arms side by side, including a combined benchmark score that blends heuristic rubric coverage with the mandatory judge metric.
11. Surface whether recursive-on completed the recursive artifact set, whether it passed controller-side recursive lint, and whether it used an isolated worktree or stayed in the repo root.

## Packaged Scenario Tiers

- `local-first-planner` - easy
- `team-capacity-board` - medium
- `release-readiness-dashboard` - hard
- `scientific-calculator-rust` - xhard

All packaged scenarios should stay:

- browser-local state only
- no external database or server dependencies
- local browser preview should work from a temp folder
- output should be suitable for later screenshot validation

Current packaged stacks:

- React + TypeScript + Vite for easy/medium/hard
- Rust + WebAssembly with Trunk for xhard

## Logging Requirements

The benchmark should preserve:

- raw agent stdout/stderr or JSON event logs when available
- per-phase timing data
- per-arm live progress files
- build/test/preview results
- screenshot paths and image embeds when screenshots exist
- timeout or failure reasons
- benchmark repo paths and report paths
- token or usage data only when the underlying CLI exposes it

Both benchmark arms should also ask the coding agent to maintain a simple in-repo benchmark activity log.
If the controller provides hints during the benchmark, the arm should record them in `benchmark/hints.md` so the report can apply any configured hint penalty.

## Output

The benchmark should produce a final report that includes:

- benchmark scenario name
- provider/runtime and model
- recursive-off vs recursive-on comparison
- total duration and timeout status
- build/test/preview outcomes
- screenshot galleries for both arms when screenshots exist
- separated runner health vs product outcome
- heuristic score breakdown
- mandatory code-review judge metric and reviewer identity
- combined benchmark score that weights heuristic coverage and judge review together
- recursive-on worktree isolation status and recorded worktree location
- artifact paths for live progress inspection
- notable issues or gaps
- links or relative paths to logs and generated artifacts
- timestamp fallback evidence when agent logging is incomplete

## Fairness Rules

- Keep the project spec identical between both arms.
- Do not silently give one arm different acceptance criteria.
- Record when a metric is unavailable instead of faking it.
- Keep the benchmark disposable; do not contaminate this reusable repo with run residue.
- Use the same timeout budget and scoring rubric for both arms.
- If one arm receives hints, record them and reflect the configured penalty in the final scoring.

## Boundaries

- This skill is for benchmark setup, execution, and reporting.
- It does not replace the recursive-mode workflow spec itself.
- It should not use hidden benchmark-specific criteria that are absent from the packaged rubric.
- It should not require external services such as a database server.

When the recursive-on arm uses delegated audit, review, or other external model help, the benchmark prompt should require it to re-read `/.recursive/config/recursive-router.json` and `/.recursive/config/recursive-router-discovered.json` immediately before choosing the delegated CLI/model.

## References

- `./references/patterns.md`
- `/references/benchmarks/README.md`
- `/references/benchmarks/local-first-planner/README.md`
- `/references/benchmarks/local-first-planner/00-requirements.md`
- `/references/benchmarks/local-first-planner/scoring-rubric.md`
- `./scripts/run-recursive-benchmark.py`
