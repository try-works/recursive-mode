#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from recursive_router_lib import RouterConfigError, invoke_route_binding, normalize_repo_path, pretty_json, write_json


def _normalize_prompt_path(repo_root: Path, prompt_path: Path) -> str:
    try:
        return normalize_repo_path(str(prompt_path.relative_to(repo_root)))
    except ValueError:
        return str(prompt_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke a recursive-router role with a real prompt bundle or inline prompt.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--role", required=True, help="Stage-aligned routed role to invoke. Legacy aliases are accepted.")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt-file", help="Path to a prompt bundle file to dispatch.")
    prompt_group.add_argument("--prompt", help="Inline prompt text to dispatch.")
    parser.add_argument("--output-file", help="Optional file path to write the routed model output text.")
    parser.add_argument("--metadata-file", help="Optional file path to write the full invocation payload JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--no-write", action="store_true", help="Do not refresh the discovery inventory file.")
    parser.add_argument("--timeout-ms", type=int, default=None, help="Override probe and invocation timeout in milliseconds.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        prompt_bundle_path = ""
        if args.prompt_file:
            prompt_path = Path(args.prompt_file).resolve()
            prompt_text = prompt_path.read_text(encoding="utf-8")
            prompt_bundle_path = _normalize_prompt_path(repo_root, prompt_path)
            prompt_source = "file"
        else:
            prompt_text = args.prompt
            prompt_source = "inline"

        payload = invoke_route_binding(
            repo_root,
            role=args.role,
            prompt=prompt_text,
            timeout_ms=args.timeout_ms,
            write_discovery=not args.no_write,
        )
        payload["prompt_source"] = prompt_source
        payload["prompt_bundle_path"] = prompt_bundle_path
    except (OSError, RouterConfigError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.output_file and payload["output_text"]:
        output_path = Path(args.output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(payload["output_text"]).rstrip() + "\n", encoding="utf-8", newline="\n")
    if args.metadata_file:
        metadata_path = Path(args.metadata_file).resolve()
        write_json(metadata_path, payload)

    if args.json:
        print(pretty_json(payload), end="")
    else:
        print(
            f"Role={payload['role']} Decision={payload['decision']['decision']} "
            f"CLI={payload['cli'] or 'none'} Model={payload['model'] or 'none'} "
            f"Success={'yes' if payload['success'] else 'no'}"
        )
        print(f"Reason: {payload['reason']}")
        if payload["output_text"]:
            print("")
            print(payload["output_text"])
        elif payload["decision"].get("prompt"):
            print("")
            print(payload["decision"]["prompt"])

    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
