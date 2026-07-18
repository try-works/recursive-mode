#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from recursive_router_lib import RouterConfigError, load_policy, normalize_repo_path, router_policy_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate recursive-router routing policy.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        load_policy(repo_root)
    except RouterConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(f"[OK] Routing policy is valid: {normalize_repo_path(str(router_policy_path(repo_root).relative_to(repo_root)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
