Implement the benchmark project in this repository.

Read:

- no controller-authored benchmark docs in the repo for this arm

Rules:

- Do not install or use recursive-mode.
- The benchmark requirements and rubric are provided in this chat prompt only, not in repository docs.
- Keep a benchmark progress log in `benchmark/agent-log.md`.
- Each log entry should include a UTC timestamp, what you tried, issues met, and whether build/test/preview status changed.
- If the controller provides a hint during the benchmark, append it to `benchmark/hints.md` with a UTC timestamp and a short note about what changed afterward.
- If you take screenshots for browser or visual validation, save them under `benchmark/screenshots/` and record the file paths in `benchmark/agent-log.md`.
- If your runtime exposes token or usage metrics, record them in the log; otherwise note that they were unavailable.
- Finish by making the project build, test, and preview locally when possible.
- In your final response, summarize completion status, build status, test status, preview status, screenshot paths if any, and any remaining gaps.
