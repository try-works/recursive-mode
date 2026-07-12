#!/usr/bin/env python3
"""
Companion extractor for recursive-training prompt evaluation.

The training scripts build extraction prompts and hand them to this script.
The default extractor skips cleanly when no extractor implementation is wired.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Companion extractor for recursive-training")
    parser.add_argument("--repo-root", required=True, help="Repository root path")
    parser.add_argument("--prompt-file", required=True, help="Path to the prompt file to evaluate")
    args = parser.parse_args()

    prompt_path = Path(args.prompt_file).resolve()
    if not prompt_path.exists():
        print("ERROR: Prompt file not found for recursive-training extraction.", file=sys.stderr)
        return 1

    print(
        "Training extractor is not available for recursive-training in this environment.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
