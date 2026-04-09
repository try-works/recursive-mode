## Skill Memory Router

This file routes durable skill and capability knowledge for the repository.
It summarizes what skills were available, what was attempted, what worked, what failed, and how future runs should use those skills.

Use the subfolders for durable Markdown-only skill memory:

- `availability/` - environment-specific skill availability and capability probe notes
- `usage/` - stable usage guidance and fit for specific skills
- `issues/` - recurring skill failures, limitations, or confusing behavior
- `patterns/` - reusable multi-skill operating patterns and delegation playbooks

Keep this file concise. Link to child docs instead of duplicating them.

## Retrieval Hints

- If the run may use delegated review, subagents, or review bundles:
  - read this router
  - read only the most relevant skill-memory docs that are actually present for the current environment and workflow
- If the run may need specialized external capability:
  - prefer the `find-skills` skill when available
  - otherwise use the Skills CLI directly and treat discovered packages as candidates until quality is checked
- If the run changes the smoke harness or cross-toolchain behavior:
  - read the most relevant availability/usage notes if any have been intentionally promoted into skill memory
- In Phase 8, promote durable skill lessons into one of these shards:
  - `availability/` for capability probes and environment constraints
  - `usage/` for stable fit/use guidance
  - `issues/` for recurring failure modes
  - `patterns/` for reusable operating playbooks
- Before promoting anything durable, capture run-local skill usage in the Phase 8 artifact:
  - what skills were available
  - what skills were sought
  - what skills were attempted or used
  - what worked well or poorly
  - what future guidance should change

## Current Docs

- `/.recursive/memory/skills/usage/skill-discovery-and-evaluation.md`
- `/.recursive/memory/skills/patterns/delegated-verification-and-refresh.md`
- `/.recursive/memory/skills/patterns/phase8-skill-memory-promotion.md`
- Add child docs here only when they are intentionally promoted as reusable repository guidance.

<!-- RECURSIVE-MODE-MEMORY:START -->
## Skill Memory Router

This file routes durable skill and capability knowledge for the repository.
It summarizes what skills were available, what was attempted, what worked, what failed, and how future runs should use those skills.

Use the subfolders for durable Markdown-only skill memory:

- `availability/` - environment-specific skill availability and capability probe notes
- `usage/` - stable usage guidance and fit for specific skills
- `issues/` - recurring skill failures, limitations, or confusing behavior
- `patterns/` - reusable multi-skill operating patterns and delegation playbooks

Keep this file concise. Link to child docs instead of duplicating them.

## Retrieval Hints

- If the run may use delegated review, subagents, or review bundles:
  - read this router
  - read only the most relevant skill-memory docs that are actually present for the current environment and workflow
- If the run may need specialized external capability:
  - prefer the `find-skills` skill when available
  - otherwise use the Skills CLI directly and treat discovered packages as candidates until quality is checked
- If the run changes the smoke harness or cross-toolchain behavior:
  - read the most relevant availability/usage notes if any have been intentionally promoted into skill memory
- In Phase 8, promote durable skill lessons into one of these shards:
  - `availability/` for capability probes and environment constraints
  - `usage/` for stable fit/use guidance
  - `issues/` for recurring failure modes
  - `patterns/` for reusable operating playbooks
- Before promoting anything durable, capture run-local skill usage in the Phase 8 artifact:
  - what skills were available
  - what skills were sought
  - what skills were attempted or used
  - what worked well or poorly
  - what future guidance should change

## Current Docs

- `/.recursive/memory/skills/usage/skill-discovery-and-evaluation.md`
- `/.recursive/memory/skills/patterns/delegated-verification-and-refresh.md`
- `/.recursive/memory/skills/patterns/phase8-skill-memory-promotion.md`
- Add child docs here only when they are intentionally promoted as reusable repository guidance.
<!-- RECURSIVE-MODE-MEMORY:END -->
