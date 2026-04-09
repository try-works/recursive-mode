#!/usr/bin/env python3
"""
Cross-platform installer/bootstrapper for recursive-mode.

Behavior is shared with install-recursive-mode.ps1:
- creates the canonical .recursive/ control-plane layout
- upserts the canonical workflow into .recursive/RECURSIVE.md
- creates a lightweight .recursive/AGENTS.md router for internal doc discovery
- upserts the primary Codex AGENTS bridge into .codex/AGENTS.md
- upserts the primary Codex plans bridge into .agent/PLANS.md
- mirrors the AGENTS bridge into repo-root AGENTS.md when that file already exists
- preserves unrelated existing file content
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def write_utf8_no_bom(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def ensure_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created directory: {path}")
    else:
        print(f"[OK] Directory exists: {path}")


def ensure_file(path: Path, content: str) -> None:
    if not path.exists():
        if path.parent:
            ensure_directory(path.parent)
        write_utf8_no_bom(path, content)
        print(f"[OK] Created file: {path}")
    else:
        print(f"[OK] File exists: {path}")


def resolve_canonical_workflow_path(skill_root: Path) -> Path:
    candidates = [
        skill_root / "references" / "bootstrap" / "RECURSIVE.md",
        skill_root / ".recursive" / "RECURSIVE.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            print(f"[INFO] Using canonical workflow template: {candidate}")
            return candidate
    raise FileNotFoundError(
        "Missing canonical workflow template. Expected one of: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def upsert_marked_block(file_path: Path, start_marker: str, end_marker: str, block_body: str) -> None:
    existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    block = f"{start_marker}\n{block_body}\n{end_marker}"
    pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL)

    if pattern.search(existing):
        updated = pattern.sub(lambda _match: block, existing)
    elif existing.strip():
        updated = f"{existing.rstrip()}\n\n{block}\n"
    else:
        updated = f"{block}\n"

    if updated != existing:
        write_utf8_no_bom(file_path, updated)
        print(f"[OK] Updated file: {file_path}")
    else:
        print(f"[OK] File already up to date: {file_path}")


def memory_router_body() -> str:
    return """## Memory Router

This file is the durable memory router for the repository.
It is not a knowledge dump. Store durable memory in sharded docs under `domains/`, `patterns/`, `incidents/`, `episodes/`, `skills/`, or `archive/`.

Control-plane docs are not memory docs:
- `/.recursive/RECURSIVE.md`
- `/.recursive/STATE.md`
- `/.recursive/DECISIONS.md`
- `/.codex/AGENTS.md`
- `/AGENTS.md`
- `/.agent/PLANS.md`

## Retrieval Rules

- Read this file before loading any other memory docs.
- Load only the memory docs relevant to the current task.
- If the task plans delegated review, subagent help, review bundles, smoke-harness portability work, or capability-sensitive execution, read `/.recursive/memory/skills/SKILLS.md` and then load the relevant skill-memory shards.
- If Phase 8 will need to promote durable lessons, first capture run-local skill usage in the run artifact and only then promote generalized conclusions into skill-memory shards.
- Prefer `Status: CURRENT` docs for planning and execution.
- `Status: SUSPECT` docs may be used as leads, but revalidate them before trust.
- Exclude `STALE` and `DEPRECATED` docs from default retrieval unless doing historical analysis.

## Registry

- `domains/` - stable functional-area knowledge with `Owns-Paths`
- `patterns/` - reusable playbooks and solution patterns
- `incidents/` - recurring failure signatures and fixes
- `episodes/` - distilled lessons from specific runs
- `skills/` - durable skill and capability memory, routed via `skills/SKILLS.md`
- `archive/` - historical or deprecated memory docs

## Freshness Rules

