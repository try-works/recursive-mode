#!/usr/bin/env python3
"""
Check a reusable workflow/skill repository for committed run residue.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".ps1",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
}
RUN_ID_REFERENCE_RE = re.compile(r"\.recursive/run/(20\d{2}-\d{2}-\d{2}[A-Za-z0-9._-]*)")
TEMP_PATH_RESIDUE_RES = [
    re.compile(r"AppData[\\/]+Local[\\/]+Temp", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])tmp(?:[\\/]|$)", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])var[\\/]folders[\\/]", re.IGNORECASE),
]
RUN_ROOT_ALLOWED = {".gitkeep"}
GENERATED_RESIDUE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".tox",
    ".nox",
    "htmlcov",
}
GENERATED_RESIDUE_SUFFIXES = {".pyc", ".pyo", ".pyd"}
CANONICAL_START_MARKER = "<!-- RECURSIVE-MODE-CANONICAL:START -->"
CANONICAL_END_MARKER = "<!-- RECURSIVE-MODE-CANONICAL:END -->"


def is_installed_skill_path(path: Path, repo_root: Path) -> bool:
    try:
        relative_parts = path.relative_to(repo_root).parts
    except ValueError:
        return False
    return len(relative_parts) >= 2 and relative_parts[:2] == (".agents", "skills")


def extract_marked_body(content: str, start_marker: str, end_marker: str) -> str:
    start_index = content.find(start_marker)
    end_index = content.rfind(end_marker)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        return content.rstrip("\r\n")
    body_start = start_index + len(start_marker)
    return content[body_start:end_index].strip("\r\n")


def iter_text_files(repo_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if is_installed_skill_path(path, repo_root):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            candidates.append(path)
    return sorted(candidates)


def is_installed_skill_workspace(repo_root: Path) -> bool:
    return (
        (repo_root / ".agents" / "skills" / "recursive-mode").exists()
        and not (repo_root / "skills" / "recursive-mode").exists()
    )


def sanitized_skills_lock_content(content: str) -> str | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None

    skills = payload.get("skills")
    if not isinstance(skills, dict):
        return None

    modified = False
    for metadata in skills.values():
        if not isinstance(metadata, dict):
            continue
        if metadata.get("sourceType") != "local":
            continue
        source = metadata.get("source")
        if not isinstance(source, str):
            continue
        metadata["source"] = "<local-skill-source>"
        modified = True

    if not modified:
        return None
    return json.dumps(payload, sort_keys=True)


def print_fail(message: str) -> None:
    print(f"[FAIL] {message}")


def print_ok(message: str) -> None:
    print(f"[OK] {message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a reusable repo for recursive-mode run residue.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Also fail if `git status --porcelain` is not empty.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    failures = 0
    run_contamination_failures = 0
    generated_residue_failures = 0
    snapshot_failures = 0
    allow_local_skills_lock_sources = is_installed_skill_workspace(repo_root)

    run_root = repo_root / ".recursive" / "run"
    if run_root.exists():
        disallowed = [entry.name for entry in run_root.iterdir() if entry.name not in RUN_ROOT_ALLOWED]
        if disallowed:
            failures += 1
            run_contamination_failures += 1
            print_fail(
                ".recursive/run/ contains committed run residue: "
                + ", ".join(sorted(disallowed))
            )
        else:
            print_ok(".recursive/run/ contains no committed run residue beyond .gitkeep.")
    else:
        failures += 1
        run_contamination_failures += 1
        print_fail("Missing .recursive/run/ directory.")

    generated_residue_paths: list[str] = []
    for path in repo_root.rglob("*"):
        if ".git" in path.parts:
            continue
        if is_installed_skill_path(path, repo_root):
            continue
        if path.is_dir() and path.name in GENERATED_RESIDUE_DIR_NAMES:
            generated_residue_paths.append(path.relative_to(repo_root).as_posix() + "/")
        elif path.is_file() and path.suffix.lower() in GENERATED_RESIDUE_SUFFIXES:
            generated_residue_paths.append(path.relative_to(repo_root).as_posix())

    if generated_residue_paths:
        failures += len(generated_residue_paths)
        generated_residue_failures += len(generated_residue_paths)
        for rel in sorted(generated_residue_paths):
            print_fail(f"Generated local residue is present in the repo tree: {rel}")
    else:
        print_ok("No generated local residue such as __pycache__/ or *.pyc is present.")

    canonical_workflow = repo_root / ".recursive" / "RECURSIVE.md"
    packaged_workflow = Path(__file__).resolve().parent.parent / "references" / "bootstrap" / "RECURSIVE.md"
    if not packaged_workflow.exists():
        failures += 1
        snapshot_failures += 1
        print_fail(f"Missing packaged bootstrap workflow template: {packaged_workflow}")
    elif not canonical_workflow.exists():
        failures += 1
        snapshot_failures += 1
        print_fail("Missing canonical workflow source file: .recursive/RECURSIVE.md")
    else:
        canonical_text = extract_marked_body(
            canonical_workflow.read_text(encoding="utf-8"),
            CANONICAL_START_MARKER,
            CANONICAL_END_MARKER,
        )
        packaged_text = packaged_workflow.read_text(encoding="utf-8").rstrip("\r\n")
        if canonical_text != packaged_text:
            failures += 1
            snapshot_failures += 1
            print_fail("Packaged bootstrap workflow template does not match .recursive/RECURSIVE.md")
        else:
            print_ok("Packaged bootstrap workflow template matches .recursive/RECURSIVE.md.")

    for path in iter_text_files(repo_root):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(repo_root).as_posix()

        run_match = RUN_ID_REFERENCE_RE.search(content)
        if run_match:
            failures += 1
            run_contamination_failures += 1
            print_fail(f"{rel} contains a concrete recursive run reference: {run_match.group(0)}")

        for pattern in TEMP_PATH_RESIDUE_RES:
            search_content = content
            if rel == "skills-lock.json" and allow_local_skills_lock_sources:
                sanitized = sanitized_skills_lock_content(content)
                if sanitized is not None:
                    search_content = sanitized

            temp_match = pattern.search(search_content)
            if temp_match:
                failures += 1
                run_contamination_failures += 1
                print_fail(f"{rel} contains temp-path residue: {temp_match.group(0)}")
                break

    if args.require_clean_git:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            failures += 1
            snapshot_failures += 1
            print_fail("Unable to query git status for cleanliness check.")
        elif completed.stdout.strip():
            failures += 1
            snapshot_failures += 1
            print_fail("Git worktree is not clean under --require-clean-git.")
        else:
            print_ok("Git worktree is clean.")

    if failures:
        print(
            "[SUMMARY] Failure categories -> "
            f"run contamination: {run_contamination_failures}, "
            f"generated residue: {generated_residue_failures}, "
            f"snapshot cleanliness: {snapshot_failures}"
        )
        print(f"[SUMMARY] Hygiene check failed with {failures} issue(s).")
        sys.exit(1)

    print("[SUMMARY] Failure categories -> run contamination: 0, generated residue: 0, snapshot cleanliness: 0")
    print("[SUMMARY] Reusable-repo hygiene check passed.")


if __name__ == "__main__":
    main()
