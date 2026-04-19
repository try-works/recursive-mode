#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("lint-recursive-run.py")
SPEC = importlib.util.spec_from_file_location("lint_recursive_run", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load lint module from {MODULE_PATH}")
lint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lint
SPEC.loader.exec_module(lint)


class LintRecursiveRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="lint-recursive-run-test-"))
        self.repo_root = self.temp_dir / "repo"
        self.run_id = "benchmark-test-run"
        self.run_dir = self.repo_root / ".recursive" / "run" / self.run_id
        self.worktree_root = self.repo_root / ".worktrees" / self.run_id

        self._write(self.repo_root / "src" / "lib.rs", "pub fn baseline() -> i32 { 0 }\n")
        self._git(self.repo_root, "init")
        self._git(self.repo_root, "config", "user.name", "Lint Tests")
        self._git(self.repo_root, "config", "user.email", "lint-tests@example.com")
        self._git(self.repo_root, "branch", "-M", "main")
        self._git(self.repo_root, "add", "-A")
        self._git(self.repo_root, "commit", "-m", "baseline")
        self.baseline_commit = self._git(self.repo_root, "rev-parse", "HEAD").stdout.strip()
        self._git(self.repo_root, "worktree", "add", str(self.worktree_root), "-b", f"recursive/{self.run_id}")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._write(
            self.run_dir / "00-worktree.md",
            "\n".join(
                [
                    "## Diff Basis For Later Audits",
                    "",
                    "- Baseline type: commit",
                    f"- Baseline reference: `{self.baseline_commit}`",
                    "- Comparison reference: working-tree",
                    f"- Normalized baseline: `{self.baseline_commit}`",
                    "- Normalized comparison: working-tree",
                    f"- Normalized diff command: `git diff --name-only {self.baseline_commit}`",
                    "",
                    "## Worktree Details",
                    "",
                    f"- Location: `.worktrees/{self.run_id}`",
                    f"- Product root: `.worktrees/{self.run_id}`",
                ]
            ),
        )

    def tearDown(self) -> None:
        subprocess.run(["git", "-C", str(self.repo_root), "worktree", "remove", "--force", str(self.worktree_root)], check=False)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=True,
        )

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    def test_filter_runtime_changed_files_ignores_playwright_runtime_dirs(self) -> None:
        filtered = lint.filter_runtime_changed_files(
            [
                ".playwright-mcp/page.yml",
                ".target/debug/app.js",
                ".cargo-target-dir/debug/output.txt",
                ".recursive/run/benchmark-test-run/03-implementation-summary.md",
                ".worktrees/benchmark-test-run/src/lib.rs",
            ],
            self.run_id,
        )

        self.assertEqual([".worktrees/benchmark-test-run/src/lib.rs"], filtered)

    def test_requirements_artifact_no_longer_requires_assumptions_section(self) -> None:
        sections = lint.get_artifact_required_sections("00-requirements.md", "recursive-mode-audit-v2")

        self.assertNotIn("Assumptions", sections)
        self.assertEqual(
            ["TODO", "Requirements", "Out of Scope", "Constraints", "Coverage Gate", "Approval Gate"],
            sections,
        )

if __name__ == "__main__":
    unittest.main()
