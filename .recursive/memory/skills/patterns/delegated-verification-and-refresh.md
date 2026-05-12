Type: `pattern`
Status: `CURRENT`
Scope: `How the main agent verifies delegated review or audit work before accepting it as lockable evidence.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/.recursive/memory/skills/SKILLS.md`
- `/.recursive/run/`
Source-Runs:
- `none (generic repository guidance)`
Validated-At-Commit: `generic-repository-guidance`
Last-Validated: `2026-04-09T00:00:00Z`
Tags:
- `skills`
- `subagent`
- `verification`
- `review-bundle`

# Delegated Verification And Refresh

Delegated work is optional helper output, not autonomous authority.

## Main-Agent Acceptance Rules

Before accepting meaningful delegated work, the main agent should verify:

- claimed file impact against the actual diff-owned file set
- claimed artifact reads or updates against files that actually exist
- review-bundle contents against the current reviewed artifact and artifact hash
- requirement, plan, addenda, and prior recursive docs that materially informed acceptance
- whether any post-review repair made the delegated context stale

## Record In The Phase Artifact

When delegated work materially contributes, `## Subagent Contribution Verification` should record:

- `Reviewed Action Records`
- `Main-Agent Verification Performed`
- `Acceptance Decision`
- `Refresh Handling`
- `Repair Performed After Verification`

## Refresh Rule

If repairs materially change the reviewed artifact, changed-file scope, or evidence basis, refresh the review bundle or action record before relying on delegated work for lockable evidence.

## Rejection Rule

If the main agent cannot verify delegated claims against actual files, actual artifacts, and the actual diff scope, reject the delegated result and fall back to self-audit for lockable completion evidence.
