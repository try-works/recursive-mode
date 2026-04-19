#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "recursive-review-bundle.py"
PS_SCRIPT_PATH = REPO_ROOT / "scripts" / "recursive-review-bundle.ps1"


class RecursiveReviewBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="recursive-review-bundle-test-"))
        self.repo_root = self.temp_dir / "repo"
        self.run_root = self.repo_root / ".recursive" / "run" / "run-123"
        self.run_root.mkdir(parents=True, exist_ok=True)
        self._write(self.repo_root / "src" / "app.py", "print('baseline')\n")
        self._git("init")
        self._git("config", "user.name", "Review Bundle Tests")
        self._git("config", "user.email", "review-bundle-tests@example.com")
        self._git("branch", "-M", "main")
        self._git("add", "-A")
        self._git("commit", "-m", "baseline")
        baseline = self._git("rev-parse", "HEAD").stdout.strip()
        self._write(
            self.run_root / "00-worktree.md",
            "\n".join(
                [
                    "## Diff Basis For Later Audits",
                    "",
                    "- Baseline type: `commit`",
                    f"- Baseline reference: `{baseline}`",
                    "- Comparison reference: `working-tree`",
                    f"- Normalized baseline: `{baseline}`",
                    "- Normalized comparison: `working-tree`",
                    f"- Normalized diff command: `git diff --name-only {baseline}`",
                ]
            ),
        )
        self._write(self.run_root / "03.5-code-review.md", "# Code Review\n")
        self._write(self.repo_root / "src" / "app.py", "print('changed')\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo_root),
            text=True,
            capture_output=True,
            check=True,
        )

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")

    def test_review_bundle_includes_routing_metadata(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--repo-root",
                str(self.repo_root),
                "--run-id",
                "run-123",
                "--phase",
                "03.5 Code Review",
                "--role",
                "code-reviewer",
                "--artifact-path",
                ".recursive/run/run-123/03.5-code-review.md",
                "--routing-config-path",
                ".recursive/config/recursive-router.json",
                "--routing-discovery-path",
                ".recursive/config/recursive-router-discovered.json",
                "--routed-cli",
                "codex",
                "--routed-model",
                "gpt-5.4",
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        bundle_path = self.run_root / "evidence" / "review-bundles" / "03-5-code-review-code-reviewer.md"
        content = bundle_path.read_text(encoding="utf-8")
        self.assertIn("## Routing", content)
        self.assertIn("- Routed CLI: `codex`", content)
        self.assertIn("- Routed Model: `gpt-5.4`", content)
        self.assertIn("- Routing Config Path: `/.recursive/config/recursive-router.json`", content)
        self.assertIn("- Routing Discovery Path: `/.recursive/config/recursive-router-discovered.json`", content)

    def test_powershell_wrapper_forwards_routing_metadata(self) -> None:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            self.skipTest("PowerShell is required for wrapper parity tests")

        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-File",
                str(PS_SCRIPT_PATH),
                "-RepoRoot",
                str(self.repo_root),
                "-RunId",
                "run-123",
                "-Phase",
                "03.5 Code Review",
                "-Role",
                "code-reviewer",
                "-ArtifactPath",
                ".recursive/run/run-123/03.5-code-review.md",
                "-RoutingConfigPath",
                ".recursive/config/recursive-router.json",
                "-RoutingDiscoveryPath",
                ".recursive/config/recursive-router-discovered.json",
                "-RoutedCli",
                "codex",
                "-RoutedModel",
                "gpt-5.4",
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        bundle_path = self.run_root / "evidence" / "review-bundles" / "03-5-code-review-code-reviewer.md"
        content = bundle_path.read_text(encoding="utf-8")
        self.assertIn("- Routed CLI: `codex`", content)
        self.assertIn("- Routed Model: `gpt-5.4`", content)
        self.assertIn("- Routing Config Path: `/.recursive/config/recursive-router.json`", content)
        self.assertIn("- Routing Discovery Path: `/.recursive/config/recursive-router-discovered.json`", content)


if __name__ == "__main__":
    unittest.main()
