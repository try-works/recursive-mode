Use the recursive-mode workflow already bootstrapped into this repository to implement the benchmark run.

Read:

- `.recursive/RECURSIVE.md`
- `.recursive/AGENTS.md`
- `.codex/AGENTS.md`
- `.agent/PLANS.md`
- `.recursive/STATE.md`
- `.recursive/DECISIONS.md`
- `.recursive/memory/MEMORY.md`
- `.recursive/run/{{RUN_ID}}/00-requirements.md`

Rules:

- Treat the bootstrapped recursive control-plane files in this repo as the recursive-mode skill for this benchmark run.
- Use the recursive-mode scaffold already present in the repo.
- Before locking any recursive artifact, remove the template `## TODO` section entirely after you have incorporated its checklist items. Locked artifacts may keep the completed content, but they must not retain the literal `## TODO` heading.
- Match lint-required section headings exactly, including `## Failures and Diagnostics (if any)`.
- Use recursive worktree isolation for the run when the control-plane docs require it, and record the chosen location clearly in `00-worktree.md`.
- Prefer implementing the product in an isolated worktree path instead of the control-plane repo root; if you intentionally stay in the repo root, justify that decision explicitly in `00-worktree.md`.
- Treat `.recursive/run/{{RUN_ID}}/00-requirements.md` as the source of truth for scope.
- After reading the control-plane docs above, implement run `{{RUN_ID}}` end-to-end instead of stopping after scaffold creation.
- Drive the run forward so the downstream run artifacts through `08-memory-impact.md` are created and reflect the work performed.
- Keep a benchmark progress log in `benchmark/agent-log.md`.
- Do not edit repo-root `.gitignore` just to hide benchmark runtime output. If browser tooling writes `.playwright-mcp/`, `.cargo-target-dir/`, or similar runtime byproducts under the control-plane repo root, clean them before audited closeout.
- When writing `Changed Files` or `Worktree Diff Audit`, account for the final diff-owned worktree files that remain after runtime cleanup, including `{{EXPECTED_PRODUCT_ROOT}}/benchmark/agent-log.md` if you changed it.
- Each log entry should include a UTC timestamp, what you tried, issues met, and whether build/test/preview status changed.
- If the controller provides a hint during the benchmark, append it to `benchmark/hints.md` with a UTC timestamp and a short note about what changed afterward.
- If you take screenshots for browser or visual validation, save them under `benchmark/screenshots/` and record the file paths in `benchmark/agent-log.md`.
- If your runtime exposes token or usage metrics, record them in the log; otherwise note that they were unavailable.
- Finish by making the project build, test, and preview locally when possible.
- In your final response, summarize completion status, build status, test status, preview status, screenshot paths if any, and any remaining gaps.
