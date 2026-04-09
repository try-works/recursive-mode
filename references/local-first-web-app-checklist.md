# Local-First Web App Checklist

Use this checklist when a recursive-mode run builds or evaluates a browser-local app that relies on client-side persistence.

It is intentionally short. The goal is to catch the failure modes that often slip through when an app "looks done" after the first green build.

## Data Integrity

- Import/export round-trips do not preserve unsafe primary keys or duplicate IDs.
- Imported records are normalized before merge.
- Legacy persisted state is sanitized or migrated on load when the previous schema could contain bad data.
- Invalid import payloads fail with user-visible feedback.

## Persistence

- Seed data appears only on first run, not after real user data exists.
- A remount or reload test proves that persisted state comes back correctly.
- Corrupt or partial persisted state fails safely.
- Activity or audit side-panels persist only if that is an intentional product choice.

## UI Flows

- Create/edit/archive/restore/favorite flows are covered at both state and UI levels when those features exist.
- Search and filter behavior is tested against realistic sample data.
- Empty states are intentionally designed and verified.

## Verification

- `lint`, `test`, and `build` evidence is stored in the run folder.
- Browser QA is run against the built or previewed app, not only jsdom/unit tests.
- Import and export are exercised with real files during QA when the product supports them.

## Windows Notes

- Prefer running Vite/Vitest/Playwright workflows from the real worktree path.
- Avoid `subst` or mapped-drive aliases for command execution when module resolution or file uploads/downloads matter.
