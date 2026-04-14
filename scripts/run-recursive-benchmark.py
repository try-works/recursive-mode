#!/usr/bin/env python3
"""
Disposable paired benchmark harness for recursive-mode.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SCENARIO = "local-first-planner"
DEFAULT_PREVIEW_HOST = "127.0.0.1"
DEFAULT_TIMEOUT_MINUTES = 60
SCENARIOS = {
    "local-first-planner": {
        "title": "Local First Planner",
        "tier": "easy",
    },
    "team-capacity-board": {
        "title": "Team Capacity Board",
        "tier": "medium",
    },
    "release-readiness-dashboard": {
        "title": "Release Readiness Dashboard",
        "tier": "hard",
    },
}

REQUIRED_RECURSIVE_RUN_FILES = (
    "00-requirements.md",
    "00-worktree.md",
    "01-as-is.md",
    "02-to-be-plan.md",
    "03-implementation-summary.md",
    "04-test-summary.md",
    "05-manual-qa.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
)

DEFAULT_JUDGE_MODEL = "gpt-5.4"
DEFAULT_JUDGE_MAX = 10.0
DEFAULT_JUDGE_TIMEOUT_SECONDS = 15 * 60
DEFAULT_HEURISTIC_WEIGHT = 0.7
DEFAULT_JUDGE_WEIGHT = 0.3
DEFAULT_BENCHMARK_SCORE_MAX = 100.0


class BenchmarkError(RuntimeError):
    """Raised when the benchmark harness encounters a hard failure."""


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


@dataclass
class RunnerConfig:
    slug: str
    display_name: str
    provider_family: str
    executable: str | None
    model: str
    supports_json: bool


@dataclass
class ArmResult:
    runner_slug: str
    runner_name: str
    provider_family: str
    model: str
    arm_name: str
    repo_root: str = ""
    product_root: str = ""
    status: str = "not-started"
    agent_status: str = "not-run"
    product_status: str = "not-evaluated"
    duration_seconds: float = 0.0
    score: float = 0.0
    score_max: float = 0.0
    build_success: bool = False
    test_success: bool = False
    preview_success: bool = False
    agent_exit_code: str = "not-run"
    timed_out: bool = False
    run_id: str = ""
    recursive_workflow_status: str = "n/a"
    recursive_isolation_status: str = "n/a"
    recursive_worktree_location: str = ""
    recursive_workflow_profile: str = "n/a"
    recursive_phase2_guardrails: str = "n/a"
    recursive_run_root: str = ""
    recursive_artifact_status: dict[str, bool] = field(default_factory=dict)
    hint_count: int = 0
    hint_penalty: float = 0.0
    timestamp_fallback_used: bool = False
    judge_score: float | None = None
    judge_max: float | None = None
    heuristic_percentage: float | None = None
    judge_percentage: float | None = None
    benchmark_score: float | None = None
    benchmark_score_max: float = DEFAULT_BENCHMARK_SCORE_MAX
    benchmark_score_method: str = "unavailable"
    judge_runner_name: str = ""
    judge_model_name: str = ""
    judge_summary: str = ""
    judge_notes: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    log_paths: dict[str, str] = field(default_factory=dict)
    screenshot_paths: list[str] = field(default_factory=list)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    phase_durations: dict[str, float] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)
    timestamp_evidence: dict[str, str] = field(default_factory=dict)


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_from_epoch(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def format_score(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def append_text(path: Path, content: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "" if not existing or existing.endswith("\n") else "\n"
    write_text(path, existing + separator + content.rstrip() + "\n")


def load_json_lines(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            rows.append(decoded)
    return rows


def command_string(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def detect_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_PREVIEW_HOST, 0))
        return int(sock.getsockname()[1])


class BenchmarkHarness:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.script_dir = Path(__file__).resolve().parent
        self.repo_source_root = self.script_dir.parent
        self.scenario_name = args.scenario
        self.scenario_meta = SCENARIOS[self.scenario_name]
        self.scenario_title = self.scenario_meta["title"]
        self.scenario_tier = self.scenario_meta["tier"]
        self.fixture_root = self.repo_source_root / "references" / "benchmarks" / self.scenario_name
        self.starter_root = self.fixture_root / "starter"
        self.requirements_path = self.fixture_root / "00-requirements.md"
        self.rubric_path = self.fixture_root / "scoring-rubric.md"
        self.prompt_off_path = self.fixture_root / "prompt-recursive-off.md"
        self.prompt_on_path = self.fixture_root / "prompt-recursive-on.md"
        self.python_exe = str(Path(sys.executable).resolve())
        self.workspace_root = self._make_workspace()
        self.max_seconds = max(1, int(args.max_minutes * 60))
        self.judge_timeout = min(self.max_seconds, DEFAULT_JUDGE_TIMEOUT_SECONDS)
        self.command_timeout = max(60, args.command_timeout)
        self.preview_timeout = max(15, args.preview_timeout)
        self.run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.results: list[ArmResult] = []
        self.summary_notes: list[str] = []
        self.effective_arm_modes: dict[str, str] = {}
        self.npm_exe = shutil.which(args.npm_command)
        self.runner_configs = self._build_runner_configs()
        self.kimi_config_path = Path.home() / ".kimi" / "config.toml"
        self.ensure_workspace_ignored()

    def _make_workspace(self) -> Path:
        if self.args.workspace_root:
            root = Path(self.args.workspace_root).resolve()
            root.mkdir(parents=True, exist_ok=True)
            return root
        return Path(tempfile.mkdtemp(prefix="recursive-benchmark-"))

    def ensure_workspace_ignored(self) -> None:
        gitignore_path = self.repo_source_root / ".gitignore"
        benchmark_ignore = ".benchmark-workspaces/"
        try:
            self.workspace_root.resolve().relative_to(self.repo_source_root.resolve())
        except ValueError:
            return
        if self.workspace_root.name != ".benchmark-workspaces" and benchmark_ignore not in self.workspace_root.as_posix():
            return
        existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        if benchmark_ignore in {line.strip() for line in existing.splitlines()}:
            return
        addition = "# Local benchmark workspaces\n.benchmark-workspaces/"
        if existing.strip():
            append_text(gitignore_path, addition)
        else:
            write_text(gitignore_path, addition)

    def _build_runner_configs(self) -> list[RunnerConfig]:
        requested = []
        if self.args.runner in {"copilot", "both", "all"}:
            requested.append(
                RunnerConfig(
                    slug="copilot",
                    display_name="GitHub Copilot CLI",
                    provider_family="github-copilot",
                    executable=shutil.which("copilot"),
                    model=self.args.copilot_model,
                    supports_json=True,
                )
            )
        if self.args.runner in {"codex", "both", "all"}:
            requested.append(
                RunnerConfig(
                    slug="codex",
                    display_name="Codex CLI",
                    provider_family="codex",
                    executable=shutil.which("codex"),
                    model=self.args.codex_model,
                    supports_json=True,
                )
            )
        if self.args.runner in {"kimi", "all"}:
            requested.append(
                RunnerConfig(
                    slug="kimi",
                    display_name="Kimi CLI",
                    provider_family="moonshot-kimi",
                    executable=shutil.which("kimi"),
                    model=self.args.kimi_model,
                    supports_json=True,
                )
            )
        if not requested:
            raise BenchmarkError("No runner configuration was selected.")
        return requested

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.workspace_root.resolve())).replace("\\", "/")
        except ValueError:
            return str(path.resolve())

    def arm_root(self, result: ArmResult) -> Path:
        return self.workspace_root / result.runner_slug / result.arm_name

    def arm_progress_path(self, result: ArmResult) -> Path:
        return self.arm_root(result) / "progress.json"

    def log(self, message: str) -> None:
        print(f"[INFO] {message}")

    def write_arm_progress(
        self,
        result: ArmResult,
        phase: str,
        *,
        detail: str = "",
        extras: dict[str, object] | None = None,
    ) -> None:
        progress_path = self.arm_progress_path(result)
        payload: dict[str, object] = {
            "updated_at": timestamp_utc(),
            "runner": result.runner_name,
            "runner_slug": result.runner_slug,
            "arm": result.arm_name,
            "phase": phase,
            "detail": detail,
            "status": result.status,
            "agent_status": result.agent_status,
            "product_status": result.product_status,
            "run_id": result.run_id,
            "repo_root": result.repo_root,
            "product_root": result.product_root,
            "recursive_workflow_status": result.recursive_workflow_status,
            "recursive_isolation_status": result.recursive_isolation_status,
            "recursive_worktree_location": result.recursive_worktree_location,
            "phase_durations": result.phase_durations,
            "log_paths": result.log_paths,
            "issues": result.issues,
            "judge_score": result.judge_score,
            "judge_max": result.judge_max,
            "heuristic_percentage": result.heuristic_percentage,
            "judge_percentage": result.judge_percentage,
            "benchmark_score": result.benchmark_score,
            "benchmark_score_max": result.benchmark_score_max,
            "benchmark_score_method": result.benchmark_score_method,
            "judge_runner": result.judge_runner_name,
            "judge_model": result.judge_model_name,
        }
        if extras:
            payload.update(extras)
        write_text(progress_path, json.dumps(payload, indent=2, sort_keys=True))
        result.log_paths["progress"] = self.rel(progress_path)
        self.write_workspace_progress_index(result, payload)
        result.log_paths["workspace_status"] = self.rel(self.workspace_root / "benchmark-status.json")

    def write_workspace_progress_index(self, result: ArmResult, payload: dict[str, object]) -> None:
        index_path = self.workspace_root / "benchmark-status.json"
        if index_path.exists():
            try:
                index_payload = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                index_payload = {}
        else:
            index_payload = {}
        if not isinstance(index_payload, dict):
            index_payload = {}
        arms = index_payload.get("arms")
        if not isinstance(arms, dict):
            arms = {}
        arms[f"{result.runner_slug}/{result.arm_name}"] = payload
        index_payload["updated_at"] = timestamp_utc()
        index_payload["workspace"] = str(self.workspace_root)
        index_payload["scenario"] = self.scenario_name
        index_payload["arms"] = arms
        write_text(index_path, json.dumps(index_payload, indent=2, sort_keys=True))

    def run_command(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
        allowed_returncodes: tuple[int, ...] = (0,),
        check: bool = True,
    ) -> CommandResult:
        start = time.perf_counter()
        merged_env = os.environ.copy()
        merged_env["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            merged_env.update(env)
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                env=merged_env,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start
            return CommandResult(
                command=command,
                returncode=-1,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_seconds=duration,
                timed_out=True,
            )
        duration = time.perf_counter() - start
        result = CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
            timed_out=False,
        )
        if completed.returncode not in allowed_returncodes and check:
            raise BenchmarkError(
                "\n".join(
                    [
                        f"Command failed: {command_string(command)}",
                        f"Return code: {completed.returncode}",
                        f"Duration seconds: {duration:.2f}",
                        "",
                        "STDOUT:",
                        completed.stdout.rstrip(),
                        "",
                        "STDERR:",
                        completed.stderr.rstrip(),
                    ]
                )
            )
        return result

    def write_command_log(self, path: Path, label: str, result: CommandResult) -> None:
        write_text(
            path,
            "\n".join(
                [
                    label,
                    f"Timestamp: {timestamp_utc()}",
                    f"Command: {command_string(result.command)}",
                    f"Return code: {result.returncode}",
                    f"Timed out: {'yes' if result.timed_out else 'no'}",
                    f"Duration seconds: {result.duration_seconds:.2f}",
                    "",
                    "STDOUT:",
                    result.stdout.rstrip(),
                    "",
                    "STDERR:",
                    result.stderr.rstrip(),
                ]
            ),
        )

    def ensure_npm(self) -> None:
        if self.args.skip_npm_install:
            return
        if not self.npm_exe:
            raise BenchmarkError(
                f"npm executable '{self.args.npm_command}' was not found, but npm install is enabled."
            )

    def run(self) -> Path:
        self.ensure_npm()
        for runner in self.runner_configs:
            self.results.extend(self.run_runner(runner))
        report_path = self.write_report()
        print(f"[OK] Benchmark report: {report_path}")
        print(f"[OK] Benchmark workspace: {self.workspace_root}")
        return report_path

    def run_runner(self, runner: RunnerConfig) -> list[ArmResult]:
        runner_results: list[ArmResult] = []
        if runner.executable is None:
            note = f"{runner.display_name} is not available on PATH; marking both arms unavailable."
            self.summary_notes.append(note)
            for arm_name in ("recursive-off", "recursive-on"):
                runner_results.append(
                    ArmResult(
                        runner_slug=runner.slug,
                        runner_name=runner.display_name,
                        provider_family=runner.provider_family,
                        model=runner.model,
                        arm_name=arm_name,
                        status="runner-unavailable",
                        issues=[note],
                    )
                )
            return runner_results

        arm_names = ("recursive-off", "recursive-on")
        arm_mode = self.resolve_arm_mode(runner)
        if arm_mode == "parallel":
            ordered: list[ArmResult | None] = [None] * len(arm_names)
            with ThreadPoolExecutor(max_workers=len(arm_names)) as executor:
                futures = {
                    executor.submit(self.run_arm, runner, arm_name): index for index, arm_name in enumerate(arm_names)
                }
                for future in as_completed(futures):
                    ordered[futures[future]] = future.result()
            runner_results.extend(result for result in ordered if result is not None)
            return runner_results

        for arm_name in arm_names:
            runner_results.append(self.run_arm(runner, arm_name))
        return runner_results

    def resolve_arm_mode(self, runner: RunnerConfig) -> str:
        effective = self.args.arm_mode
        if runner.slug == "kimi" and effective == "parallel":
            effective = "sequential"
            note = (
                "Kimi CLI arm execution was auto-downgraded from parallel to sequential because "
                "concurrent runs have been unstable on Windows."
            )
            if note not in self.summary_notes:
                self.summary_notes.append(note)
        self.effective_arm_modes[runner.slug] = effective
        return effective

    def run_arm(self, runner: RunnerConfig, arm_name: str) -> ArmResult:
        result = ArmResult(
            runner_slug=runner.slug,
            runner_name=runner.display_name,
            provider_family=runner.provider_family,
            model=runner.model,
            arm_name=arm_name,
        )
        arm_root = self.workspace_root / runner.slug / arm_name
        repo_root = arm_root / "repo"
        logs_root = arm_root / "logs"
        prompts_root = arm_root / "prompts"
        repo_root.parent.mkdir(parents=True, exist_ok=True)
        result.repo_root = self.rel(repo_root)
        self.write_arm_progress(result, "preparing", detail="Creating benchmark repo and setup artifacts.")
        self.log(f"Preparing {runner.display_name} {arm_name} in {repo_root}")
        self.prepare_repo(repo_root, logs_root, runner, result, recursive_on=arm_name == "recursive-on")
        if self.args.prepare_only:
            result.status = "prepared"
            self.write_arm_progress(result, "prepared", detail="Prepare-only benchmark workspace is ready.")
            return result

        prompt_text, prompt_path = self.render_prompt(prompts_root, result)
        if prompt_path is not None:
            result.log_paths["prompt"] = self.rel(prompt_path)
        self.write_arm_progress(result, "agent-running", detail="Agent run has started.")
        agent_record = self.invoke_runner(repo_root, logs_root, runner, result, prompt_text)
        product_root = self.resolve_product_root(repo_root, result)
        result.product_root = self.rel(product_root)
        result.duration_seconds = agent_record.duration_seconds
        result.phase_durations["agent_run"] = round(agent_record.duration_seconds, 2)
        result.agent_exit_code = str(agent_record.returncode)
        result.timed_out = agent_record.timed_out
        if agent_record.timed_out:
            result.agent_status = "timed-out"
            result.issues.append("Agent execution hit the benchmark timeout.")
        elif agent_record.returncode != 0:
            result.agent_status = "non-zero-exit"
        else:
            result.agent_status = "clean-exit"

        usage = self.extract_usage(agent_record.stdout, agent_record.stderr)
        if usage:
            result.token_usage = usage

        self.write_arm_progress(result, "evaluating", detail="Agent run finished; evaluating build, tests, preview, and artifacts.")
        self.evaluate_repo(repo_root, product_root, logs_root, result)
        self.write_arm_progress(result, "judging", detail="Controller-side judge review is running.")
        self.run_judge_review(repo_root, product_root, logs_root, runner, result)
        self.finalize_result(runner, agent_record, result)
        self.write_arm_progress(result, "complete", detail="Benchmark arm completed.")
        return result

    def finalize_result(self, runner: RunnerConfig, agent_record: CommandResult, result: ArmResult) -> None:
        result.product_status = "pass" if result.build_success and result.test_success and result.preview_success else "fail"
        if result.timed_out:
            result.status = "timed-out"
            return

        runner_issue = self.detect_runner_issue(runner.slug, agent_record.stderr)
        if result.agent_status == "clean-exit":
            result.status = "pass" if result.product_status == "pass" else "product-fail"
            return

        if result.product_status == "pass":
            result.status = "pass-with-runner-issue"
            result.issues.append(
                runner_issue or "Agent execution exited non-zero after producing a passing artifact set."
            )
            return

        result.status = "product-fail-with-runner-issue"
        result.issues.append(runner_issue or "Agent execution exited with a non-zero status.")

    def update_combined_benchmark_score(self, result: ArmResult) -> None:
        if result.score_max > 0:
            result.heuristic_percentage = round((result.score / result.score_max) * DEFAULT_BENCHMARK_SCORE_MAX, 1)
        else:
            result.heuristic_percentage = None
        if result.judge_score is not None and result.judge_max and result.judge_max > 0:
            result.judge_percentage = round((result.judge_score / result.judge_max) * DEFAULT_BENCHMARK_SCORE_MAX, 1)
        else:
            result.judge_percentage = None

        if result.heuristic_percentage is None and result.judge_percentage is None:
            result.benchmark_score = None
            result.benchmark_score_method = "unavailable"
            return
        if result.heuristic_percentage is None:
            result.benchmark_score = result.judge_percentage
            result.benchmark_score_method = "judge-only-fallback"
            return
        if result.judge_percentage is None:
            result.benchmark_score = result.heuristic_percentage
            result.benchmark_score_method = "heuristic-only-fallback"
            return

        result.benchmark_score = round(
            (result.heuristic_percentage * DEFAULT_HEURISTIC_WEIGHT)
            + (result.judge_percentage * DEFAULT_JUDGE_WEIGHT),
            1,
        )
        result.benchmark_score_method = "blended"

    def detect_runner_issue(self, runner_slug: str, stderr: str) -> str:
        lower = stderr.lower()
        if runner_slug == "kimi" and "charmap" in lower and "can't encode character" in lower:
            return "Kimi CLI hit a Windows encoding error after the benchmark work completed."
        return ""

    def prepare_repo(
        self,
        repo_root: Path,
        logs_root: Path,
        runner: RunnerConfig,
        result: ArmResult,
        *,
        recursive_on: bool,
    ) -> None:
        if repo_root.exists():
            shutil.rmtree(repo_root)
        shutil.copytree(self.starter_root, repo_root)

        benchmark_dir = repo_root / "benchmark"
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir = benchmark_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        if recursive_on:
            write_text(
                benchmark_dir / "agent-log.md",
                "\n".join(
                    [
                        "# Benchmark agent log",
                        "",
                        "Append UTC timestamped progress notes here during the benchmark run.",
                        "If you take screenshots, store them under benchmark/screenshots/ and mention the file paths in this log.",
                    ]
                ),
            )
            write_text(
                benchmark_dir / "benchmark-context.json",
                json.dumps(
                    {
                        "scenario": self.scenario_name,
                        "scenario_title": self.scenario_title,
                        "scenario_tier": self.scenario_tier,
                        "arm": result.arm_name,
                        "runner": runner.display_name,
                        "provider_family": runner.provider_family,
                        "model": runner.model,
                        "generated_at": timestamp_utc(),
                        "timeout_minutes": self.args.max_minutes,
                    },
                    indent=2,
                ),
            )

        self.git_init(repo_root)

        if not self.args.skip_npm_install:
            install_result = self.run_command(
                [self.npm_exe, "install"],
                cwd=repo_root,
                timeout_seconds=self.command_timeout,
                check=False,
            )
            self.write_command_log(logs_root / "npm-install.log", "npm install", install_result)
            result.log_paths["npm_install"] = self.rel(logs_root / "npm-install.log")
            result.phase_durations["npm_install"] = round(install_result.duration_seconds, 2)
            if install_result.returncode != 0 or install_result.timed_out:
                raise BenchmarkError(
                    f"Failed to prepare benchmark dependencies for {runner.display_name} {result.arm_name}."
            )
            self.write_arm_progress(result, "dependencies-installed", detail="npm install completed.")

        if recursive_on:
            bootstrap_result = self.run_command(
                [self.python_exe, str(self.script_dir / "install-recursive-mode.py"), "--repo-root", str(repo_root)],
                cwd=repo_root,
                timeout_seconds=self.command_timeout,
                check=False,
            )
            self.write_command_log(logs_root / "recursive-bootstrap.log", "recursive bootstrap", bootstrap_result)
            result.log_paths["recursive_bootstrap"] = self.rel(logs_root / "recursive-bootstrap.log")
            result.phase_durations["recursive_bootstrap"] = round(bootstrap_result.duration_seconds, 2)
            if bootstrap_result.returncode != 0 or bootstrap_result.timed_out:
                raise BenchmarkError("Failed to bootstrap recursive-mode in the recursive-on benchmark repo.")
            self.write_arm_progress(result, "recursive-bootstrapped", detail="Recursive scaffold bootstrap completed.")

        self.git_commit(repo_root, "Benchmark starter baseline")

        if recursive_on:
            run_id = f"benchmark-{runner.slug}-{self.run_stamp}"
            init_result = self.run_command(
                [
                    self.python_exe,
                    str(self.script_dir / "recursive-init.py"),
                    "--repo-root",
                    str(repo_root),
                    "--run-id",
                    run_id,
                    "--template",
                    "feature",
                ],
                cwd=repo_root,
                timeout_seconds=self.command_timeout,
                check=False,
            )
            self.write_command_log(logs_root / "recursive-init.log", "recursive init", init_result)
            result.log_paths["recursive_init"] = self.rel(logs_root / "recursive-init.log")
            result.phase_durations["recursive_init"] = round(init_result.duration_seconds, 2)
            if init_result.returncode != 0 or init_result.timed_out:
                raise BenchmarkError("Failed to scaffold the recursive benchmark run.")
            run_root = repo_root / ".recursive" / "run" / run_id
            run_requirements = run_root / "00-requirements.md"
            shutil.copy2(self.requirements_path, run_requirements)
            result.run_id = run_id
            result.recursive_run_root = self.rel(run_root)
            write_text(repo_root / "benchmark" / "run-id.txt", run_id)
            result.log_paths["recursive_run_root"] = self.rel(run_root)
            result.log_paths["run_requirements"] = self.rel(run_requirements)
            self.write_arm_progress(
                result,
                "run-initialized",
                detail="Recursive run scaffold and run-local requirements are ready.",
            )

    def git_init(self, repo_root: Path) -> None:
        self.run_command(["git", "init"], cwd=repo_root, timeout_seconds=self.command_timeout)
        self.run_command(["git", "config", "user.name", "Recursive Benchmark Harness"], cwd=repo_root, timeout_seconds=self.command_timeout)
        self.run_command(["git", "config", "user.email", "benchmark@example.com"], cwd=repo_root, timeout_seconds=self.command_timeout)
        self.run_command(["git", "branch", "-M", "main"], cwd=repo_root, timeout_seconds=self.command_timeout)

    def git_commit(self, repo_root: Path, message: str) -> None:
        self.run_command(["git", "add", "-A"], cwd=repo_root, timeout_seconds=self.command_timeout)
        commit_result = self.run_command(
            ["git", "commit", "-m", message],
            cwd=repo_root,
            timeout_seconds=self.command_timeout,
            allowed_returncodes=(0, 1),
            check=False,
        )
        if commit_result.returncode not in (0, 1):
            raise BenchmarkError(f"Git commit failed for {repo_root}.")

    def render_prompt(self, prompts_root: Path, result: ArmResult) -> tuple[str, Path | None]:
        template_path = self.prompt_on_path if result.arm_name == "recursive-on" else self.prompt_off_path
        text = template_path.read_text(encoding="utf-8")
        text = text.replace("{{RUN_ID}}", result.run_id or "benchmark-run-id-missing")
        if result.arm_name == "recursive-off":
            requirements_text = self.requirements_path.read_text(encoding="utf-8").strip()
            rubric_text = self.rubric_path.read_text(encoding="utf-8").strip()
            text += "\n\nBenchmark requirements provided in chat only:\n\n" + requirements_text + "\n"
            text += "\nBenchmark scoring rubric provided in chat only:\n\n" + rubric_text + "\n"
        text += (
            "\n\nBenchmark metadata:\n"
            f"- Scenario: {self.scenario_name}\n"
            f"- Scenario title: {self.scenario_title}\n"
            f"- Scenario tier: {self.scenario_tier}\n"
            f"- Arm: {result.arm_name}\n"
            f"- Runner: {result.runner_name}\n"
            f"- Provider family: {result.provider_family}\n"
            f"- Model: {result.model}\n"
            f"- Timeout budget: {self.args.max_minutes} minutes\n"
        )
        if result.arm_name == "recursive-off":
            return text, None
        prompts_root.mkdir(parents=True, exist_ok=True)
        prompt_path = prompts_root / f"{result.arm_name}.md"
        write_text(prompt_path, text)
        return text, prompt_path

    def run_model_prompt(
        self,
        repo_root: Path,
        logs_root: Path,
        *,
        runner_slug: str,
        executable: str | None,
        model: str,
        prompt_text: str,
        log_stem: str,
        timeout_seconds: int,
    ) -> tuple[CommandResult, Path, Path]:
        if runner_slug == "copilot":
            command = [
                executable or "copilot",
                "--model",
                model,
                "--allow-all",
                "--no-ask-user",
                "--output-format",
                "json",
                "--stream",
                "off",
                "--no-color",
                "-p",
                prompt_text,
            ]
            record = self.run_command(command, cwd=repo_root, timeout_seconds=timeout_seconds, check=False)
        elif runner_slug == "codex":
            command = [
                executable or "codex",
                "exec",
                "--model",
                model,
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "-C",
                str(repo_root),
                prompt_text,
            ]
            record = self.run_command(command, cwd=repo_root, timeout_seconds=timeout_seconds, check=False)
        elif runner_slug == "kimi":
            temp_config = self.build_kimi_temp_config(model)
            try:
                command = [
                    executable or "kimi",
                    "--config-file",
                    str(temp_config),
                    "--work-dir",
                    str(repo_root),
                    "--print",
                    "--output-format",
                    "stream-json",
                    "--prompt",
                    prompt_text,
                ]
                record = self.run_command(command, cwd=repo_root, timeout_seconds=timeout_seconds, check=False)
            finally:
                if temp_config.exists():
                    temp_config.unlink()
        else:
            raise BenchmarkError(f"Unsupported runner: {runner_slug}")

        stdout_log = logs_root / f"{log_stem}-output.jsonl"
        stderr_log = logs_root / f"{log_stem}-stderr.log"
        write_text(stdout_log, record.stdout or "")
        write_text(stderr_log, record.stderr or "")
        return record, stdout_log, stderr_log

    def invoke_runner(
        self,
        repo_root: Path,
        logs_root: Path,
        runner: RunnerConfig,
        result: ArmResult,
        prompt_text: str,
    ) -> CommandResult:
        record, stdout_log, stderr_log = self.run_model_prompt(
            repo_root,
            logs_root,
            runner_slug=runner.slug,
            executable=runner.executable,
            model=runner.model,
            prompt_text=prompt_text,
            log_stem=runner.slug,
            timeout_seconds=self.max_seconds,
        )
        result.log_paths["agent_stdout"] = self.rel(stdout_log)
        result.log_paths["agent_stderr"] = self.rel(stderr_log)
        return record

    def resolve_product_root(self, repo_root: Path, result: ArmResult) -> Path:
        if result.arm_name != "recursive-on" or not result.run_id:
            return repo_root
        worktree_doc = repo_root / ".recursive" / "run" / result.run_id / "00-worktree.md"
        if worktree_doc.exists():
            text = worktree_doc.read_text(encoding="utf-8", errors="replace")
            candidate, _, _ = self.parse_worktree_location(repo_root, text)
            if candidate is not None and candidate.exists():
                return candidate
        fallback = repo_root / ".worktrees" / result.run_id
        if fallback.exists():
            return fallback
        return repo_root

    def parse_worktree_location(self, repo_root: Path, text: str) -> tuple[Path | None, str, str]:
        match = re.search(r"(?im)^\s*-\s*(?:Selected\s+)?Worktree location:\s*(.+?)\s*$", text)
        if not match:
            return None, "missing", ""

        raw_value = match.group(1).strip()
        cleaned = raw_value.strip().strip("`").strip().rstrip("/\\")
        if not cleaned:
            return None, "missing", raw_value

        lowered = cleaned.lower()
        if "current directory" in lowered or "repository root" in lowered:
            return repo_root, "repo-root", cleaned

        candidate = Path(cleaned)
        if not candidate.is_absolute():
            candidate = repo_root / cleaned
        if candidate.exists():
            try:
                same_root = candidate.resolve() == repo_root.resolve()
            except OSError:
                same_root = False
            return candidate, "repo-root" if same_root else "isolated-worktree", cleaned
        return candidate, "missing-path", cleaned

    @staticmethod
    def has_heading(content: str, heading_text: str) -> bool:
        return bool(re.search(rf"(?m)^[ \t]*##\s+{re.escape(heading_text)}\s*$", content))

    @staticmethod
    def read_workflow_version(content: str) -> str:
        match = re.search(r"(?m)^[ \t]*Workflow version:\s*(?:`|\")?([^`\"\r\n]+)(?:`|\")?\s*$", content)
        return match.group(1).strip() if match else ""

    def resolve_agent_log_path(self, repo_root: Path, product_root: Path) -> Path:
        candidates = [product_root / "benchmark" / "agent-log.md", repo_root / "benchmark" / "agent-log.md"]
        existing = [candidate for candidate in candidates if candidate.exists()]
        for candidate in existing:
            text = candidate.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text):
                return candidate
        if existing:
            return existing[0]
        return candidates[0]

    def build_kimi_temp_config(self, model_name: str) -> Path:
        if not self.kimi_config_path.exists():
            raise BenchmarkError(
                f"Kimi config file was not found at {self.kimi_config_path}. Run `kimi login` before benchmarking."
            )
        original = self.kimi_config_path.read_text(encoding="utf-8")
        default_model_match = re.search(r'(?m)^default_model\s*=\s*"([^"]+)"\s*$', original)
        if not default_model_match:
            raise BenchmarkError("Kimi config does not define default_model, so the benchmark cannot infer a provider.")
        default_alias = default_model_match.group(1)
        provider = self.extract_kimi_provider(original, default_alias)
        if not provider:
            raise BenchmarkError(
                f"Kimi config default model {default_alias!r} does not declare a provider, so the benchmark cannot infer one."
            )

        alias = "benchmark-kimi"
        updated = re.sub(r'(?m)^default_model\s*=\s*"[^"]*"\s*$', f'default_model = "{alias}"', original, count=1)
        updated = self.remove_kimi_model_section(updated, alias)
        if not updated.endswith("\n"):
            updated += "\n"
        updated += (
            "\n"
            f'[models."{alias}"]\n'
            f'provider = "{provider}"\n'
            f'model = "{model_name}"\n'
            "max_context_size = 262144\n"
        )

        temp_path = Path(tempfile.gettempdir()) / f"recursive-benchmark-kimi-{uuid.uuid4()}.toml"
        write_text(temp_path, updated)
        return temp_path

    def extract_kimi_provider(self, config_text: str, model_alias: str) -> str:
        pattern = re.compile(
            rf'(?ms)^\[models\.(?:"{re.escape(model_alias)}"|{re.escape(model_alias)})\]\s*\n(.*?)(?=^\[|\Z)'
        )
        match = pattern.search(config_text)
        if not match:
            return ""
        body = match.group(1)
        provider_match = re.search(r'(?m)^provider\s*=\s*"([^"]+)"\s*$', body)
        if not provider_match:
            return ""
        return provider_match.group(1)

    def remove_kimi_model_section(self, config_text: str, alias: str) -> str:
        pattern = re.compile(
            rf'(?ms)^\[models\.(?:"{re.escape(alias)}"|{re.escape(alias)})\]\s*\n.*?(?=^\[|\Z)'
        )
        return pattern.sub("", config_text)

    def evaluate_repo(self, repo_root: Path, product_root: Path, logs_root: Path, result: ArmResult) -> None:
        build_result = self.run_command(
            [self.npm_exe or "npm", "run", "build"],
            cwd=product_root,
            timeout_seconds=self.command_timeout,
            check=False,
        )
        self.write_command_log(logs_root / "build.log", "npm run build", build_result)
        result.log_paths["build"] = self.rel(logs_root / "build.log")
        result.phase_durations["build"] = round(build_result.duration_seconds, 2)
        result.build_success = build_result.returncode == 0 and not build_result.timed_out
        if not result.build_success:
            result.issues.append("Build failed.")

        test_result = self.run_command(
            [self.npm_exe or "npm", "run", "test"],
            cwd=product_root,
            timeout_seconds=self.command_timeout,
            check=False,
        )
        self.write_command_log(logs_root / "test.log", "npm run test", test_result)
        result.log_paths["test"] = self.rel(logs_root / "test.log")
        result.phase_durations["test"] = round(test_result.duration_seconds, 2)
        result.test_success = test_result.returncode == 0 and not test_result.timed_out
        if not result.test_success:
            result.issues.append("Tests failed.")

        preview_port = detect_port()
        preview_url = f"http://{DEFAULT_PREVIEW_HOST}:{preview_port}/"
        preview_log = logs_root / "preview.log"
        preview_started = False
        preview_process: subprocess.Popen | None = None
        preview_start = time.perf_counter()
        cleanup_note = ""
        try:
            preview_process = subprocess.Popen(
                [self.npm_exe or "npm", "run", "preview", "--", "--host", DEFAULT_PREVIEW_HOST, "--port", str(preview_port)],
                cwd=str(product_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=os.environ.copy(),
            )
            deadline = time.time() + self.preview_timeout
            while time.time() < deadline:
                if preview_process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(preview_url, timeout=5) as response:
                        html = response.read(512).decode("utf-8", errors="replace")
                    if "<!doctype html" in html.lower():
                        preview_started = True
                        break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    time.sleep(1.0)
        finally:
            if preview_process is not None:
                if preview_process.poll() is None:
                    preview_process.terminate()
                    try:
                        preview_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        preview_process.kill()
                        try:
                            preview_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            cleanup_note = "Preview process did not exit cleanly during cleanup."
        write_text(
            preview_log,
            "\n".join(
                [
                    f"Preview URL: {preview_url}",
                    f"Preview success: {'yes' if preview_started else 'no'}",
                    cleanup_note,
                ]
            ),
        )
        result.log_paths["preview"] = self.rel(preview_log)
        result.phase_durations["preview"] = round(time.perf_counter() - preview_start, 2)
        result.preview_success = preview_started
        if preview_started:
            result.log_paths["preview_url"] = preview_url
        else:
            result.issues.append("Preview server did not become reachable.")

        result.screenshot_paths = self.discover_screenshots(repo_root, product_root, logs_root)
        result.timestamp_evidence = self.collect_timestamp_evidence(
            repo_root,
            product_root,
            logs_root,
            result,
            result.screenshot_paths,
        )
        hint_log_path = self.find_hint_log(repo_root, product_root)
        if hint_log_path is not None:
            result.log_paths["hints"] = self.rel(hint_log_path)
        result.hint_count = self.count_hint_events(hint_log_path)
        self.evaluate_recursive_run(repo_root, result)
        self.score_repo(repo_root, product_root, result)

    def score_repo(self, repo_root: Path, product_root: Path, result: ArmResult) -> None:
        breakdown: dict[str, float] = {}
        score_max = 0.0

        def add_score(
            label: str,
            awarded: float,
            maximum: float,
            *,
            zero_issue: str = "",
            partial_issue: str = "",
        ) -> None:
            nonlocal score_max
            score_max += maximum
            bounded = max(0.0, min(maximum, awarded))
            breakdown[label] = bounded
            if bounded == 0 and zero_issue:
                result.issues.append(zero_issue)
            elif 0 < bounded < maximum and partial_issue:
                result.issues.append(partial_issue)

        add_score("build", 20 if result.build_success else 0, 20, zero_issue="Build criterion not met.")
        add_score("test", 20 if result.test_success else 0, 20, zero_issue="Test criterion not met.")
        add_score("preview", 10 if result.preview_success else 0, 10, zero_issue="Preview criterion not met.")

        agent_log_path = self.resolve_agent_log_path(repo_root, product_root)
        agent_log_text = agent_log_path.read_text(encoding="utf-8", errors="replace") if agent_log_path.exists() else ""
        has_timestamps = bool(re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", agent_log_text))
        agent_log_score = 5.0 if has_timestamps else 0.0
        if agent_log_score == 0 and result.timestamp_evidence:
            agent_log_score = 2.5
            result.timestamp_fallback_used = True
        add_score(
            "agent_log",
            agent_log_score,
            5,
            zero_issue="Benchmark agent log is missing timestamped entries.",
            partial_issue="Benchmark agent log lacked timestamps; timestamp fallback evidence was used instead.",
        )

        source_text = self.read_repo_source(product_root)
        if self.scenario_name == "release-readiness-dashboard":
            self.score_release_dashboard_repo(source_text, result, add_score)
        else:
            self.score_planner_repo(source_text, result, add_score)

        result.hint_penalty = round(result.hint_count * max(0.0, self.args.hint_penalty), 2)
        if result.hint_penalty:
            result.issues.append(
                f"Applied hint penalty: {format_score(result.hint_penalty)} point(s) across {result.hint_count} hint event(s)."
            )

        result.score_breakdown = breakdown
        result.score_max = score_max
        result.score = max(0.0, sum(breakdown.values()) - result.hint_penalty)
        self.update_combined_benchmark_score(result)

    def score_planner_repo(self, source_text: str, result: ArmResult, add_score) -> None:
        add_score(
            "local_persistence",
            10 if "localstorage" in source_text else 0,
            10,
            zero_issue="Local persistence heuristic was not detected.",
        )
        import_export = "json.stringify" in source_text and "json.parse" in source_text
        add_score(
            "import_export",
            10 if import_export else 0,
            10,
            zero_issue="Import/export heuristic was not detected.",
        )
        search_filter = "search" in source_text and "filter" in source_text
        add_score(
            "search_filter",
            10 if search_filter else 0,
            10,
            zero_issue="Search/filter heuristic was not detected.",
        )
        grouped_view = any(marker in source_text for marker in ("todo", "in progress", "done")) and any(
            marker in source_text for marker in ("summary", "metrics", "total")
        )
        add_score(
            "grouped_view",
            5 if grouped_view else 0,
            5,
            zero_issue="Grouped planner view heuristic was not detected.",
        )
        displayed_summary = 0.0
        if "const total = filtereditems.length" in source_text or re.search(
            r"summary\s*=\s*usememo\(.*?filtereditems",
            source_text,
            flags=re.DOTALL,
        ):
            displayed_summary = 5.0
        add_score(
            "displayed_summary",
            displayed_summary,
            5,
            zero_issue="Summary metrics do not appear tied to the displayed data set.",
        )
        work_item_shape = all(marker in source_text for marker in ("priority", "status", "tag")) and (
            "duedate" in source_text or "due date" in source_text
        )
        add_score(
            "work_item_model",
            5 if work_item_shape else 0,
            5,
            zero_issue="Work-item shape heuristic was not detected.",
        )
        empty_and_error = (
            ("empty" in source_text or "no work items" in source_text)
            and ("invalid import" in source_text or "error" in source_text)
        )
        add_score(
            "empty_error_states",
            5 if empty_and_error else 0,
            5,
            zero_issue="Empty/error state heuristic was not detected.",
        )
        add_score(
            "overdue_indicator",
            5 if "overdue" in source_text else 0,
            5,
            zero_issue="Overdue-item heuristic was not detected.",
        )

    def score_release_dashboard_repo(self, source_text: str, result: ArmResult, add_score) -> None:
        has_local_storage = "localstorage" in source_text
        has_reset = "reset" in source_text and "sample" in source_text
        add_score(
            "local_persistence",
            10 if has_local_storage and has_reset else 5 if has_local_storage else 0,
            10,
            zero_issue="Local persistence or sample/reset support was not detected.",
            partial_issue="Local persistence was detected, but sample or reset handling appears incomplete.",
        )
        import_export = "json.stringify" in source_text and "json.parse" in source_text
        invalid_import = "invalid import" in source_text or "import error" in source_text or "validation" in source_text
        add_score(
            "import_export_validation",
            10 if import_export and invalid_import else 5 if import_export else 0,
            10,
            zero_issue="Import/export validation heuristic was not detected.",
            partial_issue="Import/export exists, but visible invalid-import handling appears incomplete.",
        )
        filtered_views = all(marker in source_text for marker in ("search", "filter")) and any(
            marker in source_text for marker in ("group", "view", "board", "table")
        )
        add_score(
            "filtered_views",
            10 if filtered_views else 0,
            10,
            zero_issue="Filtered dashboard or grouped-view heuristics were not detected.",
        )
        multi_release_model = all(
            marker in source_text for marker in ("release", "milestone", "owner")
        ) and any(marker in source_text for marker in ("target date", "targetdate", "window"))
        add_score(
            "multi_release_model",
            10 if multi_release_model else 0,
            10,
            zero_issue="Multi-release program data model heuristic was not detected.",
        )
        gating_dependency = (
            "approval" in source_text
            and "blocker" in source_text
            and any(marker in source_text for marker in ("dependency", "dependson", "blockedby"))
        )
        add_score(
            "gating_dependency_model",
            10 if gating_dependency else 0,
            10,
            zero_issue="Approval-gate or dependency heuristics were not detected.",
        )
        incident_risk = "incident" in source_text and "severity" in source_text and "risk" in source_text
        add_score(
            "incident_risk_model",
            5 if incident_risk else 0,
            5,
            zero_issue="Incident/risk heuristics were not detected.",
        )
        derived_readiness = "readiness" in source_text and any(
            marker in source_text for marker in ("score", "band", "health")
        )
        add_score(
            "derived_readiness",
            10 if derived_readiness else 0,
            10,
            zero_issue="Derived readiness heuristic was not detected.",
        )
        detail_drilldown = any(
            marker in source_text for marker in ("selectedrelease", "detail", "drawer", "sidepanel", "details")
        )
        add_score(
            "detail_drilldown",
            5 if detail_drilldown else 0,
            5,
            zero_issue="Release detail drill-down heuristic was not detected.",
        )
        exception_summary = "overdue" in source_text and any(
            marker in source_text for marker in ("missing approval", "approval gap", "blocker total", "critical")
        )
        add_score(
            "exception_summary",
            5 if exception_summary else 0,
            5,
            zero_issue="Exception summary heuristic was not detected.",
        )
        audit_or_snapshot = any(marker in source_text for marker in ("audit", "history", "snapshot", "timeline"))
        add_score(
            "audit_or_snapshot",
            5 if audit_or_snapshot else 0,
            5,
            zero_issue="Audit-trail or snapshot heuristic was not detected.",
        )
        empty_and_error = (
            ("empty" in source_text or "no releases" in source_text)
            and ("invalid import" in source_text or "error" in source_text)
        )
        add_score(
            "empty_error_states",
            5 if empty_and_error else 0,
            5,
            zero_issue="Empty/error state heuristic was not detected.",
        )

    def read_repo_source(self, repo_root: Path) -> str:
        parts: list[str] = []
        for path in sorted((repo_root / "src").rglob("*")):
            if path.suffix.lower() not in {".ts", ".tsx", ".css", ".json"}:
                continue
            parts.append(path.read_text(encoding="utf-8", errors="replace").lower())
        return "\n".join(parts)

    def extract_usage(self, stdout: str, stderr: str) -> dict[str, int]:
        usage: dict[str, int] = {}
        for row in load_json_lines(stdout) + load_json_lines(stderr):
            self.walk_usage(row, usage)
        combined = stdout + "\n" + stderr
        patterns = {
            "input_tokens": r"input[_ ]tokens[^0-9]*(\d+)",
            "output_tokens": r"output[_ ]tokens[^0-9]*(\d+)",
            "total_tokens": r"total[_ ]tokens[^0-9]*(\d+)",
        }
        for key, pattern in patterns.items():
            for match in re.finditer(pattern, combined, flags=re.IGNORECASE):
                usage[key] = max(usage.get(key, 0), int(match.group(1)))
        return usage

    def discover_screenshots(self, repo_root: Path, product_root: Path, logs_root: Path) -> list[str]:
        screenshot_paths: list[str] = []
        benchmark_screenshot_roots: list[Path] = []
        for candidate in (repo_root / "benchmark" / "screenshots", product_root / "benchmark" / "screenshots"):
            if candidate not in benchmark_screenshot_roots:
                benchmark_screenshot_roots.append(candidate)
        evidence_root = repo_root / ".recursive" / "run"
        search_roots = [*benchmark_screenshot_roots, logs_root]
        if evidence_root.exists():
            search_roots.append(evidence_root)

        allowed_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        excluded_parts = {"node_modules", "dist", "coverage", ".git"}

        for root in search_roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed_suffixes:
                    continue
                lower_parts = {part.lower() for part in path.parts}
                if lower_parts & excluded_parts:
                    continue
                screenshot_paths.append(self.rel(path))

        # Also include screenshot-like image paths outside the conventional folders.
        repo_candidates: list[Path] = []
        for candidate in (repo_root, product_root):
            if candidate not in repo_candidates:
                repo_candidates.append(candidate)
        for repo_candidate in repo_candidates:
            for path in sorted(repo_candidate.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed_suffixes:
                    continue
                lower_parts = {part.lower() for part in path.parts}
                if lower_parts & excluded_parts:
                    continue
                if "screenshot" not in path.name.lower():
                    continue
                rel_path = self.rel(path)
                if rel_path not in screenshot_paths:
                    screenshot_paths.append(rel_path)

        return screenshot_paths

    def collect_timestamp_evidence(
        self,
        repo_root: Path,
        product_root: Path,
        logs_root: Path,
        result: ArmResult,
        screenshot_paths: list[str],
    ) -> dict[str, str]:
        agent_log_path = self.resolve_agent_log_path(repo_root, product_root)
        candidates = [
            agent_log_path,
            product_root / "src" / "App.tsx",
            product_root / "src" / "App.test.tsx",
            logs_root / "npm-install.log",
            logs_root / "build.log",
            logs_root / "test.log",
            logs_root / "preview.log",
            logs_root / "recursive-bootstrap.log",
            logs_root / "recursive-init.log",
            self.arm_progress_path(result),
            self.workspace_root / "benchmark-status.json",
        ]
        for screenshot in screenshot_paths[:3]:
            candidate = self.workspace_root / Path(screenshot)
            candidates.append(candidate)

        evidence: dict[str, str] = {}
        for path in candidates:
            if not path.exists() or not path.is_file():
                continue
            evidence[self.rel(path)] = timestamp_from_epoch(path.stat().st_mtime)
        return evidence

    def find_hint_log(self, repo_root: Path, product_root: Path) -> Path | None:
        for search_root in (product_root, repo_root):
            for candidate_name in ("hints.md", "hint-log.md"):
                candidate = search_root / "benchmark" / candidate_name
                if candidate.exists():
                    return candidate
        return None

    def count_hint_events(self, hint_log_path: Path | None) -> int:
        if hint_log_path is None or not hint_log_path.exists():
            return 0
        text = hint_log_path.read_text(encoding="utf-8", errors="replace")
        timestamp_matches = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text)
        if timestamp_matches:
            return len(timestamp_matches)
        bullet_matches = re.findall(r"(?m)^\s*-\s+", text)
        return len(bullet_matches)

    def load_judge_metric(self, repo_root: Path, result: ArmResult) -> None:
        candidate = repo_root / "benchmark" / "judge-metric.json"
        if not candidate.exists():
            return
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result.issues.append("Judge metric file exists but is not valid JSON.")
            return
        if not isinstance(payload, dict):
            result.issues.append("Judge metric file exists but is not a JSON object.")
            return
        score = payload.get("score")
        score_max = payload.get("max")
        judge_runner = payload.get("judge_runner")
        judge_model = payload.get("judge_model")
        summary = payload.get("summary")
        notes = payload.get("notes")
        if isinstance(score, (int, float)):
            result.judge_score = float(score)
        if isinstance(score_max, (int, float)):
            result.judge_max = float(score_max)
        if isinstance(judge_runner, str):
            result.judge_runner_name = judge_runner.strip()
        if isinstance(judge_model, str):
            result.judge_model_name = judge_model.strip()
        if isinstance(summary, str):
            result.judge_summary = summary.strip()
        if isinstance(notes, list):
            result.judge_notes = [str(note).strip() for note in notes if str(note).strip()]
        result.log_paths["judge_metric"] = self.rel(candidate)

    def build_judge_candidates(self, benchmark_runner: RunnerConfig) -> list[RunnerConfig]:
        candidates: list[RunnerConfig] = []
        seen: set[tuple[str, str]] = set()

        def add_candidate(candidate: RunnerConfig) -> None:
            if candidate.executable is None:
                return
            key = (candidate.slug, candidate.model)
            if key in seen:
                return
            seen.add(key)
            candidates.append(candidate)

        add_candidate(
            RunnerConfig(
                slug="codex",
                display_name="Codex CLI",
                provider_family="codex",
                executable=shutil.which("codex"),
                model=DEFAULT_JUDGE_MODEL,
                supports_json=True,
            )
        )
        add_candidate(
            RunnerConfig(
                slug="copilot",
                display_name="GitHub Copilot CLI",
                provider_family="github-copilot",
                executable=shutil.which("copilot"),
                model=DEFAULT_JUDGE_MODEL,
                supports_json=True,
            )
        )
        add_candidate(benchmark_runner)
        return candidates

    def write_judge_brief(self, repo_root: Path, product_root: Path, result: ArmResult) -> Path:
        requirements_text = self.requirements_path.read_text(encoding="utf-8").strip()
        rubric_text = self.rubric_path.read_text(encoding="utf-8").strip()
        try:
            product_root_rel = os.path.relpath(product_root, repo_root).replace("\\", "/")
        except ValueError:
            product_root_rel = str(product_root.resolve()).replace("\\", "/")
        product_root_display = "." if product_root_rel in {"", "."} else product_root_rel
        product_src_path = "./src/" if product_root_display == "." else f"{product_root_display}/src/"
        product_benchmark_path = "./benchmark/" if product_root_display == "." else f"{product_root_display}/benchmark/"
        recursive_context = ""
        if result.arm_name == "recursive-on":
            missing = [name for name, present in result.recursive_artifact_status.items() if not present] or ["none"]
            recursive_context = (
                "\nRecursive workflow context:\n"
                f"- Recursive workflow status: {result.recursive_workflow_status}\n"
                f"- Worktree isolation status: {result.recursive_isolation_status}\n"
                f"- Worktree location: {result.recursive_worktree_location or 'n/a'}\n"
                f"- Run id: {result.run_id or 'n/a'}\n"
                f"- Run root: {result.recursive_run_root or 'n/a'}\n"
                f"- Product root: {product_root_display}\n"
                f"- Missing recursive artifacts: {', '.join(missing)}\n"
            )

        brief_text = (
            "You are the mandatory controller-side code-review judge for a recursive-mode benchmark.\n"
            "Review the repository in the current working directory against the requirements and rubric below.\n"
            "Do not modify product code or benchmark logs. Only write benchmark/judge-metric.json.\n"
            "If benchmark/judge-metric.json already exists, overwrite it.\n"
            "Use a 0-10 overall score where 10 means the implementation is highly faithful, robust, and benchmark-complete.\n"
            "Apply the evidence-form rule: if something is implemented but the required evidence form is incomplete, deduct half credit for that portion.\n"
            "Prefer concrete issues over generic comments. Return a short confirmation after writing the file.\n\n"
            "Write benchmark/judge-metric.json with this exact JSON shape:\n"
            "{\n"
            '  "score": 0,\n'
            f'  "max": {int(DEFAULT_JUDGE_MAX)},\n'
            '  "judge_runner": "<runner name>",\n'
            '  "judge_model": "<model name>",\n'
            '  "summary": "<1-2 sentence summary>",\n'
            '  "notes": ["<concrete finding>", "<concrete finding>"]\n'
            "}\n\n"
            f"Scenario: {self.scenario_name}\n"
            f"Scenario title: {self.scenario_title}\n"
            f"Scenario tier: {self.scenario_tier}\n"
            f"Benchmark arm: {result.arm_name}\n"
            f"Benchmark runner: {result.runner_name}\n"
            f"Benchmark model: {result.model}\n"
            f"Build success: {'yes' if result.build_success else 'no'}\n"
            f"Test success: {'yes' if result.test_success else 'no'}\n"
            f"Preview success: {'yes' if result.preview_success else 'no'}\n"
            f"Screenshots found: {len(result.screenshot_paths)}\n"
            f"Heuristic score: {format_score(result.score)}/{format_score(result.score_max)}\n"
            f"Known issues so far: {', '.join(result.issues) if result.issues else 'none'}\n"
            f"{recursive_context}\n"
            "Repository paths to inspect:\n"
            f"- {product_src_path}\n"
            f"- {product_benchmark_path}\n"
            "- benchmark/\n"
            "- .recursive/run/\n"
            "- .worktrees/\n\n"
            "Benchmark requirements:\n\n"
            f"{requirements_text}\n\n"
            "Benchmark scoring rubric:\n\n"
            f"{rubric_text}\n"
        )
        brief_path = repo_root / "benchmark" / "judge-brief.md"
        write_text(brief_path, brief_text)
        return brief_path

    def reset_judge_result(self, result: ArmResult) -> None:
        result.judge_score = None
        result.judge_max = None
        result.judge_runner_name = ""
        result.judge_model_name = ""
        result.judge_summary = ""
        result.judge_notes = []

    def run_judge_review(
        self,
        repo_root: Path,
        product_root: Path,
        logs_root: Path,
        benchmark_runner: RunnerConfig,
        result: ArmResult,
    ) -> None:
        judge_metric_path = repo_root / "benchmark" / "judge-metric.json"
        if judge_metric_path.exists():
            judge_metric_path.unlink()
        self.reset_judge_result(result)
        judge_brief_path = self.write_judge_brief(repo_root, product_root, result)
        result.log_paths["judge_brief"] = self.rel(judge_brief_path)
        judge_prompt = (
            "Read benchmark/judge-brief.md in the current repository, inspect the referenced files, "
            "write benchmark/judge-metric.json, and return a short confirmation."
        )
        attempt_notes: list[str] = []

        for judge_runner in self.build_judge_candidates(benchmark_runner):
            model_slug = re.sub(r"[^a-z0-9]+", "-", judge_runner.model.lower()).strip("-") or "model"
            log_stem = f"judge-{judge_runner.slug}-{model_slug}"
            record, stdout_log, stderr_log = self.run_model_prompt(
                repo_root,
                logs_root,
                runner_slug=judge_runner.slug,
                executable=judge_runner.executable,
                model=judge_runner.model,
                prompt_text=judge_prompt,
                log_stem=log_stem,
                timeout_seconds=self.judge_timeout,
            )
            attempt_notes.append(f"{judge_runner.display_name} {judge_runner.model}: exit {record.returncode}")
            if not judge_metric_path.exists():
                continue
            self.reset_judge_result(result)
            self.load_judge_metric(repo_root, result)
            if result.judge_score is not None:
                result.judge_runner_name = judge_runner.display_name
                result.judge_model_name = judge_runner.model
                result.log_paths["judge_stdout"] = self.rel(stdout_log)
                result.log_paths["judge_stderr"] = self.rel(stderr_log)
                if judge_runner.model != DEFAULT_JUDGE_MODEL:
                    result.judge_notes.insert(
                        0,
                        f"Judge fallback used {judge_runner.display_name} {judge_runner.model} because {DEFAULT_JUDGE_MODEL} was unavailable.",
                    )
                self.update_combined_benchmark_score(result)
                return
            judge_metric_path.unlink(missing_ok=True)

        self.reset_judge_result(result)
        result.judge_summary = "Automatic judge attempts did not produce a structured metric."
        result.judge_notes = attempt_notes
        result.issues.append("Automatic code-review judge did not produce a structured metric.")
        self.update_combined_benchmark_score(result)

    def evaluate_recursive_run(self, repo_root: Path, result: ArmResult) -> None:
        if result.arm_name != "recursive-on":
            result.recursive_workflow_status = "n/a"
            result.recursive_isolation_status = "n/a"
            return
        if not result.run_id:
            result.recursive_workflow_status = "missing-run-id"
            result.recursive_isolation_status = "missing-run-id"
            result.issues.append("Recursive benchmark arm is missing a run id.")
            return

        run_root = repo_root / ".recursive" / "run" / result.run_id
        result.recursive_run_root = self.rel(run_root)
        result.log_paths.setdefault("recursive_run_root", self.rel(run_root))
        if not run_root.exists():
            result.recursive_workflow_status = "missing-run-root"
            result.recursive_isolation_status = "missing-run-root"
            result.issues.append("Recursive benchmark run folder was not created.")
            return

        artifact_status: dict[str, bool] = {}
        missing_files: list[str] = []
        for file_name in REQUIRED_RECURSIVE_RUN_FILES:
            file_exists = (run_root / file_name).exists()
            artifact_status[file_name] = file_exists
            if not file_exists:
                missing_files.append(file_name)
        result.recursive_artifact_status = artifact_status

        if missing_files:
            result.recursive_workflow_status = "incomplete"
            result.issues.append(
                "Recursive workflow artifacts missing: " + ", ".join(missing_files) + "."
            )
            if "00-worktree.md" in missing_files:
                result.recursive_isolation_status = "missing-worktree-doc"
            return

        result.recursive_workflow_status = "complete"
        requirements_text = (run_root / "00-requirements.md").read_text(encoding="utf-8", errors="replace")
        workflow_version = self.read_workflow_version(requirements_text) or "missing"
        result.recursive_workflow_profile = workflow_version

        phase1_text = (run_root / "01-as-is.md").read_text(encoding="utf-8", errors="replace")
        phase2_text = (run_root / "02-to-be-plan.md").read_text(encoding="utf-8", errors="replace")
        missing_guardrails: list[str] = []
        if workflow_version != "recursive-mode-audit-v2":
            missing_guardrails.append(f"workflow-version={workflow_version}")
        if not self.has_heading(phase1_text, "Source Requirement Inventory"):
            missing_guardrails.append("01-as-is.md:Source Requirement Inventory")
        if not self.has_heading(phase2_text, "Requirement Mapping"):
            missing_guardrails.append("02-to-be-plan.md:Requirement Mapping")
        if not self.has_heading(phase2_text, "Plan Drift Check"):
            missing_guardrails.append("02-to-be-plan.md:Plan Drift Check")
        if not self.has_heading(phase2_text, "Requirement Completion Status"):
            missing_guardrails.append("02-to-be-plan.md:Requirement Completion Status")
        result.recursive_phase2_guardrails = "present" if not missing_guardrails else ", ".join(missing_guardrails)
        if missing_guardrails:
            result.recursive_workflow_status = "phase2-guardrails-missing"
            result.issues.append(
                "Recursive Phase 1/2 guardrails missing or outdated: " + ", ".join(missing_guardrails) + "."
            )

        worktree_doc = run_root / "00-worktree.md"
        worktree_text = worktree_doc.read_text(encoding="utf-8", errors="replace")
        _, isolation_status, raw_location = self.parse_worktree_location(repo_root, worktree_text)
        result.recursive_isolation_status = isolation_status
        result.recursive_worktree_location = raw_location
        if isolation_status == "missing":
            result.issues.append("Recursive worktree doc does not record a parsable worktree location.")
        elif isolation_status == "missing-path":
            result.issues.append("Recursive worktree doc points to a worktree path that does not exist.")

    def append_arm_comparisons(self, summary_lines: list[str]) -> None:
        grouped: dict[str, dict[str, ArmResult]] = {}
        for result in self.results:
            grouped.setdefault(result.runner_slug, {})[result.arm_name] = result

        sections_added = False
        for runner_slug, pair in grouped.items():
            off = pair.get("recursive-off")
            on = pair.get("recursive-on")
            if off is None or on is None:
                continue
            if not sections_added:
                summary_lines.extend(["## Arm comparison", ""])
                sections_added = True

            runner_name = on.runner_name or off.runner_name or runner_slug
            summary_lines.extend(
                [
                    f"### {runner_name}",
                    "",
                    f"- Benchmark score blends heuristic coverage ({int(DEFAULT_HEURISTIC_WEIGHT * 100)}%) and judge review ({int(DEFAULT_JUDGE_WEIGHT * 100)}%).",
                    "",
                    "| Metric | recursive-off | recursive-on | Delta (on-off) |",
                    "| --- | --- | --- | --- |",
                    f"| Benchmark outcome | `{off.status}` | `{on.status}` | n/a |",
                    f"| Benchmark score | `{format_score(off.benchmark_score or 0)}/{format_score(off.benchmark_score_max) if off.benchmark_score is not None else 'n/a'}` | `{format_score(on.benchmark_score or 0)}/{format_score(on.benchmark_score_max) if on.benchmark_score is not None else 'n/a'}` | `{format_score((on.benchmark_score or 0) - (off.benchmark_score or 0)) if off.benchmark_score is not None and on.benchmark_score is not None else 'n/a'}` |",
                    f"| Agent status | `{off.agent_status}` | `{on.agent_status}` | n/a |",
                    f"| Product outcome | `{off.product_status}` | `{on.product_status}` | n/a |",
                    f"| Recursive workflow | `{off.recursive_workflow_status}` | `{on.recursive_workflow_status}` | n/a |",
                    f"| Recursive workflow profile | `{off.recursive_workflow_profile}` | `{on.recursive_workflow_profile}` | n/a |",
                    f"| Phase 1/2 guardrails | `{off.recursive_phase2_guardrails}` | `{on.recursive_phase2_guardrails}` | n/a |",
                    f"| Worktree isolation | `{off.recursive_isolation_status}` | `{on.recursive_isolation_status}` | n/a |",
                    f"| Duration seconds | `{off.duration_seconds:.2f}` | `{on.duration_seconds:.2f}` | `{on.duration_seconds - off.duration_seconds:+.2f}` |",
                    f"| Build | `{'pass' if off.build_success else 'fail'}` | `{'pass' if on.build_success else 'fail'}` | n/a |",
                    f"| Test | `{'pass' if off.test_success else 'fail'}` | `{'pass' if on.test_success else 'fail'}` | n/a |",
                    f"| Preview | `{'pass' if off.preview_success else 'fail'}` | `{'pass' if on.preview_success else 'fail'}` | n/a |",
                    f"| Heuristic harness score | `{format_score(off.score)}/{format_score(off.score_max)}` | `{format_score(on.score)}/{format_score(on.score_max)}` | `{format_score(on.score - off.score)}` |",
                    f"| Screenshots | `{len(off.screenshot_paths)}` | `{len(on.screenshot_paths)}` | `{len(on.screenshot_paths) - len(off.screenshot_paths):+d}` |",
                    f"| Hint penalty | `{format_score(off.hint_penalty)}` | `{format_score(on.hint_penalty)}` | `{format_score(on.hint_penalty - off.hint_penalty)}` |",
                    f"| Timestamp fallback used | `{'yes' if off.timestamp_fallback_used else 'no'}` | `{'yes' if on.timestamp_fallback_used else 'no'}` | n/a |",
                ]
            )
            off_metric = (
                f"{format_score(off.judge_score)}/{format_score(off.judge_max or 0)}"
                if off.judge_score is not None
                else "n/a"
            )
            on_metric = (
                f"{format_score(on.judge_score)}/{format_score(on.judge_max or 0)}"
                if on.judge_score is not None
                else "n/a"
            )
            delta_text = (
                format_score((on.judge_score or 0) - (off.judge_score or 0))
                if off.judge_score is not None and on.judge_score is not None
                else "n/a"
            )
            summary_lines.append(f"| Code-review judge metric | `{off_metric}` | `{on_metric}` | `{delta_text}` |")

            phase_keys = sorted(set(off.phase_durations) | set(on.phase_durations))
            if phase_keys:
                summary_lines.extend(["", "Phase deltas:", ""])
                summary_lines.extend(
                    [
                        "| Phase | recursive-off (s) | recursive-on (s) | Delta (on-off) |",
                        "| --- | ---: | ---: | ---: |",
                    ]
                )
                for key in phase_keys:
                    off_value = off.phase_durations.get(key)
                    on_value = on.phase_durations.get(key)
                    off_text = f"{off_value:.2f}" if off_value is not None else "n/a"
                    on_text = f"{on_value:.2f}" if on_value is not None else "n/a"
                    delta_text = (
                        f"{(on_value - off_value):+.2f}"
                        if off_value is not None and on_value is not None
                        else "n/a"
                    )
                    summary_lines.append(f"| `{key}` | {off_text} | {on_text} | {delta_text} |")

            summary_lines.extend(["", "Score and issue comparison:", ""])
            summary_lines.extend(
                [
                    "| Entry | recursive-off | recursive-on | Delta / note |",
                    "| --- | --- | --- | --- |",
                    f"| `normalized:heuristic` | `{format_score(off.heuristic_percentage or 0)}/100` | `{format_score(on.heuristic_percentage or 0)}/100` | `{format_score((on.heuristic_percentage or 0) - (off.heuristic_percentage or 0)) if off.heuristic_percentage is not None and on.heuristic_percentage is not None else 'n/a'}` |",
                    f"| `normalized:judge` | `{format_score(off.judge_percentage or 0)}/100` | `{format_score(on.judge_percentage or 0)}/100` | `{format_score((on.judge_percentage or 0) - (off.judge_percentage or 0)) if off.judge_percentage is not None and on.judge_percentage is not None else 'n/a'}` |",
                    f"| `normalized:benchmark` | `{format_score(off.benchmark_score or 0)}/100` | `{format_score(on.benchmark_score or 0)}/100` | `{format_score((on.benchmark_score or 0) - (off.benchmark_score or 0)) if off.benchmark_score is not None and on.benchmark_score is not None else 'n/a'}` |",
                ]
            )
            score_keys = sorted(set(off.score_breakdown) | set(on.score_breakdown))
            for key in score_keys:
                off_value = off.score_breakdown.get(key, 0.0)
                on_value = on.score_breakdown.get(key, 0.0)
                summary_lines.append(
                    f"| `score:{key}` | `{format_score(off_value)}` | `{format_score(on_value)}` | `{format_score(on_value - off_value)}` |"
                )

            all_issues = sorted(set(off.issues) | set(on.issues))
            for issue in all_issues:
                off_state = "present" if issue in off.issues else "absent"
                on_state = "present" if issue in on.issues else "absent"
                if off_state == on_state == "present":
                    note = "present on both"
                elif off_state == "present":
                    note = "off only"
                elif on_state == "present":
                    note = "on only"
                else:
                    note = "n/a"
                summary_lines.append(f"| issue: {issue} | `{off_state}` | `{on_state}` | {note} |")
            summary_lines.append("")

    def walk_usage(self, value, usage: dict[str, int]) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                normalized = key.lower()
                if isinstance(inner, int) and ("token" in normalized or normalized.endswith("usage")):
                    usage[normalized] = max(usage.get(normalized, 0), inner)
                else:
                    self.walk_usage(inner, usage)
        elif isinstance(value, list):
            for item in value:
                self.walk_usage(item, usage)

    def write_report(self) -> Path:
        report_path = self.workspace_root / "benchmark-report.md"
        for result in self.results:
            self.update_combined_benchmark_score(result)
        summary_lines = [
            "# recursive-mode benchmark report",
            "",
            f"- Generated at: `{timestamp_utc()}`",
            f"- Scenario: `{self.scenario_name}`",
            f"- Scenario title: `{self.scenario_title}`",
            f"- Scenario tier: `{self.scenario_tier}`",
            f"- Workspace: `{self.workspace_root}`",
            f"- Prepare only: `{self.args.prepare_only}`",
            f"- Timeout minutes per arm: `{self.args.max_minutes}`",
            f"- Arm execution mode requested: `{self.args.arm_mode}`",
            f"- Benchmark score weighting: `{int(DEFAULT_HEURISTIC_WEIGHT * 100)}% heuristic + {int(DEFAULT_JUDGE_WEIGHT * 100)}% judge`",
            "",
        ]
        if self.effective_arm_modes:
            mode_summary = ", ".join(
                f"{runner_slug}={mode}" for runner_slug, mode in sorted(self.effective_arm_modes.items())
            )
            summary_lines.insert(-1, f"- Effective arm execution by runner: `{mode_summary}`")
        if self.summary_notes:
            summary_lines.extend(["## Notes", ""])
            summary_lines.extend(f"- {note}" for note in self.summary_notes)
            summary_lines.append("")

        summary_lines.extend(
            [
                "## Scoreboard",
                "",
                "| Runner | Arm | Model | Outcome | Benchmark score | Agent status | Product outcome | Recursive workflow | Worktree isolation | Duration (s) | Build | Test | Preview | Heuristic score | Judge metric | Screenshots | Tokens |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for result in self.results:
            token_text = ", ".join(f"{key}={value}" for key, value in sorted(result.token_usage.items())) or "n/a"
            judge_metric_text = (
                f"{format_score(result.judge_score)}/{format_score(result.judge_max or 0)}"
                if result.judge_score is not None
                else "n/a"
            )
            benchmark_score_text = (
                f"{format_score(result.benchmark_score or 0)}/{format_score(result.benchmark_score_max)}"
                if result.benchmark_score is not None
                else "n/a"
            )
            summary_lines.append(
                "| {runner} | {arm} | `{model}` | {status} | {benchmark_score} | {agent_status} | {product_status} | {workflow} | {isolation} | {duration:.2f} | {build} | {test} | {preview} | {score}/{score_max} | {judge_metric} | {screenshots} | {tokens} |".format(
                    runner=result.runner_name,
                    arm=result.arm_name,
                    model=result.model,
                    status=result.status,
                    benchmark_score=benchmark_score_text,
                    agent_status=result.agent_status,
                    product_status=result.product_status,
                    workflow=result.recursive_workflow_status,
                    isolation=result.recursive_isolation_status,
                    duration=result.duration_seconds,
                    build="pass" if result.build_success else "fail",
                    test="pass" if result.test_success else "fail",
                    preview="pass" if result.preview_success else "fail",
                    score=format_score(result.score),
                    score_max=format_score(result.score_max),
                    judge_metric=judge_metric_text,
                    screenshots=len(result.screenshot_paths),
                    tokens=token_text,
                )
            )
        summary_lines.append("")
        self.append_arm_comparisons(summary_lines)

        summary_lines.extend(["## Detailed results", ""])
        for result in self.results:
            summary_lines.extend(
                [
                    f"### {result.runner_name} - {result.arm_name}",
                    "",
                    f"- Provider family: `{result.provider_family}`",
                    f"- Model: `{result.model}`",
                    f"- Benchmark outcome: `{result.status}`",
                    f"- Agent status: `{result.agent_status}`",
                    f"- Product outcome: `{result.product_status}`",
                    f"- Recursive workflow: `{result.recursive_workflow_status}`",
                    f"- Recursive workflow profile: `{result.recursive_workflow_profile}`",
                    f"- Phase 1/2 guardrails: `{result.recursive_phase2_guardrails}`",
                    f"- Worktree isolation: `{result.recursive_isolation_status}`",
                    (
                        f"- Worktree location: `{result.recursive_worktree_location}`"
                        if result.recursive_worktree_location
                        else "- Worktree location: `n/a`"
                    ),
                    f"- Repo: `{result.repo_root}`" if result.repo_root else "- Repo: `n/a`",
                    (
                        f"- Product root: `{result.product_root}`"
                        if result.product_root
                        else "- Product root: `n/a`"
                    ),
                    f"- Recursive run id: `{result.run_id}`" if result.run_id else "- Recursive run id: `n/a`",
                    (
                        f"- Recursive run root: `{result.recursive_run_root}`"
                        if result.recursive_run_root
                        else "- Recursive run root: `n/a`"
                    ),
                    f"- Duration seconds: `{result.duration_seconds:.2f}`",
                    f"- Agent exit code: `{result.agent_exit_code}`",
                    f"- Timed out: `{'yes' if result.timed_out else 'no'}`",
                    (
                        f"- Benchmark score: `{format_score(result.benchmark_score or 0)}/{format_score(result.benchmark_score_max)}`"
                        if result.benchmark_score is not None
                        else "- Benchmark score: `n/a`"
                    ),
                    f"- Benchmark score method: `{result.benchmark_score_method}`",
                    (
                        f"- Normalized heuristic score: `{format_score(result.heuristic_percentage or 0)}/100`"
                        if result.heuristic_percentage is not None
                        else "- Normalized heuristic score: `n/a`"
                    ),
                    (
                        f"- Normalized judge score: `{format_score(result.judge_percentage or 0)}/100`"
                        if result.judge_percentage is not None
                        else "- Normalized judge score: `n/a`"
                    ),
                    f"- Heuristic harness score: `{format_score(result.score)}/{format_score(result.score_max)}`",
                    (
                        f"- Code-review judge metric: `{format_score(result.judge_score)}/{format_score(result.judge_max or 0)}`"
                        if result.judge_score is not None
                        else "- Code-review judge metric: `n/a`"
                    ),
                    (
                        f"- Judge reviewer: `{result.judge_runner_name} {result.judge_model_name}`"
                        if result.judge_runner_name and result.judge_model_name
                        else "- Judge reviewer: `n/a`"
                    ),
                    f"- Hint count: `{result.hint_count}`",
                    f"- Hint penalty: `{format_score(result.hint_penalty)}`",
                    f"- Timestamp fallback used: `{'yes' if result.timestamp_fallback_used else 'no'}`",
                    "",
                    "#### Score breakdown",
                    "",
                ]
            )
            if result.score_breakdown:
                for key, value in sorted(result.score_breakdown.items()):
                    summary_lines.append(f"- `{key}`: {format_score(value)}")
            else:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Issues", ""])
            if result.issues:
                for issue in result.issues:
                    summary_lines.append(f"- {issue}")
            else:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Artifact paths", ""])
            if result.log_paths:
                for key, value in sorted(result.log_paths.items()):
                    summary_lines.append(f"- `{key}`: `{value}`")
            else:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Recursive run artifacts", ""])
            if result.recursive_artifact_status:
                for file_name, present in result.recursive_artifact_status.items():
                    summary_lines.append(f"- `{file_name}`: `{'present' if present else 'missing'}`")
            else:
                summary_lines.append("- n/a")
            summary_lines.extend(["", "#### Screenshots", ""])
            if result.screenshot_paths:
                for screenshot in result.screenshot_paths:
                    summary_lines.append(f"- `{screenshot}`")
                    summary_lines.append(f"![{Path(screenshot).name}]({screenshot})")
            else:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Phase durations", ""])
            if result.phase_durations:
                for key, value in sorted(result.phase_durations.items()):
                    summary_lines.append(f"- `{key}`: `{value:.2f}`")
            else:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Judge notes", ""])
            if result.judge_summary:
                summary_lines.append(f"- Summary: {result.judge_summary}")
            if result.judge_notes:
                for note in result.judge_notes:
                    summary_lines.append(f"- {note}")
            elif not result.judge_summary:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Timestamp evidence", ""])
            if result.timestamp_evidence:
                for key, value in sorted(result.timestamp_evidence.items()):
                    summary_lines.append(f"- `{key}`: `{value}`")
            else:
                summary_lines.append("- none")
            summary_lines.append("")

        write_text(report_path, "\n".join(summary_lines))
        return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired recursive-mode benchmarks in disposable repos.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default=DEFAULT_SCENARIO, help="Scenario fixture to benchmark.")
    parser.add_argument("--runner", choices=["copilot", "codex", "kimi", "both", "all"], default="all", help="Runner to benchmark.")
    parser.add_argument("--workspace-root", default="", help="Directory to place benchmark workspaces. Defaults to a temp folder.")
    parser.add_argument("--copilot-model", default="gpt-5.4", help="Model string for GitHub Copilot CLI.")
    parser.add_argument("--codex-model", default="gpt-5.1", help="Model string for Codex CLI.")
    parser.add_argument("--kimi-model", default="kimi-k2-5", help="Model string for Kimi CLI.")
    parser.add_argument("--max-minutes", type=int, default=DEFAULT_TIMEOUT_MINUTES, help="Per-arm benchmark timeout in minutes.")
    parser.add_argument("--command-timeout", type=int, default=900, help="Timeout in seconds for setup and evaluation commands.")
    parser.add_argument("--preview-timeout", type=int, default=45, help="Timeout in seconds when waiting for preview readiness.")
    parser.add_argument("--npm-command", default="npm", help="npm executable name or path.")
    parser.add_argument("--arm-mode", choices=["sequential", "parallel"], default="sequential", help="Whether to run recursive-off and recursive-on sequentially or in parallel.")
    parser.add_argument("--hint-penalty", type=float, default=5.0, help="Points deducted per hint event recorded in benchmark/hints.md.")
    parser.add_argument("--prepare-only", action="store_true", help="Set up repos and prompts but do not run agent commands.")
    parser.add_argument("--skip-npm-install", action="store_true", help="Skip npm install during repo preparation.")
    parser.add_argument("--list-scenarios", action="store_true", help="List packaged benchmark scenarios and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_scenarios:
        for slug, metadata in SCENARIOS.items():
            print(f"{slug} [{metadata['tier']}] - {metadata['title']}")
        return 0
    harness = BenchmarkHarness(args)
    harness.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
