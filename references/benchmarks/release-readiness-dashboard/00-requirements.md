## Requirements

### `R1` Multi-release program records

Description: Build a local-first release operations workspace where a user can manage multiple concurrent releases without any backend service.

Acceptance criteria:
- A user can create, edit, duplicate, and delete release records.
- Each release stores a name, stream or product area, target window or target date, owner, manual status, notes, tags, and rollback or contingency notes.
- The UI keeps release rows, detail views, and summaries in sync after every change.
- The data model is rich enough to support multiple active releases at once instead of a single checklist.

### `R2` Milestones, approval gates, blockers, and dependencies

Description: The app should model real release coordination work rather than a flat todo list.

Acceptance criteria:
- Each release can contain milestones or checklist items with owner, due date, and status.
- Milestones can record approval or sign-off gates such as QA, security, or operations.
- Releases or milestones can record dependencies or blocked-by links.
- Active blockers are visible in both the detail view and higher-level dashboard summaries.

### `R3` Incidents, risks, and mitigation tracking

Description: The app should make operational risk visible and actionable.

Acceptance criteria:
- A release can record one or more incidents or risk entries with severity.
- Risk or incident records can store mitigation notes and ownership.
- Critical or unresolved incidents visibly affect the release presentation.
- Dashboard summaries expose critical-risk counts, open incident counts, or similar exception totals.

### `R4` Filtered dashboard, grouping, and exception queues

Description: The main dashboard should support real review workflows from a laptop browser session.

Acceptance criteria:
- A user can search releases by text.
- A user can filter by stream, owner, status, readiness band, and at least one exception-oriented signal such as blockers, overdue items, or approval gaps.
- The dashboard can group or switch views by stream, readiness, risk, or similar operational slices.
- Summary metrics and exception queues reflect the currently displayed data set instead of the full unfiltered set.

### `R5` Detail drill-down and release inspection

Description: The app should support drilling into one release instead of stopping at a summary-only board.

Acceptance criteria:
- A user can open a release-specific detail view, side panel, drawer, or equivalent focused inspection surface.
- The detail surface shows milestones, blockers, incidents, approvals, and derived readiness information for the selected release.
- Missing approvals, overdue milestones, and blockers are visible in the detail view.
- The detail surface updates correctly after edits and filter changes.

### `R6` Derived readiness, approval health, and critical-path signals

Description: The app should compute visible operational health from local state instead of relying only on manual labels.

Acceptance criteria:
- The UI computes a readiness score, band, or health indicator from milestone completion, blockers, incidents, approvals, and overdue state.
- The derived indicator changes when milestones, blockers, incidents, approvals, or dependencies change.
- The derived indicator is visible in list/group views, detail content, and summary content.
- The app exposes at least one visible critical-path, blocked, overdue, or approval-gap signal derived from the local data.

### `R7` Local audit trail or snapshot support

Description: The hard benchmark should require a little more operational depth than a CRUD board.

Acceptance criteria:
- The app records a visible recent-activity trail, audit history, snapshot, or comparable local trace of meaningful release changes.
- A user can duplicate or snapshot release state for what-if planning, rollback prep, or freeze tracking.
- The audit or snapshot surface is visible enough to be validated in a browser screenshot or focused UI state.
- The implementation works entirely in browser-local state.

### `R8` Local persistence, sample data, import, and export

Description: The dashboard must remain portable and fully local.

Acceptance criteria:
- The app persists its data in browser-local storage only.
- Reloading restores the most recently saved release state.
- The app provides sample data for evaluation and a reset back to that packaged sample state.
- A user can export and import the dashboard data as JSON, with invalid input rejected visibly and with basic shape validation instead of silently failing.

### `R9` Local-browser UX states

Description: The app should feel complete enough for browser-based validation rather than only passing a build.

Acceptance criteria:
- The app includes a clear empty state.
- Important readiness, blocker, overdue, approval-gap, or critical-risk states are visually distinguishable.
- The main layout remains usable at typical laptop-browser widths.
- The UI exposes enough visible state that screenshots can show the dashboard, filters, summaries, and at least one focused release-inspection state.

### `R10` Quality gates

Description: The benchmark result should be judged on working software rather than source changes alone.

Acceptance criteria:
- `npm run build` succeeds.
- `npm run test` succeeds.
- `npm run preview -- --host 127.0.0.1 --port <port>` can serve the built app locally.
- The implementation includes meaningful automated tests for important dashboard behavior.

## Out of Scope

- `OOS1`: Authentication, accounts, or multi-user collaboration.
- `OOS2`: Any server, API, database, Docker, or cloud dependency.
- `OOS3`: Real-time synchronization across browser tabs or devices.
- `OOS4`: Notifications, email delivery, or background jobs.

## Constraints

- Use React + TypeScript + Vite.
- Keep all state local to the browser.
- The project must run from a disposable temp folder.
- Do not require any external service beyond standard Node/npm package installation.
- Keep the app suitable for later browser-agent screenshot validation.
