#!/usr/bin/env python3
"""
Generate a recursive-mode subagent action record scaffold.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def normalize_repo_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").strip().lstrip("/")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "action"


def render_path_list(title: str, values: list[str]) -> list[str]:
    lines = [title]
    if not values:
        lines.append("- none")
        return lines
    lines.extend(f"- `{value}`" for value in values)
    return lines


def render_text_list(title: str, values: list[str]) -> list[str]:
    lines = [title]
    if not values:
        lines.append("- none")
        return lines
    lines.extend(f"- {value}" for value in values)
    return lines


def content_sha256(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a recursive-mode subagent action record scaffold.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--run-id", required=True, help="Run ID under .recursive/run/.")
    parser.add_argument("--subagent-id", required=True, help="Subagent identifier.")
    parser.add_argument("--phase", required=True, help="Phase name for the action record.")
    parser.add_argument("--purpose", required=True, help="Invocation purpose.")
    parser.add_argument("--execution-mode", required=True, help="Execution mode, e.g. review, audit, bounded-implementer.")
    parser.add_argument("--artifact-path", default="", help="Repo-relative current artifact path.")
    parser.add_argument("--upstream-artifact", action="append", default=[], help="Repo-relative upstream artifact path.")
    parser.add_argument("--addendum", action="append", default=[], help="Repo-relative addendum path.")
    parser.add_argument("--review-bundle", default="", help="Repo-relative review bundle path if used.")
    parser.add_argument("--diff-basis", default="", help="Explicit diff basis summary if not inferred.")
    parser.add_argument("--code-ref", action="append", default=[], help="Repo-relative code reference path.")
    parser.add_argument("--memory-ref", action="append", default=[], help="Repo-relative memory doc path.")
    parser.add_argument("--audit-question", action="append", default=[], help="Audit/task question passed to the subagent.")
    parser.add_argument("--action-taken", action="append", default=[], help="Concrete delegated action taken by the subagent.")
    parser.add_argument("--created-file", action="append", default=[], help="Repo-relative created file path.")
    parser.add_argument("--modified-file", action="append", default=[], help="Repo-relative modified file path.")
    parser.add_argument("--reviewed-file", action="append", default=[], help="Repo-relative reviewed file path.")
    parser.add_argument("--untouched-file", action="append", default=[], help="Repo-relative relevant but untouched file path.")
    parser.add_argument("--artifact-read", action="append", default=[], help="Repo-relative recursive artifact read by the subagent.")
    parser.add_argument("--artifact-updated", action="append", default=[], help="Repo-relative recursive artifact updated by the subagent.")
    parser.add_argument("--evidence-used", action="append", default=[], help="Repo-relative evidence path used by the subagent.")
    parser.add_argument("--finding", action="append", default=[], help="Claimed finding or unresolved point.")
    parser.add_argument("--verification-path", action="append", default=[], help="Repo-relative file or artifact path the controller should inspect first.")
    parser.add_argument("--verification-item", action="append", default=[], help="Main-agent verification handoff item.")
    parser.add_argument("--output-name", default="", help="Optional action record filename under subagents/.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = repo_root / ".recursive" / "run" / args.run_id.strip()
    if not run_dir.exists():
        print(f"[FAIL] Run directory not found: {run_dir}")
        return 1

    subagents_dir = run_dir / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = normalize_repo_path(args.review_bundle) if args.review_bundle.strip() else ""
    artifact_path = normalize_repo_path(args.artifact_path) if args.artifact_path.strip() else ""
    artifact_hash = ""
    if artifact_path and (repo_root / artifact_path).exists():
        artifact_hash = content_sha256((repo_root / artifact_path).read_text(encoding="utf-8"))

    diff_basis = args.diff_basis.strip() or "See /.recursive/run/<run-id>/00-worktree.md for the normalized diff basis used."
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_name = args.output_name.strip()
    if not output_name:
        output_name = f"{timestamp.replace(':', '').replace('-', '')}-{slugify(args.subagent_id)}-action.md"
    if not output_name.lower().endswith(".md"):
        output_name = f"{output_name}.md"
    output_path = subagents_dir / output_name
    output_rel = normalize_repo_path(str(output_path.relative_to(repo_root)))

    upstream_artifacts = sorted(set(normalize_repo_path(value) for value in args.upstream_artifact if value.strip()))
    addenda = sorted(set(normalize_repo_path(value) for value in args.addendum if value.strip()))
    code_refs = sorted(set(normalize_repo_path(value) for value in args.code_ref if value.strip()))
    memory_refs = sorted(set(normalize_repo_path(value) for value in args.memory_ref if value.strip()))
    created_files = sorted(set(normalize_repo_path(value) for value in args.created_file if value.strip()))
    modified_files = sorted(set(normalize_repo_path(value) for value in args.modified_file if value.strip()))
    reviewed_files = sorted(set(normalize_repo_path(value) for value in args.reviewed_file if value.strip()))
    untouched_files = sorted(set(normalize_repo_path(value) for value in args.untouched_file if value.strip()))
    artifacts_read = sorted(set(normalize_repo_path(value) for value in args.artifact_read if value.strip()))
    artifacts_updated = sorted(set(normalize_repo_path(value) for value in args.artifact_updated if value.strip()))
    evidence_used = sorted(set(normalize_repo_path(value) for value in args.evidence_used if value.strip()))
    actions_taken = [value.strip() for value in args.action_taken if value.strip()]
    verification_paths = sorted(set(normalize_repo_path(value) for value in args.verification_path if value.strip()))

    lines: list[str] = [
        "# Subagent Action Record",
        "",
        "## Metadata",
        f"- Subagent ID: `{args.subagent_id.strip()}`",
        f"- Run ID: `{args.run_id.strip()}`",
        f"- Phase: `{args.phase.strip()}`",
        f"- Purpose: `{args.purpose.strip()}`",
        f"- Execution Mode: `{args.execution_mode.strip()}`",
        f"- Timestamp: `{timestamp}`",
        f"- Action Record Path: `/{output_rel}`",
        "",
        "## Inputs Provided",
        f"- Current Artifact: `{('/' + artifact_path) if artifact_path else 'none'}`",
        f"- Artifact Content Hash: `{artifact_hash or 'UNKNOWN'}`",
    ]
    lines.extend(render_path_list("- Upstream Artifacts:", [f"/{value}" for value in upstream_artifacts]))
    lines.extend(render_path_list("- Addenda:", [f"/{value}" for value in addenda]))
    lines.append(f"- Review Bundle: `{('/' + bundle_path) if bundle_path else 'none'}`")
    lines.append(f"- Diff Basis: `{diff_basis}`")
    lines.extend(render_path_list("- Code Refs:", [f"/{value}" for value in code_refs]))
    lines.extend(render_path_list("- Memory Refs:", [f"/{value}" for value in memory_refs]))
    lines.extend(render_text_list("- Audit / Task Questions:", args.audit_question))
    lines.append("")
    lines.extend(render_text_list("## Claimed Actions Taken", actions_taken))
    lines.append("")
    lines.append("## Claimed File Impact")
    lines.extend(render_path_list("### Created", [f"/{value}" for value in created_files]))
    lines.extend(render_path_list("### Modified", [f"/{value}" for value in modified_files]))
    lines.extend(render_path_list("### Reviewed", [f"/{value}" for value in reviewed_files]))
    lines.extend(render_path_list("### Relevant but Untouched", [f"/{value}" for value in untouched_files]))
    lines.append("")
    lines.append("## Claimed Artifact Impact")
    lines.extend(render_path_list("### Read", [f"/{value}" for value in artifacts_read]))
    lines.extend(render_path_list("### Updated", [f"/{value}" for value in artifacts_updated]))
    lines.extend(render_path_list("### Evidence Used", [f"/{value}" for value in evidence_used]))
    lines.append("")
    lines.extend(render_text_list("## Claimed Findings", args.finding))
    lines.append("")
    lines.append("## Verification Handoff")
    lines.extend(render_path_list("- Inspect first:", [f"/{value}" if value.startswith(".recursive/") else value for value in verification_paths]))
    lines.extend(render_text_list("- Notes:", args.verification_item))
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[OK] Wrote subagent action record: /{output_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
