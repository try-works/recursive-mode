#!/usr/bin/env python3
"""
Lock a recursive-mode artifact after validating gates, structure, and audit requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


LOCK_HASH_LINE_RE = re.compile(r"(?m)^[ \t]*LockHash:.*(?:\n|$)")


def load_phase_rules_module():
    module_path = Path(__file__).with_name("recursive_phase_rules.py")
    spec = importlib.util.spec_from_file_location("recursive_phase_rules", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load phase rules module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError:
        raise RuntimeError(f"Phase rules module not found: {module_path}")
    return module


def load_lint_module():
    module_path = Path(__file__).with_name("lint-recursive-run.py")
    spec = importlib.util.spec_from_file_location("recursive_mode_lint", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load lint module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_for_lock_hash(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return LOCK_HASH_LINE_RE.sub("", normalized)


def lock_hash_from_content(content: str) -> str:
    normalized = normalize_for_lock_hash(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def render_field(field_name: str, value: str) -> str:
    return f"{field_name}: `{value}`"


def set_or_insert_field(content: str, field_name: str, value: str, after_fields: list[str]) -> str:
    line = render_field(field_name, value)
    field_re = re.compile(rf"(?m)^[ \t]*(?:[-*][ \t]+)?{re.escape(field_name)}:\s*.*$")
    if field_re.search(content):
        return field_re.sub(line, content, count=1)

    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    insert_at = 0
    for after_field in after_fields:
        after_re = re.compile(rf"^[ \t]*(?:[-*][ \t]+)?{re.escape(after_field)}:\s*.*$")
        for index, existing_line in enumerate(lines):
            if after_re.match(existing_line):
                insert_at = max(insert_at, index + 1)
    lines.insert(insert_at, line)
    return "\n".join(lines)


def validate_lockable(lint, repo_root: Path, run_dir: Path, artifact_path: Path) -> tuple[list[str], str, str]:
    issues: list[str] = []
    content = artifact_path.read_text(encoding="utf-8")
    workflow_profile = lint.get_workflow_profile(run_dir)
    requirement_ids: list[str] = []
    status = lint.get_md_field_value(content, "Status") or "UNKNOWN"

    requirements_path = run_dir / "00-requirements.md"
    if requirements_path.exists():
        requirement_ids = lint.parse_requirement_ids(requirements_path.read_text(encoding="utf-8"))

    actual_changed_files: list[str] | None = None
    diff_basis_error: str | None = None
    if workflow_profile == lint.STRICT_WORKFLOW_PROFILE:
        diff_basis = lint.get_run_diff_basis(run_dir)
        raw_changed_files, diff_basis_error = lint.get_git_changed_files(repo_root, diff_basis)
        if raw_changed_files is not None:
            actual_changed_files = lint.filter_runtime_changed_files(raw_changed_files, run_dir.name)

    if status not in {"DRAFT", "LOCKED"}:
        issues.append(f"Artifact Status must be DRAFT before locking (found {status})")

    missing_header_fields = [
        field for field in ("Run", "Phase", "Status", "Inputs", "Outputs", "Scope note") if not lint.has_header_field(content, field)
    ]
    if missing_header_fields:
        issues.append(f"Missing required header field(s): {', '.join(missing_header_fields)}")

    todo_has_section, _todo_total, _todo_checked, todo_unchecked = lint.get_todo_stats(content)
    if not todo_has_section:
        issues.append("Missing required section: ## TODO")
    elif todo_unchecked > 0:
        issues.append(f"Unchecked TODO items remain: {todo_unchecked}")

    for heading in lint.get_artifact_required_sections(artifact_path.name, workflow_profile):
        if not lint.has_heading(content, heading):
            issues.append(f"Missing required section heading: ## {heading}")

    for gate_name in ("Coverage", "Approval"):
        if not lint.has_gate_line(content, gate_name):
            issues.append(f"Missing required gate line: {gate_name}: PASS|FAIL")

    issues.extend(lint.lint_traceability(artifact_path, content, requirement_ids))
    issues.extend(
        lint.lint_audit_sections(
            artifact_path,
            content,
            workflow_profile,
            actual_changed_files,
            diff_basis_error,
            run_dir.name,
            run_dir,
        )
    )
    issues.extend(
        lint.lint_phase_specific_rules(
            artifact_path,
            content,
            workflow_profile,
            run_dir,
            repo_root,
            requirement_ids,
            actual_changed_files,
        )
    )

    if lint.get_gate_status(content, "Coverage") != "PASS":
        issues.append("Coverage gate must be PASS before locking")
    if lint.get_gate_status(content, "Approval") != "PASS":
        issues.append("Approval gate must be PASS before locking")
    if artifact_path.name == "03-implementation-summary.md" and lint.get_gate_status(content, "TDD Compliance") != "PASS":
        issues.append("TDD Compliance gate must be PASS before locking Phase 3")
    if workflow_profile == lint.STRICT_WORKFLOW_PROFILE and artifact_path.name in lint.AUDITED_PHASE_FILES:
        if lint.get_gate_status(content, "Audit") != "PASS":
            issues.append("Audit gate must be PASS before locking this audited phase")

    deduped_issues = sorted(set(issues))
    if status == "LOCKED":
        locked_at = lint.get_md_field_value(content, "LockedAt")
        stored_hash = lint.get_md_field_value(content, "LockHash")
        actual_hash = lock_hash_from_content(content) if stored_hash else None
        if locked_at and stored_hash and actual_hash and stored_hash.lower() == actual_hash.lower() and not deduped_issues:
            return [], content, workflow_profile
        if not deduped_issues:
            deduped_issues.append("Artifact is already LOCKED but its lock metadata is invalid")
        else:
            deduped_issues.append("Artifact is already LOCKED but not lock-valid under current rules; set it back to DRAFT before re-locking")

    return sorted(set(deduped_issues)), content, workflow_profile


def resolve_artifact_path(run_dir: Path, artifact_arg: str) -> Path:
    artifact_path = Path(artifact_arg)
    if not artifact_path.is_absolute():
        artifact_path = run_dir / artifact_path
    artifact_path = artifact_path.resolve()
    run_root = run_dir.resolve()
    try:
        artifact_path.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(f"Artifact path must stay within the run directory: {run_root}") from exc
    return artifact_path


def reopen_artifact(phase_rules, run_dir: Path, artifact_path: Path, repo_root: Path) -> int:
    """
    Revert a locked artifact back to DRAFT status and invalidate all downstream
    lock receipts so they must be re-locked in order.
    """
    content = artifact_path.read_text(encoding="utf-8")
    status_re = re.compile(r"(?m)^[ \t]*Status:.*$")
    locked_at_re = re.compile(r"(?m)^[ \t]*LockedAt:.*\n?")
    hash_re = re.compile(r"(?m)^[ \t]*LockHash:.*\n?")

    updated = status_re.sub("Status: `DRAFT`", content, count=1)
    updated = locked_at_re.sub("", updated, count=1)
    updated = hash_re.sub("", updated, count=1)

    temp_path = artifact_path.with_name(f".{artifact_path.name}.tmp")
    temp_path.write_text(updated, encoding="utf-8", newline="\n")
    temp_path.replace(artifact_path)

    rel = artifact_path.relative_to(repo_root)
    print(f"[OK] Reopened {rel}: reverted to DRAFT")

    artifact_name = artifact_path.name
    if phase_rules.is_core_artifact(artifact_name):
        removed = phase_rules.invalidate_receipt(run_dir, artifact_name)
        if removed:
            print(f"[OK] Invalidated lock receipt for {artifact_name}")

        stale = phase_rules.get_stale_downstream_phases(artifact_name, run_dir)
        if stale:
            print("[WARN] The following downstream phases have stale receipts; re-lock them in order after fixing this phase:")
            for entry in stale:
                phase_rules.invalidate_receipt(run_dir, entry["artifact"])
                print(f"  - {entry['artifact']}: {entry['reason']} (receipt invalidated)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lock a recursive-mode artifact after validating gates and structure.")
    parser.add_argument("--run-id", required=True, help="Run ID under .recursive/run/.")
    parser.add_argument("--artifact", required=True, help="Artifact file inside the run directory, e.g. 04-test-summary.md or addenda/foo.addendum-01.md")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--reopen", action="store_true", help="Reopen a locked artifact: revert to DRAFT, remove lock metadata, and invalidate downstream receipts.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = repo_root / ".recursive" / "run" / args.run_id.strip()
    if not run_dir.exists():
        print(f"[FAIL] Run directory not found: {run_dir}")
        return 1

    try:
        artifact_path = resolve_artifact_path(run_dir, args.artifact.strip())
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if not artifact_path.exists():
        print(f"[FAIL] Artifact not found: {artifact_path}")
        return 1

    phase_rules = load_phase_rules_module()

    if args.reopen:
        return reopen_artifact(phase_rules, run_dir, artifact_path, repo_root)

    # Prerequisite gate: all earlier phases that exist must be LOCKED first.
    artifact_name = artifact_path.name
    if phase_rules.is_core_artifact(artifact_name):
        blockers = phase_rules.get_prerequisite_blockers(artifact_name, run_dir)
        if blockers:
            print(f"[FAIL] Cannot lock {artifact_path.relative_to(repo_root)}: prerequisite phases are not yet LOCKED")
            for blocker in blockers:
                print(f"  - {blocker['artifact']}: {blocker['status']} ({blocker['path']})")
            return 1

    lint = load_lint_module()
    issues, content, workflow_profile = validate_lockable(lint, repo_root, run_dir, artifact_path)

    if not issues:
        status = lint.get_md_field_value(content, "Status") or "UNKNOWN"
        if status == "LOCKED":
            print(f"[OK] Artifact already lock-valid: {artifact_path.relative_to(repo_root)}")
            print(f"Workflow Profile: {workflow_profile}")
            return 0

    if issues:
        print(f"[FAIL] Refusing to lock {artifact_path.relative_to(repo_root)}")
        print(f"Workflow Profile: {workflow_profile}")
        for issue in issues:
            print(f"- {issue}")
        return 1

    locked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = set_or_insert_field(content, "Status", "LOCKED", ["Phase"])
    updated = set_or_insert_field(updated, "LockedAt", locked_at, ["Status"])
    provisional = set_or_insert_field(updated, "LockHash", "0" * 64, ["LockedAt", "Status"])
    lock_hash = lock_hash_from_content(provisional)
    final_content = set_or_insert_field(updated, "LockHash", lock_hash, ["LockedAt", "Status"])

    temp_path = artifact_path.with_name(f".{artifact_path.name}.tmp")
    temp_path.write_text(final_content, encoding="utf-8", newline="\n")
    temp_path.replace(artifact_path)

    # Write lock receipt for chain tracking.
    if phase_rules.is_core_artifact(artifact_name):
        phase_rules.write_receipt(run_dir, artifact_name, artifact_path)

    # Report stale downstream phases so the caller knows what needs re-locking.
    if phase_rules.is_core_artifact(artifact_name):
        stale = phase_rules.get_stale_downstream_phases(artifact_name, run_dir)
        if stale:
            print(f"[WARN] The following downstream phases have stale receipts and may need re-locking:")
            for entry in stale:
                print(f"  - {entry['artifact']}: {entry['reason']}")

    print(f"[OK] Locked {artifact_path.relative_to(repo_root)}")
    print(f"Workflow Profile: {workflow_profile}")
    print(f"LockedAt: {locked_at}")
    print(f"LockHash: {lock_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
