#!/usr/bin/env python3
"""
Check a reusable workflow/skill repository for committed run residue.
"""

from __future__ import annotations

import argparse
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


def iter_text_files(repo_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            candidates.append(path)
    return sorted(candidates)


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
            temp_match = pattern.search(content)
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
