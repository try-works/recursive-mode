## Requirements

### `R1` Capacity-aware team work-item management

Description: Build a local-first team planning board where a user can create, edit, and delete work items for a team sprint or weekly plan without any backend service.

Acceptance criteria:
- A user can create a work item with title, short description, owner, status, priority, optional due date, effort points, and tags.
- A user can edit an existing work item and save the updated values.
- A user can delete an existing work item with a clear UI affordance.
- The UI keeps grouped board columns and summaries in sync after every change.

### `R2` Search, filters, grouped board, and displayed summaries

Description: The planning board should make it easy to review team work by owner, state, and current visible scope.

Acceptance criteria:
- A user can search items by text.
- A user can filter by status, priority, and owner.
- The main UI groups visible work by status.
- Summary metrics reflect the currently displayed data set, including total points and item counts.

### `R3` Dependency and risk visibility

Description: The board should make blocked or risky work visible without requiring a backend.

Acceptance criteria:
- A user can record one or more dependency references for a work item.
- A work item can be marked blocked.
- Blocked or at-risk work is visually distinct in the grouped view.
- A visible summary calls out blocked items and total blocked points.

### `R4` Local persistence, sample data, and reset

Description: The app must work entirely in the browser and preserve state across reloads.

Acceptance criteria:
- The planner persists its data in browser-local storage only.
- Reloading restores the most recently saved state.
- The app provides sample data for evaluation.
- The app provides a one-click reset back to packaged sample data.

### `R5` Import/export and visible invalid-input handling

Description: The benchmark app should support portability of local planning data without silent corruption.

Acceptance criteria:
- A user can export the current data set as JSON.
- A user can import a previously exported JSON data set.
- Invalid imported JSON is rejected with a visible error state instead of silently failing.
- Importing valid data updates the grouped view and summaries immediately.

### `R6` Local-browser UX states

Description: The app should be polished enough for browser-based validation rather than only passing a build.

Acceptance criteria:
- The app includes a clear empty state.
- Blocked or overdue work is visually distinguishable.
- The main layout remains usable at typical laptop-browser widths.
- The UI exposes enough visible state that screenshots can show the board, filters, and summary content.

### `R7` Quality gates

Description: The benchmark result should be judged on working software rather than source changes alone.

Acceptance criteria:
- `npm run build` succeeds.
- `npm run test` succeeds.
- `npm run preview -- --host 127.0.0.1 --port <port>` can serve the built app locally.
- The implementation includes meaningful automated tests for important planner behavior.

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