- Durable memory docs must declare the metadata defined in `references/artifact-template.md`.
- Any doc whose `Owns-Paths` or `Watch-Paths` overlaps final changed code paths must be reviewed in Phase 8.
- Affected `CURRENT` docs should be downgraded to `SUSPECT` until revalidated against final code, `STATE.md`, and `DECISIONS.md`.
- If changed paths have no owning domain doc, create one or record the uncovered-path follow-up in `08-memory-impact.md`.
- Skill-memory docs should record source runs, last validated date, environment notes, and current trust/fit guidance.
- If a run materially teaches the repo something about skill availability, delegated-review quality, review-bundle usage, or toolchain fallback behavior, Phase 8 must either create/refresh a skill-memory shard or record why no durable lesson was promoted.
- If the repo itself is a reusable skill/workflow distribution, durable memory must remain generalized. Do not store current-session run residue or temp-environment observations as if they were universal truth.
"""


def skill_memory_router_body() -> str:
    return """## Skill Memory Router

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
"""


def skill_discovery_memory_doc() -> str:
    return """Type: `pattern`
Status: `CURRENT`
Scope: `How recursive-mode runs should discover, evaluate, and record external skills or missing capabilities.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/SKILL.md`
- `/README.md`
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
"""


def delegated_verification_memory_doc() -> str:
    return """Type: `pattern`
Status: `CURRENT`
Scope: `How the main agent verifies delegated review or audit work before accepting it as lockable evidence.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/skills/recursive-subagent/SKILL.md`
- `/agents/code-reviewer.md`
- `/agents/implementer.md`
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
"""


def phase8_skill_memory_doc() -> str:
    return """Type: `pattern`
Status: `CURRENT`
Scope: `How Phase 8 captures run-local skill usage and promotes only durable lessons into skill memory.`
Owns-Paths:
Watch-Paths:
- `/.recursive/RECURSIVE.md`
- `/references/artifact-template.md`
- `/scripts/recursive-closeout.py`
- `/scripts/lint-recursive-run.py`
- `/scripts/recursive-status.py`
Source-Runs:
- `none (generic repository guidance)`
Validated-At-Commit: `generic-repository-guidance`
Last-Validated: `2026-04-09T00:00:00Z`
Tags:
- `skills`
- `memory`
- `phase8`
- `promotion`

# Phase 8 Skill Memory Promotion

Skill memory should be operational, not accidental.

## First Capture It Run-Locally

Before promoting durable guidance, record run-local skill usage in `08-memory-impact.md`:

- what skills were available
- what skills were sought
- what skills were attempted or used
- what worked well
- what issues were encountered
- what future guidance changed
- what promotion candidates exist

## Then Decide What Becomes Durable

Promote only lessons that are:

- reusable across runs
- specific enough to change future planning or verification behavior
- not merely one-off environmental noise

## Keep The Boundary Honest

- Run-local observations belong in the run artifact first.
- Durable memory should contain generalized guidance, not session history.
- In reusable skill/workflow repos, do not turn current-session implementation residue into durable memory unless it has been rewritten as generic repository guidance.
"""


def recursive_agents_router_body() -> str:
    return """## .recursive AGENTS Router

This file is a lightweight routing/index doc for agents already working inside the repository.
It exists to reduce blind doc-by-doc scanning. It is not a second workflow spec.

## Canonical Rule

- Treat `/.recursive/RECURSIVE.md` as the single workflow source of truth.
- If this file conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

## Suggested Read Order

1. Read `/.recursive/RECURSIVE.md` first for workflow rules and required behavior.
2. Read `/.recursive/STATE.md` when the current repo state matters.
3. Read `/.recursive/DECISIONS.md` when prior rationale or relevant earlier work matters.
4. Read `/.recursive/memory/MEMORY.md` when task context may depend on durable memory.
5. Read `/.recursive/memory/skills/SKILLS.md` when the task may use delegated review, subagents, review bundles, smoke-harness portability work, or other capability-sensitive execution.
6. Read `/.recursive/README.md` for repo-maintainer/bootstrap notes when changing the package itself.

## Task Routing

- Starting or resuming a recursive-mode run:
  - `/.recursive/RECURSIVE.md`
  - `/.recursive/STATE.md`
  - `/.recursive/DECISIONS.md`
  - `/.recursive/memory/MEMORY.md`
