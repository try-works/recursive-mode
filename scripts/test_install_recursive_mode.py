#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("install-recursive-mode.py")
SPEC = importlib.util.spec_from_file_location("install_recursive_mode", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load install module from {MODULE_PATH}")
install = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = install
SPEC.loader.exec_module(install)


class InstallRecursiveModeTests(unittest.TestCase):
    def test_normalize_plain_or_wrapped_content_prefers_plain_prefix(self) -> None:
        start = "<!-- START -->"
        end = "<!-- END -->"
        plain = "alpha\nbeta"
        malformed = f"{plain}\n\n{start}\nwrapped body\n{end}\n"

        self.assertEqual(plain, install.normalize_plain_or_wrapped_content(malformed, start, end))

    def test_recursive_agents_router_treats_benchmark_as_opt_in(self) -> None:
        body = install.recursive_agents_router_body()

        self.assertIn("separate optional `recursive-benchmark` add-on", body)
        self.assertIn("<recursive-benchmark-package-or-repo>", body)
        self.assertNotIn("/skills/recursive-benchmark/SKILL.md", body)
        self.assertNotIn("/references/benchmarks/local-first-planner/README.md", body)
        self.assertNotIn("/scripts/run-recursive-benchmark.py", body)

    def test_plans_bridge_treats_benchmark_as_opt_in(self) -> None:
        body = install.plans_bridge_body()

        self.assertIn("separate optional `recursive-benchmark` add-on", body)
        self.assertIn("<recursive-benchmark-package-or-repo>", body)
        self.assertNotIn("should use the packaged benchmark fixture", body)

    def test_gitattributes_excludes_benchmark_add_on_from_default_exports(self) -> None:
        gitattributes = Path(__file__).resolve().parent.parent / ".gitattributes"
        content = gitattributes.read_text(encoding="utf-8")

        self.assertIn("skills/recursive-benchmark export-ignore", content)
        self.assertIn("references/benchmarks export-ignore", content)
        self.assertIn("scripts/run-recursive-benchmark.py export-ignore", content)

    def test_current_workflow_docs_default_to_v2(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        expectations = {
            Path(".recursive/STATE.md"): (
                "The workflow profile in active use is `recursive-mode-audit-v2`.",
            ),
            Path(".recursive/RECURSIVE.md"): (
                "New runs should also include `Workflow version: recursive-mode-audit-v2`.",
                "add `Workflow version: recursive-mode-audit-v2` to `00-requirements.md`",
            ),
            Path("references/bootstrap/RECURSIVE.md"): (
                "New runs should also include `Workflow version: recursive-mode-audit-v2`.",
                "add `Workflow version: recursive-mode-audit-v2` to `00-requirements.md`",
            ),
            Path("docs/templates/commands/recursive-init.md"): (
                "Marks the run as `recursive-mode-audit-v2`",
            ),
            Path("docs/templates/commands/recursive-status.md"): (
                "Workflow Profile: recursive-mode-audit-v2",
            ),
            Path("references/artifact-template.md"): (
                "Use this block in every audited phase for `recursive-mode-audit-v1` and `recursive-mode-audit-v2`:",
                "Workflow version: `recursive-mode-audit-v2`",
            ),
            Path("references/fixtures/tiny-tasks-smoke-recipe.md"): (
                "- Workflow profile: `recursive-mode-audit-v2`",
            ),
        }

        for relative_path, required_snippets in expectations.items():
            content = (repo_root / relative_path).read_text(encoding="utf-8")
            for snippet in required_snippets:
                with self.subTest(path=str(relative_path), snippet=snippet):
                    self.assertIn(snippet, content)


if __name__ == "__main__":
    unittest.main()
