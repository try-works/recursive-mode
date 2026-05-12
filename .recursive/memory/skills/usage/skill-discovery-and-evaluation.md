Type: `pattern`
Status: `CURRENT`
Scope: `How recursive-mode runs should discover, evaluate, and record external skills or missing capabilities.`
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
- `discovery`
- `find-skills`
- `capability`

# Skill Discovery And Evaluation

Use this guidance when a run needs a specialized capability that is not already available.

## Preferred Order

1. Use the `find-skills` skill if it is already installed.
2. Otherwise use the Skills CLI directly.
3. If nothing suitable exists, proceed with built-in capability and record that no suitable external skill was available.

## Useful Commands

- `npx skills find <query>`
- `npx skills add <package-or-repo>`
- `npx skills add <package-or-repo> --skill <skill-name>`
- `npx skills check`
- `npx skills update`

## Evaluation Rules

- Prefer skills from reputable publishers or organizations.
- Prefer higher install counts when the skills are otherwise comparable.
- Check upstream repository quality before recommending or installing a skill.
- Do not treat search results as proof of quality; verify source and documentation first.

## Phase 8 Recording

If a run materially used skill discovery, capture it in `08-memory-impact.md` under:

- `## Run-Local Skill Usage Capture`
- `## Skill Memory Promotion Review`

Promote only durable, reusable conclusions into skill memory. Leave one-off session notes in the run artifact instead of turning them into durable guidance.
