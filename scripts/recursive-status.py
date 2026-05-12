#!/usr/bin/env python3
"""
Show recursive-mode run status, lock-chain validity, and audit blockers.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


CURRENT_WORKFLOW_PROFILE = "recursive-mode-audit-v2"
STRICT_WORKFLOW_PROFILE = "recursive-mode-audit-v1"
COMPAT_WORKFLOW_PROFILE = "memory-phase8"
STRICT_WORKFLOW_PROFILES = {CURRENT_WORKFLOW_PROFILE, STRICT_WORKFLOW_PROFILE}
LATE_PHASE_KEYS = {"06", "07", "08"}
LATE_PHASE_FILES = {"06-decisions-update.md", "07-state-update.md", "08-memory-impact.md"}
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
PRODUCT_DIFF_PHASE_FILES = {"03-implementation-summary.md", "03.5-code-review.md", "04-test-summary.md"}
DECISIONS_DIFF_PHASE_FILES = {"06-decisions-update.md"}
STATE_DIFF_PHASE_FILES = {"07-state-update.md"}
MEMORY_DIFF_PHASE_FILES = {"08-memory-impact.md"}
LOCK_HASH_LINE_RE = re.compile(r"(?m)^[ \t]*LockHash:.*(?:\n|$)")
TDD_MODES = {"strict", "pragmatic"}
QA_EXECUTION_MODES = {"human", "agent-operated", "hybrid"}
TRANSIENT_RUNTIME_DIR_MARKERS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".tox", ".nox"}
TRANSIENT_RUNTIME_FILE_NAMES = {".ds_store", "thumbs.db"}
TRANSIENT_RUNTIME_SUFFIXES = (".pyc", ".pyo", ".pyd")
DIFF_BASIS_ALLOWED_TYPES = {"local commit", "local branch", "remote ref", "merge-base derived"}
WORKING_TREE_COMPARISON_REFS = {"working-tree", "working-tree@head", "worktree", "working-tree+head"}
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
SKILL_MEMORY_ROUTER_NAMES = {"MEMORY.md", "SKILLS.md"}
SUBAGENT_ACTION_REQUIRED_HEADINGS = [
    "Metadata",
    "Inputs Provided",
    "Claimed Actions Taken",
    "Claimed File Impact",
    "Claimed Artifact Impact",
    "Claimed Findings",
    "Verification Handoff",
]
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


def load_lint_module():
    module_path = Path(__file__).with_name("lint-recursive-run.py")
    spec = importlib.util.spec_from_file_location("recursive_mode_lint", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load lint module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_phase_rules_module():
    module_path = Path(__file__).with_name("recursive_phase_rules.py")
    spec = importlib.util.spec_from_file_location("recursive_phase_rules", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load phase rules module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def has_gate_line(content: str, gate_name: str) -> bool:
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(gate_name)}:\s*(PASS|FAIL)\s*$")
    return bool(pattern.search(content))


def get_gate_status(content: str, gate_name: str) -> str:
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(gate_name)}:\s*(PASS|FAIL)\s*$")
    match = pattern.search(content)
    return match.group(1).upper() if match else "MISSING"


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


def normalize_for_lock_hash(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return LOCK_HASH_LINE_RE.sub("", normalized)


def lock_hash_from_content(content: str) -> str:
    normalized = normalize_for_lock_hash(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


def parse_requirement_ids(requirements_content: str) -> list[str]:
    requirements_body = get_heading_body(requirements_content, "Requirements") or requirements_content
    ids = sorted(set(re.findall(r"\bR\d+\b", requirements_body)), key=lambda value: int(value[1:]))
    return ids


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


def collect_subagent_delegation_blockers(audit_context: str) -> list[str]:
    blockers: list[str] = []
    audit_execution_mode = get_md_field_value(audit_context, "Audit Execution Mode")
    subagent_availability = get_md_field_value(audit_context, "Subagent Availability")
    override_reason = get_md_field_value(audit_context, "Delegation Override Reason")

    if subagent_availability == "unavailable" and audit_execution_mode == "subagent":
        blockers.append("Audit Execution Mode cannot be subagent when Subagent Availability is unavailable")

    if subagent_availability == "available" and audit_execution_mode == "self-audit":
        if not has_meaningful_value(override_reason, disallowed={"n/a", "none"}):
            blockers.append("Delegation Override Reason is required when available subagents were not used")

    return blockers


def collect_paths_under_prefix(text: str, prefix: str) -> list[str]:
    return sorted(path for path in extract_paths_from_text(text) if path.startswith(prefix))


def find_missing_repo_paths(repo_root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if not (repo_root / path).exists()]


def normalize_repo_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").strip().lstrip("/")


def is_placeholder_only(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return True
    return compact in {"...", "<content>", "[...]", "[same structure]"}


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


def collect_effective_input_addenda_blockers(file_name: str, content: str, workflow_profile: str, run_dir: Path) -> list[str]:
    if workflow_profile not in (STRICT_WORKFLOW_PROFILES | {COMPAT_WORKFLOW_PROFILE}):
        return []
    if is_addendum_artifact(file_name):
        return []

    expected_addenda = get_expected_effective_input_addenda_paths(run_dir, file_name)
    if not expected_addenda:
        return []

    blockers: list[str] = []
    header_inputs = {normalize_repo_path(path) for path in get_header_input_paths(content)}
    missing_inputs = [path for path in expected_addenda if path not in header_inputs]
    if missing_inputs:
        blockers.append(f"Missing effective-input addenda in Inputs: {', '.join(missing_inputs[:5])}")

    if workflow_profile in STRICT_WORKFLOW_PROFILES and file_name in AUDITED_PHASE_FILES:
        reread_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(content, "Effective Inputs Re-read"))}
        missing_reread = [path for path in expected_addenda if path not in reread_paths]
        if missing_reread:
            blockers.append(f"Missing effective-input addenda in Effective Inputs Re-read: {', '.join(missing_reread[:5])}")

        reconciliation_paths = {normalize_repo_path(path) for path in extract_paths_from_text(get_heading_body(content, "Earlier Phase Reconciliation"))}
        missing_reconciliation = [path for path in expected_addenda if path not in reconciliation_paths]
        if missing_reconciliation:
            blockers.append(f"Missing effective-input addenda in Earlier Phase Reconciliation: {', '.join(missing_reconciliation[:5])}")

    return blockers


def parse_requirement_completion_entries(section_body: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    entries: dict[str, dict[str, str]] = {}
    issues: list[str] = []
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line.startswith(("-", "*")):
            continue
        body = line[1:].strip()
        parts = [part.strip() for part in body.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        requirement_id = parts[0]
        if not re.fullmatch(r"R\d+", requirement_id):
            continue
        fields: dict[str, str] = {"Requirement ID": requirement_id}
        for part in parts[1:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            fields[key.strip()] = value.strip()
        if requirement_id in entries:
            issues.append(f"Duplicate Requirement Completion Status entry for {requirement_id}")
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


def collect_requirement_disposition_blockers(
    requirement_id: str,
    status: str,
    fields: dict[str, str],
    file_name: str,
    run_dir: Path,
    repo_root: Path,
    actual_changed_files: list[str] | None,
) -> list[str]:
    blockers: list[str] = []
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
        blockers.append(
            f"Requirement {requirement_id} with Status {status} contains contradictory field(s): "
            + ", ".join(unexpected_fields)
        )

    if status == "implemented":
        changed_files = fields.get("Changed Files", "")
        changed_paths = collect_requirement_field_paths(fields, ["Changed Files"])
        implementation_evidence = fields.get("Implementation Evidence", "")
        implementation_paths = collect_requirement_field_paths(fields, ["Implementation Evidence"])
        if not is_meaningful_requirement_field(changed_files):
            blockers.append(f"Requirement {requirement_id} with Status implemented must cite Changed Files")
        elif not changed_paths:
            blockers.append(f"Requirement {requirement_id} with Status implemented must cite repo paths in Changed Files")
        else:
            missing_changed_paths = find_missing_repo_paths(repo_root, sorted(changed_paths))
            if missing_changed_paths:
                blockers.append(f"Requirement {requirement_id} Changed Files path(s) do not exist: {', '.join(missing_changed_paths[:5])}")
            if actual_changed_scope:
                unexplained_paths = sorted(path for path in changed_paths if path not in actual_changed_scope)
                if unexplained_paths:
                    blockers.append(
                        f"Requirement {requirement_id} Changed Files are outside the current diff scope: {', '.join(unexplained_paths[:5])}"
                    )
        if not is_meaningful_requirement_field(implementation_evidence):
            blockers.append(f"Requirement {requirement_id} with Status implemented must cite Implementation Evidence")
        elif not implementation_paths:
            blockers.append(f"Requirement {requirement_id} with Status implemented must cite file or artifact paths in Implementation Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(implementation_paths))
            if missing:
                blockers.append(f"Requirement {requirement_id} Implementation Evidence path(s) do not exist: {', '.join(missing[:5])}")
            if changed_paths and not implementation_paths.intersection(changed_paths) and not any(
                path.startswith(f".recursive/run/{run_dir.name}/") for path in implementation_paths
            ):
                blockers.append(
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
            blockers.append(f"Requirement {requirement_id} with Status verified must cite Changed Files")
        elif not changed_paths:
            blockers.append(f"Requirement {requirement_id} with Status verified must cite repo paths in Changed Files")
        else:
            missing_changed_paths = find_missing_repo_paths(repo_root, sorted(changed_paths))
            if missing_changed_paths:
                blockers.append(f"Requirement {requirement_id} Changed Files path(s) do not exist: {', '.join(missing_changed_paths[:5])}")
            if actual_changed_scope:
                unexplained_paths = sorted(path for path in changed_paths if path not in actual_changed_scope)
                if unexplained_paths:
                    blockers.append(
                        f"Requirement {requirement_id} Changed Files are outside the current diff scope: {', '.join(unexplained_paths[:5])}"
                    )
        if not is_meaningful_requirement_field(implementation_evidence):
            blockers.append(f"Requirement {requirement_id} with Status verified must cite Implementation Evidence")
        elif not implementation_paths:
            blockers.append(f"Requirement {requirement_id} with Status verified must cite file or artifact paths in Implementation Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(implementation_paths))
            if missing:
                blockers.append(f"Requirement {requirement_id} Implementation Evidence path(s) do not exist: {', '.join(missing[:5])}")
            if changed_paths and not implementation_paths.intersection(changed_paths) and not any(
                path.startswith(f".recursive/run/{run_dir.name}/") for path in implementation_paths
            ):
                blockers.append(
                    f"Requirement {requirement_id} Implementation Evidence must reference the changed files or a current-run artifact that proves the implementation work"
                )
        if not is_meaningful_requirement_field(verification_evidence):
            blockers.append(f"Requirement {requirement_id} with Status verified must cite Verification Evidence")
        elif not verification_paths:
            blockers.append(f"Requirement {requirement_id} with Status verified must cite test, review, QA, or artifact paths in Verification Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(verification_paths))
            if missing:
                blockers.append(f"Requirement {requirement_id} Verification Evidence path(s) do not exist: {', '.join(missing[:5])}")
            if changed_paths and verification_paths.issubset(changed_paths):
                blockers.append(
                    f"Requirement {requirement_id} Verification Evidence must cite verification artifacts, review receipts, or evidence beyond the changed files themselves"
                )
            if implementation_paths and verification_paths.issubset(implementation_paths):
                blockers.append(
                    f"Requirement {requirement_id} Verification Evidence cannot be satisfied by restating only the implementation evidence"
                )

    elif status == "deferred":
        rationale = fields.get("Rationale", "")
        deferred_by = fields.get("Deferred By", "") or fields.get("Addendum", "")
        deferred_paths = collect_requirement_field_paths(fields, ["Deferred By", "Addendum"])
        if not is_meaningful_requirement_field(rationale):
            blockers.append(f"Requirement {requirement_id} with Status deferred is missing Rationale")
        if not is_meaningful_requirement_field(deferred_by):
            blockers.append(f"Requirement {requirement_id} with Status deferred must cite Deferred By or Addendum")
        elif not deferred_paths:
            blockers.append(f"Requirement {requirement_id} with Status deferred must cite an approved deferral path")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(deferred_paths))
            if missing:
                blockers.append(f"Requirement {requirement_id} deferral reference path(s) do not exist: {', '.join(missing[:5])}")

    elif status == "out-of-scope":
        rationale = fields.get("Rationale", "")
        scope_decision = fields.get("Scope Decision", "") or fields.get("Addendum", "")
        scope_paths = collect_requirement_field_paths(fields, ["Scope Decision", "Addendum"])
        if not is_meaningful_requirement_field(rationale):
            blockers.append(f"Requirement {requirement_id} with Status out-of-scope is missing Rationale")
        if not is_meaningful_requirement_field(scope_decision):
            blockers.append(f"Requirement {requirement_id} with Status out-of-scope must cite Scope Decision or Addendum")
        elif not scope_paths:
            blockers.append(f"Requirement {requirement_id} with Status out-of-scope must cite an approved scope decision path")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(scope_paths))
            if missing:
                blockers.append(f"Requirement {requirement_id} scope decision path(s) do not exist: {', '.join(missing[:5])}")

    elif status == "blocked":
        rationale = fields.get("Rationale", "")
        blocking_evidence = fields.get("Blocking Evidence", "")
        blocking_paths = collect_requirement_field_paths(fields, ["Blocking Evidence"])
        if not is_meaningful_requirement_field(rationale):
            blockers.append(f"Requirement {requirement_id} with Status blocked is missing Rationale")
        if not is_meaningful_requirement_field(blocking_evidence):
            blockers.append(f"Requirement {requirement_id} with Status blocked must cite Blocking Evidence")
        elif not blocking_paths:
            blockers.append(f"Requirement {requirement_id} with Status blocked must cite file, artifact, or evidence paths in Blocking Evidence")
        else:
            missing = find_missing_repo_paths(repo_root, sorted(blocking_paths))
            if missing:
                blockers.append(f"Requirement {requirement_id} Blocking Evidence path(s) do not exist: {', '.join(missing[:5])}")

    elif status == "superseded by approved addendum":
        addendum_path = normalize_repo_path(fields.get("Addendum", ""))
        if not addendum_path:
            blockers.append(f"Requirement {requirement_id} superseded by approved addendum must cite Addendum")
        elif not addendum_path.startswith(f".recursive/run/{run_dir.name}/addenda/"):
            blockers.append(f"Requirement {requirement_id} addendum reference must live under the current run addenda/")
        elif not (repo_root / addendum_path).exists():
            blockers.append(f"Requirement {requirement_id} addendum reference does not exist: {addendum_path}")

    if file_name in FINAL_REQUIREMENT_DISPOSITION_FILES:
        if status == "implemented":
            blockers.append(f"Requirement {requirement_id} cannot remain implemented in {file_name}; final closeout phases require verified or explicitly approved non-completion states")
        if status == "blocked":
            blockers.append(f"Requirement {requirement_id} cannot remain blocked in {file_name} while the phase is approaching closeout")

    return blockers


def collect_requirement_completion_blockers(
    file_name: str,
    content: str,
    workflow_profile: str,
    requirement_ids: list[str],
    run_dir: Path,
    repo_root: Path,
    actual_changed_files: list[str] | None,
) -> list[str]:
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_name not in AUDITED_PHASE_FILES:
        return []

    body = get_heading_body(content, "Requirement Completion Status")
    if not body:
        return ["Missing section: ## Requirement Completion Status"]

    entries, blockers = parse_requirement_completion_entries(body)
    missing = [requirement_id for requirement_id in requirement_ids if requirement_id not in entries]
    if missing:
        blockers.append(f"Missing requirement dispositions for: {', '.join(missing)}")

    for requirement_id, fields in entries.items():
        status = trim_md_value(fields.get("Status", "")).lower()
        if status not in REQUIREMENT_DISPOSITION_STATUSES:
            blockers.append(f"Requirement {requirement_id} has invalid Status '{fields.get('Status', '')}'")
            continue
        blockers.extend(
            collect_requirement_disposition_blockers(
                requirement_id,
                status,
                fields,
                file_name,
                run_dir,
                repo_root,
                actual_changed_files,
            )
        )

    if file_name in REQUIREMENT_CHANGED_FILE_ACCOUNTING_FILES:
        expected_scope = set(get_phase_owned_actual_changed_files(file_name, actual_changed_files) or [])
        if expected_scope:
            claimed_changed_files = set()
            for fields in entries.values():
                status = trim_md_value(fields.get("Status", "")).lower()
                if status in {"implemented", "verified"}:
                    claimed_changed_files.update(collect_requirement_field_paths(fields, ["Changed Files"]))
            missing_claims = sorted(path for path in expected_scope if path not in claimed_changed_files)
            if missing_claims:
                blockers.append(
                    "Requirement Completion Status leaves diff-owned changed file(s) unaccounted for: "
                    + ", ".join(missing_claims[:5])
                )

    return sorted(set(blockers))


def collect_prior_recursive_evidence_blockers(
    file_name: str,
    content: str,
    workflow_profile: str,
    repo_root: Path,
) -> list[str]:
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_name not in PRIOR_RECURSIVE_EVIDENCE_FILES:
        return []

    body = get_heading_body(content, "Prior Recursive Evidence Reviewed")
    if not body:
        return ["Missing section: ## Prior Recursive Evidence Reviewed"]

    referenced_paths = {
        normalize_repo_path(path)
        for path in extract_paths_from_text(body)
        if normalize_repo_path(path).startswith(".recursive/run/") or normalize_repo_path(path).startswith(".recursive/memory/")
    }
    if referenced_paths:
        missing_paths = find_missing_repo_paths(repo_root, sorted(referenced_paths))
        if missing_paths:
            return [f"Prior Recursive Evidence references missing path(s): {', '.join(missing_paths[:5])}"]
        return []

    if re.search(r"\bnone\b", body, re.IGNORECASE) and re.search(r"\b(justification|reason|because)\b", body, re.IGNORECASE):
        return []

    return ["Prior Recursive Evidence Reviewed must cite run/memory paths or an explicit no-relevant-evidence justification"]


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


def collect_subagent_contribution_blockers(
    file_name: str,
    content: str,
    workflow_profile: str,
    run_dir: Path,
    repo_root: Path,
    actual_changed_files: list[str] | None,
) -> list[str]:
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_name not in AUDITED_PHASE_FILES:
        return []

    body = get_heading_body(content, "Subagent Contribution Verification")
    if not body:
        return ["Missing section: ## Subagent Contribution Verification"]

    blockers: list[str] = []
    action_record_paths = get_subagent_action_record_paths(content, run_dir)
    all_action_record_paths = get_all_subagent_action_record_paths(content)
    audit_mode = get_md_field_value(get_heading_body(content, "Audit Context"), "Audit Execution Mode") or ""
    if audit_mode == "subagent" and not action_record_paths:
        blockers.append("Audit Execution Mode subagent requires at least one reviewed subagent action record")
    out_of_run_action_records = sorted(path for path in all_action_record_paths if path not in action_record_paths)
    if out_of_run_action_records:
        blockers.append(
            "Subagent Contribution Verification may only reference action records under the current run subagents/: "
            + ", ".join(out_of_run_action_records[:5])
        )

    current_bundle_path = normalize_repo_path(
        get_md_field_value(get_heading_body(content, "Review Metadata"), "Review Bundle Path")
        or get_md_field_value(content, "Review Bundle Path")
        or ""
    )
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
    for action_record_path in action_record_paths:
        action_path = repo_root / action_record_path
        if not action_path.exists():
            blockers.append(f"Referenced subagent action record does not exist: {action_record_path}")
            continue
        action_content = action_path.read_text(encoding="utf-8")
        action_claims = parse_subagent_action_record_claims(action_content)
        metadata = get_heading_body(action_content, "Metadata")
        inputs = get_heading_body(action_content, "Inputs Provided")
        claimed_actions = get_heading_body(action_content, "Claimed Actions Taken")
        claimed_file_impact = get_heading_body(action_content, "Claimed File Impact")
        claimed_artifact_impact = get_heading_body(action_content, "Claimed Artifact Impact")
        for heading in SUBAGENT_ACTION_REQUIRED_HEADINGS:
            if not get_heading_body(action_content, heading):
                blockers.append(f"Subagent action record missing section {heading}: {action_record_path}")
        for field_name in ("Subagent ID", "Run ID", "Phase", "Purpose", "Execution Mode", "Timestamp"):
            if not has_meaningful_value(get_md_field_value(metadata, field_name)):
                blockers.append(f"Subagent action record missing {field_name}: {action_record_path}")
        if action_path.parent != run_dir / "subagents":
            blockers.append(f"Subagent action record must live under `/.recursive/run/{run_dir.name}/subagents/`: {action_record_path}")
        if (get_md_field_value(metadata, "Run ID") or "") not in {"", run_dir.name}:
            blockers.append(f"Subagent action record run mismatch: {action_record_path}")
        if current_phase and (get_md_field_value(metadata, "Phase") or "") not in {"", current_phase}:
            blockers.append(f"Subagent action record phase mismatch: {action_record_path}")
        current_artifact = normalize_repo_path(get_md_field_value(inputs, "Current Artifact") or "")
        if not current_artifact:
            blockers.append(f"Subagent action record missing Current Artifact: {action_record_path}")
        elif not (repo_root / current_artifact).exists():
            blockers.append(f"Subagent action record Current Artifact does not exist: {action_record_path}")
        artifact_hash = trim_md_value(get_md_field_value(inputs, "Artifact Content Hash") or "")
        if current_artifact and (repo_root / current_artifact).exists():
            current_artifact_hash = content_sha256((repo_root / current_artifact).read_text(encoding="utf-8"))
            if not artifact_hash:
                blockers.append(f"Subagent action record missing Artifact Content Hash: {action_record_path}")
            elif artifact_hash != current_artifact_hash:
                blockers.append(f"Subagent action record Artifact Content Hash is stale: {action_record_path}")
        if not has_meaningful_value(get_md_field_value(inputs, "Diff Basis"), disallowed={"n/a", "none"}):
            blockers.append(f"Subagent action record missing Diff Basis: {action_record_path}")
        if is_placeholder_only(claimed_actions):
            blockers.append(f"Subagent action record Claimed Actions Taken is empty: {action_record_path}")
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
        claimed_file_refs = claimed_created | claimed_modified | claimed_reviewed | claimed_relevant_untouched
        if not claimed_file_refs:
            blockers.append(f"Subagent action record Claimed File Impact is empty: {action_record_path}")
        claimed_artifact_refs = {
            normalize_repo_path(path)
            for path in extract_paths_from_text(claimed_artifact_impact)
            if normalize_repo_path(path).startswith(".recursive/")
        }
        evidence_refs = {
            normalize_repo_path(path)
            for path in extract_paths_from_text(get_subheading_body(claimed_artifact_impact, "Evidence Used"))
            if normalize_repo_path(path).startswith(f".recursive/run/{run_dir.name}/evidence/")
        }
        if not claimed_artifact_refs and not evidence_refs:
            blockers.append(f"Subagent action record Claimed Artifact Impact is empty: {action_record_path}")
        else:
            missing_artifact_refs = find_missing_repo_paths(repo_root, sorted(claimed_artifact_refs))
            if missing_artifact_refs:
                blockers.append(
                    f"Subagent action record references missing recursive artifacts: {action_record_path} -> {', '.join(missing_artifact_refs[:5])}"
                )
            missing_evidence_refs = find_missing_repo_paths(repo_root, sorted(evidence_refs))
            if missing_evidence_refs:
                blockers.append(
                    f"Subagent action record references missing evidence: {action_record_path} -> {', '.join(missing_evidence_refs[:5])}"
                )
        action_bundle_path = normalize_repo_path(get_md_field_value(inputs, "Review Bundle") or "")
        if current_bundle_path and action_bundle_path and current_bundle_path != action_bundle_path:
            blockers.append(f"Subagent action record review bundle mismatch: {action_record_path}")
        if action_bundle_path and (repo_root / action_bundle_path).exists():
            bundle_content = (repo_root / action_bundle_path).read_text(encoding="utf-8")
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
                blockers.append(
                    f"Subagent action record Current Artifact must match the review bundle Artifact Path or a cited upstream artifact: {action_record_path}"
                )
            action_upstream_artifacts = extract_paths_from_named_field(inputs, "Upstream Artifacts")
            missing_bundle_upstream = sorted(path for path in bundle_upstream_artifacts if path not in {
                normalize_repo_path(path)
                for path in action_upstream_artifacts
                if normalize_repo_path(path)
            })
            if missing_bundle_upstream:
                blockers.append(
                    "Subagent action record Upstream Artifacts omit bundle upstream artifact(s): "
                    + ", ".join(missing_bundle_upstream[:5])
                )
            required_bundle_file_scope = bundle_code_refs or bundle_changed_paths
            if required_bundle_file_scope:
                missing_bundle_scope_paths = sorted(path for path in required_bundle_file_scope if path not in claimed_file_refs)
                if missing_bundle_scope_paths:
                    blockers.append(
                        "Subagent action record omits targeted file scope present in the review bundle: "
                        + ", ".join(missing_bundle_scope_paths[:5])
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
                blockers.append(
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
                blockers.append(
                    "Main-Agent Verification Performed must cite the reviewed artifact, bundle, or upstream recursive artifacts used to accept delegated work"
                )

    if action_record_paths:
        reviewed_record_paths = {
            normalize_repo_path(path)
            for path in extract_paths_from_field_value(reviewed_action_records_field)
            if normalize_repo_path(path).startswith(f".recursive/run/{run_dir.name}/subagents/")
        }
        if not reviewed_action_records_field.strip():
            blockers.append("Subagent Contribution Verification must record Reviewed Action Records")
        else:
            missing_reviewed_records = sorted(path for path in action_record_paths if path not in reviewed_record_paths)
            if missing_reviewed_records:
                blockers.append(
                    "Reviewed Action Records is missing referenced action record path(s): "
                    + ", ".join(missing_reviewed_records[:5])
                )
        if not has_meaningful_value(main_agent_verification, disallowed={"n/a", "none"}):
            blockers.append("Subagent Contribution Verification must record Main-Agent Verification Performed")
        elif not verification_paths:
            blockers.append("Main-Agent Verification Performed must cite files, artifacts, or diff-owned paths that were checked")
        else:
            missing_verification_paths = find_missing_repo_paths(repo_root, sorted(verification_paths))
            if missing_verification_paths:
                blockers.append(
                    "Main-Agent Verification Performed references missing path(s): "
                    + ", ".join(missing_verification_paths[:5])
                )
        if acceptance_decision not in {"accepted", "partially accepted", "rejected"}:
            blockers.append("Subagent Contribution Verification must record Acceptance Decision: accepted|partially accepted|rejected")
        if not has_meaningful_value(refresh_handling, disallowed={"n/a", "none"}):
            blockers.append("Subagent Contribution Verification must record Refresh Handling")
        if not trim_md_value(repair_performed):
            blockers.append("Subagent Contribution Verification must record Repair Performed After Verification")
        elif repair_paths:
            missing_repair_paths = find_missing_repo_paths(repo_root, sorted(repair_paths))
            if missing_repair_paths:
                blockers.append(
                    "Repair Performed After Verification references missing path(s): "
                    + ", ".join(missing_repair_paths[:5])
                )

    return sorted(set(blockers))


def collect_reviewed_paths(run_dir: Path, artifact_name: str, content: str) -> set[str]:
    reviewed_paths = extract_paths_from_text(get_heading_body(content, "Worktree Diff Audit"))
    for addendum_path in get_related_addenda_paths(run_dir, artifact_name):
        reviewed_paths.update(extract_paths_from_text(addendum_path.read_text(encoding="utf-8")))
    return reviewed_paths


def collect_review_bundle_blockers(content: str, run_dir: Path, repo_root: Path) -> list[str]:
    blockers: list[str] = []
    review_metadata = get_heading_body(content, "Review Metadata")
    bundle_path = (
        get_md_field_value(review_metadata, "Review Bundle Path")
        or get_md_field_value(content, "Review Bundle Path")
        or ""
    ).strip()
    expected_prefix = f".recursive/run/{run_dir.name}/evidence/review-bundles/"

    if not bundle_path:
        blockers.append("Missing Review Bundle Path in Review Metadata")
        return blockers

    normalized_bundle_path = normalize_repo_path(bundle_path)
    if not normalized_bundle_path.startswith(expected_prefix):
        blockers.append(f"Review Bundle Path must live under `/{expected_prefix}`")
        return blockers

    if not (repo_root / normalized_bundle_path).exists():
        blockers.append(f"Missing review bundle file: {normalized_bundle_path}")
        return blockers

    bundle_content = (repo_root / normalized_bundle_path).read_text(encoding="utf-8")
    artifact_path = normalize_repo_path(get_md_field_value(bundle_content, "Artifact Path") or "")
    artifact_hash = trim_md_value(get_md_field_value(bundle_content, "Artifact Content Hash") or "")
    if not artifact_path:
        blockers.append("Review bundle is missing Artifact Path")
    elif not (repo_root / artifact_path).exists():
        blockers.append(f"Review bundle Artifact Path does not exist: {artifact_path}")
    if artifact_path:
        current_hash = content_sha256((repo_root / artifact_path).read_text(encoding="utf-8")) if (repo_root / artifact_path).exists() else ""
        if artifact_hash and current_hash and artifact_hash != current_hash:
            blockers.append("Review bundle is stale: Artifact Content Hash no longer matches the current artifact")
    if not artifact_hash:
        blockers.append("Review bundle is missing Artifact Content Hash")

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
        blockers.append(f"Review bundle is missing required section(s): {', '.join(missing_bundle_headings)}")

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
        blockers.append("Review bundle Audit Questions cannot be placeholder-only")
    diff_basis_body = get_heading_body(bundle_content, "Diff Basis")
    for field_name in DIFF_BASIS_FIELDS:
        if get_md_field_value(diff_basis_body, field_name) is None:
            blockers.append(f"Review bundle Diff Basis is missing {field_name}")
    if not changed_paths:
        blockers.append("Review bundle Changed Files Reviewed cannot be empty")
    else:
        missing_changed_paths = find_missing_repo_paths(repo_root, sorted(changed_paths))
        if missing_changed_paths:
            blockers.append(f"Review bundle changed file path(s) do not exist: {', '.join(missing_changed_paths[:5])}")
    if not code_ref_paths:
        blockers.append("Review bundle Targeted Code References cannot be empty")
    else:
        missing_code_refs = find_missing_repo_paths(repo_root, sorted(code_ref_paths))
        if missing_code_refs:
            blockers.append(f"Review bundle code ref path(s) do not exist: {', '.join(missing_code_refs[:5])}")
        elif changed_paths and not any(path in changed_paths for path in code_ref_paths):
            blockers.append("Review bundle Targeted Code References do not overlap the changed-file scope")
    expected_addenda = set(get_expected_effective_input_addenda_paths(run_dir, "03.5-code-review.md"))
    missing_bundle_addenda = sorted(path for path in expected_addenda if path not in addenda_paths)
    if missing_bundle_addenda:
        blockers.append(f"Review bundle is missing effective-input addenda: {', '.join(missing_bundle_addenda[:5])}")

    if upstream_paths and not any(path in cited_review_paths for path in upstream_paths):
        blockers.append("Review narrative does not cite any upstream artifact from the review bundle")
    if addenda_paths and not any(path in cited_review_paths for path in addenda_paths):
        blockers.append("Review narrative does not cite any relevant addendum from the review bundle")
    if prior_paths and not any(path in cited_review_paths for path in prior_paths):
        blockers.append("Review narrative does not cite any prior recursive evidence from the review bundle")
    if (changed_paths or code_ref_paths) and not any(path in cited_review_paths for path in (changed_paths | code_ref_paths)):
        blockers.append("Review narrative does not cite any changed file or code reference from the review bundle")
    if normalized_bundle_path not in cited_paths:
        blockers.append("Review artifact does not cite its Review Bundle Path")

    verdict_body = get_heading_body(content, "Verdict")
    if not verdict_body or is_placeholder_only(verdict_body):
        blockers.append("Verdict section must contain a concrete review verdict grounded in the review bundle")

    return blockers


def collect_phase8_skill_usage_blockers(content: str) -> list[str]:
    blockers: list[str] = []
    usage_body = get_heading_body(content, "Run-Local Skill Usage Capture")
    if not usage_body:
        return ["Missing section: ## Run-Local Skill Usage Capture"]

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
            blockers.append(f"Run-Local Skill Usage Capture is missing {field_name}")

    relevance = normalize_skill_usage_relevance(get_md_field_value(usage_body, "Skill Usage Relevance"))
    if relevance not in SKILL_USAGE_RELEVANCE_STATUSES:
        blockers.append("Run-Local Skill Usage Capture must declare Skill Usage Relevance: relevant|not-relevant")
        return blockers

    if relevance in {"relevant", "yes"}:
        for field_name in ("Available Skills", "Skills Attempted", "Skills Used", "Future Guidance"):
            if not is_meaningful_requirement_field(get_md_field_value(usage_body, field_name)):
                blockers.append(f"Run-Local Skill Usage Capture must record {field_name} when skill usage is relevant")
        attempted = trim_md_value(get_md_field_value(usage_body, "Skills Attempted") or "").lower()
        used = trim_md_value(get_md_field_value(usage_body, "Skills Used") or "").lower()
        if attempted in {"none", "n/a"} and used in {"none", "n/a"}:
            blockers.append("Run-Local Skill Usage Capture cannot mark skill usage relevant while claiming no attempted or used skills")

    promotion_body = get_heading_body(content, "Skill Memory Promotion Review")
    if not promotion_body:
        blockers.append("Missing section: ## Skill Memory Promotion Review")
        return blockers

    for field_name in (
        "Durable Skill Lessons Promoted",
        "Generalized Guidance Updated",
        "Run-Local Observations Left Unpromoted",
        "Promotion Decision Rationale",
    ):
        if get_md_field_value(promotion_body, field_name) is None:
            blockers.append(f"Skill Memory Promotion Review is missing {field_name}")

    if relevance in {"relevant", "yes"} and not is_meaningful_requirement_field(
        get_md_field_value(promotion_body, "Promotion Decision Rationale")
    ):
        blockers.append("Skill Memory Promotion Review must explain why relevant run-local observations were or were not promoted")

    return blockers


def collect_phase_specific_blockers(
    file_name: str,
    content: str,
    workflow_profile: str,
    run_dir: Path,
    repo_root: Path,
    requirement_ids: list[str],
    actual_changed_files: list[str] | None,
) -> list[str]:
    lint = load_lint_module()
    blockers = lint.lint_phase_specific_rules(
        run_dir / file_name,
        content,
        workflow_profile,
        run_dir,
        repo_root,
        requirement_ids,
        actual_changed_files,
    )
    if workflow_profile not in STRICT_WORKFLOW_PROFILES:
        return blockers

    if file_name == "00-worktree.md":
        _diff_basis, diff_basis_error = normalize_diff_basis(repo_root, get_run_diff_basis(run_dir))
        if diff_basis_error:
            blockers.append(f"Phase 0 diff basis is not executable: {diff_basis_error}")

    if file_name == "03-implementation-summary.md":
        tdd_body = get_heading_body(content, "TDD Compliance Log")
        tdd_mode = (get_md_field_value(tdd_body, "TDD Mode") or get_md_field_value(content, "TDD Mode") or "").lower()
        tdd_gate = get_gate_status(content, "TDD Compliance")

        if not has_gate_line(content, "TDD Compliance"):
            blockers.append("Missing TDD Compliance gate line")
        elif tdd_gate != "PASS":
            blockers.append(f"TDD Compliance gate is {tdd_gate}")

        if tdd_mode not in TDD_MODES:
            blockers.append("Missing TDD Mode: strict|pragmatic")
        elif tdd_mode == "strict":
            red_prefix = f".recursive/run/{run_dir.name}/evidence/logs/red/"
            green_prefix = f".recursive/run/{run_dir.name}/evidence/logs/green/"
            red_paths = collect_paths_under_prefix(tdd_body, red_prefix)
            green_paths = collect_paths_under_prefix(tdd_body, green_prefix)
            if not red_paths:
                blockers.append(f"Strict TDD requires RED evidence under `/{red_prefix}`")
            else:
                missing_red = find_missing_repo_paths(repo_root, red_paths)
                if missing_red:
                    blockers.append(f"Missing RED evidence file(s): {', '.join(missing_red[:5])}")
            if not green_paths:
                blockers.append(f"Strict TDD requires GREEN evidence under `/{green_prefix}`")
            else:
                missing_green = find_missing_repo_paths(repo_root, green_paths)
                if missing_green:
                    blockers.append(f"Missing GREEN evidence file(s): {', '.join(missing_green[:5])}")
        else:
            exception_body = get_heading_body(content, "Pragmatic TDD Exception")
            if not exception_body:
                blockers.append("TDD Mode pragmatic requires ## Pragmatic TDD Exception")
            else:
                if not has_meaningful_value(get_md_field_value(exception_body, "Exception reason"), disallowed={"n/a", "none"}):
                    blockers.append("Pragmatic TDD Exception is missing Exception reason")
                if not has_meaningful_value(get_md_field_value(exception_body, "Compensating validation"), disallowed={"n/a", "none"}):
                    blockers.append("Pragmatic TDD Exception is missing Compensating validation")
                pragmatic_paths = collect_paths_under_prefix(exception_body, f".recursive/run/{run_dir.name}/evidence/")
                if not pragmatic_paths:
                    blockers.append(f"Pragmatic TDD requires compensating evidence under `/.recursive/run/{run_dir.name}/evidence/`")
                else:
                    missing_pragmatic = find_missing_repo_paths(repo_root, pragmatic_paths)
                    if missing_pragmatic:
                        blockers.append(f"Missing pragmatic TDD evidence file(s): {', '.join(missing_pragmatic[:5])}")

    if file_name == "05-manual-qa.md":
        qa_record = get_heading_body(content, "QA Execution Record")
        evidence_body = get_heading_body(content, "Evidence and Artifacts")
        signoff_body = get_heading_body(content, "User Sign-Off")
        qa_mode = (get_md_field_value(qa_record, "QA Execution Mode") or get_md_field_value(content, "QA Execution Mode") or "").lower()

        if not qa_record:
            blockers.append("Missing QA Execution Record section")
        if qa_mode not in QA_EXECUTION_MODES:
            blockers.append("Missing QA Execution Mode: human|agent-operated|hybrid")
        else:
            if qa_mode in {"human", "hybrid"}:
                if not has_meaningful_value(get_md_field_value(signoff_body, "Approved by"), disallowed={"n/a", "not required", "none"}):
                    blockers.append(f"QA mode {qa_mode} requires Approved by in User Sign-Off")
                if not has_meaningful_value(get_md_field_value(signoff_body, "Date"), disallowed={"n/a", "not required", "none"}):
                    blockers.append(f"QA mode {qa_mode} requires Date in User Sign-Off")
            if qa_mode in {"agent-operated", "hybrid"}:
                if not has_meaningful_value(get_md_field_value(qa_record, "Agent Executor"), disallowed={"n/a", "none"}):
                    blockers.append(f"QA mode {qa_mode} requires Agent Executor")
                if not has_meaningful_value(get_md_field_value(qa_record, "Tools Used"), disallowed={"n/a", "none"}):
                    blockers.append(f"QA mode {qa_mode} requires Tools Used")
                qa_paths = collect_paths_under_prefix(f"{qa_record}\n{evidence_body}", f".recursive/run/{run_dir.name}/evidence/")
                if not qa_paths:
                    blockers.append(f"QA mode {qa_mode} requires evidence paths under `/.recursive/run/{run_dir.name}/evidence/`")
                else:
                    missing_qa_paths = find_missing_repo_paths(repo_root, qa_paths)
                    if missing_qa_paths:
                        blockers.append(f"Missing QA evidence file(s): {', '.join(missing_qa_paths[:5])}")

    if file_name == "03.5-code-review.md":
        blockers.extend(collect_review_bundle_blockers(content, run_dir, repo_root))
    if file_name == "08-memory-impact.md":
        blockers.extend(collect_phase8_skill_usage_blockers(content))

    return blockers


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

    if any((run_dir / file_name).exists() for file_name in LATE_PHASE_FILES):
        return COMPAT_WORKFLOW_PROFILE

    return "legacy"


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


@dataclass
class ArtifactState:
    exists: bool
    status: str
    lock_valid: bool
    lock_problems: list[str]
    blockers: list[str]
    locked_at: str | None
    stored_hash: str | None
    actual_hash: str | None
    coverage: str
    approval: str
    audit: str
    todo_has_section: bool
    todo_unchecked: int


def collect_audit_blockers(
    file_name: str,
    content: str,
    workflow_profile: str,
    requirement_ids: list[str],
    actual_changed_files: list[str] | None,
    diff_basis_error: str | None,
    run_dir: Path,
) -> list[str]:
    blockers: list[str] = []
    if workflow_profile not in STRICT_WORKFLOW_PROFILES or file_name not in AUDITED_PHASE_FILES:
        return blockers

    audit = get_gate_status(content, "Audit")
    coverage = get_gate_status(content, "Coverage")
    approval = get_gate_status(content, "Approval")

    if audit != "PASS":
        blockers.append(f"Audit verdict is {audit}")
    if coverage == "PASS" and audit != "PASS":
        blockers.append("Coverage cannot pass before Audit: PASS")
    if approval == "PASS" and audit != "PASS":
        blockers.append("Approval cannot pass before Audit: PASS")

    audit_context = get_heading_body(content, "Audit Context")
    if not audit_context:
        blockers.append("Missing Audit Context section")
    else:
        if get_md_field_value(audit_context, "Audit Execution Mode") not in {"subagent", "self-audit"}:
            blockers.append("Missing valid Audit Execution Mode")
        if get_md_field_value(audit_context, "Subagent Availability") not in {"available", "unavailable"}:
            blockers.append("Missing valid Subagent Availability")
        if not has_meaningful_value(get_md_field_value(audit_context, "Subagent Capability Probe"), disallowed={"n/a", "none"}):
            blockers.append("Missing Subagent Capability Probe")
        if not has_meaningful_value(get_md_field_value(audit_context, "Delegation Decision Basis"), disallowed={"n/a", "none"}):
            blockers.append("Missing Delegation Decision Basis")
        if get_md_field_value(audit_context, "Audit Inputs Provided") is None and "Audit Inputs Provided:" not in audit_context:
            blockers.append("Missing Audit Inputs Provided")
        blockers.extend(collect_subagent_delegation_blockers(audit_context))

    for heading in AUDIT_REQUIRED_HEADINGS:
        if not get_heading_body(content, heading):
            blockers.append(f"Missing section: ## {heading}")

    traceability_body = get_heading_body(content, "Traceability")
    if file_name not in {"00-worktree.md", "00-requirements.md"}:
        missing_ids = [requirement_id for requirement_id in requirement_ids if requirement_id not in traceability_body]
        if missing_ids:
            blockers.append(f"Traceability missing requirement IDs: {', '.join(missing_ids)}")

    diff_audit_body = get_heading_body(content, "Worktree Diff Audit")
    for field_name in DIFF_BASIS_FIELDS:
        if get_md_field_value(diff_audit_body, field_name) is None:
            blockers.append(f"Missing diff basis field: {field_name}:")
    gaps_body = get_heading_body(content, "Gaps Found")
    if audit == "PASS" and gaps_body and not re.search(r"\bnone\b", gaps_body, re.IGNORECASE):
        blockers.append("Audit: PASS is invalid while Gaps Found still lists unresolved in-scope gaps")

    expected_changed_files = get_phase_owned_actual_changed_files(file_name, actual_changed_files)
    if file_name in DIFF_AUDITED_FILES and expected_changed_files is not None:
        if diff_basis_error:
            blockers.append(f"Cannot verify git diff basis: {diff_basis_error}")
        else:
            reviewed_paths = collect_reviewed_paths(run_dir, file_name, content)
            missing_paths = [path for path in expected_changed_files if path not in reviewed_paths]
            if missing_paths:
                preview = ", ".join(missing_paths[:5])
                suffix = " ..." if len(missing_paths) > 5 else ""
                blockers.append(f"Unexplained changed files outside reviewed scope: {preview}{suffix}")

    return blockers


def get_artifact_state(
    artifact_path: Path,
    workflow_profile: str,
    requirement_ids: list[str],
    actual_changed_files: list[str] | None,
    diff_basis_error: str | None,
) -> ArtifactState:
    if not artifact_path.exists():
        return ArtifactState(
            exists=False,
            status="PENDING",
            lock_valid=False,
            lock_problems=["File missing"],
            blockers=["File missing"],
            locked_at=None,
            stored_hash=None,
            actual_hash=None,
            coverage="MISSING",
            approval="MISSING",
            audit="MISSING",
            todo_has_section=False,
            todo_unchecked=0,
        )

    content = artifact_path.read_text(encoding="utf-8")
    status = get_md_field_value(content, "Status") or "UNKNOWN"
    has_todo, _, _, unchecked = get_todo_stats(content)
    coverage = get_gate_status(content, "Coverage")
    approval = get_gate_status(content, "Approval")
    audit = get_gate_status(content, "Audit")
    tdd_compliance = get_gate_status(content, "TDD Compliance")
    locked_at = get_md_field_value(content, "LockedAt")
    stored_hash = get_md_field_value(content, "LockHash")
    actual_hash = None
    lock_problems: list[str] = []
    blockers: list[str] = []
    lock_valid = False
    run_dir = artifact_path.parent
    repo_root = run_dir.parent.parent.parent

    if status != "LOCKED":
        lock_problems.append(f"Status is '{status}' (expected LOCKED for lock-valid)")
    else:
        if not locked_at:
            lock_problems.append("Missing LockedAt")
        if not stored_hash:
            lock_problems.append("Missing LockHash")
        if stored_hash:
            actual_hash = lock_hash_from_content(content)
            if stored_hash.lower() != actual_hash.lower():
                lock_problems.append("LockHash mismatch")
        if coverage != "PASS":
            lock_problems.append(f"Coverage gate is {coverage}")
        if approval != "PASS":
            lock_problems.append(f"Approval gate is {approval}")
        if workflow_profile in STRICT_WORKFLOW_PROFILES and artifact_path.name in AUDITED_PHASE_FILES and audit != "PASS":
            lock_problems.append(f"Audit gate is {audit}")
        if artifact_path.name == "03-implementation-summary.md" and tdd_compliance != "PASS":
            lock_problems.append(f"TDD Compliance gate is {tdd_compliance}")
        if not has_todo:
            lock_problems.append("Missing ## TODO section")
        elif unchecked > 0:
            lock_problems.append(f"Unchecked TODO items: {unchecked}")
        lock_problems.extend(
            collect_phase_specific_blockers(
                artifact_path.name,
                content,
                workflow_profile,
                run_dir,
                repo_root,
                requirement_ids,
                actual_changed_files,
            )
        )
        if not lock_problems:
            lock_valid = True

    blockers.extend(collect_audit_blockers(artifact_path.name, content, workflow_profile, requirement_ids, actual_changed_files, diff_basis_error, artifact_path.parent))
    blockers.extend(
        collect_phase_specific_blockers(
            artifact_path.name,
            content,
            workflow_profile,
            run_dir,
            repo_root,
            requirement_ids,
            actual_changed_files,
        )
    )
    if not has_todo:
        blockers.append("Missing ## TODO section")
    elif unchecked > 0:
        blockers.append(f"Unchecked TODO items: {unchecked}")
    if coverage != "PASS":
        blockers.append(f"Coverage gate is {coverage}")
    if approval != "PASS":
        blockers.append(f"Approval gate is {approval}")
    if artifact_path.name == "03-implementation-summary.md" and tdd_compliance != "PASS":
        blockers.append(f"TDD Compliance gate is {tdd_compliance}")

    deduped_blockers: list[str] = []
    for blocker in blockers:
        if blocker not in deduped_blockers:
            deduped_blockers.append(blocker)

    return ArtifactState(
        exists=True,
        status=status,
        lock_valid=lock_valid,
        lock_problems=lock_problems,
        blockers=deduped_blockers,
        locked_at=locked_at,
        stored_hash=stored_hash,
        actual_hash=actual_hash,
        coverage=coverage,
        approval=approval,
        audit=audit,
        todo_has_section=has_todo,
        todo_unchecked=unchecked,
    )


def print_phase_status(phases: list[dict[str, str]], states: dict[str, ArtifactState], show_hashes: bool, run_id: str, workflow_profile: str) -> None:
    print("Phase Status:")
    for phase in phases:
        state = states[phase["Key"]]
        display = state.status
        suffix = ""
        if display == "SKIPPED":
            suffix = " (legacy workflow)" if phase["Key"] in LATE_PHASE_KEYS and workflow_profile == "legacy" else " (not needed)"
        elif display == "LOCKED" and not state.lock_valid:
            display = "LOCKED*"
            suffix = " (invalid)"
        print(f"  {phase['Label']:<26} [{display}]{suffix}")
        if state.blockers and display not in {"SKIPPED"}:
            preview = "; ".join(state.blockers[:2])
            if len(state.blockers) > 2:
                preview += "; ..."
            print(f"    blockers: {preview}")

    print()
    print("Lock Chain:")
    for phase in phases:
        state = states[phase["Key"]]
        if state.status == "SKIPPED":
            continue

        artifact_rel = f".recursive/run/{run_id}/{phase['File']}"
        if state.lock_valid:
            print(f"  [OK]  {artifact_rel}")
            if show_hashes and state.stored_hash:
                print(f"        LockHash: {state.stored_hash}")
            continue

        if not state.exists:
            print(f"  [PENDING] {artifact_rel}")
        elif state.status != "LOCKED":
            print(f"  [DRAFT]   {artifact_rel}")
        else:
            reason = state.lock_problems[0] if state.lock_problems else "Not lock-valid"
            print(f"  [FAIL]    {artifact_rel} - {reason}")
        break


def main() -> None:
    parser = argparse.ArgumentParser(description="Show recursive-mode run status and lock-chain summary.")
    parser.add_argument("--run-id", default="", help="Run ID to inspect (default: latest run).")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--show-hashes", action="store_true", help="Show LockHash values for lock-valid phases.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_root = repo_root / ".recursive" / "run"
    if not run_root.exists():
        print(f"[FAIL] recursive run directory not found at: {run_root}")
        print("       Is this the project repo root? (Expected .recursive/run/)")
        sys.exit(1)

    if args.run_id.strip():
        run_dir = run_root / args.run_id.strip()
        if not run_dir.exists():
            print(f"[FAIL] Run directory not found: {run_dir}")
            sys.exit(1)
        run_id = args.run_id.strip()
    else:
        latest = get_latest_run_directory(run_root)
        if latest is None:
            print(f"[FAIL] No runs found under: {run_root}")
            sys.exit(1)
        run_dir = latest
        run_id = latest.name

    workflow_profile = get_workflow_profile(run_dir)
    requirement_ids: list[str] = []
    requirements_path = run_dir / "00-requirements.md"
    if requirements_path.exists():
        requirement_ids = load_lint_module().get_run_requirement_ids(run_dir, workflow_profile)

    actual_changed_files: list[str] | None = None
    diff_basis_error: str | None = None
    if workflow_profile in STRICT_WORKFLOW_PROFILES:
        diff_basis = get_run_diff_basis(run_dir)
        raw_changed_files, diff_basis_error = get_git_changed_files(repo_root, diff_basis)
        if raw_changed_files is not None:
            actual_changed_files = filter_runtime_changed_files(raw_changed_files, run_id)

    phases = [
        {"Key": "00R", "Label": "Phase 0 (Requirements)", "File": "00-requirements.md", "Optional": False, "PhaseName": "0 (Requirements)"},
        {"Key": "00W", "Label": "Phase 0 (Worktree)", "File": "00-worktree.md", "Optional": False, "PhaseName": "0 (Worktree)"},
        {"Key": "01", "Label": "Phase 1 (AS-IS)", "File": "01-as-is.md", "Optional": False, "PhaseName": "1 (AS-IS)"},
        {"Key": "01.5", "Label": "Phase 1.5 (Root Cause)", "File": "01.5-root-cause.md", "Optional": True, "PhaseName": "1.5 (Root Cause)"},
        {"Key": "02", "Label": "Phase 2 (TO-BE Plan)", "File": "02-to-be-plan.md", "Optional": False, "PhaseName": "2 (TO-BE Plan)"},
        {"Key": "03", "Label": "Phase 3 (Implementation)", "File": "03-implementation-summary.md", "Optional": False, "PhaseName": "3 (Implementation)"},
        {"Key": "03.5", "Label": "Phase 3.5 (Code Review)", "File": "03.5-code-review.md", "Optional": True, "PhaseName": "3.5 (Code Review)"},
        {"Key": "04", "Label": "Phase 4 (Test Summary)", "File": "04-test-summary.md", "Optional": False, "PhaseName": "4 (Test Summary)"},
        {"Key": "05", "Label": "Phase 5 (Manual QA)", "File": "05-manual-qa.md", "Optional": False, "PhaseName": "5 (Manual QA)"},
        {"Key": "06", "Label": "Phase 6 (Decisions)", "File": "06-decisions-update.md", "Optional": False, "PhaseName": "6 (Decisions Update)"},
        {"Key": "07", "Label": "Phase 7 (State)", "File": "07-state-update.md", "Optional": False, "PhaseName": "7 (State Update)"},
        {"Key": "08", "Label": "Phase 8 (Memory)", "File": "08-memory-impact.md", "Optional": False, "PhaseName": "8 (Memory Impact)"},
    ]

    states: dict[str, ArtifactState] = {}
    for phase in phases:
        state = get_artifact_state(run_dir / phase["File"], workflow_profile, requirement_ids, actual_changed_files, diff_basis_error)
        if phase["Optional"] and not state.exists:
            state.status = "SKIPPED"
        elif workflow_profile == "legacy" and phase["Key"] in LATE_PHASE_KEYS and not state.exists:
            state.status = "SKIPPED"
        states[phase["Key"]] = state

    current_phase: dict[str, str] | None = None
    current_state: ArtifactState | None = None
    for phase in phases:
        state = states[phase["Key"]]
        if state.status == "SKIPPED":
            continue
        if not state.exists or not state.lock_valid:
            current_phase = phase
            current_state = state
            break

    title = f"Recursive Run: {run_id}"
    print(title)
    print("=" * max(8, len(title)))
    print()
    print(f"Workflow Profile: {workflow_profile}")
    if workflow_profile in STRICT_WORKFLOW_PROFILES:
        print("Audit Contract: audited phases must reach Audit: PASS before Coverage/Approval may pass")
    print()
    print_phase_status(phases, states, args.show_hashes, run_id, workflow_profile)

    # Next-legal-phase and stale-chain summary using the canonical phase-rules model.
    phase_rules = load_phase_rules_module()
    next_legal = phase_rules.get_next_legal_phase(run_dir)
    stale_entries = phase_rules.get_all_stale_receipts(run_dir)

    if next_legal:
        print(f"Next Legal Phase: {next_legal}")
        prereq_blockers = phase_rules.get_prerequisite_blockers(next_legal, run_dir)
        if prereq_blockers:
            print("  Prerequisite blockers:")
            for blocker in prereq_blockers:
                print(f"    - {blocker['artifact']}: {blocker['status']}")
    elif current_phase is None:
        print("Next Legal Phase: COMPLETE (all phases locked)")
    else:
        print("Next Legal Phase: BLOCKED")
        print("  All candidate phases have unresolved prerequisites.")

    if stale_entries:
        print()
        print("Stale Lock-Chain Receipts (re-lock downstream phases in order):")
        for entry in stale_entries:
            print(f"  - {entry['artifact']}: {entry['reason']}")
    print()
    if current_phase is None:
        print("Current Phase: COMPLETE")
        print("Status: LOCKED")
    else:
        print(f"Current Phase: {current_phase['PhaseName']}")
        print(f"Status: {current_state.status}")
        if current_state.blockers:
            print("Audit Blockers:")
            for blocker in current_state.blockers:
                print(f"  - {blocker}")

    evidence_dir = run_dir / "evidence"
    evidence_files = sum(1 for path in evidence_dir.rglob("*") if path.is_file()) if evidence_dir.exists() else 0
    evidence_rel = f".recursive/run/{run_id}/evidence/"
    print()
    print("Evidence:")
    print(f"  Path:   {evidence_rel}")
    print(f"  Exists: {'Yes' if evidence_dir.exists() else 'No'}")
    print(f"  Files:  {evidence_files}")

    if workflow_profile in STRICT_WORKFLOW_PROFILES:
        print()
        print("Diff Audit:")
        if diff_basis_error:
            print(f"  Status: blocked - {diff_basis_error}")
        else:
            print(f"  Changed files reviewed from git diff basis: {len(actual_changed_files or [])}")

    print()
    print("Next Steps:")
    if current_phase is None:
        if workflow_profile == "legacy":
            print("  1. Legacy run is complete under the pre-Phase-8 workflow contract.")
            print("  2. If you resume this run under the new workflow, add `Workflow version: recursive-mode-audit-v2` and continue with the stricter audited closeout.")
        elif workflow_profile == COMPAT_WORKFLOW_PROFILE:
            print("  1. Compatibility run is complete through Phase 8.")
            print("  2. Use `Workflow version: recursive-mode-audit-v2` for new runs that should enforce the stronger audit loop.")
        else:
            print("  1. Run is complete through audited Phase 8.")
            print("  2. Merge the worktree branch when ready.")
    else:
        next_artifact = f".recursive/run/{run_id}/{current_phase['File']}"
        if workflow_profile in STRICT_WORKFLOW_PROFILES and current_phase["File"] in AUDITED_PHASE_FILES:
            print(f"  1. Update {next_artifact} so the audit sections are complete and grounded in upstream artifacts plus the recorded diff basis.")
            print("  2. Repair any in-scope gaps or unexplained drift, then rerun the audit.")
            print("  3. Only after `Audit: PASS` may Coverage/Approval pass and the phase lock.")
        else:
            print(f"  1. Complete {next_artifact}.")
            print("  2. Pass the required gates and lock the artifact before advancing.")

    print()
    print("Quick Command:")
    print(f"  Implement requirement '{run_id}'")


if __name__ == "__main__":
    main()
