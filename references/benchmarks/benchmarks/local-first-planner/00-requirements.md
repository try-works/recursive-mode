## Requirements

### `R1` Local planner work-item management

Description: Build a local-first planner app where a user can create, edit, and delete work items without any backend service.

Acceptance criteria:
- A user can create a work item with title, short description, status, priority, optional due date, and tags.
- A user can edit an existing work item and save the updated values.
- A user can delete a work item with a clear UI affordance.
- The UI keeps the item list and any summary widgets in sync after each change.

### `R2` Search, filters, and grouped planning view

Description: The planner should make it easy to review work items by search and filter state in a local browser session.

Acceptance criteria:
- A user can search work items by text.
- A user can filter work items by status and priority.
- The main UI presents work items in a grouped planner view that makes status visible at a glance.
- The UI includes summary counts that reflect the currently displayed data set.

### `R3` Local persistence and resettable sample data

Description: The app must work entirely in the browser and preserve data across reloads.

Acceptance criteria:
- The planner persists its data in browser-local storage only.
- Reloading the page restores the most recently saved planner state.
- The app provides a way to load or restore sample data for evaluation.
- The app provides a way to reset back to the packaged sample state without requiring a backend.

### `R4` Import and export of planner data

Description: The benchmark app should support basic portability of its local planner data.

Acceptance criteria:
- A user can export the current planner data set as JSON.
- A user can import a previously exported JSON data set into the app.
- Invalid imported JSON is rejected with a visible error state instead of silently failing.
- Importing data updates the grouped view and summary counts immediately.

### `R5` Local-browser UX states

Description: The app should feel finished enough for browser-based validation rather than only passing a build.

Acceptance criteria:
- The app includes a clear empty state when no work items are present.
- Overdue items are visually distinguishable from non-overdue items.
- The main layout remains usable at typical laptop-browser widths.
- The app exposes enough visible UI state that a browser screenshot can show the planner, filters, and summary content.

### `R6` Quality gates

Description: The benchmark result should be judged on working software rather than source changes alone.

Acceptance criteria:
- `npm run build` succeeds.
- `npm run test` succeeds.
- `npm run preview -- --host 127.0.0.1 --port <port>` can serve the built app locally.
- The implementation includes at least a small automated test surface for important planner behavior.

## Out of Scope

- `OOS1`: Authentication, accounts, or multi-user collaboration.
- `OOS2`: Any server, API, database, Docker, or cloud dependency.
- `OOS3`: Drag-and-drop kanban interactions.
- `OOS4`: Real-time synchronization across browser tabs or devices.

## Constraints

- Use React + TypeScript + Vite.
- Keep all state local to the browser.
- The project must run from a disposable temp folder.
- Do not require any external service beyond standard Node/npm package installation.
- Keep the app suitable for later browser-agent screenshot validation.
