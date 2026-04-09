# DECISIONS.md

## Recursive Run Index

- No run history is intentionally checked into this reusable skill repository.

## Current Working Decisions

- Keep Python as the canonical implementation surface for complex enforcement logic and use PowerShell wrappers where that materially reduces parity drift.
- Treat subagent availability as environment-dependent and require a concrete capability probe before choosing delegated review.
- Treat delegated review as valid only when the bundle and any meaningful subagent work can be verified against actual files, actual recursive artifacts, and the actual diff basis.
- Prefer `mixed` as the documented smoke mode when cross-toolchain parity is desired, while keeping `python` independently runnable in environments without PowerShell.
- Require status-specific evidence fields in `## Requirement Completion Status` so audited artifacts cannot pass on vague prose-only completion claims.
- Treat `/.recursive/memory/skills/` as an optional durable memory surface: retrieve or update specific skill-memory docs only when those docs have been intentionally promoted as reusable repository guidance.
