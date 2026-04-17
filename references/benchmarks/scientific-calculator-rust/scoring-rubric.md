# Scientific Calculator (Rust/WASM) scoring rubric

Total heuristic score: **145**

## Delivery and reliability

- **20** - `trunk build --release` succeeds
- **20** - `cargo test` succeeds
- **10** - local preview starts successfully and serves HTML
- **5** - `benchmark/agent-log.md` exists with timestamped progress notes; timestamp fallback may earn partial credit when the log form is incomplete

## Feature coverage

- **10** - dual display or expression-tape plus editing controls are implemented
- **15** - expression parsing with operator precedence and parentheses is implemented
- **15** - scientific functions and constants are implemented visibly
- **10** - degree/radian mode affects trig behavior and is visible in the UI
- **10** - memory-register support and reusable history are implemented
- **10** - browser-local persistence is implemented
- **5** - keyboard input support is implemented
- **5** - visible error handling is implemented for invalid or domain-error cases
- **5** - result-formatting logic is present for readable output
- **5** - the calculator UI remains usable and screenshot-friendly at laptop widths

## Notes

- Missing metrics should be marked unavailable, not estimated.
- A failed build, failed tests, or timeout should remain visible in the final report.
- If a criterion is substantively met but the evidence form is incomplete, the benchmark may award partial credit instead of a full pass.
- The rubric is intentionally heuristic; it is meant to compare benchmark arms consistently, not to replace human review.
