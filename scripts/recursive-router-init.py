#!/usr/bin/env python3
from __future__ import annotations

import argparse

from pathlib import Path

from recursive_router_lib import RouterConfigError, ensure_router_scaffold, normalize_repo_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize recursive-router config files.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        policy_path, discovery_path = ensure_router_scaffold(repo_root)
    except RouterConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(f"[OK] Router policy path: {normalize_repo_path(str(policy_path.relative_to(repo_root)))}")
    print(f"[OK] Discovery inventory path: {normalize_repo_path(str(discovery_path.relative_to(repo_root)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
