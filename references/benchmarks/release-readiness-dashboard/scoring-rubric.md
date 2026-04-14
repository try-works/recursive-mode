# Release Readiness Dashboard scoring rubric

Total heuristic score: **140**

## Delivery and reliability

- **20** - `npm run build` succeeds
- **20** - `npm run test` succeeds
- **10** - local preview starts successfully and serves HTML
- **5** - `benchmark/agent-log.md` exists with timestamped progress notes; timestamp fallback may earn partial credit when the log form is incomplete

## Feature coverage

- **10** - local persistence, packaged sample data, and reset are implemented
- **10** - import/export JSON flow is implemented with visible invalid-input handling
- **10** - filtered dashboard views and grouped operational slices are implemented
- **10** - the release data model covers multiple releases, milestones, owners, and target windows or dates
- **10** - approval gates, blockers, and dependencies are represented visibly
- **5** - incidents or risk records with severity are represented visibly
- **10** - derived readiness or health scoring is implemented and visible
- **5** - a release detail drill-down or focused inspection view is implemented
- **5** - exception summaries such as overdue items, approval gaps, or critical blockers are visible
- **5** - a local audit trail, recent-activity surface, or snapshot/duplicate workflow is visible

## UX and edge handling

- **5** - clear empty-state and invalid-import/error handling are visible
- **5** - important risk, blocker, overdue, or approval-gap states have clear visual distinction

## Notes

- Missing metrics should be marked unavailable, not estimated.
- A failed build, failed tests, or timeout should remain visible in the final report.
- If a criterion is substantively met but the evidence form is incomplete, the benchmark may award partial credit instead of a full pass.
- The rubric is intentionally heuristic; it is meant to compare benchmark arms consistently, not to replace human review.
