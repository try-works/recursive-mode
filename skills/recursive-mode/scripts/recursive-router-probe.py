#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from recursive_router_lib import RouterConfigError, ensure_router_scaffold, pretty_json, probe_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe available routers for recursive-router.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--no-write", action="store_true", help="Do not refresh the discovery inventory file.")
    parser.add_argument("--timeout-ms", type=int, default=None, help="Override probe timeout in milliseconds.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        ensure_router_scaffold(repo_root)
        inventory = probe_inventory(
            repo_root,
            timeout_ms=args.timeout_ms,
            probe_tool="recursive-router-probe",
            write_discovery=not args.no_write,
        )
    except RouterConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.json:
        print(pretty_json(inventory), end="")
    else:
        for entry in inventory["clis"]:
            status = "available" if entry["available"] else "unavailable"
            version = entry["version"] or "unknown version"
            models = ", ".join(entry["models"]) if entry["models"] else "(no models listed)"
            print(f"- {entry['id']}: {status}; version={version}; models={models}; source={entry['model_source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
