# Local First Planner scoring rubric

Total heuristic score: **110**

## Delivery and reliability

- **20** - `npm run build` succeeds
- **20** - `npm run test` succeeds
- **10** - local preview starts successfully and serves HTML
- **5** - `benchmark/agent-log.md` exists with timestamped progress notes; timestamp fallback may earn partial credit when the log form is incomplete

## Feature coverage

- **10** - local persistence is implemented
- **10** - import/export JSON flow is implemented
- **10** - search and filtering are implemented
- **5** - grouped planner view is implemented
- **5** - summary metrics reflect the currently displayed data set
- **5** - work-item model includes status, priority, optional due date, and tags

## UX and edge handling

- **5** - empty-state and invalid-import/error handling are visible
- **5** - overdue items have a visible distinction

## Notes

- Missing metrics should be marked unavailable, not estimated.
- A failed build, failed tests, or timeout should remain visible in the final report.
- If a criterion is substantively met but the evidence form is incomplete, the benchmark may award partial credit instead of a full pass.
- The rubric is intentionally heuristic; it is meant to compare benchmark arms consistently, not to replace human review.
