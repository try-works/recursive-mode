# recursive-training memory architecture

## Architecture overview

```text
.recursive/run/<run-id>/          -> parse -> rollout summaries
  any *.md file                       |
                                      v
                              group by subsystem
                                      |
                                      v
                         classify group: contrastive | winner-only | insufficient
                                      |
                                      v
                         extractor emits structured learning items
                                      |
                                      v
       /.recursive/memory/domains/<subsystem>.md
       /.recursive/memory/training/<task-type>.md
```

The extractor writes every learning item to the domain shard for its subsystem, then fans those same items out to task-type training shards.

## Structured memory schema

Each extracted item should include:

- `title`
- `description`
- `content`
- `task_type`
- `subsystem`
- `source_runs`
- `applies_to`
- `created_at`
- `success_rate`

The intent is a compact, reusable memory item rather than a long narrative dump.

## Training data source

The parser treats **all** markdown in each completed run folder as eligible evidence, including:

- `00-requirements.md`
- `01-as-is.md`
- `02-to-be-plan.md`
- `03-implementation-summary.md`
- `04-test-summary.md`
- `05-manual-qa.md`
- `06-decisions-update.md`
- `07-state-update.md`
- `08-memory-impact.md`
- audit docs, addenda, evidence summaries, and any other agent-authored markdown

## Evidence signals

Reward and classification signals come from the artifacts themselves, including:

- audit verdicts
- coverage and approval gates
- QA verdict or equivalent approval markers
- build/typecheck pass or fail
- test counts and pass/fail signals
- evidence of implementation and verification across the run artifacts

If a run has neither implementation evidence nor test evidence anywhere in its markdown set, it should be treated as critically incomplete.

## Grouping strategy

Group runs by **subsystem only**.

Why:

- one run often teaches multiple lessons at once
- `00-requirements.md`, `02-to-be-plan.md`, `03-implementation-summary.md`, and `04-test-summary.md` can all yield different task-type learnings
- grouping by task type too early would throw away those cross-cutting signals

The extractor, not the grouping stage, decides each learning item's `task_type`.

## Extraction modes

| Mode | When to use it | Goal |
| --- | --- | --- |
| Contrastive | At least one winner and one loser in the same subsystem group | Explain why successful runs worked where failed runs did not |
| Winner-only | Enough successful runs but no losers | Capture repeated successful conventions and repo quirks |
| Insufficient | Too little evidence or too little variance | Skip extraction |

## Output contract

After a successful extraction pass:

- subsystem items live in `/.recursive/memory/domains/<subsystem>.md`
- task-type items live in `/.recursive/memory/training/<task-type>.md`
- `/.recursive/memory/MEMORY.md` remains the discovery router
- pointer files such as `.cursorrules`, `CLAUDE.md`, and `.github/copilot-instructions.md` stay non-authoritative

Files never modified by training:

- assistant internals
- files outside the current git working tree
- locked earlier-phase artifacts
- `AGENTS.md` bridges

## Script boundary

Training scripts own prompt construction, extraction orchestration, parsing, and memory-file writes.

They do **not** own:

- bridge-file updates
- transport-selection policy
- overall recursive-mode phase orchestration
