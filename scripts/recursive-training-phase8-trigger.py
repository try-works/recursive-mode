#!/usr/bin/env python3
"""
Post-Phase 8 training trigger for recursive-mode.

Run this immediately after Phase 8 (08-memory-impact.md) is locked.
Thin wrapper: checks preconditions, then delegates to recursive-training-grpo.py.

Usage (after Phase 8 lock):
    python .recursive/scripts/recursive-training-phase8-trigger.py \
        --repo-root . \
        --run-id phase25-organizations-teams-rbac \
        [--auto] \
        [--grpo-args "--winner-only-threshold 3"]

Arguments:
    --repo-root: Path to git repository root
    --run-id: The run that just completed Phase 8
    --auto: Skip the "Train now?" prompt and run immediately
    --grpo-args: Extra arguments passed through to recursive-training-grpo.py

Exit codes:
    0: OK (training ran, or skipped because < 2 runs)
    1: Error (missing scripts, bridge failure, etc.)
    2: User declined (or --auto not set and user not prompted)
"""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def count_completed_runs(runs_dir: Path) -> int:
    """Count runs with a locked 08-memory-impact.md artifact."""
    if not runs_dir.exists():
        return 0
    count = 0
    for run_dir in runs_dir.iterdir():
        if run_dir.is_dir():
            phase8 = run_dir / "08-memory-impact.md"
            if phase8.exists():
                text = phase8.read_text(encoding="utf-8")
                if "LockedAt" in text or "Status: LOCKED" in text:
                    count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-Phase 8 training trigger for recursive-mode"
    )
    parser.add_argument("--repo-root", type=str, required=True)
    parser.add_argument("--run-id", type=str, required=True)
    parser.add_argument("--auto", action="store_true",
                        help="Run training immediately without prompting")
    parser.add_argument("--grpo-args", type=str, default="",
                        help='Extra args for recursive-training-grpo.py, e.g. "--winner-only-threshold 3"')
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    scripts_dir = repo_root / ".recursive" / "scripts"
    runs_dir = repo_root / ".recursive" / "run"
    grpo_script = scripts_dir / "recursive-training-grpo.py"

    # --- Check scripts exist ---
    if not grpo_script.exists():
        print("ERROR: recursive-training-grpo.py not found.")
        print("Run: python scripts/install-recursive-mode.py --repo-root .")
        return 1

    # --- Check enough runs ---
    completed = count_completed_runs(runs_dir)
    if completed < 2:
        print(f"Only {completed} completed run(s). Need 2+ for training.")
        print("Training skipped. Complete more runs and try again.")
        return 0

    # --- Prompt or auto-run ---
    if not args.auto:
        print(f"Run '{args.run_id}' completed Phase 8.")
        print(f"{completed} completed runs available.")
        print("")
        print("To extract learnings, run:")
        print(f"  python .recursive/scripts/recursive-training-grpo.py \\")
        print(f"    --repo-root . --incremental --run-id {args.run_id}")
        if args.grpo_args:
            print(f"    {args.grpo_args}")
        print("")
        print("Or re-run this script with --auto to skip confirmation.")
        return 2

    # --- Run training ---
    print(f"Auto-triggering training for {args.run_id} ({completed} runs)...")

    cmd = [
        "python", str(grpo_script),
        "--repo-root", str(repo_root),
        "--incremental",
        "--run-id", args.run_id,
    ]
    if args.grpo_args:
        cmd.extend(shlex.split(args.grpo_args))

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("ERROR: Training extraction failed.")
        return 1

    print("Training extraction updated the memory plane.")
    print("Future runs should read .recursive/memory/MEMORY.md and use recursive-training-loader.py when experiential memory is relevant.")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
