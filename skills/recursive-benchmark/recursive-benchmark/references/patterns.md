# recursive-benchmark patterns

## Table of Contents

- [Purpose](#purpose)
- [Paired Benchmark Rule](#paired-benchmark-rule)
- [Runner Selection](#runner-selection)
- [Project Fixture Rule](#project-fixture-rule)
- [Scenario Tier Rule](#scenario-tier-rule)
- [Execution Rule](#execution-rule)
- [Logging Rule](#logging-rule)
- [Scoring Rule](#scoring-rule)
- [Report Rule](#report-rule)
- [Failure Handling](#failure-handling)

## Purpose

Use this reference when the user wants a concrete benchmark that compares recursive-mode against a non-recursive baseline.

## Paired Benchmark Rule

Always create two comparable arms:

- `recursive-off`
- `recursive-on`

Both arms must start from the same benchmark project spec. The recursive-on arm may add recursive-mode scaffolding and a run-local `00-requirements.md`, but it must not receive a different product scope.
The recursive-off arm should receive the same requirements and other controller guidance in the prompt only, not as repository or workspace benchmark docs.

## Runner Selection

Record the exact runtime used for each benchmark:

- runner name
- provider family
- model string
- timeout budget

If the runtime does not expose token usage, report that as unavailable instead of guessing.

## Project Fixture Rule

Packaged benchmark fixtures should be:

- realistic enough to require multi-file implementation work
- local-browser friendly
- runnable from a temp folder
- free of database or external service requirements

## Scenario Tier Rule

Support packaged tiers such as:

- easy
- medium
- hard

The harness should let the user choose a scenario explicitly instead of hardcoding one benchmark forever.

## Execution Rule

Use disposable repos and bounded timeouts.

Recommended first-version behavior:

1. copy the packaged starter app into temp repos
2. provide the same benchmark requirements to both arms, while keeping recursive-off requirements in prompt text only
3. bootstrap the live recursive scaffold only in the recursive-on repo, place the benchmark requirements in the run-local `00-requirements.md`, and prompt the agent to read `/.recursive/RECURSIVE.md` plus the bridge docs before starting
4. invoke the selected coding-agent CLI non-interactively
5. run a mandatory controller-side judge review for every completed arm, preferring `gpt-5.4` and falling back to the benchmarked model when necessary
6. update per-arm progress files so status can be inferred from file changes in the benchmark workspace
7. evaluate the finished repos with build, test, preview, and recursive-run-artifact checks for the recursive-on arm

If the runtime and provider can handle it, the harness may also offer a parallel arm mode. If a runner proves unstable in parallel, the harness should automatically downgrade that runner to sequential execution and note the downgrade in the report.

## Logging Rule

Capture:

- raw runner output
- setup and execution timestamps
- build/test/preview command results
- screenshot artifact paths
- timeout or failure details
- in-repo agent activity log path
- hint log path when hints were provided
- per-arm progress artifact path
- report path

When the in-repo activity log is incomplete, the harness may fall back to controller-visible file timestamps and should report that it did so.

## Scoring Rule

Use a fixed rubric that rewards:

- successful build
- successful tests
- successful local preview
- major feature coverage
- presence of benchmark logging/evidence

The harness report should distinguish:

- runner or CLI health
- product outcome
- heuristic harness score
- any later controller-side review score
- combined benchmark score that blends heuristic coverage and judge review
- recursive-on worktree isolation status sourced from `00-worktree.md`

Recommended default weighting:

- heuristic harness score: 70%
- mandatory judge metric: 30%

Keep the rubric transparent and packaged with the fixture.

## Report Rule

The final report should behave like a scoreboard:

- summary comparison table
- per-arm score breakdown
- recursive workflow completion status for the recursive-on arm
- recursive-on worktree isolation status and recorded worktree location
- mandatory judge metric with reviewer provenance
- live progress artifact paths
- screenshot sections with image embeds when available
- notable failures and missing evidence
- artifact and log paths
- timestamp fallback evidence when used

## Failure Handling

If one or both arms fail:

- keep the logs
- keep the score breakdown
- clearly mark timeout, crash, or incomplete implementation state
- still write the report instead of aborting without results
