# Scientific Calculator (Rust/WASM) benchmark

Tier: **xhard**

This packaged benchmark scenario raises the implementation bar with a browser-hosted Rust/WebAssembly scientific calculator. It is meant to be complex enough that recursive planning, audit, and repair loops should have more room to differentiate from a non-recursive baseline.

## Scenario goals

- realistic multi-file Rust + WebAssembly UI work
- local-browser execution from a temp folder
- no external database or service dependencies
- enough scope to require parser or evaluator design, UI state modeling, scientific-function handling, keyboard support, and visible validation evidence

## Included files

- `00-requirements.md` - canonical project requirements used for both benchmark arms
- `scoring-rubric.md` - transparent scoring weights
- `prompt-recursive-off.md` - prompt template for the non-recursive arm
- `prompt-recursive-on.md` - prompt template for the recursive arm
- `starter/` - bootstrap-only starter copied into disposable benchmark repos; it keeps dependency/bootstrap metadata but does not preseed calculator product code. The Rust starter manifest includes an empty `[workspace]` section so nested recursive worktree cargo commands stay rooted in the product worktree.

If a benchmark agent takes browser or validation screenshots, it should store them under `benchmark/screenshots/` so the harness can include them in the final report.
