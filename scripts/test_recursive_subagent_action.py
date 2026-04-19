#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "recursive-subagent-action.py"


class RecursiveSubagentActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="recursive-subagent-action-test-"))
        self.repo_root = self.temp_dir / "repo"
        (self.repo_root / ".recursive" / "run" / "run-123").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_action_record_includes_router_metadata_fields(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--repo-root",
                str(self.repo_root),
                "--run-id",
                "run-123",
                "--subagent-id",
                "code-reviewer",
                "--phase",
                "Phase 3.5",
                "--purpose",
                "Delegated code review",
                "--execution-mode",
                "review",
                "--router-used",
                "recursive-router",
                "--routed-role",
                "code-reviewer",
                "--routed-cli",
                "codex",
                "--routed-model",
                "gpt-5",
                "--routing-config-path",
                ".recursive/config/recursive-router.json",
                "--routing-discovery-path",
                ".recursive/config/recursive-router-discovered.json",
                "--routing-resolution-basis",
                "role_routes.code-reviewer",
                "--cli-probe-summary",
                "codex available",
                "--prompt-bundle-path",
                ".recursive/run/run-123/evidence/review-bundles/prompt.txt",
                "--invocation-exit-code",
                "0",
                "--output-capture-path",
                ".recursive/run/run-123/evidence/logs/code-reviewer.txt",
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

        action_records = list((self.repo_root / ".recursive" / "run" / "run-123" / "subagents").glob("*.md"))
        self.assertEqual(len(action_records), 1)
        content = action_records[0].read_text(encoding="utf-8")
        self.assertIn("- Router Used: `recursive-router`", content)
        self.assertIn("- Routed Role: `code-reviewer`", content)
        self.assertIn("- Routed CLI: `codex`", content)
        self.assertIn("- Routed Model: `gpt-5`", content)
        self.assertIn("- Routing Config Path: `/.recursive/config/recursive-router.json`", content)
        self.assertIn("- Prompt Bundle Path: `/.recursive/run/run-123/evidence/review-bundles/prompt.txt`", content)
        self.assertIn("- Invocation Exit Code: `0`", content)
        self.assertIn("- `/.recursive/run/run-123/evidence/logs/code-reviewer.txt`", content)


if __name__ == "__main__":
    unittest.main()
