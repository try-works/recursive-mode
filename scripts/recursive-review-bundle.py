#!/usr/bin/env python3
"""
Generate a canonical recursive-mode review bundle for delegated audit or review.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TRANSIENT_RUNTIME_DIR_MARKERS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".tox", ".nox"}
TRANSIENT_RUNTIME_FILE_NAMES = {".ds_store", "thumbs.db"}
TRANSIENT_RUNTIME_SUFFIXES = (".pyc", ".pyo", ".pyd")
DIFF_BASIS_ALLOWED_TYPES = {"local commit", "local branch", "remote ref", "merge-base derived"}
WORKING_TREE_COMPARISON_REFS = {"working-tree", "working-tree@head", "worktree", "working-tree+head"}


def trim_md_value(value: str) -> str:
    return value.strip().strip("`\"'")


def get_md_field_value(content: str, field_name: str) -> str | None:
    pattern = re.compile(rf"(?m)^[ \t]*(?:[-*][ \t]+)?{re.escape(field_name)}:\s*(.+?)\s*$")
    match = pattern.search(content)
    if not match:
        return None
    return trim_md_value(match.group(1))


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
    diff_body = re.search(r"(?ms)^##\s+Diff Basis For Later Audits\s*$\n?(.*?)(?=^##\s+|\Z)", content)
    if diff_body:
        return diff_body.group(1)
    diff_body = re.search(r"(?ms)^##\s+Diff Basis\s*$\n?(.*?)(?=^##\s+|\Z)", content)
    if diff_body:
        return diff_body.group(1)
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


def normalize_repo_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").strip().lstrip("/")


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


def get_stage_local_addenda_paths(run_dir: Path, artifact_name: str) -> list[Path]:
    addenda_dir = run_dir / "addenda"
    if not addenda_dir.exists():
        return []
    base_name = artifact_name[:-3] if artifact_name.endswith(".md") else artifact_name
    return sorted(addenda_dir.glob(f"{base_name}.addendum-*.md"))


def get_current_phase_addenda_paths(run_dir: Path, artifact_name: str) -> list[Path]:
    addenda_dir = run_dir / "addenda"
    if not addenda_dir.exists():
        return []
    base_name = artifact_name[:-3] if artifact_name.endswith(".md") else artifact_name
    matches = list(get_stage_local_addenda_paths(run_dir, artifact_name))
    matches.extend(sorted(addenda_dir.glob(f"{base_name}.upstream-gap.*.addendum-*.md")))
    unique: dict[str, Path] = {}
    for path in matches:
        unique[str(path.resolve())] = path
    return [unique[key] for key in sorted(unique)]


def auto_discover_addenda(run_dir: Path, run_id: str, artifact_path: str, upstream_artifacts: list[str]) -> list[str]:
    run_prefix = f".recursive/run/{run_id}/"
    discovered: list[str] = []

    for artifact in upstream_artifacts:
        normalized = normalize_repo_path(artifact)
        if not normalized.startswith(run_prefix):
            continue
        relative = normalized[len(run_prefix):]
        if relative.startswith("addenda/"):
            continue
        for addendum_path in get_stage_local_addenda_paths(run_dir, Path(relative).name):
            discovered.append(f"{run_prefix}addenda/{addendum_path.name}")

    normalized_artifact_path = normalize_repo_path(artifact_path)
    if normalized_artifact_path.startswith(run_prefix):
        artifact_name = Path(normalized_artifact_path[len(run_prefix):]).name
        for addendum_path in get_current_phase_addenda_paths(run_dir, artifact_name):
            discovered.append(f"{run_prefix}addenda/{addendum_path.name}")

    return sorted(set(discovered))


def auto_discover_skill_memory_refs(repo_root: Path, phase: str, role: str) -> list[str]:
    skills_router = ".recursive/memory/skills/SKILLS.md"
    discovered: list[str] = []
    if (repo_root / skills_router).exists():
        discovered.append(skills_router)

    skills_root = repo_root / ".recursive" / "memory" / "skills"
    if not skills_root.exists():
        return discovered

    query_tokens = set(re.findall(r"[a-z0-9]+", f"{phase} {role}".lower()))
    if not query_tokens:
        return discovered

    for path in sorted(skills_root.rglob("*.md")):
        relative = normalize_repo_path(str(path.relative_to(repo_root)))
        if relative == skills_router:
            continue
        stem_tokens = set(re.findall(r"[a-z0-9]+", path.stem.lower()))
        if query_tokens & stem_tokens:
            discovered.append(relative)
    return sorted(set(discovered))


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "bundle"


def render_list(title: str, values: list[str], *, indent: str = "- ") -> list[str]:
    lines = [title]
    if not values:
        lines.append(f"{indent}none")
        return lines
    lines.extend(f"{indent}`{value}`" for value in values)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a canonical recursive-mode review bundle.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--run-id", required=True, help="Run ID under .recursive/run/.")
    parser.add_argument("--phase", required=True, help="Phase name for the bundle, e.g. '03.5 Code Review'.")
    parser.add_argument("--role", required=True, help="Delegated role, e.g. code-reviewer, phase-auditor, test-reviewer.")
    parser.add_argument("--artifact-path", required=True, help="Repo-relative artifact path the review is for.")
    parser.add_argument("--upstream-artifact", action="append", default=[], help="Repo-relative upstream artifact path. Repeat as needed.")
    parser.add_argument("--addendum", action="append", default=[], help="Repo-relative addendum path. Repeat as needed.")
    parser.add_argument("--prior-ref", action="append", default=[], help="Repo-relative prior run or recursive memory path. Repeat as needed.")
    parser.add_argument("--control-doc", action="append", default=[], help="Repo-relative control-plane doc path. Repeat as needed.")
    parser.add_argument("--code-ref", action="append", default=[], help="Repo-relative code file to inspect. Repeat as needed.")
    parser.add_argument("--evidence-ref", action="append", default=[], help="Repo-relative evidence artifact path. Repeat as needed.")
    parser.add_argument("--audit-question", action="append", default=[], help="Audit or review question. Repeat as needed.")
    parser.add_argument("--required-output", action="append", default=[], help="Required output bullet. Repeat as needed.")
    parser.add_argument("--output-name", default="", help="Optional bundle filename under evidence/review-bundles/.")
    parser.add_argument("--no-auto-addenda", action="store_true", help="Disable automatic addenda discovery for upstream artifacts and the current phase.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = repo_root / ".recursive" / "run" / args.run_id.strip()
    if not run_dir.exists():
        print(f"[FAIL] Run directory not found: {run_dir}")
        return 1

    diff_basis = get_run_diff_basis(run_dir)
    normalized_diff_basis, diff_basis_error = normalize_diff_basis(repo_root, diff_basis)
    if diff_basis_error:
        print(f"[FAIL] {diff_basis_error}")
        return 1
    changed_files, diff_error = get_git_changed_files(repo_root, diff_basis)
    if diff_error:
        print(f"[FAIL] {diff_error}")
        return 1

    filtered_changed_files = filter_runtime_changed_files(changed_files or [], run_dir.name)

    artifact_path = normalize_repo_path(args.artifact_path)
    upstream_artifacts = [normalize_repo_path(item) for item in args.upstream_artifact]
    addenda = [normalize_repo_path(item) for item in args.addendum]
    if not (repo_root / artifact_path).exists():
        print(f"[FAIL] Artifact path not found: /{artifact_path}")
        return 1
    if not args.no_auto_addenda:
        addenda.extend(auto_discover_addenda(run_dir, run_dir.name, artifact_path, upstream_artifacts))
    addenda = sorted(set(addenda))
    prior_refs = sorted(set(normalize_repo_path(item) for item in args.prior_ref if item.strip()))
    prior_refs.extend(auto_discover_skill_memory_refs(repo_root, args.phase, args.role))
    prior_refs = sorted(set(prior_refs))
    control_docs = [normalize_repo_path(item) for item in args.control_doc]
    code_refs = [normalize_repo_path(item) for item in args.code_ref]
    evidence_refs = [normalize_repo_path(item) for item in args.evidence_ref]
    audit_questions = [item.strip() for item in args.audit_question if item.strip()]
    required_output = [item.strip() for item in args.required_output if item.strip()]

    if not required_output:
        required_output = [
            "Findings ordered by severity",
            "Requirement and plan alignment assessment",
            "Diff reconciliation summary",
            "Explicit verdict and repair recommendation",
        ]

    bundle_name = args.output_name.strip()
    if not bundle_name:
        bundle_name = f"{slugify(args.phase)}-{slugify(args.role)}.md"
    if not bundle_name.lower().endswith(".md"):
        bundle_name = f"{bundle_name}.md"

    bundle_dir = run_dir / "evidence" / "review-bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / bundle_name
    bundle_rel = normalize_repo_path(str(bundle_path.relative_to(repo_root)))
    artifact_content_hash = content_sha256((repo_root / artifact_path).read_text(encoding="utf-8"))

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        f"Run: `/.recursive/run/{run_dir.name}/`",
        f"Phase: `{args.phase.strip()}`",
        f"Role: `{args.role.strip()}`",
        f"Bundle Path: `/{bundle_rel}`",
        f"Artifact Path: `/{artifact_path}`",
        f"Artifact Content Hash: `{artifact_content_hash}`",
        f"GeneratedAt: `{generated_at}`",
        "",
        "## Bundle Scope",
        "- Canonical delegated review bundle for recursive-mode audit/review work.",
        "- Regenerate this bundle if the draft, changed files, or required evidence changes materially before review.",
        "",
        "## Diff Basis",
        f"- Baseline type: `{normalized_diff_basis['baseline_type']}`",
        f"- Baseline reference: `{diff_basis['baseline_reference'] or 'UNKNOWN'}`",
        f"- Comparison reference: `{normalized_diff_basis['comparison_reference']}`",
        f"- Normalized baseline: `{normalized_diff_basis['normalized_baseline']}`",
        f"- Normalized comparison: `{normalized_diff_basis['normalized_comparison']}`",
        f"- Normalized diff command: `{normalized_diff_basis['normalized_diff_command']}`",
        "",
    ]
    lines.extend(render_list("## Changed Files Reviewed", filtered_changed_files))
    lines.append("")
    lines.extend(render_list("## Upstream Artifacts To Re-read", upstream_artifacts))
    lines.append("")
    lines.extend(render_list("## Relevant Addenda", addenda))
    lines.append("")
    lines.extend(render_list("## Prior Recursive Evidence", prior_refs))
    lines.append("")
    lines.extend(render_list("## Control-Plane Docs", control_docs))
    lines.append("")
    lines.extend(render_list("## Targeted Code References", code_refs))
    lines.append("")
    lines.extend(render_list("## Evidence References", evidence_refs))
    lines.append("")
    lines.extend(render_list("## Audit Questions", audit_questions))
    lines.append("")
    lines.extend(render_list("## Required Output", required_output))
    lines.append("")
    lines.append("## Notes")
    lines.append("- Review output is invalid if it does not cite the upstream artifacts, diff basis, changed files, and final verdict.")
    lines.append("- If this bundle is incomplete, reject delegation and perform the audit as self-audit.")
    lines.append("")

    bundle_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    print(f"[OK] Wrote review bundle: /{bundle_rel}")
    print(f"Changed files: {len(filtered_changed_files)}")
    print(f"Role: {args.role.strip()}")
    print(f"Phase: {args.phase.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
