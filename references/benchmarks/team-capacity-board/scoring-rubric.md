# Team Capacity Board scoring rubric

Total heuristic score: **110**

## Delivery and reliability

- **20** - `npm run build` succeeds
- **20** - `npm run test` succeeds
- **10** - local preview starts successfully and serves HTML
- **5** - `benchmark/agent-log.md` exists with timestamped progress notes; timestamp fallback may earn partial credit when the log form is incomplete

## Feature coverage

- **10** - local persistence and sample reset are implemented
- **10** - import/export JSON flow is implemented
- **10** - search and filtering are implemented
- **5** - grouped board view is implemented
- **5** - summary metrics reflect the currently displayed data set
- **10** - owner, effort points, and blocked/dependency fields are represented in the work-item model

## UX and edge handling

- **10** - blocked or risk states are visible in the UI and summaries
- **5** - empty-state and invalid-import/error handling are visible
- **5** - overdue or blocked items have a visible distinction

## Notes

- Missing metrics should be marked unavailable, not estimated.
- A failed build, failed tests, or timeout should remain visible in the final report.
- If a criterion is substantively met but the evidence form is incomplete, the benchmark may award partial credit instead of a full pass.
- The rubric is intentionally heuristic; it is meant to compare benchmark arms consistently, not to replace human review.