- Working on reusable package/bootstrap/docs for this repo:
  - `/.recursive/README.md`
  - `/README.md`
  - `/scripts/install-recursive-mode.py`
  - `/scripts/install-recursive-mode.ps1`
- Working on phase artifact structure or lint expectations:
  - `/references/artifact-template.md`
  - `/scripts/lint-recursive-run.py`
  - `/scripts/recursive-status.py`
- Working on delegated review or subagent behavior:
  - `/.recursive/memory/skills/SKILLS.md`
  - `/skills/recursive-subagent/SKILL.md`
  - `/skills/recursive-review-bundle/SKILL.md`
- Working on memory behavior:
  - `/.recursive/memory/MEMORY.md`
  - `/.recursive/memory/skills/SKILLS.md`

## Non-Canonical Bridges

These are adapters, not second specs:

- `/.codex/AGENTS.md`
- `/AGENTS.md`
- `/.agent/PLANS.md`

Read them only when the tool or host expects those entrypoints.
"""


def plans_bridge_body() -> str:
    return """## recursive-mode plans bridge

This file exists only for tools that expect the Codex plans bridge at `/.agent/PLANS.md`.

The canonical workflow specification lives in `/.recursive/RECURSIVE.md`.
Do not maintain a second authoritative workflow here.

If this bridge conflicts with `/.recursive/RECURSIVE.md`, follow `/.recursive/RECURSIVE.md`.

Short user commands that should trigger recursive-mode orchestration include:

- `Implement the run`
- `Implement run <run-id>`
- `Implement requirement '<run-id>'`
- `Implement the plan`
- `Create a new run based on the plan`
- `Start a recursive run`

Resolution rule:

- If a run id is explicit, use that run.
- If exactly one active/incomplete run exists and no run id is given, resume it.
- If the user refers to a plan, create a new run only when a unique source plan/requirements artifact can be identified from repo docs or immediate task context.
- If the command is ambiguous, ask for the run id or the repo path of the source plan/requirements artifact.

Audit delegation rule:

