# recursive-training phase8 and loading

## Phase 8 handoff

`08-memory-impact.md` is where a single run records what it learned.

Training then reads **many** completed runs and turns those run-local observations into cross-run memory.

That flow is:

```text
run completes Phase 8
  -> Phase 8 locks
  -> recursive-training-phase8-trigger.py runs
  -> recursive-training-grpo.py extracts memory
  -> memory files update under /.recursive/memory/
  -> later runs load only the relevant items through recursive-training-loader.py
```

## Trigger behavior

`recursive-training-phase8-trigger.py` is intentionally thin.

It should:

1. check whether enough completed runs exist
2. skip clearly when they do not
3. print the grpo command when `--auto` is not requested
4. run grpo immediately when `--auto` is requested

Examples:

```bash
python .recursive/scripts/recursive-training-phase8-trigger.py --repo-root . --run-id <run-id>
python .recursive/scripts/recursive-training-phase8-trigger.py --repo-root . --run-id <run-id> --auto
```

## Canonical commands

Full training:

```bash
python .recursive/scripts/recursive-training-grpo.py --repo-root .
```

Incremental training:

```bash
python .recursive/scripts/recursive-training-grpo.py --repo-root . --incremental --run-id <run-id>
```

Sync-only guidance:

```bash
python .recursive/scripts/recursive-training-sync.py --repo-root .
```

## Progressive disclosure

Training memory should load in three steps:

1. Read `/.recursive/memory/MEMORY.md`.
2. Run `recursive-training-loader.py` with the current task description and file paths.
3. Apply only the returned items that match the current task.

This keeps the system from stuffing all historical memory into every session.

## Loader timing

Call the loader after reading `/.recursive/RECURSIVE.md` and `/.recursive/memory/MEMORY.md`, but before planning or implementation starts.

Typical loader call:

```bash
python .recursive/scripts/recursive-training-loader.py \
  --repo-root . \
  --query "implementing frontend feature with react and tanstack router" \
  --files "apps/web/src/App.tsx,apps/web/src/stores/ui-store.ts" \
  --max-docs 3 \
  --max-items 10
```

## Integration guidance

The loader returns formatted text on stdout. Inject that into context as:

- system-prompt context
- a pre-task context message
- a tool result in a tool-aware caller

If the loader finds nothing relevant, continue normally rather than fabricating memory.

## Loader and MCP relationship

- `recursive-training-loader.py` is the canonical path because it works everywhere
- `recursive-training-mcp.py` is an optional convenience layer for MCP-aware environments
- both read the same memory files

Use one or the other, not both for the same retrieval step.

## Failure handling

Common outcomes:

- no training scripts installed -> explain that recursive-mode bootstrap must run first
- no completed runs -> explain why extraction is skipped
- only one completed run -> explain that extraction needs more evidence
- extractor unavailable -> surface that training could not run
- no learnings extracted -> report that the available runs did not yield reusable signal
