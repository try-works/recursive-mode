#!/usr/bin/env python3
"""
Scaffold recursive-mode closeout artifacts for Phases 4-8.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path


PHASE_CONFIG: dict[str, dict[str, object]] = {
    "04": {
        "file_name": "04-test-summary.md",
        "phase_label": "04 Test Summary",
        "scope_note": "Scaffolds the audited test-summary receipt from the existing implementation, review, and evidence context.",
        "todo_items": [
            "Record the pre-test implementation audit and execution environment",
            "Capture exact commands, evidence, and final results",
            "Complete the audited test-summary gates before locking",
        ],
        "extra_outputs": [],
        "extra_inputs": [],
    },
    "05": {
        "file_name": "05-manual-qa.md",
        "phase_label": "05 Manual QA",
        "scope_note": "Scaffolds the manual-QA receipt and captures any preview URL evidence that should appear in the QA record.",
        "todo_items": [
            "Declare the QA execution mode and supporting evidence",
            "Record the manual QA scenarios and observed results",
            "Complete Coverage and Approval gates before locking",
        ],
        "extra_outputs": [],
        "extra_inputs": [],
    },
    "06": {
        "file_name": "06-decisions-update.md",
        "phase_label": "06 Decisions Update",
        "scope_note": "Scaffolds the compact decision-ledger delta receipt for the completed run closeout.",
        "todo_items": [
            "Record the exact decisions delta applied during closeout",
            "Reference the updated decision ledger entry",
            "Complete the audited decision-update gates before locking",
        ],
        "extra_outputs": [".recursive/DECISIONS.md"],
        "extra_inputs": [".recursive/DECISIONS.md"],
    },
    "07": {
        "file_name": "07-state-update.md",
        "phase_label": "07 State Update",
        "scope_note": "Scaffolds the compact state-ledger delta receipt for the validated final repository state.",
        "todo_items": [
            "Record the exact state delta applied during closeout",
            "Reference the updated state ledger summary",
            "Complete the audited state-update gates before locking",
        ],
        "extra_outputs": [".recursive/STATE.md"],
        "extra_inputs": [".recursive/STATE.md"],
    },
    "08": {
        "file_name": "08-memory-impact.md",
        "phase_label": "08 Memory Impact",
        "scope_note": "Scaffolds the compact memory-plane delta receipt for the final validated run impact.",
        "todo_items": [
            "Review affected memory docs and freshness outcomes",
            "Document uncovered paths and router/parent refresh work",
            "Complete the audited memory-impact gates before locking",
        ],
        "extra_outputs": [".recursive/memory/MEMORY.md", ".recursive/memory/skills/SKILLS.md"],
        "extra_inputs": [".recursive/memory/MEMORY.md", ".recursive/memory/skills/SKILLS.md"],
    },
}


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
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError:
        raise RuntimeError(f"Phase rules module not found: {module_path}")
    return module


def write_utf8_no_bom(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("/")


def repo_rel(repo_root: Path, path: Path) -> str:
    return "/" + path.resolve().relative_to(repo_root.resolve()).as_posix()


def resolve_optional_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / raw_path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path must stay within repo root: {repo_root}") from exc
    return candidate


def detect_preview_url(preview_log_path: Path | None, explicit_preview_url: str) -> str:
    if explicit_preview_url.strip():
        return explicit_preview_url.strip()
    if preview_log_path is None:
        return ""
    content = preview_log_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"https?://[^\s`'\"]+", content)
    return match.group(0) if match else ""


def list_block(values: list[str]) -> str:
    if not values:
        return "- None recorded yet; update before locking."
    return "\n".join(f"- `{value}`" for value in values)


def unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = normalize_repo_path(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def parse_requirement_ids(lint, run_dir: Path) -> list[str]:
    requirements_path = run_dir / "00-requirements.md"
    if not requirements_path.exists():
        return []
    return lint.parse_requirement_ids(requirements_path.read_text(encoding="utf-8"))


def collect_phase_inputs(
    lint,
    repo_root: Path,
    run_dir: Path,
    file_name: str,
    phase_key: str,
    preview_log_path: Path | None,
) -> list[str]:
    run_prefix = f".recursive/run/{run_dir.name}/"
    inputs: list[str] = []
    for artifact_name in lint.get_phase_expected_input_artifact_names(file_name, run_dir):
        inputs.append(f"{run_prefix}{artifact_name}")
    inputs.extend(lint.get_expected_effective_input_addenda_paths(run_dir, file_name))
    config = PHASE_CONFIG[phase_key]
    inputs.extend(config.get("extra_inputs", []))  # type: ignore[arg-type]

    if phase_key == "04":
        for relative_dir in ("evidence/logs/red", "evidence/logs/green", "evidence/review-bundles"):
            candidate_dir = run_dir / relative_dir
            if candidate_dir.exists():
                for file_path in sorted(path for path in candidate_dir.rglob("*") if path.is_file()):
                    inputs.append(repo_rel(repo_root, file_path))
    elif phase_key == "05":
        logs_dir = run_dir / "evidence" / "logs"
        if logs_dir.exists():
            for file_path in sorted(path for path in logs_dir.rglob("*") if path.is_file()):
                inputs.append(repo_rel(repo_root, file_path))
        if preview_log_path is not None:
            inputs.append(repo_rel(repo_root, preview_log_path))

    return unique_preserve(inputs)


def collect_phase_outputs(run_dir: Path, phase_key: str, file_name: str) -> list[str]:
    run_prefix = f".recursive/run/{run_dir.name}/"
    outputs = [f"{run_prefix}{file_name}"]
    outputs.extend(PHASE_CONFIG[phase_key].get("extra_outputs", []))  # type: ignore[arg-type]
    return unique_preserve(outputs)


def render_header(run_dir: Path, phase_key: str, inputs: list[str], outputs: list[str]) -> str:
    config = PHASE_CONFIG[phase_key]
    lines = [
        f"Run: `/.recursive/run/{run_dir.name}/`",
        f"Phase: `{config['phase_label']}`",
        "Status: `DRAFT`",
        "Inputs:",
        *[f"- `/{value}`" for value in inputs],
        "Outputs:",
        *[f"- `/{value}`" for value in outputs],
        f"Scope note: {config['scope_note']}",
    ]
    return "\n".join(lines)


def default_requirement_status_section(requirement_ids: list[str], run_dir: Path) -> str:
    if not requirement_ids:
        return "- Add machine-checkable requirement completion lines before locking.\n"
    return "\n".join(
        f"- {requirement_id} | Status: blocked | Rationale: Replace this scaffold line with the phase-specific outcome before locking. | Blocking Evidence: `/.recursive/run/{run_dir.name}/00-requirements.md`"
        for requirement_id in requirement_ids
    )


def default_audit_context(file_name: str, inputs: list[str]) -> str:
    return "\n".join(
        [
            "- Audit Execution Mode: self-audit",
            "- Subagent Availability: unavailable",
            f"- Subagent Capability Probe: `Populate whether delegated audit is actually available for {file_name}.`",
            "- Delegation Decision Basis: `Populate why this phase remains self-audited or how delegated review was grounded.`",
            "- Audit Inputs Provided:",
            *[f"  - `/{value}`" for value in inputs],
        ]
    )


def default_diff_basis_section(lint, run_dir: Path) -> str:
    diff_basis = lint.get_run_diff_basis(run_dir)
    baseline_type = diff_basis.get("baseline_type") or "local commit"
    baseline_reference = diff_basis.get("baseline_reference") or "<update-before-locking>"
    comparison_reference = diff_basis.get("comparison_reference") or "working-tree"
    normalized_baseline = diff_basis.get("normalized_baseline") or "<update-before-locking>"
    normalized_comparison = diff_basis.get("normalized_comparison") or "working-tree"
    normalized_diff_command = diff_basis.get("normalized_diff_command") or "git diff --name-only <update-before-locking>"
    return "\n".join(
        [
            f"- Baseline type: `{baseline_type}`",
            f"- Baseline reference: `{baseline_reference}`",
            f"- Comparison reference: `{comparison_reference}`",
            f"- Normalized baseline: `{normalized_baseline}`",
            f"- Normalized comparison: `{normalized_comparison}`",
            f"- Normalized diff command: `{normalized_diff_command}`",
            "- Planned or claimed changed files:",
            "  - Populate the owned changed files for this closeout phase before locking.",
            "- Actual changed files reviewed:",
            "  - Populate the final reviewed changed-file list before locking.",
            "- Unexplained drift:",
            "  - Record any unexplained drift or replace with `None.` only after the audit is complete.",
        ]
    )


def section_body(
    lint,
    repo_root: Path,
    run_dir: Path,
    phase_key: str,
    heading: str,
    inputs: list[str],
    preview_log_path: Path | None,
    preview_url: str,
    requirement_ids: list[str],
) -> str:
    run_prefix = f".recursive/run/{run_dir.name}/"
    preview_log_rel = repo_rel(repo_root, preview_log_path) if preview_log_path is not None else ""
    if heading == "TODO":
        return "\n".join(f"- [ ] {item}" for item in PHASE_CONFIG[phase_key]["todo_items"])  # type: ignore[index]
    if heading == "Pre-Test Implementation Audit":
        return "- Re-read the implementation summary, code review, addenda, and owned diff before finalizing this test receipt."
    if heading == "Environment":
        return "- Record the actual runtime, tool versions, and any disposable-repo constraints here before locking."
    if heading == "Execution Mode":
        return "- Record whether test execution was local, CI-backed, or hybrid before locking."
    if heading == "Commands Executed (Exact)":
        return "- Record the exact commands run for this test summary, one command per bullet."
    if heading == "Results Summary":
        return "- Summarize the final pass/fail outcomes and any reruns here before locking."
    if heading == "Evidence and Artifacts":
        return "- List concrete evidence paths under `/.recursive/run/<run-id>/evidence/` that support this phase."
    if heading == "Failures and Diagnostics (if any)":
        return "- Record expected failures and any final diagnostics here; use `None.` only when no diagnostics were needed."
    if heading == "Flake/Rerun Notes":
        return "- Record any reruns or explicitly state that none were required."
    if heading == "QA Execution Record":
        lines = [
            "- QA Execution Mode: agent-operated",
            "- Agent Executor: populate the actual executor before locking",
            "- Tools Used: populate the actual tools used before locking",
        ]
        if preview_url:
            lines.append(f"- Preview URL: `{preview_url}`")
        if preview_log_rel:
            lines.append(f"- Preview Log: `{preview_log_rel}`")
        lines.append("- Evidence Path: populate the concrete QA evidence path before locking")
        return "\n".join(lines)
    if heading == "QA Scenarios and Results":
        return "- Record each manual QA scenario and observed result here before locking."
    if heading == "User Sign-Off":
        return "- Approved by: N/A (set a real approver when QA mode requires human sign-off)\n- Date: N/A (set a real approval date when required)"
    if heading == "Decisions Changes Applied":
        return "- Record the exact `.recursive/DECISIONS.md` delta applied during closeout."
    if heading == "Resulting Decision Entry":
        return "- Point to the final ledger entry heading or path after updating `.recursive/DECISIONS.md`."
    if heading == "State Changes Applied":
        return "- Record the exact `.recursive/STATE.md` delta applied during closeout."
    if heading == "Resulting State Summary":
        return "- Summarize the final state line or section that now reflects the completed run."
    if heading == "Diff Basis":
        return "- Reconfirm the final memory review against the executable Phase 0 diff basis before locking."
    if heading == "Changed Paths Review":
        return "- Record the final changed product/control-plane paths reviewed for memory impact."
    if heading == "Affected Memory Docs":
        return "- List the affected memory docs under `/.recursive/memory/`, including any skill-memory router or shard docs reviewed or updated before locking."
    if heading == "Uncovered Paths":
        return "- Record uncovered paths or replace with `None.` only after the memory review is complete."
    if heading == "Router and Parent Refresh":
        return "- Record any router, parent, freshness, or skill-memory updates made in the memory plane."
    if heading == "Run-Local Skill Usage Capture":
        return "\n".join(
            [
                "- Skill Usage Relevance: not-relevant",
                "- Available Skills: record the skills available in the run environment, or `none`",
                "- Skills Sought: record any skills the run tried to discover, or `none`",
                "- Skills Attempted: record any skills attempted, or `none`",
                "- Skills Used: record any skills actually used, or `none`",
                "- Worked Well: record what helped, or `none`",
                "- Issues Encountered: record any skill issues or `none`",
                "- Future Guidance: record prefer/caution/avoid guidance, or `none`",
                "- Promotion Candidates: record candidate durable lessons, or `none`",
            ]
        )
    if heading == "Skill Memory Promotion Review":
        return "\n".join(
            [
                "- Durable Skill Lessons Promoted: record any generalized skill-memory shards updated, or `none`",
                "- Generalized Guidance Updated: record router/index or reusable guidance updates, or `none`",
                "- Run-Local Observations Left Unpromoted: record transient observations kept run-local, or `none`",
                "- Promotion Decision Rationale: explain why observations were or were not promoted into durable skill memory",
            ]
        )
    if heading == "Final Status Summary":
        return "- Summarize the resulting memory freshness, uncovered paths outcome, and any durable skill-memory lessons captured here before locking."
    if heading == "Rationale":
        return "- Record why this closeout delta was necessary and how it aligns with the completed run."
    if heading == "Traceability":
        return "- Map the closeout evidence back to the in-scope requirements before locking."
    if heading == "Coverage Gate":
        return "- Replace these checklist items with phase-specific proof before locking.\nCoverage: FAIL"
    if heading == "Approval Gate":
        return "- Replace these checklist items with phase-specific approval proof before locking.\nApproval: FAIL"
    if heading == "Audit Context":
        return default_audit_context(PHASE_CONFIG[phase_key]["file_name"], inputs)  # type: ignore[index]
    if heading == "Effective Inputs Re-read":
        return list_block(inputs)
    if heading == "Prior Recursive Evidence Reviewed":
        return "- Record any earlier recursive evidence re-read for this late closeout phase, or explain why none was relevant."
    if heading == "Earlier Phase Reconciliation":
        return "- Reconcile this closeout receipt against earlier locked phases and any approved addenda before locking."
    if heading == "Subagent Contribution Verification":
        return "- No subagent work recorded yet; if delegated closeout work materially contributes, record Reviewed Action Records, Main-Agent Verification Performed, Acceptance Decision, Refresh Handling, and Repair Performed After Verification."
    if heading == "Worktree Diff Audit":
        return default_diff_basis_section(lint, run_dir)
    if heading == "Gaps Found":
        return "- Record unresolved gaps here. Replace with `None.` only after the audit is complete."
    if heading == "Repair Work Performed":
        return "- Record any repair work performed during closeout, or explain why no repair was required."
    if heading == "Requirement Completion Status":
        return default_requirement_status_section(requirement_ids, run_dir)
    if heading == "Audit Verdict":
        return "- Record the final audit verdict grounded in the reviewed inputs and outputs before locking.\nAudit: FAIL"
    return "- Populate this section before locking."


def build_scaffold(
    lint,
    repo_root: Path,
    run_dir: Path,
    phase_key: str,
    preview_log_path: Path | None,
    preview_url: str,
) -> str:
    file_name = PHASE_CONFIG[phase_key]["file_name"]  # type: ignore[index]
    workflow_profile = lint.get_workflow_profile(run_dir)
    headings = lint.get_artifact_required_sections(file_name, workflow_profile)
    inputs = collect_phase_inputs(lint, repo_root, run_dir, file_name, phase_key, preview_log_path)
    outputs = collect_phase_outputs(run_dir, phase_key, file_name)
    requirement_ids = parse_requirement_ids(lint, run_dir)

    blocks = [render_header(run_dir, phase_key, inputs, outputs)]
    for heading in headings:
        blocks.append(f"## {heading}\n\n{section_body(lint, repo_root, run_dir, phase_key, heading, inputs, preview_log_path, preview_url, requirement_ids)}")
    return "\n\n".join(blocks).rstrip() + "\n"


def resolve_phase_key(raw_phase: str) -> str:
    compact = raw_phase.strip().lower().replace(".md", "")
    aliases = {
        "4": "04",
        "04": "04",
        "04-test-summary": "04",
        "5": "05",
        "05": "05",
        "05-manual-qa": "05",
        "6": "06",
        "06": "06",
        "06-decisions-update": "06",
        "7": "07",
        "07": "07",
        "07-state-update": "07",
        "8": "08",
        "08": "08",
        "08-memory-impact": "08",
    }
    phase_key = aliases.get(compact)
    if not phase_key:
        raise ValueError(f"Unsupported closeout phase: {raw_phase}")
    return phase_key


def artifact_is_locked(artifact_path: Path) -> bool:
    if not artifact_path.exists():
        return False
    content = artifact_path.read_text(encoding="utf-8")
    return bool(re.search(r"(?m)^Status:\s*`?LOCKED`?\s*$", content)) or "LockedAt:" in content


def run_phase8_training_trigger(repo_root: Path, run_id: str) -> int:
    trigger_script = repo_root / ".recursive" / "scripts" / "recursive-training-phase8-trigger.py"
    if not trigger_script.exists():
        print("[INFO] recursive-training Phase 8 trigger not installed; skipping experiential training refresh.")
        return 0

    command = [
        sys.executable,
        str(trigger_script),
        "--repo-root",
        str(repo_root),
        "--run-id",
        run_id,
        "--auto",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "no diagnostics emitted"
        print(f"[FAIL] recursive-training Phase 8 trigger failed: {details}")
        return result.returncode or 1

    print("[OK] Ran recursive-training Phase 8 trigger.")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold recursive-mode closeout artifacts for Phases 4-8.")
    parser.add_argument("--run-id", required=True, help="Run ID under .recursive/run/.")
    parser.add_argument("--phase", required=True, help="Closeout phase to scaffold: 04, 05, 06, 07, or 08.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--preview-log", default="", help="Optional preview server log path used to capture the actual served URL in Phase 5.")
    parser.add_argument("--preview-url", default="", help="Optional explicit preview URL override.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing closeout artifact.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = repo_root / ".recursive" / "run" / args.run_id.strip()
    if not run_dir.exists():
        print(f"[FAIL] Run directory not found: {run_dir}")
        return 1

    try:
        phase_key = resolve_phase_key(args.phase)
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    preview_log_path: Path | None = None
    if args.preview_log.strip():
        try:
            preview_log_path = resolve_optional_repo_path(repo_root, args.preview_log.strip())
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        if not preview_log_path.exists():
            print(f"[FAIL] Preview log not found: {preview_log_path}")
            return 1

    preview_url = detect_preview_url(preview_log_path, args.preview_url)
    if phase_key == "05" and preview_log_path is not None and not preview_url:
        print(f"[FAIL] Could not parse a preview URL from: {preview_log_path}")
        return 1

    lint = load_lint_module()
    phase_rules = load_phase_rules_module()
    file_name = PHASE_CONFIG[phase_key]["file_name"]  # type: ignore[index]
    artifact_path = run_dir / file_name

    # Advisory prerequisite check: warn if earlier phases are not yet locked.
    # (Hard enforcement happens at lock time via recursive-lock.py.)
    blockers = phase_rules.get_prerequisite_blockers(file_name, run_dir)
    if blockers:
        print(f"[WARN] Scaffolding {file_name} before prerequisite phases are LOCKED")
        for blocker in blockers:
            print(f"  - {blocker['artifact']}: {blocker['status']}")

    if phase_key == "08" and artifact_path.exists() and not args.force and artifact_is_locked(artifact_path):
        print(f"[INFO] Phase 8 artifact already locked: {artifact_path}")
        return run_phase8_training_trigger(repo_root, args.run_id)
    if artifact_path.exists() and not args.force:
        print(f"[INFO] Closeout artifact exists, not overwriting: {artifact_path}")
        return 0

    content = build_scaffold(lint, repo_root, run_dir, phase_key, preview_log_path, preview_url)
    write_utf8_no_bom(artifact_path, content)
    print(f"[OK] Wrote closeout scaffold: {artifact_path}")
    if phase_key == "05" and preview_url:
        print(f"[OK] Parsed preview URL: {preview_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
