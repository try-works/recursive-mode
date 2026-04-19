#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from recursive_router_lib import RouterConfigError, canonicalize_router_role, configure_verified_routes, pretty_json


def parse_assignment(raw: str) -> tuple[str, str, str]:
    if "=" not in raw:
        raise RouterConfigError(f"Invalid --set value {raw!r}. Expected role=cli:model.")
    role, target = raw.split("=", 1)
    role = canonicalize_router_role(role.strip())
    if ":" not in target:
        raise RouterConfigError(f"Invalid --set value {raw!r}. Expected role=cli:model.")
    cli_id, model = target.split(":", 1)
    cli_id = cli_id.strip()
    model = model.strip()
    if not cli_id:
        raise RouterConfigError(f"Invalid --set value {raw!r}. CLI id must be non-empty.")
    if not model:
        raise RouterConfigError(f"Invalid --set value {raw!r}. Model must be non-empty.")
    return role, cli_id, model


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify recursive-router bindings before saving them.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument(
        "--set",
        dest="assignments",
        action="append",
        required=True,
        help="Role binding in role=cli:model form. Repeatable. Prefer stage-aligned roles; legacy aliases are accepted.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=50000,
        help="Verification timeout in milliseconds. Defaults to 50000.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        assignments: dict[str, dict[str, str]] = {}
        for raw_assignment in args.assignments:
            role, cli_id, model = parse_assignment(raw_assignment)
            if role in assignments:
                raise RouterConfigError(f"Duplicate role assignment provided for {role}.")
            assignments[role] = {"cli": cli_id, "model": model}

        payload = configure_verified_routes(repo_root, assignments=assignments, timeout_ms=args.timeout_ms)
    except RouterConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.json:
        print(pretty_json(payload), end="")
    else:
        print(f"Saved={'yes' if payload['saved'] else 'no'} Policy={payload['policy_path']}")
        for role, result in payload["verification_results"].items():
            print(
                f"{role}: verified={'yes' if result['verified'] else 'no'} "
                f"cli={result['cli']} model={result['model']} transport={result['transport']}"
            )
            print(f"  reason: {result['reason']}")
    return 0 if payload["saved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
