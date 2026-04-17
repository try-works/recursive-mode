#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run-recursive-benchmark.py")
SPEC = importlib.util.spec_from_file_location("run_recursive_benchmark", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load benchmark harness module from {MODULE_PATH}")
rrb = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rrb
SPEC.loader.exec_module(rrb)


class RecursiveBenchmarkIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required for benchmark integrity tests")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="recursive-benchmark-test-"))
        self.workspace_root = self.temp_dir / "workspace"
        args = argparse.Namespace(
            scenario="scientific-calculator-rust",
            runner="codex",
            workspace_root=str(self.workspace_root),
            copilot_model="gpt-5.4",
            codex_model="gpt-5.1",
            kimi_model="kimi-k2.6",
            max_minutes=5,
            command_timeout=120,
            preview_timeout=30,
            npm_command="npm",
            arm_mode="sequential",
            hint_penalty=5.0,
            prepare_only=False,
            skip_npm_install=True,
            list_scenarios=False,
        )
        self.harness = rrb.BenchmarkHarness(args)
        self.repo_root = self.temp_dir / "repo"
        self.run_id = "benchmark-test-run"
        self.worktree_root = self.repo_root / ".worktrees" / self.run_id
        self._create_repo_with_worktree()

    def tearDown(self) -> None:
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
        path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")

    def _create_repo_with_worktree(self) -> None:
        self._write(self.repo_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"starter\" }\n")
        self._write(
            self.repo_root / "src" / "calculator.rs",
            "pub fn starter_expression() -> &'static str { \"sin(45) + 2^3\" }\n",
        )
        self._write(self.repo_root / "Cargo.toml", "[package]\nname = \"benchmark\"\nversion = \"0.1.0\"\n")
        self._write(self.repo_root / "Cargo.lock", "version = 3\n")
        self._write(self.repo_root / ".gitignore", ".worktrees/\n.playwright-mcp/\n.cargo-target-dir/\n")
        self._write(self.repo_root / "styles.css", ".app-shell { display: grid; }\n")
        self._write(self.repo_root / "benchmark" / "agent-log.md", "# Benchmark agent log\n")
        self._git(self.repo_root, "init")
        self._git(self.repo_root, "config", "user.name", "Benchmark Tests")
        self._git(self.repo_root, "config", "user.email", "benchmark-tests@example.com")
        self._git(self.repo_root, "branch", "-M", "main")
        self._git(self.repo_root, "add", "-A")
        self._git(self.repo_root, "commit", "-m", "starter")
        self._git(self.repo_root, "worktree", "add", str(self.worktree_root), "-b", f"recursive/{self.run_id}")
        self._write_run_artifacts(["src/app.rs"])

    def _write_run_artifacts(self, claimed_files: list[str]) -> None:
        run_root = self.repo_root / ".recursive" / "run" / self.run_id
        baseline_ref = self._git(self.repo_root, "rev-parse", "HEAD").stdout.strip()
        claimed_block = "\n".join(f"- `{path}`" for path in claimed_files)
        changed_files_line = ", ".join(f"`{path}`" for path in claimed_files)
        self._write(
            run_root / "00-worktree.md",
            "\n".join(
                [
                    "## Diff Basis",
                    "",
                    "- Baseline type: `commit`",
                    f"- Baseline reference: `{baseline_ref}`",
                    "- Comparison reference: `working-tree`",
                    f"- Normalized baseline: `{baseline_ref}`",
                    "- Normalized comparison: `working-tree`",
                    f"- Normalized diff command: `git diff --name-only {baseline_ref}`",
                ]
            ),
        )
        self._write(
            run_root / "02-to-be-plan.md",
            "\n".join(
                [
                    "## Requirement Completion Status",
                    "",
                    f"- R1 | Status: planned | Changed Files: {changed_files_line}",
                    "",
                    "## Files Changed",
                    "",
                    claimed_block,
                ]
            ),
        )
        self._write(
            run_root / "03-implementation-summary.md",
            "\n".join(
                [
                    "## Files Changed",
                    "",
                    claimed_block,
                    "",
                    "## Requirement Completion Status",
                    "",
                    f"- R1 | Status: implemented | Changed Files: {changed_files_line}",
                ]
            ),
        )

    def _make_result(self) -> rrb.ArmResult:
        return rrb.ArmResult(
            runner_slug="codex",
            runner_name="Codex CLI",
            provider_family="codex",
            model="gpt-5.1",
            arm_name="recursive-on",
            run_id=self.run_id,
            expected_product_root=f".worktrees/{self.run_id}",
            recursive_isolation_status="isolated-worktree",
        )

    def test_seeded_run_requirements_are_locked_recursive_artifact(self) -> None:
        content = self.harness.render_seeded_run_requirements(self.run_id)

        self.assertIn(f"Run: `/.recursive/run/{self.run_id}/`", content)
        self.assertIn("Phase: `00 Requirements`", content)
        self.assertIn("Status: `LOCKED`", content)
        self.assertIn("Workflow version: `recursive-mode-audit-v2`", content)
        self.assertIn("## TODO", content)
        self.assertIn("## Requirements", content)
        self.assertIn("## Out of Scope", content)
        self.assertIn("## Constraints", content)
        self.assertIn("## Assumptions", content)
        self.assertIn("Coverage: PASS", content)
        self.assertIn("Approval: PASS", content)
        self.assertRegex(content, r"LockHash: `[0-9a-f]{64}`")
        self.assertIn("### `R7` Quality gates", content)

    def test_seeded_recursive_templates_include_phase2_and_repo_root_relative_worktree_examples(self) -> None:
        templates = self.harness.render_recursive_template_files(
            self.run_id,
            f".worktrees/{self.run_id}",
            "a" * 40,
        )

        self.assertIn("00-worktree.md", templates)
        self.assertIn("02-to-be-plan.md", templates)
        self.assertIn("03-implementation-summary.md", templates)
        self.assertIn("benchmark/recursive-templates/", templates["00-worktree.md"])
        self.assertIn("Implementation Surface:", templates["02-to-be-plan.md"])
        self.assertIn("Verification Surface:", templates["02-to-be-plan.md"])
        self.assertIn("QA Surface:", templates["02-to-be-plan.md"])
        self.assertIn(f".worktrees/{self.run_id}/src/main.rs", templates["02-to-be-plan.md"])
        self.assertIn("Audit: FAIL", templates["03-implementation-summary.md"])
        self.assertIn("TDD Compliance: FAIL", templates["03-implementation-summary.md"])
        self.assertIn(f".recursive/run/{self.run_id}/evidence/screenshots/replace-me.png", templates["02-to-be-plan.md"])
        self.assertIn("None because", templates["01-as-is.md"])
        self.assertIn("Keep `Gaps Found` limited to real audit defects", templates["01-as-is.md"])
        self.assertIn("Prefer file-only screenshot capture", templates["04-test-summary.md"])
        self.assertIn(f"`{'a' * 40}`", templates["00-worktree.md"])

    def test_seed_recursive_templates_creates_run_evidence_directories(self) -> None:
        template_root = self.repo_root / "benchmark" / "recursive-templates"

        self.harness.seed_recursive_run_templates(
            template_root,
            self.run_id,
            f".worktrees/{self.run_id}",
            "b" * 40,
        )

        evidence_root = self.repo_root / ".recursive" / "run" / self.run_id / "evidence"
        self.assertTrue((evidence_root / "logs" / "baseline").is_dir())
        self.assertTrue((evidence_root / "logs" / "green").is_dir())
        self.assertTrue((evidence_root / "manual").is_dir())
        self.assertTrue((evidence_root / "screenshots").is_dir())

    def test_recursive_on_prompt_only_references_existing_control_plane_files(self) -> None:
        prepared_repo = self.temp_dir / "prepared-repo"
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        result = rrb.ArmResult(
            runner_slug="codex",
            runner_name="Codex CLI",
            provider_family="codex",
            model="gpt-5.1",
            arm_name="recursive-on",
        )
        runner = self.harness.runner_configs[0]

        self.harness.prepare_repo(prepared_repo, logs_root, runner, result, recursive_on=True)
        prompt_text, _ = self.harness.render_prompt(self.workspace_root / "prompts", result)

        read_block = re.search(r"(?ms)^Read:\s*$\n(.*?)(?=^\s*$|^Rules:\s*$)", prompt_text)
        self.assertIsNotNone(read_block)
        prompt_paths = [
            line.strip()[2:].strip().strip("`")
            for line in read_block.group(1).splitlines()
            if line.strip().startswith("- ")
        ]

        missing_paths = [path for path in prompt_paths if not (prepared_repo / Path(path)).exists()]
        self.assertEqual([], missing_paths, f"Prompt referenced missing files: {missing_paths}")

    def test_recursive_on_prompt_calls_out_lint_critical_headings_and_closeout_receipts(self) -> None:
        prompt_text, _ = self.harness.render_prompt(self.workspace_root / "prompts", self._make_result())
        prompt_text_lower = prompt_text.lower()

        self.assertIn("remove the template `## todo` section entirely", prompt_text_lower)
        self.assertIn("`## Changes Applied`", prompt_text)
        self.assertIn(
            "`05-manual-qa.md`, `06-decisions-update.md`, `07-state-update.md`, and `08-memory-impact.md`",
            prompt_text,
        )
        self.assertIn("distinct from the Phase 3 implementation evidence", prompt_text)
        self.assertIn("bootstrapped control-plane files under the worktree", prompt_text)
        self.assertIn("`Compensating validation:` field", prompt_text)

    def test_maybe_repair_recursive_run_prompts_for_missing_artifacts_and_none_gaps(self) -> None:
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        self._write(
            logs_root / "recursive-lint.log",
            "\n".join(
                [
                    "Linting run: benchmark-test-run",
                    "[FAIL] 01-as-is.md: Audit: PASS is invalid while Gaps Found still lists unresolved in-scope gaps",
                    "[WARN] Missing artifact (ok if not reached yet): .recursive/run/benchmark-test-run/03-implementation-summary.md",
                    "[WARN] Missing artifact (ok if not reached yet): .recursive/run/benchmark-test-run/05-manual-qa.md",
                    "## Gaps Found",
                    "- No gaps",
                ]
            ),
        )
        result = self._make_result()
        result.recursive_workflow_status = "incomplete"
        result.recursive_artifact_status = {
            "00-requirements.md": True,
            "00-worktree.md": True,
            "01-as-is.md": True,
            "02-to-be-plan.md": True,
            "03-implementation-summary.md": False,
            "04-test-summary.md": False,
            "05-manual-qa.md": False,
            "06-decisions-update.md": False,
            "07-state-update.md": False,
            "08-memory-impact.md": False,
        }
        captured: dict[str, object] = {}

        def fake_run_model_prompt(
            repo_root: Path,
            logs_root_arg: Path,
            *,
            runner_slug: str,
            executable: str | None,
            model: str,
            prompt_text: str,
            log_stem: str,
            timeout_seconds: int,
        ) -> tuple[rrb.CommandResult, Path, Path]:
            captured["prompt"] = prompt_text
            captured["log_stem"] = log_stem
            stdout_log = logs_root_arg / f"{log_stem}-output.jsonl"
            stderr_log = logs_root_arg / f"{log_stem}-stderr.log"
            stdout_log.write_text("", encoding="utf-8")
            stderr_log.write_text("", encoding="utf-8")
            return (
                rrb.CommandResult(command=["repair"], returncode=0, stdout="", stderr="", duration_seconds=1.0),
                stdout_log,
                stderr_log,
            )

        def fake_evaluate_recursive_run(repo_root: Path, logs_root_arg: Path, result_arg: rrb.ArmResult) -> None:
            captured["reevaluated"] = True
            result_arg.recursive_workflow_status = "complete"

        self.harness.run_model_prompt = fake_run_model_prompt  # type: ignore[method-assign]
        self.harness.evaluate_recursive_run = fake_evaluate_recursive_run  # type: ignore[method-assign]

        repair_record = self.harness.maybe_repair_recursive_run(
            self.repo_root,
            logs_root,
            self.harness.runner_configs[0],
            result,
        )

        self.assertIsNotNone(repair_record)
        prompt_text = captured["prompt"]
        self.assertIn("03-implementation-summary.md", prompt_text)
        self.assertIn("05-manual-qa.md", prompt_text)
        self.assertIn("Use the exact word `None`", prompt_text)
        self.assertIn("No gaps", prompt_text)
        self.assertIn("`Compensating validation:` field", prompt_text)
        self.assertTrue(captured["reevaluated"])
        self.assertEqual("complete", result.recursive_workflow_status)
        self.assertIn("recursive_repair_stdout", result.log_paths)
        self.assertIn("recursive_repair_stderr", result.log_paths)
        self.assertEqual("recursive-repair", captured["log_stem"])

    def test_recursive_repair_prompt_requires_changed_files_to_match_current_diff(self) -> None:
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        self._write(
            logs_root / "recursive-lint.log",
            "\n".join(
                [
                    "Linting run: benchmark-test-run",
                    "[FAIL] 03-implementation-summary.md: Requirement R7 Changed Files are outside the current diff scope: .recursive/DECISIONS.md, .recursive/STATE.md, .worktrees/benchmark-test-run/.codex/AGENTS.md",
                ]
            ),
        )
        result = self._make_result()
        result.recursive_workflow_status = "lint-failed"
        result.recursive_artifact_status = {name: True for name in rrb.REQUIRED_RECURSIVE_RUN_FILES}

        prompt_text = self.harness.build_recursive_repair_prompt(self.repo_root, logs_root, result)

        self.assertIn("Only list files in `Changed Files`", prompt_text)
        self.assertIn("actually present in the current `git diff --name-only` output", prompt_text)
        self.assertIn("Remove unchanged bootstrap or control-plane files", prompt_text)

    def test_reconcile_recursive_requirement_changed_files_trims_out_of_diff_paths(self) -> None:
        self._write(self.worktree_root / "src" / "main.rs", "fn main() {}\n")
        run_root = self.repo_root / ".recursive" / "run" / self.run_id
        artifact_body = "\n".join(
            [
                "## Requirement Completion Status",
                "",
                f"- R7 | Status: verified | Changed Files: `.worktrees/{self.run_id}/src/main.rs`, `.recursive/DECISIONS.md`, `.worktrees/{self.run_id}/.codex/AGENTS.md` | Verification Evidence: `.recursive/run/{self.run_id}/evidence/logs/green/r7.log`",
            ]
        )
        for artifact_name in (
            "03-implementation-summary.md",
            "04-test-summary.md",
            "06-decisions-update.md",
            "07-state-update.md",
            "08-memory-impact.md",
        ):
            self._write(run_root / artifact_name, artifact_body)

        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        result = self._make_result()
        self.harness.prepare_recursive_lint_root(self.repo_root, self.worktree_root, logs_root, result)
        self._write(
            logs_root / "recursive-lint.log",
            "\n".join(
                [
                    "Linting run: benchmark-test-run",
                    "[FAIL] 03-implementation-summary.md: Requirement R7 Changed Files are outside the current diff scope: .recursive/DECISIONS.md, .worktrees/benchmark-test-run/.codex/AGENTS.md",
                ]
            ),
        )
        result.recursive_workflow_status = "lint-failed"

        changed = self.harness.reconcile_recursive_requirement_changed_files(self.repo_root, logs_root, result)

        self.assertTrue(changed)
        updated = (run_root / "08-memory-impact.md").read_text(encoding="utf-8")
        self.assertIn(f"`.worktrees/{self.run_id}/src/main.rs`", updated)
        self.assertNotIn("`.recursive/DECISIONS.md`", updated)
        self.assertNotIn(f"`.worktrees/{self.run_id}/.codex/AGENTS.md`", updated)

    def test_optional_missing_artifact_warnings_are_tolerated_for_recursive_lint(self) -> None:
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        self._write(
            logs_root / "recursive-lint.log",
            "\n".join(
                [
                    "Linting run: benchmark-test-run",
                    "[WARN] Missing artifact (ok if not reached yet): D:/repo/.recursive/run/benchmark-test-run/01.5-root-cause.md",
                    "[WARN] Missing artifact (ok if not reached yet): D:/repo/.recursive/run/benchmark-test-run/03.5-code-review.md",
                    "[FAIL] Lint failed",
                ]
            ),
        )

        tolerated = self.harness.lint_has_only_optional_missing_artifact_warnings(logs_root / "recursive-lint.log")

        self.assertTrue(tolerated)

    def test_reconcile_pragmatic_tdd_exception_adds_compensating_validation_field(self) -> None:
        run_root = self.repo_root / ".recursive" / "run" / self.run_id
        self._write(
            run_root / "03-implementation-summary.md",
            "\n".join(
                [
                    "## TDD Compliance Log",
                    "",
                    "- TDD Mode: pragmatic",
                    "TDD Compliance: PASS",
                    "",
                    "## Pragmatic TDD Exception",
                    "",
                    "- Exception reason: Blank starter",
                    "",
                    "### Compensating validation",
                    "",
                    f"- `.recursive/run/{self.run_id}/evidence/logs/green/sp1.log`",
                ]
            ),
        )
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        self._write(
            logs_root / "recursive-lint.log",
            "\n".join(
                [
                    "Linting run: benchmark-test-run",
                    "[FAIL] 03-implementation-summary.md: Pragmatic TDD Exception is missing Compensating validation",
                ]
            ),
        )
        result = self._make_result()
        result.recursive_workflow_status = "lint-failed"

        changed = self.harness.reconcile_pragmatic_tdd_exception_field(self.repo_root, logs_root, result)

        self.assertTrue(changed)
        updated = (run_root / "03-implementation-summary.md").read_text(encoding="utf-8")
        self.assertIn("- Compensating validation: See evidence paths listed below.", updated)
        self.assertIn("### Compensating validation", updated)

    def test_evaluate_recursive_run_clears_stale_lint_and_missing_artifact_issues(self) -> None:
        run_root = self.repo_root / ".recursive" / "run" / self.run_id
        self._write(run_root / "00-requirements.md", self.harness.render_seeded_run_requirements(self.run_id))
        self._write(
            run_root / "00-worktree.md",
            "\n".join(
                [
                    "## Directory Selection",
                    "",
                    "- Selected worktree location: `.`",
                    "- Product root: `.`",
                    "",
                    "## Diff Basis For Later Audits",
                    "",
                    f"- Baseline reference: `{self._git(self.repo_root, 'rev-parse', 'HEAD').stdout.strip()}`",
                ]
            ),
        )
        self._write(run_root / "01-as-is.md", "## Source Requirement Inventory\n")
        self._write(
            run_root / "02-to-be-plan.md",
            "\n".join(
                [
                    "## Requirement Mapping",
                    "",
                    "## Plan Drift Check",
                    "",
                    "## Requirement Completion Status",
                ]
            ),
        )
        for artifact_name in ("03-implementation-summary.md", "04-test-summary.md", "05-manual-qa.md", "06-decisions-update.md", "07-state-update.md", "08-memory-impact.md"):
            self._write(run_root / artifact_name, f"# {artifact_name}\n")

        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        result = self._make_result()
        result.expected_product_root = ""
        result.issues = [
            "Recursive run artifacts failed controller-side lint.",
            "Recursive workflow artifacts missing: 05-manual-qa.md, 06-decisions-update.md.",
            "Unrelated issue should remain.",
        ]

        def fake_run_command(*args, **kwargs) -> rrb.CommandResult:
            return rrb.CommandResult(
                command=["lint"],
                returncode=1,
                stdout="\n".join(
                    [
                        f"Linting run: {self.run_id}",
                        f"[WARN] Missing artifact (ok if not reached yet): D:/repo/.recursive/run/{self.run_id}/01.5-root-cause.md",
                        f"[WARN] Missing artifact (ok if not reached yet): D:/repo/.recursive/run/{self.run_id}/03.5-code-review.md",
                        "[FAIL] Lint failed",
                    ]
                ),
                stderr="",
                duration_seconds=0.5,
            )

        self.harness.run_command = fake_run_command  # type: ignore[method-assign]

        self.harness.evaluate_recursive_run(self.repo_root, logs_root, result)

        self.assertEqual("complete", result.recursive_workflow_status)
        self.assertNotIn("Recursive run artifacts failed controller-side lint.", result.issues)
        self.assertFalse(any(issue.startswith("Recursive workflow artifacts missing:") for issue in result.issues))
        self.assertIn("Unrelated issue should remain.", result.issues)

    def test_finalize_result_treats_kimi_image_capability_tail_as_benign(self) -> None:
        result = self._make_result()
        result.build_success = True
        result.test_success = True
        result.preview_success = True
        result.recursive_delivery_status = "ok"
        result.recursive_workflow_status = "complete"
        result.agent_status = "non-zero-exit"
        kimi_runner = rrb.RunnerConfig(
            slug="kimi",
            display_name="Kimi CLI",
            provider_family="moonshot-kimi",
            executable="kimi",
            model="kimi-k2.6",
            supports_json=False,
        )
        agent_record = rrb.CommandResult(
            command=["kimi"],
            returncode=1,
            stdout="LLM model 'kimi-k2.6' does not support required capability: image_in.",
            stderr="",
            duration_seconds=1.0,
        )

        self.harness.finalize_result(kimi_runner, agent_record, result)

        self.assertEqual("pass", result.status)
        self.assertNotIn("Agent execution exited non-zero after producing a passing artifact set.", result.issues)

    def test_maybe_repair_recursive_run_retries_once_when_first_repair_still_incomplete(self) -> None:
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        logs_root.mkdir(parents=True, exist_ok=True)
        result = self._make_result()
        result.recursive_workflow_status = "incomplete"
        result.recursive_artifact_status = {
            "00-requirements.md": True,
            "00-worktree.md": True,
            "01-as-is.md": True,
            "02-to-be-plan.md": True,
            "03-implementation-summary.md": False,
            "04-test-summary.md": False,
            "05-manual-qa.md": False,
            "06-decisions-update.md": False,
            "07-state-update.md": False,
            "08-memory-impact.md": False,
        }
        log_stems: list[str] = []
        evaluation_count = 0

        def fake_run_model_prompt(
            repo_root: Path,
            logs_root_arg: Path,
            *,
            runner_slug: str,
            executable: str | None,
            model: str,
            prompt_text: str,
            log_stem: str,
            timeout_seconds: int,
        ) -> tuple[rrb.CommandResult, Path, Path]:
            log_stems.append(log_stem)
            stdout_log = logs_root_arg / f"{log_stem}-output.jsonl"
            stderr_log = logs_root_arg / f"{log_stem}-stderr.log"
            stdout_log.write_text("", encoding="utf-8")
            stderr_log.write_text("", encoding="utf-8")
            return (
                rrb.CommandResult(command=[log_stem], returncode=0, stdout="", stderr="", duration_seconds=1.0),
                stdout_log,
                stderr_log,
            )

        def fake_evaluate_recursive_run(repo_root: Path, logs_root_arg: Path, result_arg: rrb.ArmResult) -> None:
            nonlocal evaluation_count
            evaluation_count += 1
            if evaluation_count == 1:
                result_arg.recursive_workflow_status = "incomplete"
                result_arg.recursive_artifact_status["08-memory-impact.md"] = False
            else:
                result_arg.recursive_workflow_status = "complete"
                for file_name in list(result_arg.recursive_artifact_status):
                    result_arg.recursive_artifact_status[file_name] = True

        self.harness.run_model_prompt = fake_run_model_prompt  # type: ignore[method-assign]
        self.harness.evaluate_recursive_run = fake_evaluate_recursive_run  # type: ignore[method-assign]

        repair_record = self.harness.maybe_repair_recursive_run(
            self.repo_root,
            logs_root,
            self.harness.runner_configs[0],
            result,
        )

        self.assertIsNotNone(repair_record)
        self.assertEqual(["recursive-repair", "recursive-repair-2"], log_stems)
        self.assertEqual(2, evaluation_count)
        self.assertEqual("complete", result.recursive_workflow_status)

    def test_judge_brief_marks_worktree_agent_log_as_authoritative(self) -> None:
        result = self._make_result()
        result.recursive_workflow_status = "lint-failed"
        result.recursive_delivery_status = "ok"
        result.recursive_artifact_status = {"00-worktree.md": True}
        result.score_breakdown = {"responsive_ui": 5.0, "dual_display_editing": 10.0}
        result.score_breakdown_max = {"responsive_ui": 5.0, "dual_display_editing": 10.0}
        brief_path = self.harness.write_judge_brief(self.repo_root, self.worktree_root, result)

        brief = brief_path.read_text(encoding="utf-8")
        self.assertIn(f"- Authoritative benchmark progress log: .worktrees/{self.run_id}/benchmark/agent-log.md", brief)
        self.assertIn("repo-root `benchmark/agent-log.md` may contain controller metadata only", brief)
        self.assertIn('"entry_adjustments"', brief)
        self.assertIn("- responsive_ui: 5/5", brief)
        self.assertIn("- dual_display_editing: 10/10", brief)

    def test_load_judge_metric_applies_structured_entry_adjustments(self) -> None:
        result = self._make_result()
        result.score_breakdown = {
            "dual_display_editing": 10.0,
            "responsive_ui": 0.0,
            "scientific_functions": 15.0,
        }
        result.score_breakdown_max = {
            "dual_display_editing": 10.0,
            "responsive_ui": 5.0,
            "scientific_functions": 15.0,
        }
        result.score = 25.0
        result.score_max = 30.0
        metric_path = self.repo_root / "benchmark" / "judge-metric.json"
        metric_path.write_text(
            json.dumps(
                {
                    "score": 7,
                    "max": 10,
                    "judge_runner": "Codex CLI",
                    "judge_model": "GPT-5.4",
                    "summary": "Needs corrections.",
                    "notes": ["Visible controls are incomplete."],
                    "entry_adjustments": {
                        "dual_display_editing": {"score": 5, "reason": "Visible controls are incomplete."},
                        "responsive_ui": {"score": 99, "reason": "Responsive layout is clearly present in screenshots."},
                        "unknown_key": {"score": 1, "reason": "Should be ignored."},
                    },
                }
            ),
            encoding="utf-8",
        )

        self.harness.load_judge_metric(self.repo_root, result)

        self.assertEqual(result.judge_score, 7.0)
        self.assertEqual(result.judge_adjusted_score_breakdown["dual_display_editing"], 5.0)
        self.assertEqual(result.judge_adjusted_score_breakdown["responsive_ui"], 5.0)
        self.assertEqual(result.judge_adjusted_score_breakdown["scientific_functions"], 15.0)
        self.assertEqual(result.judge_adjusted_score, 25.0)
        self.assertEqual(
            result.judge_entry_adjustment_reasons["dual_display_editing"],
            "Visible controls are incomplete.",
        )
        self.assertIn("Judge entry adjustments referenced unknown score keys", result.issues[-1])

    def test_delivery_integrity_passes_when_expected_worktree_contains_product_edits(self) -> None:
        self._write(self.worktree_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"interactive\" }\n")
        self._write(
            self.worktree_root / "src" / "calculator.rs",
            "pub fn starter_expression() -> &'static str { \"1 + 2\" }\n",
        )
        self._write_run_artifacts(["src/app.rs", "src/calculator.rs"])

        result = self._make_result()
        self.harness.evaluate_recursive_delivery(self.repo_root, self.worktree_root, result)

        self.assertEqual(result.recursive_delivery_status, "ok")
        self.assertEqual(result.recursive_root_product_drift, [])
        self.assertEqual(result.recursive_missing_claimed_files, [])
        self.assertIn("src/app.rs", result.recursive_product_change_paths)
        self.assertIn("src/calculator.rs", result.recursive_product_change_paths)

    def test_delivery_integrity_fails_for_root_only_product_edits(self) -> None:
        self._write(self.repo_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"wrong-root\" }\n")

        result = self._make_result()
        self.harness.evaluate_recursive_delivery(self.repo_root, self.worktree_root, result)

        self.assertEqual(result.recursive_delivery_status, "wrong-root-edits")
        self.assertIn("src/app.rs", result.recursive_root_product_drift)
        self.assertEqual(result.recursive_product_change_paths, [])

    def test_delivery_integrity_fails_when_claimed_files_are_missing_from_worktree(self) -> None:
        self._write(self.worktree_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"partial\" }\n")
        self._write_run_artifacts(["src/app.rs", "src/calculator.rs"])

        result = self._make_result()
        self.harness.evaluate_recursive_delivery(self.repo_root, self.worktree_root, result)

        self.assertEqual(result.recursive_delivery_status, "claimed-files-missing-in-worktree")
        self.assertIn("src/calculator.rs", result.recursive_missing_claimed_files)
        self.assertIn("src/app.rs", result.recursive_product_change_paths)

    def test_delivery_integrity_ignores_phase2_plan_only_paths_and_normalizes_worktree_prefixed_claims(self) -> None:
        run_root = self.repo_root / ".recursive" / "run" / self.run_id
        self._write(self.worktree_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"interactive\" }\n")
        self._write(
            run_root / "02-to-be-plan.md",
            "\n".join(
                [
                    "## Requirement Completion Status",
                    "",
                    f"- R1 | Status: planned | Implementation Surface: `.worktrees/{self.run_id}/src/parser.rs` | Verification Surface: `.recursive/run/{self.run_id}/evidence/logs/green/r1.log` | QA Surface: `.worktrees/{self.run_id}/benchmark/screenshots/r1.png`",
                ]
            ),
        )
        self._write(
            run_root / "03-implementation-summary.md",
            "\n".join(
                [
                    "## Changes Applied",
                    "",
                    "Collapsed the parser into `parser.rs` prose-wise, but the real file is below.",
                    "",
                    "## Requirement Completion Status",
                    "",
                    f"- R1 | Status: implemented | Changed Files: `.worktrees/{self.run_id}/src/app.rs` | Implementation Evidence: `.worktrees/{self.run_id}/src/app.rs`",
                ]
            ),
        )
        self._write(
            run_root / "04-test-summary.md",
            "\n".join(
                [
                    "## Requirement Completion Status",
                    "",
                    f"- R1 | Status: verified | Changed Files: `.worktrees/{self.run_id}/src/app.rs` | Implementation Evidence: `.worktrees/{self.run_id}/src/app.rs` | Verification Evidence: `.recursive/run/{self.run_id}/evidence/logs/green/r1.log`",
                ]
            ),
        )

        result = self._make_result()
        self.harness.evaluate_recursive_delivery(self.repo_root, self.worktree_root, result)

        self.assertEqual(result.recursive_delivery_status, "ok")
        self.assertEqual(result.recursive_missing_claimed_files, [])
        self.assertEqual(result.recursive_claimed_files, ["src/app.rs"])

    def test_delivery_integrity_ignores_root_only_control_plane_changes(self) -> None:
        self._write(self.worktree_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"interactive\" }\n")
        self._write(self.repo_root / ".recursive" / "STATE.md", "updated state\n")
        self._write(self.repo_root / "benchmark" / "agent-log.md", "# Benchmark agent log\n\nupdated\n")
        self._write_run_artifacts(["src/app.rs"])

        result = self._make_result()
        self.harness.evaluate_recursive_delivery(self.repo_root, self.worktree_root, result)

        self.assertEqual(result.recursive_delivery_status, "ok")
        self.assertEqual(result.recursive_root_product_drift, [])
        self.assertEqual(result.recursive_missing_claimed_files, [])

    def test_delivery_integrity_ignores_root_runtime_output_dirs(self) -> None:
        self._write(self.worktree_root / "src" / "app.rs", "pub fn app_label() -> &'static str { \"interactive\" }\n")
        self._write(self.repo_root / ".cargo-target-dir" / "release" / "unit.json", "{\"artifact\": true}\n")
        self._write(self.repo_root / ".playwright-mcp" / "trace.json", "{\"trace\": true}\n")
        self._write_run_artifacts(["src/app.rs"])

        result = self._make_result()
        self.harness.evaluate_recursive_delivery(self.repo_root, self.worktree_root, result)

        self.assertEqual(result.recursive_delivery_status, "ok")
        self.assertEqual(result.recursive_root_product_drift, [])

    def _score_scientific_source(self, source_text: str) -> tuple[dict[str, float], rrb.ArmResult]:
        result = rrb.ArmResult(
            runner_slug="codex",
            runner_name="Codex CLI",
            provider_family="codex",
            model="gpt-5.1",
            arm_name="recursive-off",
        )
        breakdown: dict[str, float] = {}

        def add_score(
            label: str,
            awarded: float,
            maximum: float,
            *,
            zero_issue: str = "",
            partial_issue: str = "",
        ) -> None:
            bounded = max(0.0, min(maximum, awarded))
            breakdown[label] = bounded
            if bounded == 0 and zero_issue:
                result.issues.append(zero_issue)
            elif 0 < bounded < maximum and partial_issue:
                result.issues.append(partial_issue)

        self.harness.score_scientific_calculator_repo(source_text.lower(), result, add_score)
        return breakdown, result

    def test_scientific_calculator_heuristics_detect_recursive_descent_deg_rad_and_formatting(self) -> None:
        source_text = """
        enum AngleMode { Deg, Rad }
        fn parse_add_sub() {}
        fn parse_mul_div() {}
        fn parse_pow() {}
        fn format_val(value: f64) -> String { format!("{:.12}", value).trim_end_matches('0').trim_end_matches('.').to_string() }
        fn save_state() { let _ = storage.set_item("calc_angle_mode", "deg"); let _ = storage.set_item("calc_history", "1+2=3"); }
        fn load_state() { let _ = storage.get_item("calc_angle_mode"); let _ = storage.get_item("calc_history"); }
        let history = vec!["1+2=3"];
        let memory = 0.0;
        let expression = "sin(30)";
        let display = "result";
        let error = "division by zero";
        let keypad = "clear entry backspace sign";
        Callback::from(move |e: KeyboardEvent| match e.key().as_str() { "Enter" | "Backspace" | "Escape" => (), _ => () });
        @media (max-width: 520px) { .keypad { display: grid; grid-template-columns: repeat(4, 1fr); } .calc-container { max-width: 480px; } }
        parentheses sin cos tan sqrt log10 ln pi pow
        """

        breakdown, result = self._score_scientific_source(source_text)

        self.assertEqual(breakdown["dual_display_editing"], 10)
        self.assertEqual(breakdown["parser_precedence"], 15)
        self.assertEqual(breakdown["scientific_functions"], 15)
        self.assertEqual(breakdown["angle_mode"], 10)
        self.assertEqual(breakdown["memory_history"], 10)
        self.assertEqual(breakdown["persistence"], 10)
        self.assertEqual(breakdown["keyboard_support"], 5)
        self.assertEqual(breakdown["error_handling"], 5)
        self.assertEqual(breakdown["display_formatting"], 5)
        self.assertEqual(breakdown["responsive_ui"], 5)
        self.assertEqual(result.issues, [])

    def test_kimi_runner_env_enforces_utf8_output(self) -> None:
        env = self.harness.runner_invocation_env("kimi")
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["NO_COLOR"], "1")

    def test_parse_worktree_location_accepts_generic_location_field(self) -> None:
        text = "\n".join(
            [
                "## Worktree Details",
                "",
                f"- Location: `.worktrees/{self.run_id}`",
                f"- Product root: `.worktrees/{self.run_id}`",
            ]
        )

        candidate, isolation_status, raw_location = self.harness.parse_worktree_location(self.repo_root, text)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.resolve(), self.worktree_root.resolve())
        self.assertEqual(isolation_status, "isolated-worktree")
        self.assertEqual(raw_location, f".worktrees/{self.run_id}")

    def test_read_repo_source_includes_files_under_worktree_root(self) -> None:
        self._write(
            self.worktree_root / "src" / "main.rs",
            "fn format_result() {} // keyboardevent localstorage memory history sin cos tan sqrt log10 ln\n",
        )
        self._write(self.worktree_root / "index.html", "<div class='expression-display main-display'></div>\n")
        self._write(self.worktree_root / "target" / "debug" / "ignored.rs", "should not be scanned\n")

        source_text = self.harness.read_repo_source(self.worktree_root)

        self.assertIn("format_result", source_text)
        self.assertIn("keyboardevent", source_text)
        self.assertIn("expression-display", source_text)
        self.assertNotIn("should not be scanned", source_text)

    def test_prepare_evaluation_root_snapshots_nested_rust_worktree(self) -> None:
        self._write(self.worktree_root / "src" / "main.rs", "fn main() {}\n")
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        result = self._make_result()

        evaluation_root = self.harness.prepare_evaluation_root(self.repo_root, self.worktree_root, logs_root, result)

        self.assertNotEqual(evaluation_root.resolve(), self.worktree_root.resolve())
        self.assertTrue((evaluation_root / "Cargo.toml").exists())
        self.assertTrue((evaluation_root / "src" / "main.rs").exists())
        self.assertFalse((evaluation_root / ".git").exists())
        self.assertEqual(result.log_paths["evaluation_root"], "codex/recursive-on/logs/evaluation-root")

    def test_prepare_recursive_lint_root_materializes_worktree_changes_and_skips_runtime_dirs(self) -> None:
        self._write(self.worktree_root / "src" / "main.rs", "fn main() {}\n")
        self._write(self.repo_root / ".playwright-mcp" / "trace.json", "{\"trace\":true}\n")
        self._write(self.repo_root / ".cargo-target-dir" / "release" / "artifact.txt", "runtime\n")
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        result = self._make_result()

        lint_root = self.harness.prepare_recursive_lint_root(self.repo_root, self.worktree_root, logs_root, result)

        self.assertTrue((lint_root / ".worktrees" / self.run_id / "src" / "main.rs").exists())
        self.assertFalse((lint_root / ".worktrees" / self.run_id / ".git").exists())
        self.assertFalse((lint_root / ".playwright-mcp").exists())
        self.assertFalse((lint_root / ".cargo-target-dir").exists())
        status = self._git(lint_root, "status", "--short", "--untracked-files=all").stdout
        diff = self._git(lint_root, "diff", "--name-only").stdout
        self.assertIn(f".worktrees/{self.run_id}/src/main.rs", diff)
        self.assertNotIn(".playwright-mcp/trace.json", status)
        self.assertNotIn(".cargo-target-dir/release/artifact.txt", status)

    def test_prepare_recursive_lint_root_can_replace_existing_snapshot(self) -> None:
        self._write(self.worktree_root / "src" / "main.rs", "fn main() {}\n")
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        result = self._make_result()

        first_lint_root = self.harness.prepare_recursive_lint_root(self.repo_root, self.worktree_root, logs_root, result)
        self.assertTrue((first_lint_root / ".worktrees" / self.run_id / "src" / "main.rs").exists())

        second_lint_root = self.harness.prepare_recursive_lint_root(self.repo_root, self.worktree_root, logs_root, result)

        self.assertEqual(first_lint_root, second_lint_root)
        self.assertTrue((second_lint_root / ".worktrees" / self.run_id / "src" / "main.rs").exists())

    def test_prepare_recursive_lint_root_only_surfaces_actual_worktree_drift(self) -> None:
        self._write(self.worktree_root / "src" / "main.rs", "fn main() {}\n")
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        result = self._make_result()

        lint_root = self.harness.prepare_recursive_lint_root(self.repo_root, self.worktree_root, logs_root, result)

        diff = self._git(lint_root, "diff", "--name-only").stdout
        self.assertIn(f".worktrees/{self.run_id}/src/main.rs", diff)
        self.assertNotIn(f".worktrees/{self.run_id}/Cargo.lock", diff)
        self.assertNotIn(f".worktrees/{self.run_id}/styles.css", diff)
        self.assertNotIn(f".worktrees/{self.run_id}/benchmark/agent-log.md", diff)

    def test_prepare_recursive_lint_root_ignores_worktree_control_plane_duplicates(self) -> None:
        self._write(self.worktree_root / "src" / "main.rs", "fn main() {}\n")
        self._write(self.worktree_root / ".recursive" / "run" / self.run_id / "00-worktree.md", "worktree artifact\n")
        self._write(self.worktree_root / ".recursive" / "run" / self.run_id / "00-requirements.md", "requirements artifact\n")
        self._write(self.worktree_root / "benchmark" / "expected-product-root.txt", f".worktrees/{self.run_id}\n")
        self._write(self.worktree_root / "benchmark" / "benchmark-context.json", "{\"run_id\":\"benchmark-test-run\"}\n")
        self._write(self.worktree_root / "benchmark" / "run-id.txt", f"{self.run_id}\n")
        self._write(self.worktree_root / "benchmark" / "recursive-templates" / "00-worktree.md", "template\n")
        logs_root = self.workspace_root / "codex" / "recursive-on" / "logs"
        result = self._make_result()

        lint_root = self.harness.prepare_recursive_lint_root(self.repo_root, self.worktree_root, logs_root, result)

        diff = self._git(lint_root, "diff", "--name-only").stdout
        self.assertIn(f".worktrees/{self.run_id}/src/main.rs", diff)
        self.assertNotIn(
            f".worktrees/{self.run_id}/.recursive/run/{self.run_id}/00-worktree.md",
            diff,
        )
        self.assertNotIn(
            f".worktrees/{self.run_id}/.recursive/run/{self.run_id}/00-requirements.md",
            diff,
        )
        self.assertNotIn(f".worktrees/{self.run_id}/benchmark/expected-product-root.txt", diff)
        self.assertNotIn(f".worktrees/{self.run_id}/benchmark/benchmark-context.json", diff)
        self.assertNotIn(f".worktrees/{self.run_id}/benchmark/run-id.txt", diff)
        self.assertNotIn(f".worktrees/{self.run_id}/benchmark/recursive-templates/00-worktree.md", diff)

    def test_write_report_surfaces_judge_adjusted_entry_rows(self) -> None:
        off = rrb.ArmResult(
            runner_slug="codex",
            runner_name="Codex CLI",
            provider_family="codex",
            model="gpt-5.1",
            arm_name="recursive-off",
            status="pass",
            product_status="pass",
            agent_status="pass",
            score=30.0,
            score_max=35.0,
            heuristic_percentage=85.7,
            judge_score=8.0,
            judge_max=10.0,
            judge_percentage=80.0,
            benchmark_score=84.0,
            score_breakdown={"responsive_ui": 5.0},
            score_breakdown_max={"responsive_ui": 5.0},
        )
        on = rrb.ArmResult(
            runner_slug="codex",
            runner_name="Codex CLI",
            provider_family="codex",
            model="gpt-5.1",
            arm_name="recursive-on",
            status="pass-with-runner-issue",
            product_status="pass",
            agent_status="completed",
            score=35.0,
            score_max=35.0,
            heuristic_percentage=100.0,
            judge_score=7.0,
            judge_max=10.0,
            judge_percentage=70.0,
            benchmark_score=91.0,
            score_breakdown={"responsive_ui": 5.0},
            score_breakdown_max={"responsive_ui": 5.0},
            judge_adjusted_score_breakdown={"responsive_ui": 0.0},
            judge_adjusted_score=30.0,
            judge_entry_adjustment_reasons={"responsive_ui": "Screenshot review showed the layout broke on small screens."},
        )
        self.harness.results = [off, on]

        report_path = self.harness.write_report()
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("normalized:entry-adjusted", report)
        self.assertIn("`0 (raw 5)`", report)
        self.assertIn("on adjusted 5 -> 0 (Screenshot review showed the layout broke on small screens.)", report)
        self.assertIn("#### Judge-adjusted score breakdown", report)

    def test_packaged_node_vite_starters_match_scenario_titles(self) -> None:
        benchmark_roots = (
            self.harness.repo_source_root / "references" / "benchmarks",
            self.harness.repo_source_root / "references" / "benchmarks" / "benchmarks",
        )
        node_vite_scenarios = {
            "local-first-planner": "Local First Planner",
            "team-capacity-board": "Team Capacity Board",
            "release-readiness-dashboard": "Release Readiness Dashboard",
        }

        for benchmark_root in benchmark_roots:
            for scenario_slug, scenario_title in node_vite_scenarios.items():
                starter_root = benchmark_root / scenario_slug / "starter"
                root_label = str(starter_root.relative_to(self.harness.repo_source_root))

                with self.subTest(root=root_label, file="README.md"):
                    first_line = (starter_root / "README.md").read_text(encoding="utf-8").splitlines()[0]
                    self.assertEqual(f"# {scenario_title} benchmark starter", first_line)

                with self.subTest(root=root_label, file="index.html"):
                    index_html = (starter_root / "index.html").read_text(encoding="utf-8")
                    self.assertIn(f"<title>{scenario_title} Benchmark</title>", index_html)

                with self.subTest(root=root_label, file="src/App.tsx"):
                    app_source = (starter_root / "src" / "App.tsx").read_text(encoding="utf-8")
                    self.assertIn(f"<h1>{scenario_title}</h1>", app_source)

                with self.subTest(root=root_label, file="src/App.test.tsx"):
                    test_source = (starter_root / "src" / "App.test.tsx").read_text(encoding="utf-8")
                    self.assertIn(f'name: "{scenario_title}"', test_source)

    def test_packaged_recursive_on_prompts_remove_template_todo_heading_before_lock(self) -> None:
        benchmark_roots = (
            self.harness.repo_source_root / "references" / "benchmarks",
            self.harness.repo_source_root / "references" / "benchmarks" / "benchmarks",
        )

        for benchmark_root in benchmark_roots:
            for prompt_path in sorted(benchmark_root.glob("*/prompt-recursive-on.md")):
                prompt_text = prompt_path.read_text(encoding="utf-8")

                with self.subTest(prompt=str(prompt_path.relative_to(self.harness.repo_source_root))):
                    self.assertIn("remove the template `## TODO` section entirely", prompt_text)
                    self.assertNotIn("Keep the required `## TODO` heading", prompt_text)


if __name__ == "__main__":
    unittest.main()
