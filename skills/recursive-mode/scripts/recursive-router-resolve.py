#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from recursive_router_lib import RouterConfigError, pretty_json, resolve_route


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve recursive-router routing for a subagent role.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--role", required=True, help="Stage-aligned routed role to resolve. Legacy aliases are accepted.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--no-write", action="store_true", help="Do not refresh the discovery inventory file.")
    parser.add_argument("--timeout-ms", type=int, default=None, help="Override probe timeout in milliseconds.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        decision = resolve_route(
            repo_root,
            role=args.role,
            timeout_ms=args.timeout_ms,
            write_discovery=not args.no_write,
        )
    except RouterConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.json:
        print(pretty_json(decision), end="")
    else:
        print(
            f"Role={decision['role']} Decision={decision['decision']} "
            f"CLI={decision['cli'] or 'none'} Model={decision['model'] or 'none'}"
        )
        print(f"Reason: {decision['reason']}")
        if decision.get("prompt"):
            print("")
            print(decision["prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