- If subagents are available and the audit/review context bundle is complete, delegated audit/review is the default path.
- If the controller still chooses `self-audit`, record a concrete `Delegation Override Reason` in the audited phase artifact.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Install/bootstrap recursive-mode scaffolding.")
    parser.add_argument("--repo-root", default=".", help="Repository root path (default: current directory).")
    parser.add_argument(
        "--skip-recursive-update",
        action="store_true",
        help="Skip canonical RECURSIVE.md upsert.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    print(f"[INFO] Repo root: {repo_root}")

    skill_root = Path(__file__).resolve().parent.parent
    canonical_workflow_path = resolve_canonical_workflow_path(skill_root)
    agents_block_path = skill_root / "references" / "agents-block.md"

    recursive_root = repo_root / ".recursive"
    codex_root = repo_root / ".codex"
    memory_root = recursive_root / "memory"
    run_root = recursive_root / "run"
    agent_root = repo_root / ".agent"

    recursive_path = recursive_root / "RECURSIVE.md"
    recursive_agents_path = recursive_root / "AGENTS.md"
    state_path = recursive_root / "STATE.md"
    decisions_path = recursive_root / "DECISIONS.md"
    memory_router_path = memory_root / "MEMORY.md"
    skill_memory_root = memory_root / "skills"
    skill_memory_router_path = skill_memory_root / "SKILLS.md"
    skill_discovery_path = skill_memory_root / "usage" / "skill-discovery-and-evaluation.md"
    delegated_verification_path = skill_memory_root / "patterns" / "delegated-verification-and-refresh.md"
    phase8_skill_memory_path = skill_memory_root / "patterns" / "phase8-skill-memory-promotion.md"
    codex_agents_path = codex_root / "AGENTS.md"
    root_agents_path = repo_root / "AGENTS.md"
    plans_path = agent_root / "PLANS.md"

    recursive_start_marker = "<!-- RECURSIVE-MODE-CANONICAL:START -->"
    recursive_end_marker = "<!-- RECURSIVE-MODE-CANONICAL:END -->"
    memory_start_marker = "<!-- RECURSIVE-MODE-MEMORY:START -->"
    memory_end_marker = "<!-- RECURSIVE-MODE-MEMORY:END -->"
    agents_start_marker = "<!-- RECURSIVE-MODE-AGENTS:START -->"
    agents_end_marker = "<!-- RECURSIVE-MODE-AGENTS:END -->"
    plans_start_marker = "<!-- RECURSIVE-MODE-PLANS-BRIDGE:START -->"
    plans_end_marker = "<!-- RECURSIVE-MODE-PLANS-BRIDGE:END -->"

    ensure_directory(recursive_root)
    ensure_directory(codex_root)
    ensure_directory(agent_root)
    ensure_directory(memory_root)
    ensure_directory(skill_memory_root)
    ensure_directory(run_root)
    for subdir in ("domains", "patterns", "incidents", "episodes", "archive"):
        ensure_directory(memory_root / subdir)
        ensure_file(memory_root / subdir / ".gitkeep", "")
    for subdir in ("availability", "usage", "issues", "patterns"):
        ensure_directory(skill_memory_root / subdir)
        ensure_file(skill_memory_root / subdir / ".gitkeep", "")

    ensure_file(run_root / ".gitkeep", "")
    ensure_file(recursive_path, "# RECURSIVE.md\n")
    ensure_file(recursive_agents_path, "# AGENTS.md\n")
    ensure_file(state_path, "# STATE.md\n\n## Current State\n\n- Initial state not documented yet.\n")
    ensure_file(decisions_path, "# DECISIONS.md\n\n## Recursive Run Index\n\n- No runs recorded yet.\n")
    ensure_file(memory_router_path, "# MEMORY.md\n")
    ensure_file(skill_memory_router_path, "# SKILLS.md\n")
    ensure_file(skill_discovery_path, skill_discovery_memory_doc())
    ensure_file(delegated_verification_path, delegated_verification_memory_doc())
    ensure_file(phase8_skill_memory_path, phase8_skill_memory_doc())
    ensure_file(codex_agents_path, "# AGENTS.md\n")
    ensure_file(plans_path, "# PLANS.md\n")

    upsert_marked_block(
        recursive_agents_path,
        agents_start_marker,
        agents_end_marker,
        recursive_agents_router_body().rstrip("\r\n"),
    )
    upsert_marked_block(
        memory_router_path,
        memory_start_marker,
        memory_end_marker,
        memory_router_body().rstrip("\r\n"),
    )
    upsert_marked_block(
        skill_memory_router_path,
        memory_start_marker,
        memory_end_marker,
        skill_memory_router_body().rstrip("\r\n"),
    )

    if not agents_block_path.exists():
        raise FileNotFoundError(f"Missing AGENTS bridge template: {agents_block_path}")
    agents_block = agents_block_path.read_text(encoding="utf-8").rstrip("\r\n")
    upsert_marked_block(codex_agents_path, agents_start_marker, agents_end_marker, agents_block)
    if root_agents_path.exists():
        upsert_marked_block(root_agents_path, agents_start_marker, agents_end_marker, agents_block)
    upsert_marked_block(plans_path, plans_start_marker, plans_end_marker, plans_bridge_body().rstrip("\r\n"))

    if not args.skip_recursive_update:
        if canonical_workflow_path.resolve() == recursive_path.resolve():
            print("[INFO] Skipped RECURSIVE.md self-upsert because source and destination are the same file.")
        else:
            canonical_body = canonical_workflow_path.read_text(encoding="utf-8").rstrip("\r\n")
            upsert_marked_block(recursive_path, recursive_start_marker, recursive_end_marker, canonical_body)
    else:
        print("[INFO] Skipped RECURSIVE.md update by configuration.")

    print("[OK] recursive-mode installation bootstrap complete.")


if __name__ == "__main__":
    main()
