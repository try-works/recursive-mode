#!/usr/bin/env python3
"""
Lint recursive-mode artifacts for structure, audit discipline, and gate integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path


CURRENT_WORKFLOW_PROFILE = "recursive-mode-audit-v2"
STRICT_WORKFLOW_PROFILE = "recursive-mode-audit-v1"
COMPAT_WORKFLOW_PROFILE = "memory-phase8"
STRICT_WORKFLOW_PROFILES = {CURRENT_WORKFLOW_PROFILE, STRICT_WORKFLOW_PROFILE}
LATE_PHASE_ARTIFACTS = ["06-decisions-update.md", "07-state-update.md", "08-memory-impact.md"]
AUDITED_PHASE_FILES = {
    "01-as-is.md",
    "01.5-root-cause.md",
    "02-to-be-plan.md",
    "03-implementation-summary.md",
    "03.5-code-review.md",
    "04-test-summary.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
}
PRIOR_RECURSIVE_EVIDENCE_FILES = {
    "01-as-is.md",
    "02-to-be-plan.md",
    "04-test-summary.md",
    "07-state-update.md",
    "08-memory-impact.md",
}
DIFF_AUDITED_FILES = {
    "02-to-be-plan.md",
    "03-implementation-summary.md",
    "03.5-code-review.md",
    "04-test-summary.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
}
TRACEABILITY_REQUIRED_FILES = {
    "01-as-is.md",
    "01.5-root-cause.md",
    "02-to-be-plan.md",
    "03-implementation-summary.md",
    "03.5-code-review.md",
    "04-test-summary.md",
    "05-manual-qa.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
}
AUDIT_REQUIRED_HEADINGS = [
    "Audit Context",
    "Effective Inputs Re-read",
    "Earlier Phase Reconciliation",
    "Subagent Contribution Verification",
    "Worktree Diff Audit",
    "Gaps Found",
    "Repair Work Performed",
    "Requirement Completion Status",
    "Audit Verdict",
]
DIFF_BASIS_FIELDS = [
    "Baseline type",
    "Baseline reference",
    "Comparison reference",
    "Normalized baseline",
    "Normalized comparison",
    "Normalized diff command",
]
PRODUCT_DIFF_PHASE_FILES = {"03-implementation-summary.md", "03.5-code-review.md", "04-test-summary.md"}
DECISIONS_DIFF_PHASE_FILES = {"06-decisions-update.md"}
STATE_DIFF_PHASE_FILES = {"07-state-update.md"}
MEMORY_DIFF_PHASE_FILES = {"08-memory-impact.md"}

MEMORY_ALLOWED_TYPES = {"index", "domain", "pattern", "incident", "episode"}
MEMORY_ALLOWED_STATUSES = {"CURRENT", "SUSPECT", "STALE", "DEPRECATED", "DRAFT"}
MEMORY_REQUIRED_FIELDS = [
    "Type",
    "Status",
    "Scope",
    "Owns-Paths",
    "Watch-Paths",
    "Source-Runs",
    "Validated-At-Commit",
    "Last-Validated",
    "Tags",
]
TDD_MODES = {"strict", "pragmatic"}
QA_EXECUTION_MODES = {"human", "agent-operated", "hybrid"}
TRANSIENT_RUNTIME_DIR_MARKERS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".tox",
    ".nox",
    ".target",
    ".playwright-mcp",
    ".cargo-target-dir",
}
TRANSIENT_RUNTIME_FILE_NAMES = {".ds_store", "thumbs.db"}
TRANSIENT_RUNTIME_SUFFIXES = (".pyc", ".pyo", ".pyd")
DIFF_BASIS_ALLOWED_TYPES = {"local commit", "local branch", "remote ref", "merge-base derived"}
WORKING_TREE_COMPARISON_REFS = {"working-tree", "working-tree@head", "worktree", "working-tree+head"}
INVENTORY_DISPOSITIONS = {"in-scope", "out-of-scope", "constraint", "quality-gate"}
PHASE2_REQUIREMENT_DISPOSITION_STATUSES = {
    "planned",
    "planned-via-merge",
    "planned-indirectly",
    "deferred",
    "out-of-scope",
    "blocked",
    "superseded by approved addendum",
}
REQUIREMENT_DISPOSITION_STATUSES = {
    "implemented",
    "verified",
    "deferred",
    "out-of-scope",
    "blocked",
    "superseded by approved addendum",
}
SKILL_USAGE_RELEVANCE_STATUSES = {"relevant", "not-relevant", "yes", "no"}
FINAL_REQUIREMENT_DISPOSITION_FILES = {
    "04-test-summary.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
}
REQUIREMENT_CHANGED_FILE_ACCOUNTING_FILES = {
    "03-implementation-summary.md",
    "03.5-code-review.md",
    "04-test-summary.md",
}
SUBAGENT_ACTION_REQUIRED_HEADINGS = [
    "Metadata",
    "Inputs Provided",
    "Claimed Actions Taken",
    "Claimed File Impact",
    "Claimed Artifact Impact",
    "Claimed Findings",
    "Verification Handoff",
]
SKILL_MEMORY_ROUTER_NAMES = {"MEMORY.md", "SKILLS.md"}
RUN_ARTIFACT_SEQUENCE = [
    "00-requirements.md",
    "00-worktree.md",
    "01-as-is.md",
    "01.5-root-cause.md",
    "02-to-be-plan.md",
    "03-implementation-summary.md",
    "03.5-code-review.md",
    "04-test-summary.md",
    "05-manual-qa.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
]
REQUIREMENT_ID_RE = re.compile(r"^(R\d+|SRC-\d{3})$")


def write_issue(severity: str, file_path: Path, message: str, remediation_lines: list[str] | None = None) -> None:
    print(f"[{severity}] {file_path}: {message}")
    if remediation_lines:
        print("Remediation (copy/paste):")
        for line in remediation_lines:
            print(f"  {line}")
    print()


def trim_md_value(value: str) -> str:
    trimmed = value.strip()
    for quote in ("`", '"', "'"):
        if trimmed.startswith(quote) and trimmed.endswith(quote) and len(trimmed) >= 2:
            inner = trimmed[1:-1]
            if quote not in inner:
                return inner.strip()
    return trimmed


def get_md_field_value(content: str, field_name: str) -> str | None:
    pattern = re.compile(rf"(?m)^[ \t]*(?:[-*][ \t]+)?{re.escape(field_name)}:[ \t]*(.+?)\s*$")
    match = pattern.search(content)
    if not match:
        return None
    return trim_md_value(match.group(1))


def has_header_field(content: str, field_name: str) -> bool:
    pattern = re.compile(rf"(?m)^[ \t]*(?:[-*][ \t]+)?{re.escape(field_name)}:")
    return bool(pattern.search(content))


def has_heading(content: str, heading_text: str) -> bool:
    pattern = re.compile(rf"(?m)^[ \t]*##\s+{re.escape(heading_text)}\s*$")
    return bool(pattern.search(content))


def get_heading_body(content: str, heading_text: str) -> str:
    pattern = re.compile(
        rf"(?ms)^[ \t]*##\s+{re.escape(heading_text)}\s*$\n?(.*?)(?=^[ \t]*##\s+|\Z)"
    )
    match = pattern.search(content)
    if not match:
        return ""
    return match.group(1).strip()


def get_subheading_body(content: str, heading_text: str, level: int = 3) -> str:
    hashes = "#" * level
    pattern = re.compile(
        rf"(?ms)^[ \t]*{re.escape(hashes)}\s+{re.escape(heading_text)}\s*$\n?(.*?)(?=^[ \t]*#{{1,{level}}}\s+|\Z)"
    )
    match = pattern.search(content)
    if not match:
        return ""
    return match.group(1).strip()


def has_gate_line(content: str, gate_name: str) -> bool:
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(gate_name)}:\s*(PASS|FAIL)\s*$")
    return bool(pattern.search(content))


def get_gate_status(content: str, gate_name: str) -> str:
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(gate_name)}:\s*(PASS|FAIL)\s*$")
    match = pattern.search(content)
    return match.group(1).upper() if match else "MISSING"


def get_todo_stats(content: str) -> tuple[bool, int, int, int]:
    lines = content.splitlines()
    in_todo = False
    has_todo = False
    checked = 0
    unchecked = 0
    total = 0

    for line in lines:
        if not in_todo:
            if re.match(r"^\s*##\s+TODO\s*$", line):
                in_todo = True
                has_todo = True
            continue

        if re.match(r"^\s*##\s+", line) or re.match(r"^\s*#\s+", line):
            break

        item = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+", line)
        if item:
            total += 1
            if item.group(1).lower() == "x":
                checked += 1
            else:
                unchecked += 1

    return has_todo, total, checked, unchecked


def get_latest_run_directory(run_root: Path) -> Path | None:
    runs = [p for p in run_root.iterdir() if p.is_dir()]
    if not runs:
        return None
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


def get_workflow_profile(run_dir: Path) -> str:
    requirements_path = run_dir / "00-requirements.md"
    if requirements_path.exists():
        content = requirements_path.read_text(encoding="utf-8")
        workflow_version = get_md_field_value(content, "Workflow version")
        if workflow_version == CURRENT_WORKFLOW_PROFILE:
            return CURRENT_WORKFLOW_PROFILE
        if workflow_version == STRICT_WORKFLOW_PROFILE:
            return STRICT_WORKFLOW_PROFILE
        if workflow_version == COMPAT_WORKFLOW_PROFILE:
            return COMPAT_WORKFLOW_PROFILE

    if any((run_dir / artifact).exists() for artifact in LATE_PHASE_ARTIFACTS):
        return COMPAT_WORKFLOW_PROFILE

    return "legacy"


def is_placeholder_only(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return True
    return compact in {"...", "<content>", "[...]", "[same structure]"}


def parse_requirement_ids(requirements_content: str) -> list[str]:
    requirements_body = get_heading_body(requirements_content, "Requirements") or requirements_content
    ids = sorted(set(re.findall(r"\bR\d+\b", requirements_body)), key=lambda value: int(value[1:]))
    return ids


def requirement_sort_key(value: str) -> tuple[int, int | str, str]:
    if re.fullmatch(r"R\d+", value):
        return (0, int(value[1:]), value)
    if re.fullmatch(r"SRC-\d{3}", value):
        return (1, int(value.split("-", 1)[1]), value)
    return (2, value, value)


def normalize_source_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("`", "").replace('"', "").strip()).strip().lower()


def source_quote_matches(source_quote: str, requirements_content: str) -> bool:
    normalized_quote = normalize_source_text(source_quote)
    normalized_requirements = normalize_source_text(requirements_content)
    return bool(normalized_quote) and normalized_quote in normalized_requirements


def parse_source_requirement_inventory_entries(section_body: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    entries: dict[str, dict[str, str]] = {}
    issues: list[str] = []
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line.startswith(("-", "*")):
            continue
        body = trim_md_value(line[1:].strip())
        parts = [trim_md_value(part.strip()) for part in body.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        requirement_id = trim_md_value(parts[0])
        if not REQUIREMENT_ID_RE.fullmatch(requirement_id):
            continue
        fields: dict[str, str] = {"Requirement ID": requirement_id}
        for part in parts[1:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            fields[key.strip()] = trim_md_value(value.strip())
        if requirement_id in entries:
            issues.append(f"Source Requirement Inventory contains duplicate entries for {requirement_id}")
            continue
        entries[requirement_id] = fields
    return entries, issues


def parse_requirement_mapping_entries(section_body: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    entries: dict[str, dict[str, str]] = {}
    issues: list[str] = []
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line.startswith(("-", "*")):
            continue
        body = trim_md_value(line[1:].strip())
        parts = [trim_md_value(part.strip()) for part in body.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        requirement_id = trim_md_value(parts[0])
        if not REQUIREMENT_ID_RE.fullmatch(requirement_id):
            continue
        fields: dict[str, str] = {"Requirement ID": requirement_id}
        for part in parts[1:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            fields[key.strip()] = trim_md_value(value.strip())
        if requirement_id in entries:
            issues.append(f"Requirement Mapping contains duplicate entries for {requirement_id}")
            continue
        entries[requirement_id] = fields
    return entries, issues


def get_run_requirement_ids(run_dir: Path, workflow_profile: str) -> list[str]:
    requirements_path = run_dir / "00-requirements.md"
    explicit_ids: list[str] = []
    if requirements_path.exists():
        explicit_ids = parse_requirement_ids(requirements_path.read_text(encoding="utf-8"))
    if workflow_profile == CURRENT_WORKFLOW_PROFILE:
        phase1_path = run_dir / "01-as-is.md"
        if phase1_path.exists():
            inventory_body = get_heading_body(phase1_path.read_text(encoding="utf-8"), "Source Requirement Inventory")
            if inventory_body:
                entries, _issues = parse_source_requirement_inventory_entries(inventory_body)
                if entries:
                    return sorted(entries.keys(), key=requirement_sort_key)
    return explicit_ids


def validate_planned_surface_paths(
    requirement_id: str,
    field_name: str,
    raw_value: str,
    repo_root: Path,
) -> list[str]:
    issues: list[str] = []
    extracted_paths = collect_requirement_field_paths({field_name: raw_value}, [field_name])
    if not extracted_paths:
        issues.append(f"Requirement {requirement_id} {field_name} must cite concrete repo paths or file names")
        return issues
    unresolved: list[str] = []
    for path in sorted(extracted_paths):
        candidate = repo_root / path
        if candidate.exists():
            continue
        if candidate.parent.exists():
            continue
        unresolved.append(path)
    if unresolved:
        issues.append(f"Requirement {requirement_id} {field_name} contains unresolved planned path(s): {', '.join(unresolved[:5])}")
    return issues


def extract_paths_from_text(text: str) -> set[str]:
    paths: set[str] = set()
    for candidate in re.findall(r"`([^`\n]+)`", text):
        normalized = candidate.strip().replace("\\", "/").lstrip("/")
        if not normalized or normalized.lower().startswith("git "):
            continue
        if normalized.startswith("<") and normalized.endswith(">"):
            continue
        if "/" in normalized or "." in Path(normalized).name:
            paths.add(normalized)
    return paths


def extract_paths_from_field_value(text: str) -> set[str]:
    paths = extract_paths_from_text(text)
    if paths:
        return paths
    discovered: set[str] = set()
    for candidate in re.split(r"[,;\n]", trim_md_value(text)):
        normalized = candidate.strip().replace("\\", "/").lstrip("/")
        if not normalized or normalized.lower().startswith("git "):
            continue
        if normalized.startswith("<") and normalized.endswith(">"):
            continue
        if "/" in normalized or "." in Path(normalized).name:
            discovered.add(normalized)
    return discovered


def extract_paths_from_named_field(content: str, field_name: str) -> set[str]:
    inline_value = get_md_field_value(content, field_name)
    if inline_value is not None:
        return extract_paths_from_field_value(inline_value)

    pattern = re.compile(
        rf"(?ms)^[ \t]*(?:[-*][ \t]+)?{re.escape(field_name)}:[ \t]*$\n(.*?)(?=^[ \t]*(?:[-*][ \t]+)?[A-Za-z][^:\n]*:[ \t]*|\Z)"
    )
    match = pattern.search(content)
    if not match:
        return set()
    return {
        normalize_repo_path(path)
        for path in extract_paths_from_text(match.group(1))
        if normalize_repo_path(path)
    }


def get_named_field_text(content: str, field_name: str) -> str | None:
    inline_value = get_md_field_value(content, field_name)
    if inline_value is not None:
        return inline_value

    pattern = re.compile(
        rf"(?ms)^[ \t]*(?:[-*][ \t]+)?{re.escape(field_name)}:[ \t]*$\n(.*?)(?=^[ \t]*(?:[-*][ \t]+)?[A-Za-z][^:\n]*:[ \t]*|\Z)"
    )
    match = pattern.search(content)
    if not match:
        return None
    return match.group(1).strip()


def has_meaningful_value(value: str | None, *, disallowed: set[str] | None = None) -> bool:
    if value is None:
        return False
    normalized = trim_md_value(value).strip()
    if not normalized:
        return False
    return normalized.lower() not in (disallowed or set())


def collect_subagent_delegation_issues(audit_context: str) -> list[str]:
    issues: list[str] = []
    audit_execution_mode = get_md_field_value(audit_context, "Audit Execution Mode")
    subagent_availability = get_md_field_value(audit_context, "Subagent Availability")
    override_reason = get_md_field_value(audit_context, "Delegation Override Reason")

    if subagent_availability == "unavailable" and audit_execution_mode == "subagent":
        issues.append("Audit Context cannot claim Audit Execution Mode: subagent when Subagent Availability is unavailable")

    if subagent_availability == "available" and audit_execution_mode == "self-audit":
        if not has_meaningful_value(override_reason, disallowed={"n/a", "none"}):
            issues.append(
                "Audit Context is missing Delegation Override Reason even though subagents were available and self-audit was chosen"
            )

    return issues


def collect_paths_under_prefix(text: str, prefix: str) -> list[str]:
    return sorted(path for path in extract_paths_from_text(text) if path.startswith(prefix))


def find_missing_repo_paths(repo_root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if not (repo_root / path).exists()]


def normalize_repo_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").strip().lstrip("/")


def is_addendum_artifact(file_name: str) -> bool:
    return ".addendum-" in file_name


def is_transient_runtime_path(normalized_path: str) -> bool:
    candidate = normalize_repo_path(normalized_path)
    if not candidate:
        return False
    parts = Path(candidate).parts
    if any(part in TRANSIENT_RUNTIME_DIR_MARKERS for part in parts):
        return True
    file_name = Path(candidate).name.lower()
    if file_name in TRANSIENT_RUNTIME_FILE_NAMES:
        return True
    return file_name.endswith(TRANSIENT_RUNTIME_SUFFIXES)


def filter_runtime_changed_files(paths: list[str], run_id: str) -> list[str]:
    filtered: list[str] = []
    for raw_path in paths:
        normalized = normalize_repo_path(raw_path)
        if not normalized:
            continue
        if normalized.startswith(f".recursive/run/{run_id}/"):
            continue
        if is_transient_runtime_path(normalized):
            continue
        filtered.append(normalized)
    return sorted(set(filtered))


def content_sha256(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_git(repo_root: Path, *args: str) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return None, f"Unable to execute git: {exc}"
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed"
        return None, message
    return result.stdout.strip(), None


def normalize_baseline_type(value: str | None) -> str | None:
    if value is None:
        return None
    compact = trim_md_value(value).strip().lower().replace("-", " ")
    compact = re.sub(r"\s+", " ", compact)
    if compact in DIFF_BASIS_ALLOWED_TYPES:
        return compact
    aliases = {
        "commit": "local commit",
        "branch": "local branch",
        "remote": "remote ref",
        "remote branch": "remote ref",
        "merge base": "merge-base derived",
    }
    return aliases.get(compact)


def normalize_comparison_reference(value: str | None) -> str | None:
    if value is None:
        return None
    compact = trim_md_value(value).strip()
    if not compact:
        return None
    if compact.lower() in WORKING_TREE_COMPARISON_REFS:
        return "working-tree"
    return compact


def parse_diff_basis_source(content: str) -> str:
    diff_body = get_heading_body(content, "Diff Basis For Later Audits")
    if diff_body:
        return diff_body
    diff_body = get_heading_body(content, "Diff Basis")
    if diff_body:
        return diff_body
    return content


def get_run_diff_basis(run_dir: Path) -> dict[str, str | None]:
    worktree_path = run_dir / "00-worktree.md"
    if not worktree_path.exists():
        return {
            "baseline_type": None,
            "baseline_reference": None,
            "comparison_reference": None,
            "normalized_baseline": None,
            "normalized_comparison": None,
            "normalized_diff_command": None,
            "base_branch": None,
            "worktree_branch": None,
            "notes": None,
        }

    content = worktree_path.read_text(encoding="utf-8")
    source = parse_diff_basis_source(content)
    return {
        "baseline_type": get_md_field_value(source, "Baseline type"),
        "baseline_reference": get_md_field_value(source, "Baseline reference"),
        "comparison_reference": get_md_field_value(source, "Comparison reference"),
        "normalized_baseline": (
            get_md_field_value(source, "Normalized baseline")
            or get_md_field_value(source, "Normalized baseline commit")
            or get_md_field_value(source, "Base commit")
        ),
        "normalized_comparison": (
            get_md_field_value(source, "Normalized comparison")
            or get_md_field_value(source, "Normalized comparison reference")
            or get_md_field_value(source, "Worktree branch")
        ),
        "normalized_diff_command": (
            get_md_field_value(source, "Normalized diff command")
            or get_md_field_value(source, "Diff command convention")
        ),
        "base_branch": get_md_field_value(source, "Base branch"),
        "worktree_branch": get_md_field_value(source, "Worktree branch"),
        "notes": get_md_field_value(source, "Diff basis notes") or get_md_field_value(source, "Notes"),
    }


def normalize_diff_basis(repo_root: Path, diff_basis: dict[str, str | None]) -> tuple[dict[str, str] | None, str | None]:
    baseline_type = normalize_baseline_type(diff_basis.get("baseline_type"))
    baseline_reference = trim_md_value(diff_basis.get("baseline_reference") or "")
    comparison_reference = normalize_comparison_reference(diff_basis.get("comparison_reference"))
    normalized_baseline = trim_md_value(diff_basis.get("normalized_baseline") or "")
    normalized_comparison = normalize_comparison_reference(diff_basis.get("normalized_comparison"))
    normalized_diff_command = trim_md_value(diff_basis.get("normalized_diff_command") or "")

    missing_fields = []
    if not baseline_type:
        missing_fields.append("Baseline type")
    if not baseline_reference:
        missing_fields.append("Baseline reference")
    if not comparison_reference:
        missing_fields.append("Comparison reference")
    if not normalized_baseline:
        missing_fields.append("Normalized baseline")
    if not normalized_comparison:
        missing_fields.append("Normalized comparison")
    if not normalized_diff_command:
        missing_fields.append("Normalized diff command")
    if missing_fields:
        return None, f"Diff basis is missing required field(s): {', '.join(missing_fields)}"

    comparison_git_ref = "HEAD" if normalized_comparison == "working-tree" else normalized_comparison
    if baseline_type == "merge-base derived":
        computed_baseline, error = run_git(repo_root, "merge-base", comparison_git_ref, baseline_reference)
        if error:
            return None, f"Unable to compute merge-base for diff basis: {error}"
    else:
        computed_baseline, error = run_git(repo_root, "rev-parse", "--verify", f"{baseline_reference}^{{commit}}")
        if error:
            return None, f"Unable to resolve baseline reference '{baseline_reference}': {error}"

    if normalized_baseline != computed_baseline:
        return None, (
            "Recorded Normalized baseline does not match the executable diff basis "
            f"({normalized_baseline} != {computed_baseline})"
        )

    if normalized_comparison == "working-tree":
        expected_command = f"git diff --name-only {computed_baseline}"
        git_args = ["diff", "--name-only", computed_baseline]
    else:
        computed_comparison, error = run_git(repo_root, "rev-parse", "--verify", f"{normalized_comparison}^{{commit}}")
        if error:
            return None, f"Unable to resolve comparison reference '{normalized_comparison}': {error}"
        expected_command = f"git diff --name-only {computed_baseline}..{computed_comparison}"
        git_args = ["diff", "--name-only", f"{computed_baseline}..{computed_comparison}"]
        if normalized_comparison != computed_comparison:
            return None, (
                "Recorded Normalized comparison does not match the executable diff basis "
                f"({normalized_comparison} != {computed_comparison})"
            )

    if normalized_diff_command != expected_command:
        return None, (
            "Recorded Normalized diff command does not match the executable diff basis "
            f"({normalized_diff_command} != {expected_command})"
        )

    return {
        "baseline_type": baseline_type,
        "baseline_reference": baseline_reference,
        "comparison_reference": comparison_reference,
        "normalized_baseline": computed_baseline,
        "normalized_comparison": normalized_comparison,
        "normalized_diff_command": expected_command,
        "comparison_git_ref": comparison_git_ref,
        "git_args": git_args,
    }, None


def get_git_changed_files(repo_root: Path, diff_basis: dict[str, str | None]) -> tuple[list[str] | None, str | None]:
    normalized_basis, basis_error = normalize_diff_basis(repo_root, diff_basis)
    if basis_error:
        return None, basis_error

    try:
        diff_result = subprocess.run(
            ["git", "-C", str(repo_root), *normalized_basis["git_args"]],
            check=False,
            capture_output=True,
            text=True,
        )
        untracked_result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return None, f"Unable to execute git: {exc}"

    if diff_result.returncode != 0:
        message = diff_result.stderr.strip() or diff_result.stdout.strip() or "git diff failed"
        return None, message
    if untracked_result.returncode != 0:
        message = untracked_result.stderr.strip() or untracked_result.stdout.strip() or "git ls-files failed"
        return None, message

    tracked_changed = [path.strip() for path in diff_result.stdout.splitlines() if path.strip()]
    untracked_changed = [
        path.strip()
        for path in untracked_result.stdout.splitlines()
        if path.strip() and not is_transient_runtime_path(path.strip())
    ]
    changed = tracked_changed + untracked_changed
    return sorted(set(path.strip() for path in changed if path.strip())), None


def get_phase_owned_actual_changed_files(file_name: str, actual_changed_files: list[str] | None) -> list[str] | None:
    if actual_changed_files is None:
        return None
    if file_name == "02-to-be-plan.md":
        return None

    owned_paths: list[str] = []
    for path in actual_changed_files:
        if path == ".recursive/DECISIONS.md":
            if file_name in DECISIONS_DIFF_PHASE_FILES:
                owned_paths.append(path)
            continue
        if path == ".recursive/STATE.md":
            if file_name in STATE_DIFF_PHASE_FILES:
                owned_paths.append(path)
            continue
        if path.startswith(".recursive/memory/"):
            if file_name in MEMORY_DIFF_PHASE_FILES:
                owned_paths.append(path)
            continue
        owned_paths.append(path)

    if file_name in PRODUCT_DIFF_PHASE_FILES:
        return owned_paths
    if file_name in DECISIONS_DIFF_PHASE_FILES | STATE_DIFF_PHASE_FILES | MEMORY_DIFF_PHASE_FILES:
        return owned_paths
    return None


def get_related_addenda_paths(run_dir: Path, artifact_name: str) -> list[Path]:
    addenda_dir = run_dir / "addenda"
    if not addenda_dir.exists():
        return []

    base_name = artifact_name[:-3] if artifact_name.endswith(".md") else artifact_name
    matches: list[Path] = []
    for pattern in (f"{base_name}.addendum-*.md", f"{base_name}.upstream-gap.*.addendum-*.md"):
        matches.extend(sorted(addenda_dir.glob(pattern)))
    return matches


def get_stage_local_addenda_paths(run_dir: Path, artifact_name: str) -> list[Path]:
    addenda_dir = run_dir / "addenda"
    if not addenda_dir.exists():
        return []
    base_name = artifact_name[:-3] if artifact_name.endswith(".md") else artifact_name
    return sorted(addenda_dir.glob(f"{base_name}.addendum-*.md"))


def get_current_phase_upstream_gap_addenda_paths(run_dir: Path, artifact_name: str) -> list[Path]:
    addenda_dir = run_dir / "addenda"
    if not addenda_dir.exists():
        return []
    base_name = artifact_name[:-3] if artifact_name.endswith(".md") else artifact_name
    return sorted(addenda_dir.glob(f"{base_name}.upstream-gap.*.addendum-*.md"))


def get_header_field_block(content: str, field_name: str, stop_fields: list[str]) -> str:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    collecting = False
    captured: list[str] = []
    stop_patterns = [re.compile(rf"^\s*{re.escape(stop_field)}:") for stop_field in stop_fields]
    field_pattern = re.compile(rf"^\s*{re.escape(field_name)}:\s*$")

    for line in lines:
        if not collecting:
            if field_pattern.match(line):
                collecting = True
            continue

        if any(pattern.match(line) for pattern in stop_patterns):
            break
        captured.append(line)

    return "\n".join(captured).strip()


def get_header_input_paths(content: str) -> set[str]:
    return extract_paths_from_text(get_header_field_block(content, "Inputs", ["Outputs", "Scope note"]))


def get_phase_expected_input_artifact_names(file_name: str, run_dir: Path) -> list[str]:
    present = {artifact for artifact in RUN_ARTIFACT_SEQUENCE if (run_dir / artifact).exists()}
    if file_name == "00-worktree.md":
        candidates = ["00-requirements.md"]
    elif file_name == "01-as-is.md":
        candidates = ["00-requirements.md"]
    elif file_name == "01.5-root-cause.md":
        candidates = ["01-as-is.md"]
    elif file_name == "02-to-be-plan.md":
        candidates = ["00-requirements.md", "01-as-is.md"]
        if "01.5-root-cause.md" in present:
            candidates.append("01.5-root-cause.md")
    elif file_name == "03-implementation-summary.md":
        candidates = ["02-to-be-plan.md"]
    elif file_name == "03.5-code-review.md":
        candidates = ["02-to-be-plan.md", "03-implementation-summary.md"]
    elif file_name == "04-test-summary.md":
        candidates = ["02-to-be-plan.md", "03-implementation-summary.md"]
        if "03.5-code-review.md" in present:
            candidates.append("03.5-code-review.md")
    elif file_name == "05-manual-qa.md":
        candidates = ["02-to-be-plan.md"]
    elif file_name == "06-decisions-update.md":
        candidates = [artifact for artifact in RUN_ARTIFACT_SEQUENCE if artifact in present and artifact not in {"06-decisions-update.md", "07-state-update.md", "08-memory-impact.md"}]
    elif file_name == "07-state-update.md":
        candidates = ["06-decisions-update.md"]
    elif file_name == "08-memory-impact.md":
        candidates = [artifact for artifact in RUN_ARTIFACT_SEQUENCE if artifact in present and artifact != "08-memory-impact.md"]
    else:
        candidates = []
    return [artifact for artifact in candidates if artifact in present]


def get_expected_effective_input_addenda_paths(run_dir: Path, file_name: str) -> list[str]:
    if is_addendum_artifact(file_name):
        return []

    expected_paths: list[str] = []
    run_prefix = f".recursive/run/{run_dir.name}/"
    for artifact_name in get_phase_expected_input_artifact_names(file_name, run_dir):
        for addendum_path in get_stage_local_addenda_paths(run_dir, artifact_name):
            expected_paths.append(f"{run_prefix}addenda/{addendum_path.name}")
    for addendum_path in get_current_phase_upstream_gap_addenda_paths(run_dir, file_name):
        expected_paths.append(f"{run_prefix}addenda/{addendum_path.name}")
    return sorted(set(expected_paths))


def lint_effective_input_addenda(file_path: Path, content: str, workflow_profile: str, run_dir: Path) -> list[str]:
    if workflow_profile not in (STRICT_WORKFLOW_PROFILES | {COMPAT_WORKFLOW_PROFILE}):
        return []
    if is_addendum_artifact(file_path.name):
        return []

    expected_addenda = get_expected_effective_input_addenda_paths(run_dir, file_path.name)
    if not expected_addenda:
        return []

    issues: list[str] = []
    header_inputs = {normalize_repo_path(path) for path in get_header_input_paths(content)}
    missing_inputs = [path for path in expected_addenda if path not in header_inputs]
    if missing_inputs:
        issues.append(f"Inputs is missing relevant addenda: {', '.join(missing_inputs[:5])}")

    if workflow_profile in STRICT_WORKFLOW_PROFILES and file_path.name in AUDITED_PHASE_FILES:
        reread_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(content, 'Effective Inputs Re-read'))}
        missing_reread = [path for path in expected_addenda if path not in reread_paths]
        if missing_reread:
            issues.append(f"Effective Inputs Re-read is missing relevant addenda: {', '.join(missing_reread[:5])}")

        reconciliation_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(content, 'Earlier Phase Reconciliation'))}
        missing_reconciliation = [path for path in expected_addenda if path not in reconciliation_paths]
        if missing_reconciliation:
            issues.append(f"Earlier Phase Reconciliation is missing relevant addenda: {', '.join(missing_reconciliation[:5])}")

    return issues


def parse_requirement_completion_entries(section_body: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    entries: dict[str, dict[str, str]] = {}
    issues: list[str] = []
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line.startswith(("-", "*")):
            continue
        body = trim_md_value(line[1:].strip())
        parts = [trim_md_value(part.strip()) for part in body.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        requirement_id = trim_md_value(parts[0])
        if not REQUIREMENT_ID_RE.fullmatch(requirement_id):
            continue
        fields: dict[str, str] = {"Requirement ID": requirement_id}
        for part in parts[1:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            fields[key.strip()] = trim_md_value(value.strip())
        if requirement_id in entries:
            issues.append(f"Requirement Completion Status contains duplicate entries for {requirement_id}")
            continue
        entries[requirement_id] = fields
    return entries, issues


def is_meaningful_requirement_field(value: str | None) -> bool:
    if value is None:
        return False
    normalized = trim_md_value(value).strip()
    return bool(normalized) and normalized.lower() not in {"...", "none", "n/a", "tbd", "todo"}


def collect_requirement_field_paths(fields: dict[str, str], field_names: list[str]) -> set[str]:
    paths: set[str] = set()
    for field_name in field_names:
        raw_value = fields.get(field_name, "")
        paths.update(normalize_repo_path(path) for path in extract_paths_from_field_value(raw_value))
    return {path for path in paths if path}


def collect_meaningful_requirement_fields(fields: dict[str, str]) -> dict[str, str]:
    meaningful: dict[str, str] = {}
    for key, value in fields.items():
        if key in {"Requirement ID", "Status"}:
            continue
        if is_meaningful_requirement_field(value):
            meaningful[key] = value
    return meaningful


def normalize_skill_usage_relevance(value: str | None) -> str:
    normalized = trim_md_value(value or "").strip().lower()
    if normalized == "yes":
        return "relevant"
    if normalized == "no":
        return "not-relevant"
    return normalized


def lint_requirement_disposition_fields(
    requirement_id: str,
    status: str,
    fields: dict[str, str],
    file_name: str,
    run_dir: Path,
    repo_root: Path,
    actual_changed_files: list[str] | None,
) -> list[str]:
    issues: list[str] = []
    actual_changed_scope = set(actual_changed_files or [])
    meaningful_fields = collect_meaningful_requirement_fields(fields)
    allowed_fields_by_status = {
        "implemented": {"Changed Files", "Implementation Evidence", "Audit Note"},
        "verified": {"Changed Files", "Implementation Evidence", "Verification Evidence", "Audit Note"},
        "deferred": {"Rationale", "Deferred By", "Addendum", "Audit Note"},
        "out-of-scope": {"Rationale", "Scope Decision", "Addendum", "Audit Note"},
        "blocked": {"Rationale", "Blocking Evidence", "Audit Note"},
        "superseded by approved addendum": {"Addendum", "Audit Note"},
    }
    unexpected_fields = sorted(set(meaningful_fields) - allowed_fields_by_status[status])
    if unexpected_fields:
        issues.append(
            f"Requirement {requirement_id} with Status {status} contains contradictory field(s): "
            + ", ".join(unexpected_fields)
        )

    if status == "implemented":
        changed_files = fields.get("Changed Files", "")
        changed_paths = collect_requirement_field_paths(fields, ["Changed Files"])
        implementation_evidence = fields.get("Implementation Evidence", "")
        implementation_paths = collect_requirement_field_paths(fields, ["Implementation Evidence"])
        if not is_meaningful_requirement_field(changed_files):
            issues.append(f"Requirement {requirement_id} with Status implemented must cite Changed Files")
        elif not changed_paths:
            issues.append(f"Requirement {requirement_id} with Status implemented must cite repo paths in Changed Files")
        else:
            missing_changed_paths = find_missing_repo_paths(repo_root, sorted(changed_paths))
            if missing_changed_paths:
                issues.append(f"Requirement {requirement_id} Changed Files path(s) do not exist: {', '.join(missing_changed_paths[:5])}")
            if actual_changed_scope:
                unexplained_paths = sorted(path for path in changed_paths if path not in actual_changed_scope)
                if unexplained_paths:
                    issues.append(
                        f"Requirement {requirement_id} Changed Files are outside the current diff scope: {', '.join(unexplained_paths[:5])}"
                    )
        if not is_meaningful_requirement_field(implementation_evidence):
            issues.append(f"Requirement {requirement_id} with Status implemented must cite Implementation Evidence")
        elif not implementation_paths:
            issues.append(f"Requirement {requirement_id} with Status implemented must cite file or artifact paths in Implementation Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(implementation_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} Implementation Evidence path(s) do not exist: {', '.join(missing[:5])}")
            if changed_paths and not implementation_paths.intersection(changed_paths) and not any(
                path.startswith(f".recursive/run/{run_dir.name}/") for path in implementation_paths
            ):
                issues.append(
                    f"Requirement {requirement_id} Implementation Evidence must reference the changed files or a current-run artifact that proves the implementation work"
                )

    elif status == "verified":
        changed_files = fields.get("Changed Files", "")
        changed_paths = collect_requirement_field_paths(fields, ["Changed Files"])
        implementation_evidence = fields.get("Implementation Evidence", "")
        verification_evidence = fields.get("Verification Evidence", "")
        implementation_paths = collect_requirement_field_paths(fields, ["Implementation Evidence"])
        verification_paths = collect_requirement_field_paths(fields, ["Verification Evidence"])
        if not is_meaningful_requirement_field(changed_files):
            issues.append(f"Requirement {requirement_id} with Status verified must cite Changed Files")
        elif not changed_paths:
            issues.append(f"Requirement {requirement_id} with Status verified must cite repo paths in Changed Files")
        else:
            missing_changed_paths = find_missing_repo_paths(repo_root, sorted(changed_paths))
            if missing_changed_paths:
                issues.append(f"Requirement {requirement_id} Changed Files path(s) do not exist: {', '.join(missing_changed_paths[:5])}")
            if actual_changed_scope:
                unexplained_paths = sorted(path for path in changed_paths if path not in actual_changed_scope)
                if unexplained_paths:
                    issues.append(
                        f"Requirement {requirement_id} Changed Files are outside the current diff scope: {', '.join(unexplained_paths[:5])}"
                    )
        if not is_meaningful_requirement_field(implementation_evidence):
            issues.append(f"Requirement {requirement_id} with Status verified must cite Implementation Evidence")
        elif not implementation_paths:
            issues.append(f"Requirement {requirement_id} with Status verified must cite file or artifact paths in Implementation Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(implementation_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} Implementation Evidence path(s) do not exist: {', '.join(missing[:5])}")
            if changed_paths and not implementation_paths.intersection(changed_paths) and not any(
                path.startswith(f".recursive/run/{run_dir.name}/") for path in implementation_paths
            ):
                issues.append(
                    f"Requirement {requirement_id} Implementation Evidence must reference the changed files or a current-run artifact that proves the implementation work"
                )
        if not is_meaningful_requirement_field(verification_evidence):
            issues.append(f"Requirement {requirement_id} with Status verified must cite Verification Evidence")
        elif not verification_paths:
            issues.append(f"Requirement {requirement_id} with Status verified must cite test, review, QA, or artifact paths in Verification Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(verification_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} Verification Evidence path(s) do not exist: {', '.join(missing[:5])}")
            if changed_paths and verification_paths.issubset(changed_paths):
                issues.append(
                    f"Requirement {requirement_id} Verification Evidence must cite verification artifacts, review receipts, or evidence beyond the changed files themselves"
                )
            if implementation_paths and verification_paths.issubset(implementation_paths):
                issues.append(
                    f"Requirement {requirement_id} Verification Evidence cannot be satisfied by restating only the implementation evidence"
                )

    elif status == "deferred":
        rationale = fields.get("Rationale", "")
        deferred_by = fields.get("Deferred By", "") or fields.get("Addendum", "")
        deferred_paths = collect_requirement_field_paths(fields, ["Deferred By", "Addendum"])
        if not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement {requirement_id} with Status deferred is missing Rationale")
        if not is_meaningful_requirement_field(deferred_by):
            issues.append(f"Requirement {requirement_id} with Status deferred must cite Deferred By or Addendum")
        elif not deferred_paths:
            issues.append(f"Requirement {requirement_id} with Status deferred must cite an approved deferral path")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(deferred_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} deferral reference path(s) do not exist: {', '.join(missing[:5])}")

    elif status == "out-of-scope":
        rationale = fields.get("Rationale", "")
        scope_decision = fields.get("Scope Decision", "") or fields.get("Addendum", "")
        scope_paths = collect_requirement_field_paths(fields, ["Scope Decision", "Addendum"])
        if not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement {requirement_id} with Status out-of-scope is missing Rationale")
        if not is_meaningful_requirement_field(scope_decision):
            issues.append(f"Requirement {requirement_id} with Status out-of-scope must cite Scope Decision or Addendum")
        elif not scope_paths:
            issues.append(f"Requirement {requirement_id} with Status out-of-scope must cite an approved scope decision path")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(scope_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} scope decision path(s) do not exist: {', '.join(missing[:5])}")

    elif status == "blocked":
        rationale = fields.get("Rationale", "")
        blocking_evidence = fields.get("Blocking Evidence", "")
        blocking_paths = collect_requirement_field_paths(fields, ["Blocking Evidence"])
        if not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement {requirement_id} with Status blocked is missing Rationale")
        if not is_meaningful_requirement_field(blocking_evidence):
            issues.append(f"Requirement {requirement_id} with Status blocked must cite Blocking Evidence")
        elif not blocking_paths:
            issues.append(f"Requirement {requirement_id} with Status blocked must cite file, artifact, or evidence paths in Blocking Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(blocking_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} Blocking Evidence path(s) do not exist: {', '.join(missing[:5])}")

    elif status == "superseded by approved addendum":
        addendum_path = normalize_repo_path(fields.get("Addendum", ""))
        if not addendum_path:
            issues.append(f"Requirement {requirement_id} superseded by approved addendum must cite Addendum")
        elif not addendum_path.startswith(f".recursive/run/{run_dir.name}/addenda/"):
            issues.append(f"Requirement {requirement_id} addendum reference must live under the current run addenda/")
        elif not (repo_root / addendum_path).exists():
            issues.append(f"Requirement {requirement_id} addendum reference does not exist: {addendum_path}")

    if file_name in FINAL_REQUIREMENT_DISPOSITION_FILES:
        if status == "implemented":
            issues.append(f"Requirement {requirement_id} cannot remain implemented in {file_name}; final closeout phases require verified or explicitly approved non-completion states")
        if status == "blocked":
            issues.append(f"Requirement {requirement_id} cannot remain blocked in {file_name} while the phase is approaching closeout")

    return issues


def lint_source_requirement_inventory(file_path: Path, content: str, workflow_profile: str, run_dir: Path) -> list[str]:
    if workflow_profile != CURRENT_WORKFLOW_PROFILE or file_path.name != "01-as-is.md":
        return []

    issues: list[str] = []
    requirements_path = run_dir / "00-requirements.md"
    requirements_content = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    body = get_heading_body(content, "Source Requirement Inventory")
    if not body:
        return ["Missing or empty section: ## Source Requirement Inventory"]

    entries, entry_issues = parse_source_requirement_inventory_entries(body)
    issues.extend(entry_issues)
    if not entries:
        issues.append("Source Requirement Inventory must contain at least one requirement inventory entry")
        return sorted(set(issues))

    explicit_ids = parse_requirement_ids(requirements_content)
    missing_explicit = [requirement_id for requirement_id in explicit_ids if requirement_id not in entries]
    if missing_explicit:
        issues.append(f"Source Requirement Inventory is missing explicit requirement IDs from 00-requirements.md: {', '.join(missing_explicit)}")

    for requirement_id, fields in entries.items():
        disposition = trim_md_value(fields.get("Disposition", "")).lower()
        source_quote = fields.get("Source Quote", "")
        summary = fields.get("Summary", "")
        if disposition not in INVENTORY_DISPOSITIONS:
            issues.append(f"Source Requirement Inventory for {requirement_id} has invalid Disposition '{fields.get('Disposition', '')}'")
        if not is_meaningful_requirement_field(source_quote):
            issues.append(f"Source Requirement Inventory for {requirement_id} is missing Source Quote")
        elif not source_quote_matches(source_quote, requirements_content):
            issues.append(f"Source Requirement Inventory for {requirement_id} cites a Source Quote that does not appear in 00-requirements.md")
        if not is_meaningful_requirement_field(summary):
            issues.append(f"Source Requirement Inventory for {requirement_id} is missing Summary")

    return sorted(set(issues))


def lint_requirement_mapping(content: str, workflow_profile: str, run_dir: Path, repo_root: Path) -> list[str]:
    if workflow_profile != CURRENT_WORKFLOW_PROFILE:
        return []

    issues: list[str] = []
    phase1_path = run_dir / "01-as-is.md"
    requirements_path = run_dir / "00-requirements.md"
    if not phase1_path.exists() or not requirements_path.exists():
        return ["Requirement Mapping requires existing 00-requirements.md and 01-as-is.md inputs"]

    inventory_body = get_heading_body(phase1_path.read_text(encoding="utf-8"), "Source Requirement Inventory")
    if not inventory_body:
        return ["Requirement Mapping requires 01-as-is.md to contain ## Source Requirement Inventory"]
    inventory_entries, inventory_issues = parse_source_requirement_inventory_entries(inventory_body)
    issues.extend(inventory_issues)

    body = get_heading_body(content, "Requirement Mapping")
    if not body:
        issues.append("Missing or empty section: ## Requirement Mapping")
        return sorted(set(issues))

    mapping_entries, mapping_issues = parse_requirement_mapping_entries(body)
    issues.extend(mapping_issues)
    missing_entries = [requirement_id for requirement_id in inventory_entries if requirement_id not in mapping_entries]
    if missing_entries:
        issues.append(f"Requirement Mapping is missing source inventory items: {', '.join(missing_entries)}")

    requirements_content = requirements_path.read_text(encoding="utf-8")
    for requirement_id, fields in mapping_entries.items():
        coverage = trim_md_value(fields.get("Coverage", "")).lower()
        source_quote = fields.get("Source Quote", "")
        implementation_surface = fields.get("Implementation Surface", "")
        verification_surface = fields.get("Verification Surface", "")
        qa_surface = fields.get("QA Surface", "")
        rationale = fields.get("Rationale", "") or fields.get("Merge Rationale", "")

        if coverage not in {"direct", "merged", "indirect", "deferred", "out-of-scope", "blocked"}:
            issues.append(f"Requirement Mapping for {requirement_id} has invalid Coverage '{fields.get('Coverage', '')}'")
            continue
        if not is_meaningful_requirement_field(source_quote):
            issues.append(f"Requirement Mapping for {requirement_id} is missing Source Quote")
        elif requirement_id in inventory_entries:
            inventory_quote = inventory_entries[requirement_id].get("Source Quote", "")
            if normalize_source_text(source_quote) != normalize_source_text(inventory_quote):
                issues.append(f"Requirement Mapping for {requirement_id} must preserve the Source Quote recorded in Source Requirement Inventory")
        elif not source_quote_matches(source_quote, requirements_content):
            issues.append(f"Requirement Mapping for {requirement_id} cites a Source Quote that does not appear in 00-requirements.md")

        if coverage in {"direct", "merged", "indirect"}:
            if not is_meaningful_requirement_field(implementation_surface):
                issues.append(f"Requirement Mapping for {requirement_id} is missing Implementation Surface")
            else:
                issues.extend(validate_planned_surface_paths(requirement_id, "Implementation Surface", implementation_surface, repo_root))
            if not is_meaningful_requirement_field(verification_surface):
                issues.append(f"Requirement Mapping for {requirement_id} is missing Verification Surface")
            if not is_meaningful_requirement_field(qa_surface):
                issues.append(f"Requirement Mapping for {requirement_id} is missing QA Surface")
        if coverage == "merged" and not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement Mapping for {requirement_id} with Coverage merged must cite Merge Rationale or Rationale")
        if coverage == "indirect" and not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement Mapping for {requirement_id} with Coverage indirect must cite Rationale")
        if coverage in {"deferred", "out-of-scope", "blocked"} and not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement Mapping for {requirement_id} with Coverage {coverage} must cite Rationale")

    return sorted(set(issues))


def lint_plan_drift_check(content: str, workflow_profile: str) -> list[str]:
    if workflow_profile != CURRENT_WORKFLOW_PROFILE:
        return []
    body = get_heading_body(content, "Plan Drift Check")
    if not body:
        return ["Missing or empty section: ## Plan Drift Check"]
    if re.search(r"\bmerge\b", body, re.IGNORECASE) and not re.search(r"\brationale\b", body, re.IGNORECASE):
        return ["Plan Drift Check mentions merged obligations without explaining why the merge is lossless"]
    return []


def lint_phase2_requirement_disposition_fields(
    requirement_id: str,
    status: str,
    fields: dict[str, str],
    run_dir: Path,
    repo_root: Path,
) -> list[str]:
    issues: list[str] = []
    allowed_fields_by_status = {
        "planned": {"Implementation Surface", "Verification Surface", "QA Surface", "Audit Note"},
        "planned-via-merge": {"Implementation Surface", "Verification Surface", "QA Surface", "Rationale", "Audit Note"},
        "planned-indirectly": {"Implementation Surface", "Verification Surface", "QA Surface", "Rationale", "Audit Note"},
        "deferred": {"Rationale", "Deferred By", "Addendum", "Audit Note"},
        "out-of-scope": {"Rationale", "Scope Decision", "Addendum", "Audit Note"},
        "blocked": {"Rationale", "Blocking Evidence", "Audit Note"},
        "superseded by approved addendum": {"Addendum", "Audit Note"},
    }
    meaningful_fields = collect_meaningful_requirement_fields(fields)
    unexpected_fields = sorted(set(meaningful_fields) - allowed_fields_by_status[status])
    if unexpected_fields:
        issues.append(
            f"Requirement {requirement_id} with Status {status} contains contradictory field(s): "
            + ", ".join(unexpected_fields)
        )

    if status in {"planned", "planned-via-merge", "planned-indirectly"}:
        implementation_surface = fields.get("Implementation Surface", "")
        verification_surface = fields.get("Verification Surface", "")
        qa_surface = fields.get("QA Surface", "")
        rationale = fields.get("Rationale", "")
        if not is_meaningful_requirement_field(implementation_surface):
            issues.append(f"Requirement {requirement_id} with Status {status} must cite Implementation Surface")
        else:
            issues.extend(validate_planned_surface_paths(requirement_id, "Implementation Surface", implementation_surface, repo_root))
        if not is_meaningful_requirement_field(verification_surface):
            issues.append(f"Requirement {requirement_id} with Status {status} must cite Verification Surface")
        if not is_meaningful_requirement_field(qa_surface):
            issues.append(f"Requirement {requirement_id} with Status {status} must cite QA Surface")
        if status in {"planned-via-merge", "planned-indirectly"} and not is_meaningful_requirement_field(rationale):
            issues.append(f"Requirement {requirement_id} with Status {status} must cite Rationale")
    elif status == "deferred":
        deferred_by = fields.get("Deferred By", "") or fields.get("Addendum", "")
        deferred_paths = collect_requirement_field_paths(fields, ["Deferred By", "Addendum"])
        if not is_meaningful_requirement_field(fields.get("Rationale", "")):
            issues.append(f"Requirement {requirement_id} with Status deferred is missing Rationale")
        if not is_meaningful_requirement_field(deferred_by):
            issues.append(f"Requirement {requirement_id} with Status deferred must cite Deferred By or Addendum")
        elif not deferred_paths:
            issues.append(f"Requirement {requirement_id} with Status deferred must cite an approved deferral path")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(deferred_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} deferral reference path(s) do not exist: {', '.join(missing[:5])}")
    elif status == "out-of-scope":
        scope_decision = fields.get("Scope Decision", "") or fields.get("Addendum", "")
        scope_paths = collect_requirement_field_paths(fields, ["Scope Decision", "Addendum"])
        if not is_meaningful_requirement_field(fields.get("Rationale", "")):
            issues.append(f"Requirement {requirement_id} with Status out-of-scope is missing Rationale")
        if not is_meaningful_requirement_field(scope_decision):
            issues.append(f"Requirement {requirement_id} with Status out-of-scope must cite Scope Decision or Addendum")
        elif not scope_paths:
            issues.append(f"Requirement {requirement_id} with Status out-of-scope must cite an approved scope decision path")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(scope_paths))
            if missing:
                issues.append(f"Requirement {requirement_id} scope decision path(s) do not exist: {', '.join(missing[:5])}")
    elif status == "blocked":
        blocking_evidence = fields.get("Blocking Evidence", "")
        blocking_paths = collect_requirement_field_paths(fields, ["Blocking Evidence"])
        if not is_meaningful_requirement_field(fields.get("Rationale", "")):
            issues.append(f"Requirement {requirement_id} with Status blocked is missing Rationale")
        if not is_meaningful_requirement_field(blocking_evidence):
            issues.append(f"Requirement {requirement_id} with Status blocked must cite Blocking Evidence")
        elif not blocking_paths:
            issues.append(f"Requirement {requirement_id} with Status blocked must cite file, artifact, or evidence paths in Blocking Evidence")
    elif status == "superseded by approved addendum":
        addendum_path = normalize_repo_path(fields.get("Addendum", ""))
        if not addendum_path:
            issues.append(f"Requirement {requirement_id} superseded by approved addendum must cite Addendum")
        elif not addendum_path.startswith(f".recursive/run/{run_dir.name}/addenda/"):
            issues.append(f"Requirement {requirement_id} addendum reference must live under the current run addenda/")
        elif not (repo_root / addendum_path).exists():
            issues.append(f"Requirement {requirement_id} addendum reference does not exist: {addendum_path}")

    return issues


def lint_requirement_completion_status(
    file_path: Path,
    content: str,
    requirement_ids: list[str],
    run_dir: Path,
    workflow_profile: str,
    actual_changed_files: list[str] | None,
) -> list[str]:
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_path.name not in AUDITED_PHASE_FILES:
        return []

    body = get_heading_body(content, "Requirement Completion Status")
    if not body:
        return ["Missing or empty section: ## Requirement Completion Status"]

    entries, issues = parse_requirement_completion_entries(body)
    missing = [requirement_id for requirement_id in requirement_ids if requirement_id not in entries]
    if missing:
        issues.append(f"Requirement Completion Status is missing in-scope requirements: {', '.join(missing)}")

    if workflow_profile == CURRENT_WORKFLOW_PROFILE and file_path.name == "02-to-be-plan.md":
        for requirement_id, fields in entries.items():
            status = trim_md_value(fields.get("Status", "")).lower()
            if status not in PHASE2_REQUIREMENT_DISPOSITION_STATUSES:
                issues.append(
                    f"Requirement Completion Status for {requirement_id} has invalid Phase 2 Status '{fields.get('Status', '')}'"
                )
                continue
            issues.extend(
                lint_phase2_requirement_disposition_fields(
                    requirement_id,
                    status,
                    fields,
                    run_dir,
                    run_dir.parent.parent.parent,
                )
            )
        return sorted(set(issues))

    for requirement_id, fields in entries.items():
        status = trim_md_value(fields.get("Status", "")).lower()
        if status not in REQUIREMENT_DISPOSITION_STATUSES:
            issues.append(
                f"Requirement Completion Status for {requirement_id} has invalid Status '{fields.get('Status', '')}'"
            )
            continue

        issues.extend(
            lint_requirement_disposition_fields(
                requirement_id,
                status,
                fields,
                file_path.name,
                run_dir,
                run_dir.parent.parent.parent,
                actual_changed_files,
            )
        )

    if file_path.name in REQUIREMENT_CHANGED_FILE_ACCOUNTING_FILES:
        expected_scope = set(get_phase_owned_actual_changed_files(file_path.name, actual_changed_files) or [])
        if expected_scope:
            claimed_changed_files = set()
            for fields in entries.values():
                status = trim_md_value(fields.get("Status", "")).lower()
                if status in {"implemented", "verified"}:
                    claimed_changed_files.update(collect_requirement_field_paths(fields, ["Changed Files"]))
            missing_claims = sorted(path for path in expected_scope if path not in claimed_changed_files)
            if missing_claims:
                issues.append(
                    "Requirement Completion Status leaves diff-owned changed file(s) unaccounted for: "
                    + ", ".join(missing_claims[:5])
                )

    return sorted(set(issues))


def lint_prior_recursive_evidence(content: str, run_dir: Path, workflow_profile: str, repo_root: Path, file_name: str) -> list[str]:
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_name not in PRIOR_RECURSIVE_EVIDENCE_FILES:
        return []

    body = get_heading_body(content, "Prior Recursive Evidence Reviewed")
    if not body:
        return ["Missing or empty section: ## Prior Recursive Evidence Reviewed"]

    referenced_paths = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(body)
        if normalize_repo_path(path).startswith(".recursive/run/") or normalize_repo_path(path).startswith(".recursive/memory/")
    }
    if referenced_paths:
        missing_paths = find_missing_repo_paths(repo_root, sorted(referenced_paths))
        if missing_paths:
            return [f"Prior Recursive Evidence Reviewed references missing path(s): {', '.join(missing_paths[:5])}"]
        return []

    if re.search(r"\bnone\b", body, re.IGNORECASE) and re.search(r"\b(justification|reason|because)\b", body, re.IGNORECASE):
        return []

    return [
        "Prior Recursive Evidence Reviewed must contain structured run/memory paths or an explicit no-relevant-evidence justification"
    ]


def get_subagent_action_record_paths(content: str, run_dir: Path) -> list[str]:
    body = get_heading_body(content, "Subagent Contribution Verification")
    if not body:
        return []
    expected_prefix = f".recursive/run/{run_dir.name}/subagents/"
    return sorted(
        path
        for path in {normalize_repo_path(path) for path in extract_paths_from_text(body)}
        if path.startswith(expected_prefix)
    )


def get_all_subagent_action_record_paths(content: str) -> list[str]:
    body = get_heading_body(content, "Subagent Contribution Verification")
    if not body:
        return []
    return sorted(
        path
        for path in {normalize_repo_path(path) for path in extract_paths_from_text(body)}
        if re.match(r"^\.recursive/run/[^/]+/subagents/.+\.md$", path)
    )


def lint_subagent_action_record_file(
    file_path: Path,
    repo_root: Path,
    run_dir: Path,
    actual_changed_files: list[str] | None,
) -> list[str]:
    content = file_path.read_text(encoding="utf-8")
    issues: list[str] = []

    if "# Subagent Action Record" not in content:
        issues.append("Missing title: # Subagent Action Record")

    for heading in SUBAGENT_ACTION_REQUIRED_HEADINGS:
        if not get_heading_body(content, heading):
            issues.append(f"Missing or empty section: ## {heading}")

    metadata = get_heading_body(content, "Metadata")
    inputs = get_heading_body(content, "Inputs Provided")
    claimed_actions = get_heading_body(content, "Claimed Actions Taken")
    claimed_file_impact = get_heading_body(content, "Claimed File Impact")
    claimed_artifact_impact = get_heading_body(content, "Claimed Artifact Impact")

    if file_path.parent != run_dir / "subagents":
        issues.append(f"Subagent action record must live under `/.recursive/run/{run_dir.name}/subagents/`")

    required_metadata_fields = ("Subagent ID", "Run ID", "Phase", "Purpose", "Execution Mode", "Timestamp")
    for field_name in required_metadata_fields:
        if not has_meaningful_value(get_md_field_value(metadata, field_name)):
            issues.append(f"Metadata is missing {field_name}")

    run_id = get_md_field_value(metadata, "Run ID")
    if run_id and run_id != run_dir.name:
        issues.append(f"Run ID mismatch: {run_id} != {run_dir.name}")

    current_artifact = normalize_repo_path(get_md_field_value(inputs, "Current Artifact") or "")
    if not current_artifact:
        issues.append("Inputs Provided is missing Current Artifact")
    elif not (repo_root / current_artifact).exists():
        issues.append(f"Current Artifact does not exist: {current_artifact}")

    artifact_hash = trim_md_value(get_md_field_value(inputs, "Artifact Content Hash") or "")
    if current_artifact and (repo_root / current_artifact).exists():
        current_artifact_hash = content_sha256((repo_root / current_artifact).read_text(encoding="utf-8"))
        if not artifact_hash:
            issues.append("Inputs Provided is missing Artifact Content Hash")
        elif artifact_hash != current_artifact_hash:
            issues.append("Inputs Provided Artifact Content Hash does not match the current artifact content")

    review_bundle = normalize_repo_path(get_md_field_value(inputs, "Review Bundle") or "")
    if review_bundle and not (repo_root / review_bundle).exists():
        issues.append(f"Review Bundle does not exist: {review_bundle}")

    diff_basis_text = get_md_field_value(inputs, "Diff Basis") or ""
    if not diff_basis_text.strip():
        issues.append("Inputs Provided is missing Diff Basis")

    upstream_artifacts = {
        path for path in extract_paths_from_named_field(inputs, "Upstream Artifacts") if path.startswith(f".recursive/run/{run_dir.name}/")
    }
    code_refs = extract_paths_from_named_field(inputs, "Code Refs")
    memory_refs = {
        path for path in extract_paths_from_named_field(inputs, "Memory Refs") if path.startswith(".recursive/memory/")
    }
    audit_question_text = get_md_field_value(inputs, "Audit / Task Questions") or inputs
    if not upstream_artifacts and not review_bundle:
        issues.append("Inputs Provided must cite upstream artifacts or the review bundle used for delegation")
    if is_placeholder_only(audit_question_text):
        issues.append("Inputs Provided is missing concrete Audit / Task Questions")

    claimed_created = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Created"))
    }
    claimed_modified = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Modified"))
    }
    claimed_reviewed = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Reviewed"))
    }
    claimed_relevant_untouched = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Relevant but Untouched"))
    }

    if is_placeholder_only(claimed_actions):
        issues.append("Claimed Actions Taken must contain concrete delegated work details")
    claimed_file_refs = claimed_created | claimed_modified | claimed_reviewed | claimed_relevant_untouched
    if not claimed_file_refs:
        issues.append("Claimed File Impact must cite at least one created, modified, reviewed, or relevant untouched file")

    for created_path in sorted(claimed_created):
        if not (repo_root / created_path).exists():
            issues.append(f"Claimed created file does not exist: {created_path}")
    for reviewed_path in sorted(claimed_modified | claimed_reviewed | claimed_relevant_untouched):
        if not (repo_root / reviewed_path).exists():
            issues.append(f"Claimed file reference does not exist: {reviewed_path}")

    if actual_changed_files is not None:
        actual_changed = set(actual_changed_files)
        missing_changed_claims = [path for path in claimed_modified | claimed_created if path not in actual_changed]
        if missing_changed_claims:
            issues.append(
                f"Claimed modified/created files are not present in the current diff: {', '.join(sorted(missing_changed_claims)[:5])}"
            )

    if review_bundle and (repo_root / review_bundle).exists():
        bundle_content = (repo_root / review_bundle).read_text(encoding="utf-8")
        bundle_artifact_path = normalize_repo_path(get_md_field_value(bundle_content, "Artifact Path") or "")
        bundle_upstream_artifacts = {
            normalize_repo_path(path)
            for path in extract_paths_from_text(get_heading_body(bundle_content, "Upstream Artifacts To Re-read"))
            if normalize_repo_path(path)
        }
        bundle_changed_paths = {
            normalize_repo_path(path)
            for path in extract_paths_from_text(get_heading_body(bundle_content, "Changed Files Reviewed"))
            if normalize_repo_path(path)
        }
        bundle_code_refs = {
            normalize_repo_path(path)
            for path in extract_paths_from_text(get_heading_body(bundle_content, "Targeted Code References"))
            if normalize_repo_path(path)
        }
        allowed_artifacts = {path for path in {bundle_artifact_path, *bundle_upstream_artifacts} if path}
        if current_artifact and allowed_artifacts and current_artifact not in allowed_artifacts:
            issues.append(
                "Inputs Provided Current Artifact must match the review bundle Artifact Path or a cited upstream artifact: "
                + f"{current_artifact}"
            )
        missing_bundle_upstream = sorted(path for path in bundle_upstream_artifacts if path not in upstream_artifacts)
        if missing_bundle_upstream:
            issues.append(
                "Inputs Provided Upstream Artifacts omit bundle upstream artifact(s): "
                + ", ".join(missing_bundle_upstream[:5])
            )
        required_bundle_file_scope = bundle_code_refs or bundle_changed_paths
        if required_bundle_file_scope:
            missing_bundle_scope_paths = sorted(path for path in required_bundle_file_scope if path not in claimed_file_refs)
            if missing_bundle_scope_paths:
                issues.append(
                    "Claimed File Impact omits targeted file scope present in the review bundle: "
                    + ", ".join(missing_bundle_scope_paths[:5])
                )

    artifact_refs = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(claimed_artifact_impact)
        if normalize_repo_path(path).startswith(".recursive/")
    }
    evidence_refs = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(claimed_artifact_impact)
        if normalize_repo_path(path).startswith(f".recursive/run/{run_dir.name}/evidence/")
    }
    if not artifact_refs and not evidence_refs:
        issues.append("Claimed Artifact Impact must cite recursive artifacts or evidence paths used by the subagent")
    missing_artifact_refs = find_missing_repo_paths(repo_root, sorted(artifact_refs))
    if missing_artifact_refs:
        issues.append(f"Claimed artifact references do not exist: {', '.join(missing_artifact_refs[:5])}")
    missing_code_refs = find_missing_repo_paths(repo_root, sorted(code_refs))
    if missing_code_refs:
        issues.append(f"Inputs Provided code refs do not exist: {', '.join(missing_code_refs[:5])}")
    missing_memory_refs = find_missing_repo_paths(repo_root, sorted(memory_refs))
    if missing_memory_refs:
        issues.append(f"Inputs Provided memory refs do not exist: {', '.join(missing_memory_refs[:5])}")

    verification_handoff = get_heading_body(content, "Verification Handoff")
    if verification_handoff and not extract_paths_from_text(verification_handoff):
        issues.append("Verification Handoff must cite files, diffs, or artifacts to inspect")

    return sorted(set(issues))


def parse_subagent_action_record_claims(action_content: str) -> dict[str, set[str] | str]:
    inputs = get_heading_body(action_content, "Inputs Provided")
    claimed_file_impact = get_heading_body(action_content, "Claimed File Impact")
    claimed_artifact_impact = get_heading_body(action_content, "Claimed Artifact Impact")
    current_artifact = normalize_repo_path(get_md_field_value(inputs, "Current Artifact") or "")
    review_bundle = normalize_repo_path(get_md_field_value(inputs, "Review Bundle") or "")
    upstream_artifacts = extract_paths_from_named_field(inputs, "Upstream Artifacts")
    claimed_created = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Created"))
        if normalize_repo_path(path)
    }
    claimed_modified = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Modified"))
        if normalize_repo_path(path)
    }
    claimed_reviewed = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Reviewed"))
        if normalize_repo_path(path)
    }
    claimed_relevant_untouched = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(get_subheading_body(claimed_file_impact, "Relevant but Untouched"))
        if normalize_repo_path(path)
    }
    claimed_artifact_refs = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(claimed_artifact_impact)
        if normalize_repo_path(path).startswith(".recursive/")
    }
    return {
        "current_artifact": current_artifact,
        "review_bundle": review_bundle,
        "upstream_artifacts": upstream_artifacts,
        "created": claimed_created,
        "modified": claimed_modified,
        "reviewed": claimed_reviewed,
        "relevant_untouched": claimed_relevant_untouched,
        "artifact_refs": claimed_artifact_refs,
    }


def lint_subagent_contribution_verification(
    file_path: Path,
    content: str,
    workflow_profile: str,
    run_dir: Path,
    repo_root: Path,
    actual_changed_files: list[str] | None,
) -> list[str]:
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_path.name not in AUDITED_PHASE_FILES:
        return []

    body = get_heading_body(content, "Subagent Contribution Verification")
    if not body:
        return ["Missing or empty section: ## Subagent Contribution Verification"]

    issues: list[str] = []
    action_record_paths = get_subagent_action_record_paths(content, run_dir)
    all_action_record_paths = get_all_subagent_action_record_paths(content)
    audit_context = get_heading_body(content, "Audit Context")
    audit_mode = get_md_field_value(audit_context, "Audit Execution Mode") or ""
    current_phase = get_md_field_value(content, "Phase") or ""
    reviewed_action_records_field = get_named_field_text(body, "Reviewed Action Records") or ""
    main_agent_verification = get_named_field_text(body, "Main-Agent Verification Performed") or ""
    acceptance_decision = trim_md_value(get_md_field_value(body, "Acceptance Decision") or "").lower()
    refresh_handling = get_named_field_text(body, "Refresh Handling") or ""
    repair_performed = get_named_field_text(body, "Repair Performed After Verification") or ""
    verification_paths = {
        normalize_repo_path(path)
        for path in extract_paths_from_field_value(main_agent_verification)
        if normalize_repo_path(path)
    }
    repair_paths = {
        normalize_repo_path(path)
        for path in extract_paths_from_field_value(repair_performed)
        if normalize_repo_path(path)
    }
    current_bundle_path = normalize_repo_path(
        get_md_field_value(get_heading_body(content, "Review Metadata"), "Review Bundle Path")
        or get_md_field_value(content, "Review Bundle Path")
        or ""
    )
    if audit_mode == "subagent" and not action_record_paths:
        issues.append("Audit Execution Mode subagent requires at least one reviewed subagent action record")
    out_of_run_action_records = sorted(path for path in all_action_record_paths if path not in action_record_paths)
    if out_of_run_action_records:
        issues.append(
            "Subagent Contribution Verification may only reference action records under the current run subagents/: "
            + ", ".join(out_of_run_action_records[:5])
        )
    if action_record_paths:
        reviewed_record_paths = {
            normalize_repo_path(path)
            for path in extract_paths_from_field_value(reviewed_action_records_field)
            if normalize_repo_path(path).startswith(f".recursive/run/{run_dir.name}/subagents/")
        }
        if not reviewed_action_records_field.strip():
            issues.append("Subagent Contribution Verification must record Reviewed Action Records")
        else:
            missing_reviewed_records = sorted(path for path in action_record_paths if path not in reviewed_record_paths)
            if missing_reviewed_records:
                issues.append(
                    "Reviewed Action Records is missing referenced action record path(s): "
                    + ", ".join(missing_reviewed_records[:5])
                )
        if not has_meaningful_value(main_agent_verification, disallowed={"n/a", "none"}):
            issues.append("Subagent Contribution Verification must record Main-Agent Verification Performed")
        elif not verification_paths:
            issues.append("Main-Agent Verification Performed must cite files, artifacts, or diff-owned paths that were checked")
        else:
            missing_verification_paths = find_missing_repo_paths(repo_root, sorted(verification_paths))
            if missing_verification_paths:
                issues.append(
                    "Main-Agent Verification Performed references missing path(s): "
                    + ", ".join(missing_verification_paths[:5])
                )
        if acceptance_decision not in {"accepted", "partially accepted", "rejected"}:
            issues.append("Subagent Contribution Verification must record Acceptance Decision: accepted|partially accepted|rejected")
        if not has_meaningful_value(refresh_handling, disallowed={"n/a", "none"}):
            issues.append("Subagent Contribution Verification must record Refresh Handling")
        if not trim_md_value(repair_performed):
            issues.append("Subagent Contribution Verification must record Repair Performed After Verification")
        elif repair_paths:
            missing_repair_paths = find_missing_repo_paths(repo_root, sorted(repair_paths))
            if missing_repair_paths:
                issues.append(
                    "Repair Performed After Verification references missing path(s): "
                    + ", ".join(missing_repair_paths[:5])
                )

    for action_record_path in action_record_paths:
        if not (repo_root / action_record_path).exists():
            issues.append(f"Referenced subagent action record does not exist: {action_record_path}")
            continue
        action_content = (repo_root / action_record_path).read_text(encoding="utf-8")
        action_phase = get_md_field_value(get_heading_body(action_content, "Metadata"), "Phase") or ""
        action_claims = parse_subagent_action_record_claims(action_content)
        if current_phase and action_phase and current_phase != action_phase:
            issues.append(f"Subagent action record phase mismatch: {action_record_path} -> {action_phase}")
        if current_bundle_path:
            action_bundle_path = str(action_claims["review_bundle"])
            if action_bundle_path and action_bundle_path != current_bundle_path:
                issues.append(
                    f"Subagent action record review bundle mismatch: {action_record_path} -> {action_bundle_path}"
                )
        issues.extend(
            lint_subagent_action_record_file(
                repo_root / action_record_path,
                repo_root,
                run_dir,
                actual_changed_files,
            )
        )
        if acceptance_decision in {"accepted", "partially accepted"}:
            claimed_diff_scope = set()
            claimed_diff_scope.update(set(action_claims["created"]))  # type: ignore[arg-type]
            claimed_diff_scope.update(set(action_claims["modified"]))  # type: ignore[arg-type]
            claimed_diff_scope.update(set(action_claims["reviewed"]))  # type: ignore[arg-type]
            expected_verified_paths = set(claimed_diff_scope)
            if actual_changed_files is not None:
                expected_verified_paths = {path for path in expected_verified_paths if path in set(actual_changed_files)}
            missing_verified_paths = sorted(path for path in expected_verified_paths if path not in verification_paths and path not in repair_paths)
            if missing_verified_paths:
                issues.append(
                    "Main-Agent Verification Performed does not reconcile delegated file-impact claims against the actual diff scope: "
                    + ", ".join(missing_verified_paths[:5])
                )

            verification_artifact_scope = {
                str(action_claims["current_artifact"]),
                *set(action_claims["upstream_artifacts"]),  # type: ignore[arg-type]
                *set(action_claims["artifact_refs"]),  # type: ignore[arg-type]
            }
            if action_claims["review_bundle"]:  # type: ignore[index]
                verification_artifact_scope.add(str(action_claims["review_bundle"]))
            verification_artifact_scope.discard("")
            if verification_artifact_scope and not any(path in verification_paths for path in verification_artifact_scope):
                issues.append(
                    "Main-Agent Verification Performed must cite the reviewed artifact, bundle, or upstream recursive artifacts used to accept delegated work"
                )

    return sorted(set(issues))


def collect_reviewed_paths(run_dir: Path, artifact_name: str, content: str) -> set[str]:
    reviewed_paths = extract_paths_from_text(get_heading_body(content, "Worktree Diff Audit"))
    for addendum_path in get_related_addenda_paths(run_dir, artifact_name):
        reviewed_paths.update(extract_paths_from_text(addendum_path.read_text(encoding="utf-8")))
    return reviewed_paths


def lint_review_bundle_reference(content: str, run_dir: Path, repo_root: Path) -> list[str]:
    issues: list[str] = []
    review_metadata = get_heading_body(content, "Review Metadata")
    bundle_path = (
        get_md_field_value(review_metadata, "Review Bundle Path")
        or get_md_field_value(content, "Review Bundle Path")
        or ""
    ).strip()
    expected_prefix = f".recursive/run/{run_dir.name}/evidence/review-bundles/"

    if not bundle_path:
        issues.append("Review Metadata is missing Review Bundle Path")
        return issues

    normalized_bundle_path = normalize_repo_path(bundle_path)
    if not normalized_bundle_path.startswith(expected_prefix):
        issues.append(f"Review Bundle Path must live under `/{expected_prefix}`")
        return issues

    if not (repo_root / normalized_bundle_path).exists():
        issues.append(f"Review Bundle Path does not exist: {normalized_bundle_path}")
        return issues

    bundle_content = (repo_root / normalized_bundle_path).read_text(encoding="utf-8")
    artifact_path = normalize_repo_path(get_md_field_value(bundle_content, "Artifact Path") or "")
    artifact_hash = trim_md_value(get_md_field_value(bundle_content, "Artifact Content Hash") or "")
    if not artifact_path:
        issues.append("Review bundle is missing Artifact Path")
    elif not (repo_root / artifact_path).exists():
        issues.append(f"Review bundle Artifact Path does not exist: {artifact_path}")
    if artifact_path:
        current_hash = content_sha256((repo_root / artifact_path).read_text(encoding="utf-8")) if (repo_root / artifact_path).exists() else ""
        if artifact_hash and current_hash and artifact_hash != current_hash:
            issues.append("Review bundle is stale: Artifact Content Hash no longer matches the current artifact")
    if not artifact_hash:
        issues.append("Review bundle is missing Artifact Content Hash")

    missing_bundle_headings = []
    for heading in (
        "Diff Basis",
        "Changed Files Reviewed",
        "Upstream Artifacts To Re-read",
        "Relevant Addenda",
        "Prior Recursive Evidence",
        "Targeted Code References",
        "Audit Questions",
        "Required Output",
    ):
        if not get_heading_body(bundle_content, heading):
            missing_bundle_headings.append(heading)
    if missing_bundle_headings:
        issues.append(f"Review bundle is missing required section(s): {', '.join(missing_bundle_headings)}")

    review_narrative = "\n".join(
        [
            get_heading_body(content, "Review Scope"),
            get_heading_body(content, "Requirement And Plan Reconciliation"),
            get_heading_body(content, "Plan Alignment Assessment"),
            get_heading_body(content, "Code Quality Assessment"),
            get_heading_body(content, "Issues Found"),
            get_heading_body(content, "Verdict"),
        ]
    )
    cited_paths = {normalize_repo_path(path) for path in extract_paths_from_text(content)}
    cited_review_paths = {normalize_repo_path(path) for path in extract_paths_from_text(review_narrative)}
    upstream_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(bundle_content, "Upstream Artifacts To Re-read"))}
    addenda_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(bundle_content, "Relevant Addenda"))}
    prior_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(bundle_content, "Prior Recursive Evidence"))}
    changed_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(bundle_content, "Changed Files Reviewed"))}
    code_ref_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(bundle_content, "Targeted Code References"))}
    audit_questions = get_heading_body(bundle_content, "Audit Questions")
    if is_placeholder_only(audit_questions):
        issues.append("Review bundle Audit Questions cannot be placeholder-only")
    diff_basis_body = get_heading_body(bundle_content, "Diff Basis")
    for field_name in DIFF_BASIS_FIELDS:
        if get_md_field_value(diff_basis_body, field_name) is None:
            issues.append(f"Review bundle Diff Basis is missing {field_name}")
    if not changed_paths:
        issues.append("Review bundle Changed Files Reviewed cannot be empty")
    else:
        missing_changed_paths = find_missing_repo_paths(repo_root, sorted(changed_paths))
        if missing_changed_paths:
            issues.append(f"Review bundle changed file path(s) do not exist: {', '.join(missing_changed_paths[:5])}")
    if not code_ref_paths:
        issues.append("Review bundle Targeted Code References cannot be empty")
    else:
        missing_code_refs = find_missing_repo_paths(repo_root, sorted(code_ref_paths))
        if missing_code_refs:
            issues.append(f"Review bundle code ref path(s) do not exist: {', '.join(missing_code_refs[:5])}")
        elif changed_paths and not any(path in changed_paths for path in code_ref_paths):
            issues.append("Review bundle Targeted Code References do not overlap the changed-file scope")
    expected_addenda = set(get_expected_effective_input_addenda_paths(run_dir, "03.5-code-review.md"))
    missing_bundle_addenda = sorted(path for path in expected_addenda if path not in addenda_paths)
    if missing_bundle_addenda:
        issues.append(f"Review bundle is missing effective-input addenda: {', '.join(missing_bundle_addenda[:5])}")

    if upstream_paths and not any(path in cited_review_paths for path in upstream_paths):
        issues.append("Code review narrative does not cite any upstream artifact from the review bundle")
    if addenda_paths and not any(path in cited_review_paths for path in addenda_paths):
        issues.append("Code review narrative does not cite any relevant addendum from the review bundle")
    if prior_paths and not any(path in cited_review_paths for path in prior_paths):
        issues.append("Code review narrative does not cite any prior recursive evidence from the review bundle")
    if (changed_paths or code_ref_paths) and not any(path in cited_review_paths for path in (changed_paths | code_ref_paths)):
        issues.append("Code review narrative does not cite any changed file or code reference from the review bundle")
    if normalized_bundle_path not in cited_paths:
        issues.append("Code review must cite the Review Bundle Path in its written review artifact")

    verdict_body = get_heading_body(content, "Verdict")
    if not verdict_body or is_placeholder_only(verdict_body):
        issues.append("Verdict section must contain a concrete review verdict grounded in the review bundle")

    return issues


def lint_phase8_skill_usage_capture(content: str) -> list[str]:
    issues: list[str] = []
    usage_body = get_heading_body(content, "Run-Local Skill Usage Capture")
    if not usage_body:
        return ["Missing or empty section: ## Run-Local Skill Usage Capture"]

    required_fields = [
        "Skill Usage Relevance",
        "Available Skills",
        "Skills Sought",
        "Skills Attempted",
        "Skills Used",
        "Worked Well",
        "Issues Encountered",
        "Future Guidance",
        "Promotion Candidates",
    ]
    for field_name in required_fields:
        if get_md_field_value(usage_body, field_name) is None:
            issues.append(f"Run-Local Skill Usage Capture is missing {field_name}")

    relevance = normalize_skill_usage_relevance(get_md_field_value(usage_body, "Skill Usage Relevance"))
    if relevance not in SKILL_USAGE_RELEVANCE_STATUSES:
        issues.append("Run-Local Skill Usage Capture must declare Skill Usage Relevance: relevant|not-relevant")
        return issues

    if relevance in {"relevant", "yes"}:
        for field_name in ("Available Skills", "Skills Attempted", "Skills Used", "Future Guidance"):
            if not is_meaningful_requirement_field(get_md_field_value(usage_body, field_name)):
                issues.append(f"Run-Local Skill Usage Capture must record {field_name} when skill usage is relevant")
        attempted = trim_md_value(get_md_field_value(usage_body, "Skills Attempted") or "").lower()
        used = trim_md_value(get_md_field_value(usage_body, "Skills Used") or "").lower()
        if attempted in {"none", "n/a"} and used in {"none", "n/a"}:
            issues.append("Run-Local Skill Usage Capture cannot mark skill usage relevant while claiming no attempted or used skills")

    promotion_body = get_heading_body(content, "Skill Memory Promotion Review")
    if not promotion_body:
        issues.append("Missing or empty section: ## Skill Memory Promotion Review")
        return issues

    for field_name in (
        "Durable Skill Lessons Promoted",
        "Generalized Guidance Updated",
        "Run-Local Observations Left Unpromoted",
        "Promotion Decision Rationale",
    ):
        if get_md_field_value(promotion_body, field_name) is None:
            issues.append(f"Skill Memory Promotion Review is missing {field_name}")

    if relevance in {"relevant", "yes"} and not is_meaningful_requirement_field(
        get_md_field_value(promotion_body, "Promotion Decision Rationale")
    ):
        issues.append("Skill Memory Promotion Review must explain why relevant run-local observations were or were not promoted")

    return issues


def lint_phase_specific_rules(
    file_path: Path,
    content: str,
    workflow_profile: str,
    run_dir: Path,
    repo_root: Path,
    requirement_ids: list[str],
    actual_changed_files: list[str] | None,
) -> list[str]:
    issues: list[str] = []
    issues.extend(lint_effective_input_addenda(file_path, content, workflow_profile, run_dir))
    issues.extend(lint_source_requirement_inventory(file_path, content, workflow_profile, run_dir))
    if file_path.name == "02-to-be-plan.md":
        issues.extend(lint_requirement_mapping(content, workflow_profile, run_dir, repo_root))
        issues.extend(lint_plan_drift_check(content, workflow_profile))
    issues.extend(
        lint_requirement_completion_status(
            file_path,
            content,
            requirement_ids,
            run_dir,
            workflow_profile,
            actual_changed_files,
        )
    )
    issues.extend(lint_prior_recursive_evidence(content, run_dir, workflow_profile, repo_root, file_path.name))
    issues.extend(
        lint_subagent_contribution_verification(
            file_path,
            content,
            workflow_profile,
            run_dir,
            repo_root,
            actual_changed_files,
        )
    )
    if workflow_profile not in STRICT_WORKFLOW_PROFILES:
        return issues

    if file_path.name == "00-worktree.md":
        diff_basis, diff_basis_error = normalize_diff_basis(repo_root, get_run_diff_basis(run_dir))
        if diff_basis_error:
            issues.append(f"Phase 0 diff basis is not executable: {diff_basis_error}")
        elif diff_basis is None:
            issues.append("Phase 0 diff basis could not be normalized")

    if file_path.name == "03-implementation-summary.md":
        tdd_body = get_heading_body(content, "TDD Compliance Log")
        tdd_mode = (get_md_field_value(tdd_body, "TDD Mode") or get_md_field_value(content, "TDD Mode") or "").lower()

        if not has_gate_line(content, "TDD Compliance"):
            issues.append("Missing required gate line: TDD Compliance: PASS|FAIL")
        if tdd_mode not in TDD_MODES:
            issues.append("TDD Compliance Log is missing TDD Mode: strict|pragmatic")
        elif tdd_mode == "strict":
            if "RED Evidence:" not in tdd_body:
                issues.append("Strict TDD is missing RED Evidence in ## TDD Compliance Log")
            if "GREEN Evidence:" not in tdd_body:
                issues.append("Strict TDD is missing GREEN Evidence in ## TDD Compliance Log")

            red_prefix = f".recursive/run/{run_dir.name}/evidence/logs/red/"
            green_prefix = f".recursive/run/{run_dir.name}/evidence/logs/green/"
            red_paths = collect_paths_under_prefix(tdd_body, red_prefix)
            green_paths = collect_paths_under_prefix(tdd_body, green_prefix)

            if not red_paths:
                issues.append(f"Strict TDD requires at least one RED evidence path under `/{red_prefix}`")
            else:
                missing_red = find_missing_repo_paths(repo_root, red_paths)
                if missing_red:
                    issues.append(f"Strict TDD RED evidence path(s) do not exist: {', '.join(missing_red[:5])}")

            if not green_paths:
                issues.append(f"Strict TDD requires at least one GREEN evidence path under `/{green_prefix}`")
            else:
                missing_green = find_missing_repo_paths(repo_root, green_paths)
                if missing_green:
                    issues.append(f"Strict TDD GREEN evidence path(s) do not exist: {', '.join(missing_green[:5])}")
        else:
            exception_body = get_heading_body(content, "Pragmatic TDD Exception")
            if not exception_body:
                issues.append("TDD Mode pragmatic requires ## Pragmatic TDD Exception")
            else:
                if not has_meaningful_value(get_md_field_value(exception_body, "Exception reason"), disallowed={"n/a", "none"}):
                    issues.append("Pragmatic TDD Exception is missing Exception reason")
                if not has_meaningful_value(get_md_field_value(exception_body, "Compensating validation"), disallowed={"n/a", "none"}):
                    issues.append("Pragmatic TDD Exception is missing Compensating validation")

                pragmatic_paths = collect_paths_under_prefix(exception_body, f".recursive/run/{run_dir.name}/evidence/")
                if not pragmatic_paths:
                    issues.append(
                        f"Pragmatic TDD Exception requires compensating evidence paths under `/.recursive/run/{run_dir.name}/evidence/`"
                    )
                else:
                    missing_pragmatic = find_missing_repo_paths(repo_root, pragmatic_paths)
                    if missing_pragmatic:
                        issues.append(
                            f"Pragmatic TDD compensating evidence path(s) do not exist: {', '.join(missing_pragmatic[:5])}"
                        )

    if file_path.name == "05-manual-qa.md":
        qa_record = get_heading_body(content, "QA Execution Record")
        evidence_body = get_heading_body(content, "Evidence and Artifacts")
        signoff_body = get_heading_body(content, "User Sign-Off")
        qa_mode = (get_md_field_value(qa_record, "QA Execution Mode") or get_md_field_value(content, "QA Execution Mode") or "").lower()

        if not qa_record:
            issues.append("Missing or empty section: ## QA Execution Record")
        if qa_mode not in QA_EXECUTION_MODES:
            issues.append("QA Execution Record is missing QA Execution Mode: human|agent-operated|hybrid")
        else:
            if qa_mode in {"human", "hybrid"}:
                if not has_meaningful_value(get_md_field_value(signoff_body, "Approved by"), disallowed={"n/a", "not required", "none"}):
                    issues.append(f"QA Execution Mode {qa_mode} requires User Sign-Off -> Approved by")
                if not has_meaningful_value(get_md_field_value(signoff_body, "Date"), disallowed={"n/a", "not required", "none"}):
                    issues.append(f"QA Execution Mode {qa_mode} requires User Sign-Off -> Date")

            if qa_mode in {"agent-operated", "hybrid"}:
                if not has_meaningful_value(get_md_field_value(qa_record, "Agent Executor"), disallowed={"n/a", "none"}):
                    issues.append(f"QA Execution Mode {qa_mode} requires QA Execution Record -> Agent Executor")
                if not has_meaningful_value(get_md_field_value(qa_record, "Tools Used"), disallowed={"n/a", "none"}):
                    issues.append(f"QA Execution Mode {qa_mode} requires QA Execution Record -> Tools Used")

                qa_paths = collect_paths_under_prefix(f"{qa_record}\n{evidence_body}", f".recursive/run/{run_dir.name}/evidence/")
                if not qa_paths:
                    issues.append(f"QA Execution Mode {qa_mode} requires evidence paths under `/.recursive/run/{run_dir.name}/evidence/`")
                else:
                    missing_qa_paths = find_missing_repo_paths(repo_root, qa_paths)
                    if missing_qa_paths:
                        issues.append(f"QA evidence path(s) do not exist: {', '.join(missing_qa_paths[:5])}")

    if file_path.name == "03.5-code-review.md":
        issues.extend(lint_review_bundle_reference(content, run_dir, repo_root))

    if file_path.name == "08-memory-impact.md":
        issues.extend(lint_phase8_skill_usage_capture(content))

    return sorted(set(issues))


def get_artifact_required_sections(file_name: str, workflow_profile: str) -> list[str]:
    section_map: dict[str, list[str]] = {
        "00-worktree.md": [
            "TODO",
            "Directory Selection",
            "Safety Verification",
            "Worktree Creation",
            "Main Branch Protection",
            "Project Setup",
            "Test Baseline Verification",
            "Worktree Context",
            "Diff Basis For Later Audits",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "00-requirements.md": [
            "TODO",
            "Requirements",
            "Out of Scope",
            "Constraints",
            "Coverage Gate",
            "Approval Gate",
        ],
        "01-as-is.md": [
            "TODO",
            "Reproduction Steps (Novice-Runnable)",
            "Current Behavior by Requirement",
            "Source Requirement Inventory",
            "Relevant Code Pointers",
            "Known Unknowns",
            "Evidence",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "01.5-root-cause.md": [
            "TODO",
            "Error Analysis",
            "Reproduction Verification",
            "Recent Changes Analysis",
            "Evidence Gathering (Multi-Layer if applicable)",
            "Data Flow Trace",
            "Pattern Analysis",
            "Hypothesis Testing",
            "Root Cause Summary",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "02-to-be-plan.md": [
            "TODO",
            "Planned Changes by File",
            "Requirement Mapping",
            "Implementation Steps",
            "Testing Strategy",
            "Playwright Plan (if applicable)",
            "Manual QA Scenarios",
            "Idempotence and Recovery",
            "Implementation Sub-phases",
            "Plan Drift Check",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "03-implementation-summary.md": [
            "TODO",
            "Changes Applied",
            "TDD Compliance Log",
            "Plan Deviations",
            "Implementation Evidence",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "03.5-code-review.md": [
            "TODO",
            "Review Scope",
            "Plan Alignment Assessment",
            "Code Quality Assessment",
            "Issues Found",
            "Verdict",
            "Review Metadata",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "04-test-summary.md": [
            "TODO",
            "Pre-Test Implementation Audit",
            "Environment",
            "Execution Mode",
            "Commands Executed (Exact)",
            "Results Summary",
            "Evidence and Artifacts",
            "Failures and Diagnostics (if any)",
            "Flake/Rerun Notes",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "05-manual-qa.md": [
            "TODO",
            "QA Execution Record",
            "QA Scenarios and Results",
            "Evidence and Artifacts",
            "User Sign-Off",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "06-decisions-update.md": [
            "TODO",
            "Decisions Changes Applied",
            "Rationale",
            "Resulting Decision Entry",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "07-state-update.md": [
            "TODO",
            "State Changes Applied",
            "Rationale",
            "Resulting State Summary",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
        "08-memory-impact.md": [
            "TODO",
            "Diff Basis",
            "Changed Paths Review",
            "Affected Memory Docs",
            "Run-Local Skill Usage Capture",
            "Skill Memory Promotion Review",
            "Uncovered Paths",
            "Router and Parent Refresh",
            "Final Status Summary",
            "Traceability",
            "Coverage Gate",
            "Approval Gate",
        ],
    }
    headings = list(section_map.get(file_name, ["TODO", "Coverage Gate", "Approval Gate"]))
    if workflow_profile in STRICT_WORKFLOW_PROFILES and file_name in AUDITED_PHASE_FILES:
        headings.extend(AUDIT_REQUIRED_HEADINGS)
        if file_name in PRIOR_RECURSIVE_EVIDENCE_FILES:
            headings.append("Prior Recursive Evidence Reviewed")
    return headings


def get_header_remediation_lines(missing_fields: list[str]) -> list[str]:
    out: list[str] = []
    for field in missing_fields:
        if field == "Run":
            out.append("Run: `/.recursive/run/<run-id>/`")
        elif field == "Phase":
            out.append("Phase: `<phase name>`")
        elif field == "Status":
            out.append("Status: `DRAFT`")
        elif field == "Inputs":
            out.append("Inputs:")
            out.append("- `<path>`")
        elif field == "Outputs":
            out.append("Outputs:")
            out.append("- `<path>`")
        elif field == "Scope note":
            out.append("Scope note: <one sentence describing what this artifact decides/enables>.")
        elif field == "LockedAt":
            out.append("LockedAt: `YYYY-MM-DDTHH:mm:ssZ`")
        elif field == "LockHash":
            out.append("LockHash: `<sha256-hex>`")
    return out


def is_lock_valid_for_lint(file_path: Path, workflow_profile: str) -> bool:
    if not file_path.exists():
        return False

    content = file_path.read_text(encoding="utf-8")
    status = get_md_field_value(content, "Status") or ""
    has_todo, _, _, unchecked = get_todo_stats(content)
    audit_required = workflow_profile in STRICT_WORKFLOW_PROFILES and file_path.name in AUDITED_PHASE_FILES
    audit_ok = (not audit_required) or get_gate_status(content, "Audit") == "PASS"
    run_dir = file_path.parent
    repo_root = run_dir.parent.parent.parent
    requirement_ids: list[str] = []
    requirements_path = run_dir / "00-requirements.md"
    if requirements_path.exists():
        requirement_ids = get_run_requirement_ids(run_dir, workflow_profile)
    actual_changed_files: list[str] | None = None
    if workflow_profile in STRICT_WORKFLOW_PROFILES:
        diff_basis = get_run_diff_basis(run_dir)
        raw_changed_files, _diff_basis_error = get_git_changed_files(repo_root, diff_basis)
        if raw_changed_files is not None:
            actual_changed_files = filter_runtime_changed_files(raw_changed_files, run_dir.name)
    phase_specific_issues = lint_phase_specific_rules(
        file_path,
        content,
        workflow_profile,
        run_dir,
        repo_root,
        requirement_ids,
        actual_changed_files,
    )
    tdd_gate_ok = file_path.name != "03-implementation-summary.md" or get_gate_status(content, "TDD Compliance") == "PASS"
    return (
        status == "LOCKED"
        and has_header_field(content, "LockedAt")
        and has_header_field(content, "LockHash")
        and get_gate_status(content, "Coverage") == "PASS"
        and get_gate_status(content, "Approval") == "PASS"
        and audit_ok
        and tdd_gate_ok
        and has_todo
        and unchecked == 0
        and not phase_specific_issues
    )


def lint_traceability(file_path: Path, content: str, requirement_ids: list[str]) -> list[str]:
    issues: list[str] = []
    if file_path.name not in TRACEABILITY_REQUIRED_FILES:
        return issues

    traceability_body = get_heading_body(content, "Traceability")
    if not traceability_body:
        issues.append("Missing Traceability section content")
        return issues

    missing_ids = [requirement_id for requirement_id in requirement_ids if requirement_id not in traceability_body]
    if missing_ids:
        issues.append(f"Traceability is missing explicit coverage for: {', '.join(missing_ids)}")

    if requirement_ids and not re.search(r"\bR\d+\b", traceability_body):
        issues.append("Traceability is vague and does not mention any requirement IDs")

    return issues


def lint_audit_sections(
    file_path: Path,
    content: str,
    workflow_profile: str,
    actual_changed_files: list[str] | None,
    diff_basis_error: str | None,
    run_id: str,
    run_dir: Path,
) -> list[str]:
    issues: list[str] = []
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_path.name not in AUDITED_PHASE_FILES:
        return issues

    audit_status = get_gate_status(content, "Audit")
    coverage_status = get_gate_status(content, "Coverage")
    approval_status = get_gate_status(content, "Approval")

    if audit_status == "MISSING":
        issues.append("Missing required audit verdict line: Audit: PASS|FAIL")
    if coverage_status == "PASS" and audit_status != "PASS":
        issues.append("Coverage: PASS is invalid without Audit: PASS")
    if approval_status == "PASS" and audit_status != "PASS":
        issues.append("Approval: PASS is invalid without Audit: PASS")

    audit_context = get_heading_body(content, "Audit Context")
    if not audit_context:
        issues.append("Audit Context section is empty")
    else:
        if get_md_field_value(audit_context, "Audit Execution Mode") not in {"subagent", "self-audit"}:
            issues.append("Audit Context is missing a valid Audit Execution Mode: subagent|self-audit")
        if get_md_field_value(audit_context, "Subagent Availability") not in {"available", "unavailable"}:
            issues.append("Audit Context is missing a valid Subagent Availability: available|unavailable")
        if not has_meaningful_value(get_md_field_value(audit_context, "Subagent Capability Probe"), disallowed={"n/a", "none"}):
            issues.append("Audit Context is missing Subagent Capability Probe")
        if not has_meaningful_value(get_md_field_value(audit_context, "Delegation Decision Basis"), disallowed={"n/a", "none"}):
            issues.append("Audit Context is missing Delegation Decision Basis")
        if get_md_field_value(audit_context, "Audit Inputs Provided") is None and "Audit Inputs Provided:" not in audit_context:
            issues.append("Audit Context is missing Audit Inputs Provided")
        issues.extend(collect_subagent_delegation_issues(audit_context))

    for heading in AUDIT_REQUIRED_HEADINGS:
        section_body = get_heading_body(content, heading)
        if not section_body:
            issues.append(f"Missing or empty audited-phase section: ## {heading}")
        elif is_placeholder_only(section_body):
            issues.append(f"Audited-phase section still contains placeholder-only content: ## {heading}")

    diff_audit_body = get_heading_body(content, "Worktree Diff Audit")
    for field in DIFF_BASIS_FIELDS:
        if get_md_field_value(diff_audit_body, field) is None:
            issues.append(f"Worktree Diff Audit is missing: {field}:")

    gaps_body = get_heading_body(content, "Gaps Found")
    if audit_status == "PASS" and gaps_body and not re.search(r"\bnone\b", gaps_body, re.IGNORECASE):
        issues.append("Audit: PASS is invalid while Gaps Found still lists unresolved in-scope gaps")

    expected_changed_files = get_phase_owned_actual_changed_files(file_path.name, actual_changed_files)
    if file_path.name in DIFF_AUDITED_FILES and expected_changed_files is not None:
        if diff_basis_error:
            issues.append(f"Cannot verify git diff basis: {diff_basis_error}")
        else:
            reviewed_paths = collect_reviewed_paths(run_dir, file_path.name, content)
            missing_paths = [path for path in expected_changed_files if path not in reviewed_paths]
            if missing_paths:
                preview = ", ".join(missing_paths[:5])
                suffix = " ..." if len(missing_paths) > 5 else ""
                issues.append(f"Worktree Diff Audit does not account for actual changed files from git diff: {preview}{suffix}")

    return issues


def lint_artifact_file(
    file_path: Path,
    run_dir: Path,
    repo_root: Path,
    workflow_profile: str,
    requirement_ids: list[str],
    actual_changed_files: list[str] | None,
    diff_basis_error: str | None,
) -> tuple[int, int]:
    content = file_path.read_text(encoding="utf-8")
    file_name = file_path.name
    status = get_md_field_value(content, "Status") or "UNKNOWN"

    missing_header_fields = [
        field
        for field in ("Run", "Phase", "Status", "Inputs", "Outputs", "Scope note")
        if not has_header_field(content, field)
    ]
    if missing_header_fields:
        write_issue(
            "FAIL",
            file_path,
            f"Missing required header field(s): {', '.join(missing_header_fields)}",
            get_header_remediation_lines(missing_header_fields),
        )
        return 1, 0

    fail_count = 0
    warn_count = 0

    if status not in ("DRAFT", "LOCKED"):
        fail_count += 1
        write_issue("FAIL", file_path, f"Invalid Status value '{status}' (expected DRAFT or LOCKED)", ["Status: `DRAFT`"])

    if status == "LOCKED":
        lock_missing = [field for field in ("LockedAt", "LockHash") if not has_header_field(content, field)]
        if lock_missing:
            fail_count += 1
            write_issue(
                "FAIL",
                file_path,
                f"Status is LOCKED but missing: {', '.join(lock_missing)}",
                get_header_remediation_lines(lock_missing),
            )

    has_todo, _total, _checked, unchecked = get_todo_stats(content)
    if not has_todo:
        fail_count += 1
        write_issue("FAIL", file_path, "Missing required section: ## TODO", ["## TODO", "", "- [ ] <task 1>", "- [ ] <task 2>"])
    elif status == "LOCKED" and unchecked > 0:
        fail_count += 1
        write_issue(
            "FAIL",
            file_path,
            f"LOCKED artifact has unchecked TODO items: {unchecked}",
            ["# Option A: check all TODO boxes under ## TODO", "# Option B: set Status back to `DRAFT` until TODOs are complete"],
        )

    for heading in get_artifact_required_sections(file_name, workflow_profile):
        if not has_heading(content, heading):
            fail_count += 1
            write_issue("FAIL", file_path, f"Missing required section heading: ## {heading}", [f"## {heading}", "", "<content>"])

    for gate in ("Coverage", "Approval"):
        if not has_gate_line(content, gate):
            fail_count += 1
            write_issue("FAIL", file_path, f"Missing required gate line: {gate}: PASS|FAIL", [f"{gate}: FAIL"])

    traceability_issues = lint_traceability(file_path, content, requirement_ids)
    for issue in traceability_issues:
        fail_count += 1
        write_issue("FAIL", file_path, issue)

    audit_issues = lint_audit_sections(
        file_path,
        content,
        workflow_profile,
        actual_changed_files,
        diff_basis_error,
        run_dir.name,
        run_dir,
    )
    for issue in audit_issues:
        fail_count += 1
        write_issue("FAIL", file_path, issue)

    phase_specific_issues = lint_phase_specific_rules(
        file_path,
        content,
        workflow_profile,
        run_dir,
        repo_root,
        requirement_ids,
        actual_changed_files,
    )
    for issue in phase_specific_issues:
        fail_count += 1
        write_issue("FAIL", file_path, issue)

    if file_name in ("04-test-summary.md", "05-manual-qa.md"):
        evidence_dir = run_dir / "evidence"
        required_subdirs = ("screenshots", "logs", "perf", "traces")
        if not evidence_dir.exists():
            warn_count += 1
            remediation = [
                f'mkdir -p "{evidence_dir / "screenshots"}"',
                f'mkdir -p "{evidence_dir / "logs"}"',
                f'mkdir -p "{evidence_dir / "perf"}"',
                f'mkdir -p "{evidence_dir / "traces"}"',
                f'mkdir -p "{evidence_dir / "other"}"',
            ]
            write_issue("WARN", file_path, f"Evidence directory missing at {evidence_dir}", remediation)
        else:
            missing_subdirs = [subdir for subdir in required_subdirs if not (evidence_dir / subdir).exists()]
            if missing_subdirs:
                warn_count += 1
                remediation = [f'mkdir -p "{evidence_dir / subdir}"' for subdir in missing_subdirs]
                write_issue(
                    "WARN",
                    file_path,
                    f"Evidence subfolder(s) missing under {evidence_dir}: {', '.join(missing_subdirs)}",
                    remediation,
                )

    return fail_count, warn_count


def lint_memory_doc(file_path: Path) -> tuple[int, int]:
    content = file_path.read_text(encoding="utf-8")
    fail_count = 0
    warn_count = 0

    missing_fields = [field for field in MEMORY_REQUIRED_FIELDS if not has_header_field(content, field)]
    if missing_fields:
        fail_count += 1
        write_issue("FAIL", file_path, f"Missing required memory metadata field(s): {', '.join(missing_fields)}")
        return fail_count, warn_count

    memory_type = (get_md_field_value(content, "Type") or "").lower()
    if memory_type not in MEMORY_ALLOWED_TYPES:
        fail_count += 1
        write_issue("FAIL", file_path, f"Invalid memory Type '{memory_type}' (expected one of: {', '.join(sorted(MEMORY_ALLOWED_TYPES))})")

    memory_status = (get_md_field_value(content, "Status") or "").upper()
    if memory_status not in MEMORY_ALLOWED_STATUSES:
        fail_count += 1
        write_issue("FAIL", file_path, f"Invalid memory Status '{memory_status}' (expected one of: {', '.join(sorted(MEMORY_ALLOWED_STATUSES))})")

    if has_header_field(content, "Parent") and not get_md_field_value(content, "Parent"):
        warn_count += 1
        write_issue("WARN", file_path, "Parent metadata field is present but empty")

    if has_header_field(content, "Superseded-By") and not get_md_field_value(content, "Superseded-By"):
        warn_count += 1
        write_issue("WARN", file_path, "Superseded-By metadata field is present but empty")

    return fail_count, warn_count


def lint_memory_plane(repo_root: Path) -> tuple[int, int]:
    fail_count = 0
    warn_count = 0

    memory_root = repo_root / ".recursive" / "memory"
    router_path = memory_root / "MEMORY.md"

    if not memory_root.exists():
        write_issue("FAIL", memory_root, "Memory plane directory is missing")
        return 1, 0

    if not router_path.exists():
        fail_count += 1
        write_issue("FAIL", router_path, "Memory router file is missing")

    for subdir in ("domains", "patterns", "incidents", "episodes", "archive", "skills"):
        full = memory_root / subdir
        if not full.exists():
            warn_count += 1
            write_issue("WARN", full, "Memory subdirectory is missing")

    skill_router_path = memory_root / "skills" / "SKILLS.md"
    if not skill_router_path.exists():
        warn_count += 1
        write_issue("WARN", skill_router_path, "Skill memory router file is missing")
    else:
        for subdir in ("availability", "usage", "issues", "patterns"):
            full = memory_root / "skills" / subdir
            if not full.exists():
                warn_count += 1
                write_issue("WARN", full, "Skill memory subdirectory is missing")

    for doc in sorted(memory_root.rglob("*.md")):
        if doc.name in SKILL_MEMORY_ROUTER_NAMES:
            continue
        doc_fail, doc_warn = lint_memory_doc(doc)
        fail_count += doc_fail
        warn_count += doc_warn

    return fail_count, warn_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint recursive-mode run artifacts.")
    parser.add_argument("--run-id", default="", help="Run ID to lint (default: latest run).")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--all-runs", action="store_true", help="Lint all runs under .recursive/run/.")
    parser.add_argument("--strict", action="store_true", help="Treat WARN as FAIL.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_root = repo_root / ".recursive" / "run"
    if not run_root.exists():
        print(f"[FAIL] recursive run directory not found at: {run_root}")
        print("       Is this the project repo root? (Expected .recursive/run/)")
        sys.exit(1)

    if args.all_runs:
        run_dirs = [path for path in run_root.iterdir() if path.is_dir()]
        if not run_dirs:
            print(f"[FAIL] No runs found under: {run_root}")
            sys.exit(1)
    elif args.run_id.strip():
        run_dir = run_root / args.run_id.strip()
        if not run_dir.exists():
            print(f"[FAIL] Run directory not found: {run_dir}")
            sys.exit(1)
        run_dirs = [run_dir]
    else:
        latest = get_latest_run_directory(run_root)
        if latest is None:
            print(f"[FAIL] No runs found under: {run_root}")
            sys.exit(1)
        run_dirs = [latest]

    total_fail = 0
    total_warn = 0
    artifacts = [
        "00-requirements.md",
        "00-worktree.md",
        "01-as-is.md",
        "01.5-root-cause.md",
        "02-to-be-plan.md",
        "03-implementation-summary.md",
        "03.5-code-review.md",
        "04-test-summary.md",
        "05-manual-qa.md",
        "06-decisions-update.md",
        "07-state-update.md",
        "08-memory-impact.md",
    ]

    for run_dir in run_dirs:
        print(f"Linting run: {run_dir.name}")
        print(f"Path: {run_dir}")
        workflow_profile = get_workflow_profile(run_dir)
        print(f"Workflow Profile: {workflow_profile}")
        print()

        requirements_path = run_dir / "00-requirements.md"
        requirement_ids: list[str] = []
        if requirements_path.exists():
            requirement_ids = get_run_requirement_ids(run_dir, workflow_profile)
            if not requirement_ids:
                total_fail += 1
                write_issue("FAIL", requirements_path, "Could not determine any requirement or source-inventory IDs for the run")

        diff_basis = get_run_diff_basis(run_dir)
        actual_changed_files: list[str] | None = None
        diff_basis_error: str | None = None
        if workflow_profile in STRICT_WORKFLOW_PROFILES:
            raw_changed_files, diff_basis_error = get_git_changed_files(repo_root, diff_basis)
            if raw_changed_files is not None:
                actual_changed_files = filter_runtime_changed_files(raw_changed_files, run_dir.name)

        expected_artifacts = list(artifacts)
        if workflow_profile == "legacy":
            expected_artifacts = [artifact for artifact in expected_artifacts if artifact not in LATE_PHASE_ARTIFACTS]

        for artifact in expected_artifacts:
            artifact_path = run_dir / artifact
            if not artifact_path.exists():
                print(f"[WARN] Missing artifact (ok if not reached yet): {artifact_path}")
                total_warn += 1
                continue

            fail_count, warn_count = lint_artifact_file(
                artifact_path,
                run_dir,
                repo_root,
                workflow_profile,
                requirement_ids,
                actual_changed_files,
                diff_basis_error,
            )
            total_fail += fail_count
            total_warn += warn_count

        addenda_dir = run_dir / "addenda"
        if addenda_dir.exists():
            for addendum in sorted(addenda_dir.glob("*.md")):
                fail_count, warn_count = lint_artifact_file(
                    addendum,
                    run_dir,
                    repo_root,
                    workflow_profile,
                    requirement_ids,
                    actual_changed_files,
                    diff_basis_error,
                )
                total_fail += fail_count
                total_warn += warn_count

        subagents_dir = run_dir / "subagents"
        if subagents_dir.exists():
            for action_record in sorted(subagents_dir.glob("*.md")):
                issues = lint_subagent_action_record_file(action_record, repo_root, run_dir, actual_changed_files)
                for issue in issues:
                    total_fail += 1
                    write_issue("FAIL", action_record, issue)

        if workflow_profile in (STRICT_WORKFLOW_PROFILES | {COMPAT_WORKFLOW_PROFILE}):
            late_requirements = [
                ("05-manual-qa.md", "06-decisions-update.md"),
                ("06-decisions-update.md", "07-state-update.md"),
                ("07-state-update.md", "08-memory-impact.md"),
            ]
            for prior_artifact, next_artifact in late_requirements:
                if is_lock_valid_for_lint(run_dir / prior_artifact, workflow_profile) and not (run_dir / next_artifact).exists():
                    total_fail += 1
                    write_issue(
                        "FAIL",
                        run_dir / next_artifact,
                        f"Run profile {workflow_profile} requires {next_artifact} after {prior_artifact} locks",
                    )

            memory_fail, memory_warn = lint_memory_plane(repo_root)
            total_fail += memory_fail
            total_warn += memory_warn

        print("----")
        print()

    print("Summary")
    print(f"- FAIL: {total_fail}")
    print(f"- WARN: {total_warn}")
    print()

    effective_fail = total_fail + (total_warn if args.strict else 0)
    if effective_fail > 0:
        print("[FAIL] Lint failed")
        sys.exit(1)

    print("[OK] Lint passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
