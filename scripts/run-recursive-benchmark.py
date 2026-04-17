#!/usr/bin/env python3
"""
Disposable paired benchmark harness for recursive-mode.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import urllib.error
import urllib.request
import zipfile
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
        "runtime": "node-vite",
    },
    "team-capacity-board": {
        "title": "Team Capacity Board",
        "tier": "medium",
        "runtime": "node-vite",
    },
    "release-readiness-dashboard": {
        "title": "Release Readiness Dashboard",
        "tier": "hard",
        "runtime": "node-vite",
    },
    "scientific-calculator-rust": {
        "title": "Scientific Calculator (Rust/WASM)",
        "tier": "xhard",
        "runtime": "rust-wasm",
    },
}

NODE_SOURCE_EXTENSIONS = {".ts", ".tsx", ".css", ".json"}
RUST_WASM_SOURCE_EXTENSIONS = {".rs", ".css", ".html", ".toml", ".json", ".js"}
IGNORED_SOURCE_DIRS = {
    ".git",
    ".recursive",
    ".worktrees",
    "benchmark",
    "dist",
    "node_modules",
    "target",
}
BENCHMARK_TOOLCHAIN_DIRNAME = ".benchmark-toolchain"
TRANSIENT_RUNTIME_DIR_MARKERS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".tox",
    ".nox",
    ".target",
    ".cargo-target-dir",
    ".playwright-mcp",
}
ALLOWED_CONTROL_PLANE_PREFIXES = (
    ".recursive/",
    ".worktrees/",
    "benchmark/",
    ".agent/",
    ".codex/",
)
EXPLICIT_PRODUCT_FILE_NAMES = {
    "Cargo.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}
RECURSIVE_EVALUATION_ISSUE_PREFIXES = (
    "Recursive run lint timed out before benchmark closeout could be confirmed.",
    "Recursive run artifacts failed controller-side lint.",
    "Recursive workflow artifacts missing: ",
    "Recursive Phase 1/2 guardrails missing or outdated: ",
    "Recursive worktree doc does not record a parsable worktree location.",
    "Recursive worktree doc points to a worktree path that does not exist.",
)

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
DEFAULT_RUST_TOOL_TIMEOUT_SECONDS = 90 * 60
TRUNK_VERSION = "0.21.14"
LOCK_HASH_LINE_RE = re.compile(r"(?m)^[ \t]*LockHash:.*(?:\n|$)")


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


@dataclass(frozen=True)
class BenchmarkRequirementSpec:
    requirement_id: str
    title: str
    source_quote: str


@dataclass
class ArmResult:
    runner_slug: str
    runner_name: str
    provider_family: str
    model: str
    arm_name: str
    repo_root: str = ""
    product_root: str = ""
    expected_product_root: str = ""
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
    recursive_delivery_status: str = "n/a"
    recursive_claimed_files: list[str] = field(default_factory=list)
    recursive_product_change_paths: list[str] = field(default_factory=list)
    recursive_root_product_drift: list[str] = field(default_factory=list)
    recursive_missing_claimed_files: list[str] = field(default_factory=list)
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
    judge_entry_adjustments: dict[str, float] = field(default_factory=dict)
    judge_entry_adjustment_reasons: dict[str, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    log_paths: dict[str, str] = field(default_factory=dict)
    screenshot_paths: list[str] = field(default_factory=list)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    score_breakdown_max: dict[str, float] = field(default_factory=dict)
    judge_adjusted_score_breakdown: dict[str, float] = field(default_factory=dict)
    judge_adjusted_score: float | None = None
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


def _retry_remove_readonly(function, path: str, excinfo) -> None:
    os.chmod(path, 0o700)
    function(path)


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, onexc=_retry_remove_readonly)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_for_lock_hash(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return LOCK_HASH_LINE_RE.sub("", normalized)


def lock_hash_from_content(content: str) -> str:
    normalized = normalize_for_lock_hash(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


def normalize_benchmark_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    normalized = re.sub(r"^[.]/+", "", normalized)
    return normalized.strip("/")


def dedupe_preserve_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def parse_git_status_paths(status_output: str) -> list[str]:
    paths: list[str] = []
    for raw_line in status_output.splitlines():
        if not raw_line.strip():
            continue
        line = raw_line.rstrip()
        payload = line[3:] if len(line) > 3 else line
        if " -> " in payload:
            payload = payload.rsplit(" -> ", 1)[1]
        payload = payload.strip().strip('"')
        normalized = normalize_benchmark_path(payload)
        if normalized:
            paths.append(normalized)
    return dedupe_preserve_order(paths)


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
        self.cargo_exe = shutil.which("cargo")
        self.rustup_exe = shutil.which("rustup")
        self.trunk_exe = shutil.which("trunk")
        self.runner_configs = self._build_runner_configs()
        self.kimi_config_path = Path.home() / ".kimi" / "config.toml"
        self.ensure_workspace_ignored()

    def _make_workspace(self) -> Path:
        if self.args.workspace_root:
            root = Path(self.args.workspace_root).resolve()
            root.mkdir(parents=True, exist_ok=True)
            return root
        default_root = self.repo_source_root / ".benchmark-workspaces"
        default_root.mkdir(parents=True, exist_ok=True)
        workspace = default_root / f"{self.scenario_name}-{uuid.uuid4().hex[:8]}"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def ensure_workspace_ignored(self) -> None:
        gitignore_path = self.repo_source_root / ".gitignore"
        benchmark_ignore = ".benchmark-workspaces/"
        toolchain_ignore = f"{BENCHMARK_TOOLCHAIN_DIRNAME}/"
        existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        existing_lines = {line.strip() for line in existing.splitlines()}
        additions: list[str] = []
        try:
            self.workspace_root.resolve().relative_to(self.repo_source_root.resolve())
            if self.workspace_root.name == ".benchmark-workspaces" or benchmark_ignore in self.workspace_root.as_posix():
                if benchmark_ignore not in existing_lines:
                    additions.extend(["# Local benchmark workspaces", benchmark_ignore])
        except ValueError:
            pass
        if toolchain_ignore not in existing_lines:
            additions.extend(["# Local benchmark toolchain cache", toolchain_ignore])
        if not additions:
            return
        addition = "\n".join(additions)
        if existing.strip():
            append_text(gitignore_path, addition)
        else:
            write_text(gitignore_path, addition)

    def uses_rust_wasm_toolchain(self) -> bool:
        return self.scenario_meta.get("runtime") == "rust-wasm"

    def source_extensions(self) -> set[str]:
        return RUST_WASM_SOURCE_EXTENSIONS if self.uses_rust_wasm_toolchain() else NODE_SOURCE_EXTENSIONS

    def add_issue(self, result: ArmResult, message: str) -> None:
        if message and message not in result.issues:
            result.issues.append(message)

    def normalize_result_lists(self, result: ArmResult) -> None:
        result.issues = dedupe_preserve_order(result.issues)
        result.screenshot_paths = dedupe_preserve_order(result.screenshot_paths)
        result.recursive_claimed_files = dedupe_preserve_order(result.recursive_claimed_files)
        result.recursive_product_change_paths = dedupe_preserve_order(result.recursive_product_change_paths)
        result.recursive_root_product_drift = dedupe_preserve_order(result.recursive_root_product_drift)
        result.recursive_missing_claimed_files = dedupe_preserve_order(result.recursive_missing_claimed_files)

    def clear_recursive_evaluation_issues(self, result: ArmResult) -> None:
        result.issues = [
            issue
            for issue in result.issues
            if not any(issue.startswith(prefix) for prefix in RECURSIVE_EVALUATION_ISSUE_PREFIXES)
        ]

    def is_control_plane_path(self, rel_path: str) -> bool:
        normalized = normalize_benchmark_path(rel_path)
        if not normalized:
            return False
        if normalized == "AGENTS.md":
            return True
        return normalized.startswith(ALLOWED_CONTROL_PLANE_PREFIXES)

    def is_product_path(self, rel_path: str) -> bool:
        normalized = normalize_benchmark_path(rel_path)
        if not normalized or self.is_control_plane_path(normalized):
            return False
        parts = [part.lower() for part in normalized.split("/") if part]
        if any(part in IGNORED_SOURCE_DIRS or part in TRANSIENT_RUNTIME_DIR_MARKERS for part in parts[:-1]):
            return False
        path = Path(normalized)
        if path.name in EXPLICIT_PRODUCT_FILE_NAMES:
            return True
        return path.suffix.lower() in self.source_extensions()

    def benchmark_toolchain_root(self) -> Path:
        return self.repo_source_root / BENCHMARK_TOOLCHAIN_DIRNAME

    def rust_wasm_env(self) -> dict[str, str]:
        if not self.uses_rust_wasm_toolchain():
            return {}
        toolchain_root = self.benchmark_toolchain_root()
        cargo_root = toolchain_root / "cargo-root"
        target_root = toolchain_root / "target"
        temp_root = toolchain_root / "tmp"
        cargo_root.mkdir(parents=True, exist_ok=True)
        target_root.mkdir(parents=True, exist_ok=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        install_bin = cargo_root / "bin"
        install_bin.mkdir(parents=True, exist_ok=True)
        existing_path = os.environ.get("PATH", "")
        merged_path = str(install_bin)
        if existing_path:
            merged_path = merged_path + os.pathsep + existing_path
        return {
            "CARGO_TARGET_DIR": str(target_root),
            "TEMP": str(temp_root),
            "TMP": str(temp_root),
            "TMPDIR": str(temp_root),
            "PATH": merged_path,
        }

    def require_trunk_executable(self) -> str:
        if self.trunk_exe:
            return self.trunk_exe
        toolchain_bin = self.benchmark_toolchain_root() / "cargo-root" / "bin"
        for candidate in (toolchain_bin / "trunk.exe", toolchain_bin / "trunk"):
            if candidate.exists():
                self.trunk_exe = str(candidate)
                return self.trunk_exe
        cargo_bin_trunk = Path.home() / ".cargo" / "bin" / "trunk.exe"
        if cargo_bin_trunk.exists():
            self.trunk_exe = str(cargo_bin_trunk)
            return self.trunk_exe
        cargo_bin_trunk = Path.home() / ".cargo" / "bin" / "trunk"
        if cargo_bin_trunk.exists():
            self.trunk_exe = str(cargo_bin_trunk)
            return self.trunk_exe
        raise BenchmarkError("Trunk is required for the Rust/WASM benchmark scenario but was not available.")

    def build_command(self) -> list[str]:
        if self.uses_rust_wasm_toolchain():
            return [self.require_trunk_executable(), "build", "--release"]
        return [self.npm_exe or "npm", "run", "build"]

    def test_command(self) -> list[str]:
        if self.uses_rust_wasm_toolchain():
            if not self.cargo_exe:
                raise BenchmarkError("cargo is required for the Rust/WASM benchmark scenario but was not available.")
            return [self.cargo_exe, "test"]
        return [self.npm_exe or "npm", "run", "test"]

    def preview_command(self, port: int) -> list[str]:
        if self.uses_rust_wasm_toolchain():
            return [
                self.require_trunk_executable(),
                "serve",
                "--release",
                "--address",
                DEFAULT_PREVIEW_HOST,
                "--port",
                str(port),
            ]
        return [self.npm_exe or "npm", "run", "preview", "--", "--host", DEFAULT_PREVIEW_HOST, "--port", str(port)]

    def prepare_rust_wasm_toolchain(self, logs_root: Path, result: ArmResult) -> None:
        if not self.cargo_exe or not self.rustup_exe:
            raise BenchmarkError("Rust/WASM benchmark scenarios require both cargo and rustup to be installed.")

        self.write_arm_progress(
            result,
            "preparing-rust-toolchain",
            detail="Preparing wasm target and installing Trunk for the Rust/WASM benchmark scenario.",
        )

        target_command = [self.rustup_exe, "target", "add", "wasm32-unknown-unknown"]
        target_result = self.run_command(
            target_command,
            cwd=self.repo_source_root,
            timeout_seconds=max(self.command_timeout, 900),
            env=self.rust_wasm_env(),
            check=False,
        )
        self.write_command_log(logs_root / "rust-target.log", command_string(target_command), target_result)
        result.log_paths["rust_target"] = self.rel(logs_root / "rust-target.log")
        result.phase_durations["rust_target"] = round(target_result.duration_seconds, 2)
        if target_result.returncode != 0 or target_result.timed_out:
            raise BenchmarkError("Failed to prepare the wasm32 Rust target for the Rust/WASM benchmark scenario.")

        if not self.trunk_exe:
            if not self.try_download_prebuilt_trunk(logs_root, result):
                trunk_install_command = [
                    self.cargo_exe,
                    "install",
                    "trunk",
                    "--locked",
                    "--root",
                    str(self.benchmark_toolchain_root() / "cargo-root"),
                ]
                trunk_result = self.run_command(
                    trunk_install_command,
                    cwd=self.repo_source_root,
                    timeout_seconds=max(self.command_timeout, DEFAULT_RUST_TOOL_TIMEOUT_SECONDS),
                    env=self.rust_wasm_env(),
                    check=False,
                )
                self.write_command_log(
                    logs_root / "trunk-install.log",
                    command_string(trunk_install_command),
                    trunk_result,
                )
                result.log_paths["trunk_install"] = self.rel(logs_root / "trunk-install.log")
                result.phase_durations["trunk_install"] = round(trunk_result.duration_seconds, 2)
                if trunk_result.returncode != 0 or trunk_result.timed_out:
                    raise BenchmarkError("Failed to install Trunk for the Rust/WASM benchmark scenario.")
                self.trunk_exe = shutil.which("trunk")
                self.require_trunk_executable()

        self.write_arm_progress(
            result,
            "rust-wasm-toolchain-ready",
            detail="Rust, wasm target, and Trunk are ready for the benchmark scenario.",
        )

    def try_download_prebuilt_trunk(self, logs_root: Path, result: ArmResult) -> bool:
        asset_name = self.resolve_trunk_asset_name()
        if not asset_name:
            return False

        start = time.perf_counter()
        downloads_root = self.benchmark_toolchain_root() / "downloads"
        extract_root = self.benchmark_toolchain_root() / "extract"
        bin_root = self.benchmark_toolchain_root() / "cargo-root" / "bin"
        downloads_root.mkdir(parents=True, exist_ok=True)
        extract_root.mkdir(parents=True, exist_ok=True)
        bin_root.mkdir(parents=True, exist_ok=True)

        download_url = f"https://github.com/trunk-rs/trunk/releases/download/v{TRUNK_VERSION}/{asset_name}"
        archive_path = downloads_root / asset_name
        extracted_dir = extract_root / f"trunk-{asset_name}"
        log_path = logs_root / "trunk-download.log"
        try:
            with urllib.request.urlopen(download_url, timeout=300) as response:
                archive_path.write_bytes(response.read())
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir)
            extracted_dir.mkdir(parents=True, exist_ok=True)
            if asset_name.endswith(".zip"):
                with zipfile.ZipFile(archive_path) as archive:
                    archive.extractall(extracted_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as archive:
                    archive.extractall(extracted_dir)

            trunk_name = "trunk.exe" if sys.platform.startswith("win") else "trunk"
            candidates = sorted(extracted_dir.rglob(trunk_name))
            if not candidates:
                raise BenchmarkError(f"Prebuilt Trunk archive {asset_name} did not contain {trunk_name}.")
            destination = bin_root / trunk_name
            shutil.copy2(candidates[0], destination)
            if not sys.platform.startswith("win"):
                destination.chmod(0o755)
            self.trunk_exe = str(destination)
            duration = time.perf_counter() - start
            write_text(
                log_path,
                "\n".join(
                    [
                        f"Downloaded prebuilt Trunk asset: {asset_name}",
                        f"URL: {download_url}",
                        f"Archive path: {archive_path}",
                        f"Installed binary: {destination}",
                        f"Duration seconds: {duration:.2f}",
                    ]
                ),
            )
            result.log_paths["trunk_download"] = self.rel(log_path)
            result.phase_durations["trunk_download"] = round(duration, 2)
            return True
        except Exception as exc:
            duration = time.perf_counter() - start
            write_text(
                log_path,
                "\n".join(
                    [
                        f"Failed to download prebuilt Trunk asset: {asset_name}",
                        f"URL: {download_url}",
                        f"Duration seconds: {duration:.2f}",
                        f"Error: {exc}",
                    ]
                ),
            )
            result.log_paths["trunk_download"] = self.rel(log_path)
            result.phase_durations["trunk_download"] = round(duration, 2)
            return False

    def resolve_trunk_asset_name(self) -> str:
        machine = os.environ.get("PROCESSOR_ARCHITECTURE", "").lower()
        if not machine:
            try:
                import platform

                machine = platform.machine().lower()
            except Exception:
                machine = ""

        if sys.platform.startswith("win") and machine in {"amd64", "x86_64"}:
            return "trunk-x86_64-pc-windows-msvc.zip"
        if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
            return "trunk-aarch64-apple-darwin.tar.gz"
        if sys.platform == "darwin" and machine in {"x86_64", "amd64"}:
            return "trunk-x86_64-apple-darwin.tar.gz"
        if sys.platform.startswith("linux") and machine in {"arm64", "aarch64"}:
            return "trunk-aarch64-unknown-linux-gnu.tar.gz"
        if sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}:
            return "trunk-x86_64-unknown-linux-gnu.tar.gz"
        return ""

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
        self.normalize_result_lists(result)
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
            "expected_product_root": result.expected_product_root,
            "recursive_workflow_status": result.recursive_workflow_status,
            "recursive_isolation_status": result.recursive_isolation_status,
            "recursive_worktree_location": result.recursive_worktree_location,
            "recursive_delivery_status": result.recursive_delivery_status,
            "recursive_claimed_files": result.recursive_claimed_files,
            "recursive_product_change_paths": result.recursive_product_change_paths,
            "recursive_root_product_drift": result.recursive_root_product_drift,
            "recursive_missing_claimed_files": result.recursive_missing_claimed_files,
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
            "score_breakdown": result.score_breakdown,
            "score_breakdown_max": result.score_breakdown_max,
            "judge_adjusted_score_breakdown": result.judge_adjusted_score_breakdown,
            "judge_adjusted_score": result.judge_adjusted_score,
            "judge_entry_adjustments": result.judge_entry_adjustments,
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

    def runner_invocation_env(self, runner_slug: str) -> dict[str, str]:
        if runner_slug != "kimi":
            return {}
        return {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONLEGACYWINDOWSSTDIO": "0",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
        }

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
        if self.reconcile_pragmatic_tdd_exception_field(repo_root, logs_root, result):
            self.evaluate_recursive_run(repo_root, logs_root, result)
        if self.reconcile_recursive_requirement_changed_files(repo_root, logs_root, result):
            self.evaluate_recursive_run(repo_root, logs_root, result)
        repair_record = self.maybe_repair_recursive_run(repo_root, logs_root, runner, result)
        if repair_record is not None:
            result.duration_seconds += result.phase_durations.get("recursive_repair", 0.0)
        self.write_arm_progress(result, "judging", detail="Controller-side judge review is running.")
        self.run_judge_review(repo_root, product_root, logs_root, runner, result)
        self.finalize_result(runner, agent_record, result)
        self.write_arm_progress(result, "complete", detail="Benchmark arm completed.")
        return result

    def finalize_result(self, runner: RunnerConfig, agent_record: CommandResult, result: ArmResult) -> None:
        self.normalize_result_lists(result)
        delivery_failed = result.arm_name == "recursive-on" and result.recursive_delivery_status not in {"n/a", "ok"}
        result.product_status = (
            "pass"
            if result.build_success and result.test_success and result.preview_success and not delivery_failed
            else "fail"
        )
        if result.timed_out:
            result.status = "timed-out"
            return

        if self.is_benign_runner_exit(runner.slug, agent_record.stdout, agent_record.stderr, result):
            result.status = "pass" if result.product_status == "pass" else "product-fail"
            return

        runner_issue = self.detect_runner_issue(runner.slug, agent_record.stdout, agent_record.stderr)
        if result.agent_status == "clean-exit":
            result.status = "pass" if result.product_status == "pass" else "product-fail"
            return

        if result.product_status == "pass":
            result.status = "pass-with-runner-issue"
            self.add_issue(result, runner_issue or "Agent execution exited non-zero after producing a passing artifact set.")
            return

        result.status = "product-fail-with-runner-issue"
        self.add_issue(result, runner_issue or "Agent execution exited with a non-zero status.")

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

    def is_benign_runner_exit(self, runner_slug: str, stdout: str, stderr: str, result: ArmResult) -> bool:
        if runner_slug != "kimi":
            return False
        combined = f"{stdout}\n{stderr}".lower()
        if "does not support required capability: image_in" not in combined:
            return False
        if result.product_status != "pass":
            return False
        return result.arm_name != "recursive-on" or result.recursive_workflow_status == "complete"

    def detect_runner_issue(self, runner_slug: str, stdout: str, stderr: str) -> str:
        lower = f"{stdout}\n{stderr}".lower()
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

        if self.uses_rust_wasm_toolchain():
            self.prepare_rust_wasm_toolchain(logs_root, result)
        elif not self.args.skip_npm_install:
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
        baseline_commit = self.git_head_commit(repo_root)

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
            write_text(run_requirements, self.render_seeded_run_requirements(run_id))
            result.run_id = run_id
            result.expected_product_root = normalize_benchmark_path(f".worktrees/{run_id}")
            result.recursive_run_root = self.rel(run_root)
            write_text(repo_root / "benchmark" / "run-id.txt", run_id)
            expected_product_root_path = repo_root / result.expected_product_root
            expected_product_root_file = repo_root / "benchmark" / "expected-product-root.txt"
            write_text(expected_product_root_file, result.expected_product_root)
            template_root = repo_root / "benchmark" / "recursive-templates"
            self.seed_recursive_run_templates(template_root, run_id, result.expected_product_root, baseline_commit)
            context_path = repo_root / "benchmark" / "benchmark-context.json"
            context_payload: dict[str, object] = {}
            if context_path.exists():
                try:
                    loaded_context = json.loads(context_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    loaded_context = {}
                if isinstance(loaded_context, dict):
                    context_payload = loaded_context
            context_payload.update(
                {
                    "run_id": run_id,
                    "expected_product_root": result.expected_product_root,
                    "expected_product_root_exists": expected_product_root_path.exists(),
                    "run_requirements_source": normalize_benchmark_path(
                        str(self.requirements_path.relative_to(self.repo_source_root))
                    ),
                    "run_requirements_seed_mode": "controller-wrapped-phase0",
                    "run_template_root": "benchmark/recursive-templates",
                }
            )
            bootstrap_template = self.repo_source_root / "references" / "bootstrap" / "RECURSIVE.md"
            if bootstrap_template.exists():
                context_payload.update(
                    {
                        "recursive_bootstrap_source": str(bootstrap_template),
                        "recursive_bootstrap_source_sha256": file_sha256(bootstrap_template),
                    }
                )
            write_text(context_path, json.dumps(context_payload, indent=2))
            result.log_paths["recursive_run_root"] = self.rel(run_root)
            result.log_paths["run_requirements"] = self.rel(run_requirements)
            result.log_paths["expected_product_root"] = self.rel(expected_product_root_file)
            result.log_paths["benchmark_context"] = self.rel(context_path)
            result.log_paths["recursive_templates"] = self.rel(template_root)
            self.write_arm_progress(
                result,
                "run-initialized",
                detail="Recursive run scaffold, run-local requirements, expected worktree metadata, and lint-shaped templates are ready.",
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

    def git_head_commit(self, repo_root: Path) -> str:
        result = self.run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            timeout_seconds=min(self.command_timeout, 60),
            check=False,
            allowed_returncodes=(0,),
        )
        head = result.stdout.strip()
        if result.returncode != 0 or result.timed_out or not re.fullmatch(r"[0-9a-f]{40}", head):
            raise BenchmarkError(f"Unable to resolve benchmark baseline commit for {repo_root}.")
        return head

    def render_prompt(self, prompts_root: Path, result: ArmResult) -> tuple[str, Path | None]:
        template_path = self.prompt_on_path if result.arm_name == "recursive-on" else self.prompt_off_path
        text = template_path.read_text(encoding="utf-8")
        text = text.replace("{{RUN_ID}}", result.run_id or "benchmark-run-id-missing")
        text = text.replace(
            "{{EXPECTED_PRODUCT_ROOT}}",
            result.expected_product_root or normalize_benchmark_path(f".worktrees/{result.run_id or 'benchmark-run-id-missing'}"),
        )
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
        if result.arm_name == "recursive-on":
            text += f"- Expected product root: {result.expected_product_root or 'n/a'}\n"
        if result.arm_name == "recursive-off":
            return text, None
        prompts_root.mkdir(parents=True, exist_ok=True)
        prompt_path = prompts_root / f"{result.arm_name}.md"
        write_text(prompt_path, text)
        return text, prompt_path

    def render_seeded_run_requirements(self, run_id: str) -> str:
        scenario_body = self.requirements_path.read_text(encoding="utf-8").strip()
        scenario_source = normalize_benchmark_path(str(self.requirements_path.relative_to(self.repo_source_root)))
        locked_at = timestamp_utc()
        provisional = "\n".join(
            [
                f"Run: `/.recursive/run/{run_id}/`",
                "Phase: `00 Requirements`",
                "Status: `LOCKED`",
                "Workflow version: `recursive-mode-audit-v2`",
                "Inputs:",
                f"- Benchmark fixture: `{scenario_source}`",
                "Outputs:",
                f"- `/.recursive/run/{run_id}/00-requirements.md`",
                "Scope note: This controller-seeded Phase 0 artifact preserves the benchmark scenario requirements as the locked source of truth for the recursive-on arm.",
                f"LockedAt: `{locked_at}`",
                f"LockHash: `{'0' * 64}`",
                "",
                "## TODO",
                "",
                "- [x] Seed the benchmark scenario requirements into a recursive-compliant Phase 0 artifact",
                "- [x] Preserve stable requirement, out-of-scope, constraint, and assumption content without semantic drift",
                "- [x] Mark the seeded benchmark requirements ready for downstream recursive phases",
                "",
                scenario_body,
                "",
                "## Coverage Gate",
                "",
                "- [x] The benchmark scenario requirements are mirrored in this run-local artifact",
                "- [x] The required Phase 0 sections and identifiers are present",
                "Coverage: PASS",
                "",
                "## Approval Gate",
                "",
                "- [x] The recursive-on arm has a locked Phase 0 requirements artifact before execution begins",
                "- [x] Downstream phases can treat this file as the benchmark source of truth",
                "Approval: PASS",
            ]
        )
        lock_hash = lock_hash_from_content(provisional)
        return provisional.replace(f"`{'0' * 64}`", f"`{lock_hash}`", 1)

    def benchmark_requirement_specs(self) -> list[BenchmarkRequirementSpec]:
        requirements_text = self.requirements_path.read_text(encoding="utf-8")
        specs: list[BenchmarkRequirementSpec] = []
        pattern = re.compile(r"(?ms)^###\s+`(R\d+)`\s+([^\r\n]+)\s*\n\s*\nDescription:\s*([^\r\n]+)")
        for match in pattern.finditer(requirements_text):
            requirement_id, title, description = match.groups()
            specs.append(
                BenchmarkRequirementSpec(
                    requirement_id=requirement_id.strip(),
                    title=title.strip(),
                    source_quote=f"Description: {description.strip()}",
                )
            )
        return specs

    def seed_recursive_run_templates(
        self,
        template_root: Path,
        run_id: str,
        expected_product_root: str,
        baseline_commit: str,
    ) -> None:
        for file_name, content in self.render_recursive_template_files(
            run_id,
            expected_product_root,
            baseline_commit,
        ).items():
            write_text(template_root / file_name, content)
        repo_root = template_root.parent.parent
        evidence_root = repo_root / ".recursive" / "run" / run_id / "evidence"
        for path in (
            evidence_root / "logs" / "baseline",
            evidence_root / "logs" / "green",
            evidence_root / "manual",
            evidence_root / "screenshots",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def render_recursive_template_files(
        self,
        run_id: str,
        expected_product_root: str,
        baseline_commit: str,
    ) -> dict[str, str]:
        specs = self.benchmark_requirement_specs()
        worktree_root = normalize_benchmark_path(expected_product_root)
        baseline_example = f".recursive/run/{run_id}/evidence/logs/baseline/replace-me.log"
        green_example = f".recursive/run/{run_id}/evidence/logs/green/replace-me.log"
        qa_evidence_example = f".recursive/run/{run_id}/evidence/manual/replace-me.txt"
        screenshot_evidence_example = f".recursive/run/{run_id}/evidence/screenshots/replace-me.png"
        product_screenshot_example = f"{worktree_root}/benchmark/screenshots/replace-me.png"
        product_agent_log_example = f"{worktree_root}/benchmark/agent-log.md"

        def header(phase: str, file_name: str, inputs: list[str], scope_note: str) -> list[str]:
            return [
                f"Run: `/.recursive/run/{run_id}/`",
                f"Phase: `{phase}`",
                "Status: `DRAFT`",
                "Inputs:",
                *[f"- `{path}`" for path in inputs],
                "Outputs:",
                f"- `/.recursive/run/{run_id}/{file_name}`",
                f"Scope note: {scope_note}",
                "",
            ]

        def phase1_requirement_lines() -> list[str]:
            lines: list[str] = []
            for spec in specs:
                lines.append(
                    f"- {spec.requirement_id} | Status: blocked | Rationale: TODO replace with the concrete baseline gap for {spec.requirement_id}. | "
                    "Blocking Evidence: TODO replace with existing repo-root-relative evidence paths such as "
                    f"`benchmark/expected-product-root.txt`, `{worktree_root}/Cargo.toml`, or `{baseline_example}`. "
                    "Use actual files or current-run artifacts, not prose or bare directories like `src/`. | Audit Note: TODO"
                )
            return lines

        def phase2_mapping_lines() -> list[str]:
            lines: list[str] = []
            for spec in specs:
                lines.append(
                    f"- {spec.requirement_id} | Source Quote: {spec.source_quote} | Coverage: direct | "
                    f"Implementation Surface: TODO repo-root-relative product paths such as `{worktree_root}/src/main.rs` or `{worktree_root}/src/lib.rs` | "
                    f"Verification Surface: TODO tests or evidence such as `{green_example}` | "
                    f"QA Surface: TODO audited QA evidence such as `{screenshot_evidence_example}`"
                )
            return lines

        def phase2_status_lines() -> list[str]:
            lines: list[str] = []
            for spec in specs:
                lines.append(
                    f"- {spec.requirement_id} | Status: planned | "
                    f"Implementation Surface: TODO repo-root-relative product paths under `{worktree_root}/` | "
                    f"Verification Surface: TODO verification commands or artifacts such as `{green_example}` | "
                    f"QA Surface: TODO manual/browser evidence such as `{screenshot_evidence_example}` | Audit Note: TODO"
                )
            return lines

        def implemented_status_lines() -> list[str]:
            lines: list[str] = []
            for spec in specs:
                lines.append(
                    f"- {spec.requirement_id} | Status: implemented | "
                    f"Changed Files: TODO actual repo-root-relative worktree paths such as `{worktree_root}/src/main.rs` | "
                    f"Implementation Evidence: TODO actual changed file paths or current-run artifacts such as `{green_example}` | Audit Note: TODO"
                )
            return lines

        def verified_status_lines() -> list[str]:
            lines: list[str] = []
            for spec in specs:
                lines.append(
                    f"- {spec.requirement_id} | Status: verified | "
                    f"Changed Files: TODO actual repo-root-relative worktree paths under `{worktree_root}/` | "
                    f"Implementation Evidence: TODO changed file paths or current-run implementation artifacts | "
                    f"Verification Evidence: TODO distinct test/review/QA evidence such as `{green_example}`, `{qa_evidence_example}`, or `{screenshot_evidence_example}` | Audit Note: TODO"
                )
            return lines

        def inventory_lines() -> list[str]:
            return [
                f"- {spec.requirement_id} | Source Quote: {spec.source_quote} | Summary: {spec.title} | Disposition: in-scope"
                for spec in specs
            ]

        def traceability_lines(note: str) -> list[str]:
            return [f"- {spec.requirement_id} -> TODO {note}" for spec in specs]

        def audit_sections(requirement_lines: list[str], inputs: list[str], gap_note: str) -> list[str]:
            return [
                "## Audit Context",
                "",
                "- Audit Execution Mode: self-audit",
                "- Subagent Availability: unavailable",
                "- Subagent Capability Probe: Benchmark runner prompt does not expose durable delegated subagent execution in this disposable repo.",
                "- Delegation Decision Basis: Use self-audit unless the runner proves subagent support during the benchmark.",
                "- Audit Inputs Provided:",
                *[f"  - `{path}`" for path in inputs],
                "",
                "## Effective Inputs Re-read",
                "",
                *[f"- `{path}`" for path in inputs],
                "",
                "## Earlier Phase Reconciliation",
                "",
                "- No earlier audited phase drift has been reconciled in this template yet; replace with actual reconciliation notes before locking.",
                "",
                "## Subagent Contribution Verification",
                "",
                "- Reviewed Action Records: none (self-audit draft scaffold)",
                f"- Main-Agent Verification Performed: `.recursive/run/{run_id}/00-requirements.md`, `.recursive/RECURSIVE.md`",
                "- Acceptance Decision: accepted",
                "- Refresh Handling: No delegated artifacts were refreshed in this self-audit draft scaffold.",
                "- Repair Performed After Verification: Replace with concrete audit repairs if this phase changes after verification.",
                "",
                "## Worktree Diff Audit",
                "",
                "- Baseline type: commit",
                f"- Baseline reference: `{baseline_commit}`",
                "- Comparison reference: working-tree",
                f"- Normalized baseline: `{baseline_commit}`",
                "- Normalized comparison: working-tree",
                f"- Normalized diff command: `git diff --name-only {baseline_commit}`",
                "- Reviewed paths: TODO replace with the actual diff-owned paths for this phase.",
                "",
                "## Gaps Found",
                "",
                f"- {gap_note}",
                "",
                "## Repair Work Performed",
                "",
                "- Template scaffold only. Replace with any real audit-repair work performed before locking.",
                "",
                "## Requirement Completion Status",
                "",
                *requirement_lines,
                "",
                "## Audit Verdict",
                "",
                "Audit: FAIL",
                "- Summary: Draft scaffold only; replace placeholders, rerun the audit, then promote to PASS before locking.",
                "",
                "## Coverage Gate",
                "",
                "Coverage: FAIL",
                "",
                "## Approval Gate",
                "",
                "Approval: FAIL",
            ]

        files: dict[str, str] = {}

        files["00-worktree.md"] = "\n".join(
            header(
                "00 Worktree",
                "00-worktree.md",
                [".recursive/run/{run_id}/00-requirements.md".format(run_id=run_id), ".recursive/RECURSIVE.md"],
                "Copy this template into the real run artifact, then replace all TODO text with the actual directory and safety decisions for this benchmark run.",
            )
            + [
                "## TODO",
                "",
                "- [ ] Copy this template into `/.recursive/run/{run-id}/00-worktree.md` and replace all TODO placeholders.",
                f"- [ ] Use repo-root-relative paths in later artifacts, e.g. `{worktree_root}/src/main.rs` rather than `src/main.rs`.",
                f"- [ ] Keep the diff-basis fields executable if you change them, and preserve the full 40-character baseline commit `{baseline_commit}` instead of shortening it.",
                "",
                "## Directory Selection",
                "",
                f"- Selected worktree location: `{worktree_root}`",
                f"- Product root: `{worktree_root}`",
                "- Rationale: TODO replace with the actual worktree-selection rationale.",
                "",
                "## Safety Verification",
                "",
                "- TODO confirm the control-plane repo root remains protected from product edits.",
                "",
                "## Worktree Creation",
                "",
                f"- Expected location: `{worktree_root}`",
                "- Creation status: TODO replace with actual command/results.",
                "",
                "## Main Branch Protection",
                "",
                "- TODO record how main/root drift is avoided.",
                "",
                "## Project Setup",
                "",
                f"- Template pack: `benchmark/recursive-templates/`",
                f"- Seeded requirements: `.recursive/run/{run_id}/00-requirements.md`",
                "",
                "## Test Baseline Verification",
                "",
                "- TODO record the starter baseline commands and results before implementation begins.",
                "",
                "## Worktree Context",
                "",
                "- TODO note the product root, benchmark logs location, and any toolchain setup needed for the run.",
                "",
                "## Diff Basis For Later Audits",
                "",
                "- Baseline type: commit",
                f"- Baseline reference: `{baseline_commit}`",
                "- Comparison reference: working-tree",
                f"- Normalized baseline: `{baseline_commit}`",
                "- Normalized comparison: working-tree",
                f"- Normalized diff command: `git diff --name-only {baseline_commit}`",
                "- If you edit these fields, keep the full 40-character commit hash and an executable diff command.",
                "",
                "## Traceability",
                "",
                f"- Source requirements: `.recursive/run/{run_id}/00-requirements.md`",
                f"- Expected product root metadata: `benchmark/expected-product-root.txt`",
                f"- Benchmark context: `benchmark/benchmark-context.json`",
            ]
        )

        files["01-as-is.md"] = "\n".join(
            header(
                "01 As-Is",
                "01-as-is.md",
                [
                    f".recursive/run/{run_id}/00-requirements.md",
                    ".recursive/RECURSIVE.md",
                    "benchmark/benchmark-context.json",
                    "benchmark/expected-product-root.txt",
                ],
                "Copy this template into the real Phase 1 artifact and replace every TODO with actual baseline findings before locking.",
            )
            + [
                "## TODO",
                "",
                f"- [ ] Replace placeholder evidence with real repo-root-relative paths under `{worktree_root}/` or `/.recursive/run/{run_id}/`.",
                "- [ ] Keep prose in `Rationale`; keep `Blocking Evidence` limited to concrete existing file or artifact paths.",
                "- [ ] Keep `Gaps Found` limited to real audit defects in the analysis itself; expected blank-starter feature gaps belong in baseline findings and requirement status, not unresolved PASS-blocking gaps.",
                "- [ ] Mention every in-scope requirement ID explicitly in `Traceability` and use `None because ...` if no prior recursive evidence applies.",
                "- [ ] Do not lock while any placeholder or example text remains.",
                "",
                "## Reproduction Steps (Novice-Runnable)",
                "",
                "- TODO record the exact starter-baseline commands a novice could run before implementation.",
                "",
                "## Current Behavior by Requirement",
                "",
                "- TODO summarize the current baseline behavior for each in-scope requirement.",
                "",
                "## Source Requirement Inventory",
                "",
                *inventory_lines(),
                "",
                "## Relevant Code Pointers",
                "",
                f"- `{worktree_root}/Cargo.toml`",
                f"- `{worktree_root}/Cargo.lock`",
                f"- `.recursive/run/{run_id}/00-requirements.md`",
                f"- `{product_agent_log_example}`",
                "",
                "## Known Unknowns",
                "",
                "- TODO list unresolved baseline questions or assumptions that matter before planning.",
                "",
                "## Evidence",
                "",
                "- `benchmark/benchmark-context.json`",
                "- `benchmark/expected-product-root.txt`",
                f"- `.recursive/run/{run_id}/00-requirements.md`",
                "",
                "## Traceability",
                "",
                *traceability_lines("tie the baseline finding, blocking evidence, and rationale back to this requirement."),
                "",
                "## Prior Recursive Evidence Reviewed",
                "",
                "- None because this benchmark run starts from a fresh disposable workspace and no earlier `.recursive/run/...` or `.recursive/memory/...` path is relevant.",
                "",
            ]
            + audit_sections(
                phase1_requirement_lines(),
                [
                    f".recursive/run/{run_id}/00-requirements.md",
                    ".recursive/RECURSIVE.md",
                    "benchmark/benchmark-context.json",
                    "benchmark/expected-product-root.txt",
                ],
                "Draft scaffold only; baseline analysis and blocking evidence still need to be filled in. When the phase is otherwise complete, keep `Gaps Found` limited to actual audit defects; expected starter gaps belong in the baseline findings and requirement status instead.",
            )
        )

        files["02-to-be-plan.md"] = "\n".join(
            header(
                "02 To-Be Plan",
                "02-to-be-plan.md",
                [
                    f".recursive/run/{run_id}/00-requirements.md",
                    f".recursive/run/{run_id}/01-as-is.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Copy this template into the real Phase 2 artifact and replace every TODO with a lock-valid plan. Planned statuses must use Implementation Surface / Verification Surface / QA Surface only.",
            )
            + [
                "## TODO",
                "",
                f"- [ ] Use repo-root-relative product paths such as `{worktree_root}/src/main.rs`, not `src/main.rs`.",
                "- [ ] Do not use `Changed Files` or `Plan Evidence` in Phase 2 `Status: planned*` entries.",
                f"- [ ] Use exact evidence targets such as `{green_example}` and `{screenshot_evidence_example}`; do not cite globs like `{worktree_root}/benchmark/screenshots/*.png`.",
                "- [ ] If screenshot tooling may inline image bytes, plan to finish the written receipts first and use file-only capture as the final QA evidence step.",
                "- [ ] If implementation collapses files later, update the plan and later receipts so they cite only final real paths.",
                "",
                "## Planned Changes by File",
                "",
                f"- TODO replace with actual planned repo-root-relative paths under `{worktree_root}/` and brief rationale per file.",
                "",
                "## Requirement Mapping",
                "",
                *phase2_mapping_lines(),
                "",
                "## Implementation Steps",
                "",
                "- TODO break the implementation into concrete ordered steps.",
                "",
                "## Testing Strategy",
                "",
                f"- TODO list the exact commands, target coverage, and evidence paths you plan to produce under `/.recursive/run/{run_id}/evidence/`.",
                "",
                "## Playwright Plan (if applicable)",
                "",
                "- TODO note browser automation or explicitly say it is not applicable for this run.",
                "",
                "## Manual QA Scenarios",
                "",
                "- TODO describe the manual/browser scenarios you will use for calculator validation.",
                "",
                "## Idempotence and Recovery",
                "",
                "- TODO explain how to recover if the worktree, toolchain, or browser preview needs to be rerun.",
                "",
                "## Implementation Sub-phases",
                "",
                "- TODO list the concrete sub-phases that map back to the requirement coverage.",
                "",
                "## Plan Drift Check",
                "",
                "- TODO record any merged or indirect coverage decisions and explain why they are lossless.",
                "",
                "## Traceability",
                "",
                *traceability_lines("link the planned files, test strategy, and QA plan back to this requirement."),
                "",
                "## Prior Recursive Evidence Reviewed",
                "",
                "- None because only the current run baseline is relevant and there is no earlier durable recursive evidence path to cite.",
                "",
            ]
            + audit_sections(
                phase2_status_lines(),
                [
                    f".recursive/run/{run_id}/00-requirements.md",
                    f".recursive/run/{run_id}/01-as-is.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Draft scaffold only; planned implementation, verification, and QA surfaces still need real paths.",
            )
        )

        files["03-implementation-summary.md"] = "\n".join(
            header(
                "03 Implementation Summary",
                "03-implementation-summary.md",
                [
                    f".recursive/run/{run_id}/02-to-be-plan.md",
                    f".recursive/run/{run_id}/01-as-is.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Copy this template into the real Phase 3 artifact and replace placeholders with only the final files that actually exist in the finished worktree.",
            )
            + [
                "## TODO",
                "",
                f"- [ ] Cite only final repo-root-relative paths such as `{worktree_root}/src/main.rs`; do not claim hypothetical split files that were never created.",
                "- [ ] Keep implementation evidence tied to changed files or current-run artifacts.",
                f"- [ ] Preserve the bare gate line `TDD Compliance: PASS|FAIL` and, in pragmatic mode, replace the placeholder compensating validation with exact files under `/.recursive/run/{run_id}/evidence/`.",
                "- [ ] If using pragmatic TDD, replace the placeholder exception with real evidence paths under the current run evidence/ directory.",
                "",
                "## Changes Applied",
                "",
                f"- TODO replace with the actual changed repo-root-relative paths under `{worktree_root}/` and what changed in each.",
                "",
                "## TDD Compliance Log",
                "",
                "- TDD Mode: pragmatic",
                "- Summary: TODO replace with the actual TDD approach used in this run.",
                "TDD Compliance: FAIL",
                "",
                "## Pragmatic TDD Exception",
                "",
                "- Exception reason: TODO explain why pragmatic mode was necessary for this run.",
                f"- Compensating validation: TODO cite real evidence under `/{green_example}` or another current-run evidence path.",
                "",
                "## Plan Deviations",
                "",
                "- TODO list any deviations from Phase 2 and why they were safe.",
                "",
                "## Implementation Evidence",
                "",
                f"- TODO cite actual changed files and current-run artifacts such as `{green_example}`.",
                "",
                "## Traceability",
                "",
                *traceability_lines("tie the implemented work back to exact changed files and implementation evidence."),
                "",
            ]
            + audit_sections(
                implemented_status_lines(),
                [
                    f".recursive/run/{run_id}/02-to-be-plan.md",
                    f".recursive/run/{run_id}/01-as-is.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Draft scaffold only; implementation receipts and evidence paths still need real values.",
            )
        )

        files["04-test-summary.md"] = "\n".join(
            header(
                "04 Test Summary",
                "04-test-summary.md",
                [
                    f".recursive/run/{run_id}/03-implementation-summary.md",
                    f".recursive/run/{run_id}/02-to-be-plan.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Copy this template into the real Phase 4 artifact and replace placeholders with exact commands, results, and verification evidence.",
            )
            + [
                "## TODO",
                "",
                f"- [ ] Keep product file citations repo-root-relative under `{worktree_root}/`.",
                "- [ ] Keep verification evidence distinct from the implementation evidence; test logs, screenshots, and review receipts count.",
                f"- [ ] Do not cite globs in audited receipts; if you capture `{product_screenshot_example}`, also copy or cite the exact file under `{screenshot_evidence_example}`.",
                "- [ ] Prefer file-only screenshot capture and do not reopen `.png` evidence in the model; if inline-image tooling is unavoidable, leave it as the last step after the written receipts are ready.",
                "- [ ] Replace the prior-evidence note if earlier recursive evidence actually became relevant.",
                "",
                "## Pre-Test Implementation Audit",
                "",
                "- TODO record what you checked before running tests.",
                "",
                "## Environment",
                "",
                "- TODO record the relevant toolchain/runtime environment for the executed tests.",
                "",
                "## Execution Mode",
                "",
                "- TODO record whether test execution was automated, manual, or mixed.",
                "",
                "## Commands Executed (Exact)",
                "",
                "- TODO paste the exact commands that were run.",
                "",
                "## Results Summary",
                "",
                "- TODO summarize build/test/preview outcomes with exit codes and notable observations.",
                "",
                "## Evidence and Artifacts",
                "",
                f"- TODO cite current-run verification artifacts such as `{green_example}`, `{qa_evidence_example}`, and `{screenshot_evidence_example}`.",
                "",
                "## Failures and Diagnostics (if any)",
                "",
                "- TODO record failures, diagnostics, or explicitly say none.",
                "",
                "## Flake/Rerun Notes",
                "",
                "- TODO note any reruns or explicitly say none.",
                "",
                "## Traceability",
                "",
                *traceability_lines("map the verification commands and exact evidence files that proved this requirement."),
                "",
                "## Prior Recursive Evidence Reviewed",
                "",
                "- None because the current run artifacts provide the required evidence and no earlier recursive run or memory path was needed.",
                "",
            ]
            + audit_sections(
                verified_status_lines(),
                [
                    f".recursive/run/{run_id}/03-implementation-summary.md",
                    f".recursive/run/{run_id}/02-to-be-plan.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Draft scaffold only; exact command output and verification evidence still need real values.",
            )
        )

        files["05-manual-qa.md"] = "\n".join(
            header(
                "05 Manual QA",
                "05-manual-qa.md",
                [
                    f".recursive/run/{run_id}/04-test-summary.md",
                    f".recursive/run/{run_id}/03-implementation-summary.md",
                ],
                "Copy this template into the real Phase 5 receipt and replace placeholders with the actual QA execution record and evidence.",
            )
            + [
                "## TODO",
                "",
                "- [ ] Replace all QA placeholders with the real execution metadata and evidence.",
                "- [ ] Keep screenshot and browser evidence repo-root-relative if the app runs in the isolated worktree.",
                f"- [ ] For `QA Execution Mode: agent-operated`, cite exact files under `/.recursive/run/{run_id}/evidence/` such as `{qa_evidence_example}` or `{screenshot_evidence_example}`.",
                "- [ ] Use file-only screenshot capture, cite screenshot paths without reopening the images, and leave any risky inline-image capture path until the end.",
                "",
                "## QA Execution Record",
                "",
                "- QA Execution Mode: agent-operated",
                "- Agent Executor: TODO",
                "- Tools Used: TODO",
                "- Notes: TODO",
                "",
                "## QA Scenarios and Results",
                "",
                "- TODO list each QA scenario, outcome, and any follow-up notes.",
                "",
                "## Evidence and Artifacts",
                "",
                f"- TODO cite QA evidence such as `{qa_evidence_example}` and `{screenshot_evidence_example}`.",
                "",
                "## User Sign-Off",
                "",
                "- Approved by: not required for agent-operated mode",
                "- Date: not required for agent-operated mode",
                "- Notes: TODO if human sign-off becomes necessary.",
                "",
                "## Traceability",
                "",
                *traceability_lines("connect the QA scenario, outcome, and exact evidence files back to this requirement."),
                "",
                "## Coverage Gate",
                "",
                "Coverage: FAIL",
                "",
                "## Approval Gate",
                "",
                "Approval: FAIL",
            ]
        )

        files["06-decisions-update.md"] = "\n".join(
            header(
                "06 Decisions Update",
                "06-decisions-update.md",
                [
                    f".recursive/run/{run_id}/04-test-summary.md",
                    ".recursive/DECISIONS.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Copy this template into the real Phase 6 receipt and replace placeholders with the actual decisions delta and closeout evidence.",
            )
            + [
                "## TODO",
                "",
                "- [ ] Record only actual decisions changes and cite the resulting DECISIONS entry.",
                "- [ ] Keep requirement statuses at verified or an explicitly approved non-completion state.",
                "",
                "## Decisions Changes Applied",
                "",
                "- TODO describe the decisions delta applied in this run.",
                "",
                "## Rationale",
                "",
                "- TODO explain why the decisions update was needed.",
                "",
                "## Resulting Decision Entry",
                "",
                "- TODO cite `.recursive/DECISIONS.md` and the specific entry updated or added.",
                "",
                "## Traceability",
                "",
                *traceability_lines("connect the decisions delta back to verified implementation and verification evidence."),
                "",
            ]
            + audit_sections(
                verified_status_lines(),
                [
                    f".recursive/run/{run_id}/04-test-summary.md",
                    ".recursive/DECISIONS.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Draft scaffold only; decisions delta and verified closeout evidence still need real values.",
            )
        )

        files["07-state-update.md"] = "\n".join(
            header(
                "07 State Update",
                "07-state-update.md",
                [
                    f".recursive/run/{run_id}/06-decisions-update.md",
                    ".recursive/STATE.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Copy this template into the real Phase 7 receipt and replace placeholders with the actual state delta and closeout evidence.",
            )
            + [
                "## TODO",
                "",
                "- [ ] Record the actual state delta for this run.",
                "- [ ] Replace the prior-evidence note if earlier recursive evidence became relevant.",
                "",
                "## State Changes Applied",
                "",
                "- TODO describe the state delta applied in this run.",
                "",
                "## Rationale",
                "",
                "- TODO explain why the state update was needed.",
                "",
                "## Resulting State Summary",
                "",
                "- TODO cite `.recursive/STATE.md` and summarize the new durable state.",
                "",
                "## Traceability",
                "",
                *traceability_lines("connect the state delta back to verified implementation and verification evidence."),
                "",
                "## Prior Recursive Evidence Reviewed",
                "",
                "- None because no earlier recursive run or memory path was reviewed beyond the current benchmark run state.",
                "",
            ]
            + audit_sections(
                verified_status_lines(),
                [
                    f".recursive/run/{run_id}/06-decisions-update.md",
                    ".recursive/STATE.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Draft scaffold only; state delta and verified closeout evidence still need real values.",
            )
        )

        files["08-memory-impact.md"] = "\n".join(
            header(
                "08 Memory Impact",
                "08-memory-impact.md",
                [
                    f".recursive/run/{run_id}/07-state-update.md",
                    ".recursive/memory/MEMORY.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Copy this template into the real Phase 8 receipt and replace placeholders with the actual memory review and skill-usage conclusions.",
            )
            + [
                "## TODO",
                "",
                "- [ ] Replace all placeholder memory and skill-usage notes with the actual run conclusions.",
                "- [ ] Keep final requirement statuses verified or explicitly approved non-completion states.",
                "",
                "## Diff Basis",
                "",
                "- Baseline type: commit",
                f"- Baseline reference: `{baseline_commit}`",
                "- Comparison reference: working-tree",
                f"- Normalized baseline: `{baseline_commit}`",
                "- Normalized comparison: working-tree",
                f"- Normalized diff command: `git diff --name-only {baseline_commit}`",
                "",
                "## Changed Paths Review",
                "",
                "- TODO summarize the diff-owned paths reviewed for memory impact.",
                "",
                "## Affected Memory Docs",
                "",
                "- TODO cite any memory docs updated, or explicitly say none.",
                "",
                "## Run-Local Skill Usage Capture",
                "",
                "- Skill Usage Relevance: relevant",
                "- Available Skills: TODO",
                "- Skills Sought: TODO",
                "- Skills Attempted: TODO",
                "- Skills Used: TODO",
                "- Worked Well: TODO",
                "- Issues Encountered: TODO",
                "- Future Guidance: TODO",
                "- Promotion Candidates: TODO",
                "",
                "## Skill Memory Promotion Review",
                "",
                "- Durable Skill Lessons Promoted: TODO",
                "- Generalized Guidance Updated: TODO",
                "- Run-Local Observations Left Unpromoted: TODO",
                "- Promotion Decision Rationale: TODO",
                "",
                "## Uncovered Paths",
                "",
                "- TODO note any relevant paths left uncovered, or explicitly say none.",
                "",
                "## Router and Parent Refresh",
                "",
                "- TODO record any router/parent refresh work or explicitly say none.",
                "",
                "## Final Status Summary",
                "",
                "- TODO summarize final benchmark completion state, remaining gaps, and durability impact.",
                "",
                "## Traceability",
                "",
                *traceability_lines("connect the memory review or skill conclusion back to verified run evidence."),
                "",
                "## Prior Recursive Evidence Reviewed",
                "",
                "- None because no earlier recursive run or memory path was reviewed beyond the current benchmark run state.",
                "",
            ]
            + audit_sections(
                verified_status_lines(),
                [
                    f".recursive/run/{run_id}/07-state-update.md",
                    ".recursive/memory/MEMORY.md",
                    ".recursive/RECURSIVE.md",
                ],
                "Draft scaffold only; memory review and skill-promotion conclusions still need real values.",
            )
        )

        return files

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
            record = self.run_command(
                command,
                cwd=repo_root,
                timeout_seconds=timeout_seconds,
                env=self.runner_invocation_env(runner_slug),
                check=False,
            )
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
            record = self.run_command(
                command,
                cwd=repo_root,
                timeout_seconds=timeout_seconds,
                env=self.runner_invocation_env(runner_slug),
                check=False,
            )
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
                record = self.run_command(
                    command,
                    cwd=repo_root,
                    timeout_seconds=timeout_seconds,
                    env=self.runner_invocation_env(runner_slug),
                    check=False,
                )
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

    @staticmethod
    def collect_recursive_lint_findings(lint_log_path: Path, limit: int = 12) -> list[str]:
        if not lint_log_path.exists():
            return []
        findings: list[str] = []
        for raw_line in lint_log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if line.startswith("[FAIL]") or line.startswith("[WARN] Missing artifact"):
                findings.append(line)
            if len(findings) >= limit:
                break
        return findings

    @staticmethod
    def lint_has_only_optional_missing_artifact_warnings(lint_log_path: Path) -> bool:
        if not lint_log_path.exists():
            return False
        optional_missing = {"01.5-root-cause.md", "03.5-code-review.md"}
        saw_optional_warning = False
        for raw_line in lint_log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "[FAIL] Lint failed":
                continue
            if line.startswith("[FAIL]"):
                return False
            if line.startswith("[WARN] Missing artifact"):
                artifact_name = Path(line.split(":", 1)[1].strip()).name
                if artifact_name not in optional_missing:
                    return False
                saw_optional_warning = True
                continue
            if line.startswith("[WARN]"):
                return False
        return saw_optional_warning

    def reconcile_pragmatic_tdd_exception_field(self, repo_root: Path, logs_root: Path, result: ArmResult) -> bool:
        if result.arm_name != "recursive-on" or not result.run_id or result.recursive_workflow_status != "lint-failed":
            return False
        lint_findings = self.collect_recursive_lint_findings(logs_root / "recursive-lint.log")
        if not any("Pragmatic TDD Exception is missing Compensating validation" in finding for finding in lint_findings):
            return False
        artifact_path = repo_root / ".recursive" / "run" / result.run_id / "03-implementation-summary.md"
        if not artifact_path.exists():
            return False
        original = artifact_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?mi)^[ \t]*(?:[-*][ \t]+)?Compensating validation:\s*\S", original):
            return False
        exception_body = self.get_heading_body(original, "Pragmatic TDD Exception")
        if not exception_body:
            return False
        subsection_match = re.search(r"(?mi)^[ \t]*###\s+Compensating validation\s*$", exception_body)
        if not subsection_match:
            return False
        normalized_body = re.sub(
            r"(?mi)^([ \t]*###\s+Compensating validation\s*$)",
            "- Compensating validation: See evidence paths listed below.\n\n\\1",
            exception_body,
            count=1,
        )
        if normalized_body == exception_body:
            return False
        updated = original.replace(exception_body, normalized_body, 1)
        artifact_path.write_text(updated, encoding="utf-8", newline="\n")
        return True

    def should_attempt_recursive_repair(self, result: ArmResult) -> bool:
        return result.arm_name == "recursive-on" and result.recursive_workflow_status in {"incomplete", "lint-failed"}

    def build_recursive_repair_prompt(self, repo_root: Path, logs_root: Path, result: ArmResult) -> str:
        missing_files = [name for name, present in sorted(result.recursive_artifact_status.items()) if not present]
        run_root = f".recursive/run/{result.run_id}"
        lint_log_path = logs_root / "recursive-lint.log"
        lint_findings = self.collect_recursive_lint_findings(lint_log_path)
        prompt_lines = [
            f"Continue recursive-mode run `{result.run_id}` in this repository.",
            "",
            "The product implementation, build/test/preview, and benchmark workspace already exist. Focus on repairing the recursive run artifacts so controller-side recursive lint passes.",
            "Do not re-implement the product unless an artifact fix truly requires a matching evidence refresh.",
            "",
            "Read:",
            "- `.recursive/RECURSIVE.md`",
            f"- `{run_root}/00-requirements.md`",
            f"- `{run_root}/00-worktree.md`",
            f"- `{run_root}/01-as-is.md`",
            f"- `{run_root}/02-to-be-plan.md`",
            "- `benchmark/recursive-templates/`",
            "- `benchmark/expected-product-root.txt`",
        ]
        if lint_log_path.exists():
            prompt_lines.append(f"- `{self.rel(lint_log_path)}`")
        prompt_lines.extend(
            [
                "",
                "Repair requirements:",
                "- Complete and lock any missing required run artifacts before finishing.",
                "- Do not stop after Phase 2 or after the product build succeeds; the run is incomplete until `03-implementation-summary.md`, `04-test-summary.md`, `05-manual-qa.md`, `06-decisions-update.md`, `07-state-update.md`, and `08-memory-impact.md` all exist and are lock-valid.",
                "- Keep the template headings exactly as required, including `## TODO`, `## Changes Applied`, and `## Failures and Diagnostics (if any)`.",
                "- Use the exact word `None` in `## Gaps Found` whenever `Audit: PASS` is true and there are no unresolved gaps. `No gaps` is not sufficient for strict lint.",
                "- If you use `TDD Mode: pragmatic`, include a real `Compensating validation:` field with concrete evidence-file citations. Do not turn `Compensating validation` into its own heading.",
                "- In `04-test-summary.md` and later audited phases, `Verification Evidence` must be distinct from the Phase 3 implementation evidence.",
                "- In `Changed Files`, `Worktree Diff Audit`, and `Requirement Completion Status`, account for final diff-owned benchmark files and bootstrapped control-plane files under the worktree, not just the main product source files.",
                "- Only list files in `Changed Files`, `Worktree Diff Audit`, and `Requirement Completion Status` when they are actually present in the current `git diff --name-only` output. Remove unchanged bootstrap or control-plane files instead of claiming them.",
                "- Keep benchmark progress notes in `benchmark/agent-log.md` with UTC timestamps when you repair the run.",
            ]
        )
        if missing_files:
            prompt_lines.extend(["", "Currently missing required artifacts:"])
            prompt_lines.extend(f"- `{name}`" for name in missing_files)
        if lint_findings:
            prompt_lines.extend(["", "Recent controller lint findings to fix:"])
            prompt_lines.extend(f"- {finding}" for finding in lint_findings)
        prompt_lines.extend(["", "Finish only after the run folder is complete and strict recursive lint would pass."])
        return "\n".join(prompt_lines)

    def maybe_repair_recursive_run(
        self,
        repo_root: Path,
        logs_root: Path,
        runner: RunnerConfig,
        result: ArmResult,
    ) -> CommandResult | None:
        if not self.should_attempt_recursive_repair(result) or not result.run_id:
            return None
        total_duration = 0.0
        last_record: CommandResult | None = None
        attempt = 1
        while attempt <= 2 and self.should_attempt_recursive_repair(result):
            repair_prompt = self.build_recursive_repair_prompt(repo_root, logs_root, result)
            prompt_name = "recursive-repair-prompt.md" if attempt == 1 else f"recursive-repair-{attempt}-prompt.md"
            repair_prompt_path = logs_root / prompt_name
            write_text(repair_prompt_path, repair_prompt)
            result.log_paths["recursive_repair_prompt"] = self.rel(repair_prompt_path)
            log_stem = "recursive-repair" if attempt == 1 else f"recursive-repair-{attempt}"
            repair_record, stdout_log, stderr_log = self.run_model_prompt(
                repo_root,
                logs_root,
                runner_slug=runner.slug,
                executable=runner.executable,
                model=runner.model,
                prompt_text=repair_prompt,
                log_stem=log_stem,
                timeout_seconds=min(self.max_seconds, 900 if attempt == 1 else 600),
            )
            last_record = repair_record
            total_duration += repair_record.duration_seconds
            result.log_paths["recursive_repair_stdout"] = self.rel(stdout_log)
            result.log_paths["recursive_repair_stderr"] = self.rel(stderr_log)
            self.evaluate_recursive_run(repo_root, logs_root, result)
            if self.reconcile_pragmatic_tdd_exception_field(repo_root, logs_root, result):
                self.evaluate_recursive_run(repo_root, logs_root, result)
            if self.reconcile_recursive_requirement_changed_files(repo_root, logs_root, result):
                self.evaluate_recursive_run(repo_root, logs_root, result)
            attempt += 1
        result.phase_durations["recursive_repair"] = round(total_duration, 2)
        if last_record is not None and self.should_attempt_recursive_repair(result):
            if last_record.timed_out:
                result.issues.append("Recursive repair pass timed out before closeout artifacts were completed.")
            elif last_record.returncode != 0:
                result.issues.append("Recursive repair pass exited non-zero.")
        return last_record

    def read_recursive_lint_baseline_ref(self, repo_root: Path, result: ArmResult) -> str:
        if not result.run_id:
            return ""
        worktree_doc = repo_root / ".recursive" / "run" / result.run_id / "00-worktree.md"
        if not worktree_doc.exists():
            return ""
        text = worktree_doc.read_text(encoding="utf-8", errors="replace")
        for label in ("Normalized baseline", "Baseline reference"):
            match = re.search(rf"(?mi)^-\s*{re.escape(label)}:\s*`?([^`\r\n]+)`?\s*$", text)
            if match:
                return match.group(1).strip()
        return ""

    def materialize_git_archive(self, repo_root: Path, destination_root: Path, git_ref: str) -> bool:
        archive_path = destination_root.parent / f"baseline-{uuid.uuid4().hex}.tar"
        try:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            record = self.run_command(
                ["git", "archive", "--format=tar", "-o", str(archive_path), git_ref],
                cwd=repo_root,
                timeout_seconds=60,
                check=False,
            )
            if record.returncode != 0 or not archive_path.exists():
                return False
            destination_root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path) as archive:
                archive.extractall(destination_root)
            return True
        finally:
            archive_path.unlink(missing_ok=True)

    def commit_lint_snapshot_baseline(self, lint_root: Path) -> str:
        add_result = self.run_command(["git", "add", "-A", "-f", "--", "."], cwd=lint_root, timeout_seconds=60, check=False)
        if add_result.returncode != 0:
            return ""
        commit_result = self.run_command(
            [
                "git",
                "-c",
                "user.name=Benchmark Snapshot",
                "-c",
                "user.email=benchmark-snapshot@example.com",
                "commit",
                "--no-gpg-sign",
                "-m",
                "benchmark lint snapshot baseline",
            ],
            cwd=lint_root,
            timeout_seconds=60,
            check=False,
        )
        if commit_result.returncode != 0:
            return ""
        head_result = self.run_command(["git", "rev-parse", "HEAD"], cwd=lint_root, timeout_seconds=30, check=False)
        if head_result.returncode != 0:
            return ""
        return head_result.stdout.strip()

    def rewrite_snapshot_diff_basis(self, snapshot_run_root: Path, baseline_commit: str) -> None:
        worktree_doc = snapshot_run_root / "00-worktree.md"
        if not worktree_doc.exists():
            return
        text = worktree_doc.read_text(encoding="utf-8", errors="replace")
        replacements = {
            "Baseline type": "local commit",
            "Baseline reference": baseline_commit,
            "Comparison reference": "working-tree",
            "Normalized baseline": baseline_commit,
            "Normalized comparison": "working-tree",
            "Normalized diff command": f"git diff --name-only {baseline_commit}",
        }
        for label, value in replacements.items():
            text = re.sub(
                rf"(?mi)^([ \t]*-\s*{re.escape(label)}:\s*)(`?)[^`\r\n]+(`?)\s*$",
                rf"\1`{value}`",
                text,
                count=1,
            )
        worktree_doc.write_text(text, encoding="utf-8", newline="\n")

    def resolve_product_root(self, repo_root: Path, result: ArmResult) -> Path:
        if result.arm_name != "recursive-on" or not result.run_id:
            return repo_root
        if result.expected_product_root:
            expected_candidate = repo_root / result.expected_product_root
            if expected_candidate.exists():
                return expected_candidate
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
        raw_value = ""
        for pattern in (
            r"(?im)^\s*-\s*(?:Selected\s+)?Worktree location:\s*(.+?)\s*$",
            r"(?im)^\s*-\s*Location:\s*(.+?)\s*$",
            r"(?im)^\s*-\s*Product root:\s*(.+?)\s*$",
        ):
            match = re.search(pattern, text)
            if match:
                raw_value = match.group(1).strip()
                break
        if not raw_value:
            return None, "missing", ""
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

    def collect_changed_paths(self, repo_root: Path) -> list[str]:
        status_result = self.run_command(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=repo_root,
            timeout_seconds=min(self.command_timeout, 120),
            check=False,
            allowed_returncodes=(0,),
        )
        if status_result.returncode != 0:
            return []
        return parse_git_status_paths(status_result.stdout)

    def extract_claimed_product_files(self, run_root: Path, product_root: Path, expected_product_root: str) -> list[str]:
        claimed: list[str] = []
        section_field_map: dict[str, dict[str, tuple[str, ...]]] = {
            "03-implementation-summary.md": {
                "Requirement Completion Status": ("Changed Files", "Implementation Evidence"),
            },
            "04-test-summary.md": {
                "Requirement Completion Status": ("Changed Files", "Implementation Evidence", "Verification Evidence"),
            },
        }
        plain_sections: dict[str, tuple[str, ...]] = {
            "03-implementation-summary.md": ("Changes Applied", "Implementation Evidence"),
            "04-test-summary.md": ("Evidence and Artifacts",),
        }
        for file_name in ("03-implementation-summary.md", "04-test-summary.md"):
            artifact_path = run_root / file_name
            if not artifact_path.exists():
                continue
            artifact_text = artifact_path.read_text(encoding="utf-8", errors="replace")
            for heading in plain_sections.get(file_name, ()):
                section_body = self.get_heading_body(artifact_text, heading)
                for candidate in self.extract_claimed_paths_from_text(section_body, product_root, expected_product_root):
                    if self.is_product_path(candidate):
                        claimed.append(candidate)
            for heading, field_names in section_field_map.get(file_name, {}).items():
                section_body = self.get_heading_body(artifact_text, heading)
                for entry in self.parse_pipe_entry_fields(section_body):
                    for field_name in field_names:
                        for candidate in self.extract_claimed_paths_from_text(
                            entry.get(field_name, ""),
                            product_root,
                            expected_product_root,
                        ):
                            if self.is_product_path(candidate):
                                claimed.append(candidate)
        return dedupe_preserve_order(claimed)

    def evaluate_recursive_delivery(self, repo_root: Path, product_root: Path, result: ArmResult) -> None:
        if result.arm_name != "recursive-on":
            result.recursive_delivery_status = "n/a"
            return

        expected_root = repo_root / result.expected_product_root if result.expected_product_root else None
        if expected_root is None:
            result.recursive_delivery_status = "missing-expected-product-root"
            self.add_issue(result, "Recursive benchmark metadata did not record an expected product worktree.")
            return
        if not expected_root.exists():
            result.recursive_delivery_status = "missing-expected-product-root"
            self.add_issue(result, "Recursive benchmark expected product worktree was not created.")
            return

        try:
            resolved_product_matches_expected = product_root.resolve() == expected_root.resolve()
        except OSError:
            resolved_product_matches_expected = False
        if not resolved_product_matches_expected:
            result.recursive_delivery_status = "unexpected-product-root"
            self.add_issue(
                result,
                "Recursive benchmark evaluation resolved a different product root than the expected worktree.",
            )
            return

        run_root = repo_root / ".recursive" / "run" / result.run_id
        result.recursive_claimed_files = (
            self.extract_claimed_product_files(run_root, product_root, result.expected_product_root)
            if run_root.exists()
            else []
        )
        result.recursive_product_change_paths = [
            path for path in self.collect_changed_paths(product_root) if self.is_product_path(path)
        ]
        result.recursive_root_product_drift = [
            path for path in self.collect_changed_paths(repo_root) if self.is_product_path(path)
        ]
        changed_set = set(result.recursive_product_change_paths)
        result.recursive_missing_claimed_files = [
            path for path in result.recursive_claimed_files if path not in changed_set
        ]

        if not result.recursive_product_change_paths:
            if result.recursive_root_product_drift:
                result.recursive_delivery_status = "wrong-root-edits"
                self.add_issue(
                    result,
                    "Recursive benchmark run changed product files in the control-plane repo root while the declared worktree remained at baseline.",
                )
            else:
                result.recursive_delivery_status = "baseline-worktree"
                self.add_issue(result, "Recursive benchmark run left the declared product worktree at baseline.")
            return

        if result.recursive_missing_claimed_files:
            result.recursive_delivery_status = "claimed-files-missing-in-worktree"
            self.add_issue(
                result,
                "Recursive run artifacts claim product file changes missing from the declared worktree: "
                + ", ".join(result.recursive_missing_claimed_files)
                + ".",
            )
            return

        if result.recursive_root_product_drift:
            result.recursive_delivery_status = "split-delivery"
            self.add_issue(
                result,
                "Recursive benchmark run split product edits between the declared worktree and the control-plane repo root.",
            )
            return

        result.recursive_delivery_status = "ok"

    def should_snapshot_rust_evaluation_root(self, repo_root: Path, product_root: Path, result: ArmResult) -> bool:
        if not self.uses_rust_wasm_toolchain() or result.arm_name != "recursive-on":
            return False
        if not product_root.exists() or not (repo_root / "Cargo.toml").exists():
            return False
        try:
            repo_resolved = repo_root.resolve()
            product_resolved = product_root.resolve()
        except OSError:
            return False
        if product_resolved == repo_resolved:
            return False
        try:
            product_resolved.relative_to(repo_resolved)
        except ValueError:
            return False
        return True

    def prepare_evaluation_root(self, repo_root: Path, product_root: Path, logs_root: Path, result: ArmResult) -> Path:
        if not self.should_snapshot_rust_evaluation_root(repo_root, product_root, result):
            return product_root
        evaluation_root = logs_root / "evaluation-root"
        if evaluation_root.exists():
            remove_tree(evaluation_root)
        ignore = shutil.ignore_patterns(".git", "target", "dist", ".cargo-target-dir", ".playwright-mcp", "__pycache__")
        shutil.copytree(product_root, evaluation_root, ignore=ignore)
        result.log_paths["evaluation_root"] = self.rel(evaluation_root)
        return evaluation_root

    def should_snapshot_recursive_lint_root(self, repo_root: Path, product_root: Path, result: ArmResult) -> bool:
        if result.arm_name != "recursive-on":
            return False
        if not product_root.exists():
            return False
        try:
            repo_resolved = repo_root.resolve()
            product_resolved = product_root.resolve()
        except OSError:
            return False
        if product_resolved == repo_resolved:
            return False
        try:
            product_resolved.relative_to(repo_resolved)
        except ValueError:
            return False
        return True

    def prepare_recursive_lint_root(self, repo_root: Path, product_root: Path, logs_root: Path, result: ArmResult) -> Path:
        if not self.should_snapshot_recursive_lint_root(repo_root, product_root, result):
            return repo_root
        lint_root = logs_root / "recursive-lint-root"
        if lint_root.exists():
            remove_tree(lint_root)
        root_ignore = shutil.ignore_patterns(".worktrees", ".playwright-mcp", ".cargo-target-dir", "__pycache__")
        shutil.copytree(repo_root, lint_root, ignore=root_ignore)
        try:
            relative_product_root = product_root.resolve().relative_to(repo_root.resolve())
        except (OSError, ValueError):
            result.log_paths["recursive_lint_root"] = self.rel(lint_root)
            return lint_root
        destination_product_root = lint_root / relative_product_root
        product_runtime_ignore = {".git", "target", "dist", ".cargo-target-dir", ".playwright-mcp", "__pycache__", ".recursive"}

        def product_ignore(directory: str, names: list[str]) -> set[str]:
            ignored = {name for name in names if name in product_runtime_ignore}
            try:
                relative_directory = Path(directory).resolve().relative_to(product_root.resolve())
            except OSError:
                relative_directory = Path()
            except ValueError:
                relative_directory = Path()
            if relative_directory == Path("benchmark"):
                for name in names:
                    if name in {"agent-log.md", "screenshots"}:
                        continue
                    ignored.add(name)
            return ignored

        baseline_ref = self.read_recursive_lint_baseline_ref(repo_root, result)
        baseline_seeded = False
        if baseline_ref:
            baseline_seeded = self.materialize_git_archive(repo_root, destination_product_root, baseline_ref)
            if baseline_seeded:
                baseline_commit = self.commit_lint_snapshot_baseline(lint_root)
                if baseline_commit:
                    snapshot_run_root = lint_root / ".recursive" / "run" / result.run_id
                    self.rewrite_snapshot_diff_basis(snapshot_run_root, baseline_commit)
                else:
                    baseline_seeded = False
                    remove_tree(destination_product_root)
        destination_product_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(product_root, destination_product_root, ignore=product_ignore, dirs_exist_ok=baseline_seeded)
        # The benchmark repos commonly ignore `.worktrees/`, so register the copied worktree
        # path as intent-to-add inside the disposable lint snapshot so `git diff` can see it.
        self.run_command(
            ["git", "add", "-N", "-f", "--", str(relative_product_root).replace("\\", "/")],
            cwd=lint_root,
            timeout_seconds=30,
        )
        result.log_paths["recursive_lint_root"] = self.rel(lint_root)
        return lint_root

    @staticmethod
    def has_heading(content: str, heading_text: str) -> bool:
        return bool(re.search(rf"(?m)^[ \t]*##\s+{re.escape(heading_text)}\s*$", content))

    @staticmethod
    def get_heading_body(content: str, heading_text: str) -> str:
        match = re.search(
            rf"(?ms)^[ \t]*##\s+{re.escape(heading_text)}\s*$\n?(.*?)(?=^[ \t]*##\s+|\Z)",
            content,
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def parse_pipe_entry_fields(section_body: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        if not section_body:
            return entries
        for raw_line in section_body.splitlines():
            line = raw_line.strip()
            if not line.startswith(("-", "*")):
                continue
            body = line[1:].strip()
            parts = [part.strip() for part in body.split("|") if part.strip()]
            if len(parts) < 2:
                continue
            fields: dict[str, str] = {"Requirement ID": parts[0].strip("`")}
            for part in parts[1:]:
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                fields[key.strip()] = value.strip().strip("`")
            entries.append(fields)
        return entries

    @staticmethod
    def normalize_changed_files_field(field_value: str, diff_paths: set[str]) -> tuple[str, bool]:
        cited_paths = re.findall(r"`([^`\r\n]+)`", field_value)
        if not cited_paths:
            return field_value, False
        kept_paths = [path for path in cited_paths if normalize_benchmark_path(path) in diff_paths]
        if not kept_paths or kept_paths == cited_paths:
            return field_value, False
        return ", ".join(f"`{path}`" for path in kept_paths), True

    def trim_requirement_changed_files_to_diff(self, artifact_path: Path, diff_paths: set[str]) -> bool:
        if not artifact_path.exists():
            return False
        original = artifact_path.read_text(encoding="utf-8", errors="replace")
        lines = original.splitlines()
        updated_lines: list[str] = []
        in_requirement_status = False
        changed = False
        for line in lines:
            stripped = line.strip()
            if re.match(r"^[ \t]*##\s+Requirement Completion Status\s*$", line):
                in_requirement_status = True
                updated_lines.append(line)
                continue
            if in_requirement_status and re.match(r"^[ \t]*##\s+", line):
                in_requirement_status = False
            if in_requirement_status and stripped.startswith("- ") and "Changed Files:" in line:
                indent = line[: len(line) - len(line.lstrip())]
                body = stripped[2:]
                parts = [part.strip() for part in body.split(" | ")]
                for index, part in enumerate(parts):
                    if not part.startswith("Changed Files:"):
                        continue
                    value = part[len("Changed Files:") :].strip()
                    normalized_value, part_changed = self.normalize_changed_files_field(value, diff_paths)
                    if part_changed:
                        parts[index] = f"Changed Files: {normalized_value}"
                        changed = True
                line = indent + "- " + " | ".join(parts)
            updated_lines.append(line)
        if not changed:
            return False
        artifact_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8", newline="\n")
        return True

    def reconcile_recursive_requirement_changed_files(self, repo_root: Path, logs_root: Path, result: ArmResult) -> bool:
        if result.arm_name != "recursive-on" or not result.run_id or result.recursive_workflow_status != "lint-failed":
            return False
        lint_findings = self.collect_recursive_lint_findings(logs_root / "recursive-lint.log")
        if not any("Changed Files are outside the current diff scope" in finding for finding in lint_findings):
            return False
        lint_root = logs_root / "recursive-lint-root"
        run_root = repo_root / ".recursive" / "run" / result.run_id
        if not lint_root.exists() or not run_root.exists():
            return False
        diff_result = self.run_command(
            ["git", "diff", "--name-only"],
            cwd=lint_root,
            timeout_seconds=30,
            check=False,
        )
        if diff_result.returncode != 0:
            return False
        diff_paths = {
            normalize_benchmark_path(raw_line.strip())
            for raw_line in diff_result.stdout.splitlines()
            if raw_line.strip()
        }
        if not diff_paths:
            return False
        changed = False
        for artifact_name in (
            "03-implementation-summary.md",
            "04-test-summary.md",
            "06-decisions-update.md",
            "07-state-update.md",
            "08-memory-impact.md",
        ):
            if self.trim_requirement_changed_files_to_diff(run_root / artifact_name, diff_paths):
                changed = True
        return changed

    def normalize_claimed_product_path(self, raw_value: str, product_root: Path, expected_product_root: str) -> str:
        candidate = raw_value.strip().strip("`").strip()
        if not candidate:
            return ""
        try:
            path_candidate = Path(candidate)
        except OSError:
            path_candidate = None
        if path_candidate is not None and path_candidate.is_absolute():
            try:
                return normalize_benchmark_path(str(path_candidate.resolve().relative_to(product_root.resolve())))
            except (OSError, ValueError):
                pass
        normalized = normalize_benchmark_path(candidate)
        product_prefix = normalize_benchmark_path(expected_product_root)
        if product_prefix and normalized.startswith(product_prefix + "/"):
            return normalized[len(product_prefix) + 1 :]
        return normalized

    def extract_claimed_paths_from_text(self, text: str, product_root: Path, expected_product_root: str) -> list[str]:
        if not text:
            return []
        raw_candidates: list[str] = []
        raw_candidates.extend(re.findall(r"`([^`\r\n]+)`", text))
        raw_candidates.extend(re.findall(r"(?<![\w.-])(?:[.\w-]+[\\/])+[.\w-]+", text))
        for file_name in sorted(EXPLICIT_PRODUCT_FILE_NAMES):
            if re.search(rf"(?<![\w/\\.-]){re.escape(file_name)}(?![\w/\\.-])", text):
                raw_candidates.append(file_name)
        normalized_candidates: list[str] = []
        for raw_candidate in raw_candidates:
            raw_text = raw_candidate.strip().strip("`").strip()
            normalized_raw = normalize_benchmark_path(raw_text)
            if (
                "/" not in normalized_raw
                and "\\" not in raw_text
                and Path(normalized_raw).name not in EXPLICIT_PRODUCT_FILE_NAMES
            ):
                continue
            candidate = self.normalize_claimed_product_path(raw_candidate, product_root, expected_product_root)
            if candidate:
                normalized_candidates.append(candidate)
        return dedupe_preserve_order(normalized_candidates)

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
        evaluation_root = self.prepare_evaluation_root(repo_root, product_root, logs_root, result)
        build_command = self.build_command()
        build_result = self.run_command(
            build_command,
            cwd=evaluation_root,
            timeout_seconds=self.command_timeout,
            env=self.rust_wasm_env(),
            check=False,
        )
        self.write_command_log(logs_root / "build.log", command_string(build_command), build_result)
        result.log_paths["build"] = self.rel(logs_root / "build.log")
        result.phase_durations["build"] = round(build_result.duration_seconds, 2)
        result.build_success = build_result.returncode == 0 and not build_result.timed_out
        if not result.build_success:
            self.add_issue(result, "Build failed.")

        test_command = self.test_command()
        test_result = self.run_command(
            test_command,
            cwd=evaluation_root,
            timeout_seconds=self.command_timeout,
            env=self.rust_wasm_env(),
            check=False,
        )
        self.write_command_log(logs_root / "test.log", command_string(test_command), test_result)
        result.log_paths["test"] = self.rel(logs_root / "test.log")
        result.phase_durations["test"] = round(test_result.duration_seconds, 2)
        result.test_success = test_result.returncode == 0 and not test_result.timed_out
        if not result.test_success:
            self.add_issue(result, "Tests failed.")

        preview_port = detect_port()
        preview_url = f"http://{DEFAULT_PREVIEW_HOST}:{preview_port}/"
        preview_log = logs_root / "preview.log"
        preview_started = False
        preview_process: subprocess.Popen | None = None
        preview_start = time.perf_counter()
        cleanup_note = ""
        preview_command = self.preview_command(preview_port)
        try:
            preview_env = os.environ.copy()
            preview_env.update(self.rust_wasm_env())
            preview_process = subprocess.Popen(
                preview_command,
                cwd=str(evaluation_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=preview_env,
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
            self.add_issue(result, "Preview server did not become reachable.")

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
        self.evaluate_recursive_run(repo_root, logs_root, result)
        self.evaluate_recursive_delivery(repo_root, product_root, result)
        self.score_repo(repo_root, product_root, result)

    def score_repo(self, repo_root: Path, product_root: Path, result: ArmResult) -> None:
        breakdown: dict[str, float] = {}
        breakdown_max: dict[str, float] = {}
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
            breakdown_max[label] = maximum
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
        elif self.scenario_name == "scientific-calculator-rust":
            self.score_scientific_calculator_repo(source_text, result, add_score)
        else:
            self.score_planner_repo(source_text, result, add_score)

        result.hint_penalty = round(result.hint_count * max(0.0, self.args.hint_penalty), 2)
        if result.hint_penalty:
            result.issues.append(
                f"Applied hint penalty: {format_score(result.hint_penalty)} point(s) across {result.hint_count} hint event(s)."
            )

        result.score_breakdown = breakdown
        result.score_breakdown_max = breakdown_max
        result.judge_adjusted_score_breakdown = {}
        result.judge_adjusted_score = None
        result.judge_entry_adjustments = {}
        result.judge_entry_adjustment_reasons = {}
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

    def score_scientific_calculator_repo(self, source_text: str, result: ArmResult, add_score) -> None:
        dual_display = ("expression" in source_text or "tape" in source_text) and (
            "display" in source_text or "result" in source_text
        )
        editing_controls = any(
            marker in source_text
            for marker in (
                "backspace",
                "clear entry",
                "clear_entry",
                "clearentry",
                "clear all",
                "clear_all",
                "clearall",
                "toggle_sign",
                "sign",
                '"ce"',
                '"ac"',
                "⌫",
            )
        )
        add_score(
            "dual_display_editing",
            10 if dual_display and editing_controls else 5 if dual_display else 0,
            10,
            zero_issue="Dual-display or expression-editing heuristics were not detected.",
            partial_issue="A calculator display was detected, but expression-editing controls appear incomplete.",
        )
        parser_precedence = (
            "parenth" in source_text
            and any(
                marker in source_text
                for marker in (
                    "precedence",
                    "precedence climbing",
                    "shunting",
                    "operator_stack",
                    "parse_expression",
                    "recursive descent",
                    "parse_add_sub",
                    "parse_mul_div",
                    "parse_pow",
                    "parse_power",
                )
            )
        ) or ("^" in source_text and any(marker in source_text for marker in ("operator", "parse_pow", "parse_power")))
        add_score(
            "parser_precedence",
            15 if parser_precedence else 0,
            15,
            zero_issue="Expression parser or operator-precedence heuristics were not detected.",
        )
        scientific_markers = sum(
            marker in source_text for marker in ("sin", "cos", "tan", "sqrt", "log", "ln", "pow", "pi", " e ")
        )
        add_score(
            "scientific_functions",
            15 if scientific_markers >= 6 else 8 if scientific_markers >= 4 else 0,
            15,
            zero_issue="Scientific-function heuristics were not detected.",
            partial_issue="Some scientific functions were detected, but the calculator surface still appears incomplete.",
        )
        angle_mode = (
            "degree" in source_text and "radian" in source_text
        ) or (
            "anglemode" in source_text
            and any(marker in source_text for marker in ("deg", "degree"))
            and any(marker in source_text for marker in ("rad", "radian"))
        )
        add_score(
            "angle_mode",
            10 if angle_mode else 0,
            10,
            zero_issue="Degree/radian mode heuristics were not detected.",
        )
        memory_history = "memory" in source_text and "history" in source_text
        add_score(
            "memory_history",
            10 if memory_history else 5 if ("memory" in source_text or "history" in source_text) else 0,
            10,
            zero_issue="Memory-register or history heuristics were not detected.",
            partial_issue="Memory or history support was partially detected, but one surface appears incomplete.",
        )
        persistence = any(
            marker in source_text
            for marker in ("local_storage", "localstorage", "gloo_storage", "storage::", "set_item(", "get_item(")
        )
        add_score(
            "persistence",
            10 if persistence else 0,
            10,
            zero_issue="Local persistence heuristics were not detected.",
        )
        keyboard_support = any(
            marker in source_text for marker in ("keyboardevent", "keydown", "onkeydown", "enter", "backspace", "escape")
        )
        add_score(
            "keyboard_support",
            5 if keyboard_support else 0,
            5,
            zero_issue="Keyboard-input heuristics were not detected.",
        )
        error_handling = any(
            marker in source_text
            for marker in (
                "divide by zero",
                "division by zero",
                "domain",
                "error",
                "invalid expression",
                "sqrt of negative",
                "non-positive",
            )
        )
        add_score(
            "error_handling",
            5 if error_handling else 0,
            5,
            zero_issue="Visible calculator error-handling heuristics were not detected.",
        )
        display_formatting = any(
            marker in source_text
            for marker in ("scientific notation", "format_result", "format_val", "trim_trailing", "trim_end_matches", "{:.12}")
        )
        add_score(
            "display_formatting",
            5 if display_formatting else 0,
            5,
            zero_issue="Result-formatting heuristics were not detected.",
        )
        responsive_ui = (
            ("@media" in source_text and "grid" in source_text)
            or "minmax" in source_text
            or ("grid-template-columns" in source_text and "max-width" in source_text)
            or ("display: grid" in source_text and "max-width" in source_text)
        )
        add_score(
            "responsive_ui",
            5 if responsive_ui else 0,
            5,
            zero_issue="Responsive scientific-calculator UI heuristics were not detected.",
        )

    def read_repo_source(self, repo_root: Path) -> str:
        parts: list[str] = []
        allowed_extensions = self.source_extensions()
        for path in sorted(repo_root.rglob("*")):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(repo_root).parts
            if any(part in IGNORED_SOURCE_DIRS for part in relative_parts[:-1]):
                continue
            if path.suffix.lower() not in allowed_extensions:
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
        entry_adjustments = payload.get("entry_adjustments")
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
        parsed_adjustments: dict[str, float] = {}
        parsed_adjustment_reasons: dict[str, str] = {}
        if isinstance(entry_adjustments, dict):
            for raw_key, raw_value in entry_adjustments.items():
                key = str(raw_key).strip()
                if not key:
                    continue
                score_value: float | None = None
                reason = ""
                if isinstance(raw_value, (int, float)):
                    score_value = float(raw_value)
                elif isinstance(raw_value, dict):
                    candidate_score = raw_value.get("score")
                    if isinstance(candidate_score, (int, float)):
                        score_value = float(candidate_score)
                    candidate_reason = raw_value.get("reason")
                    if isinstance(candidate_reason, str):
                        reason = candidate_reason.strip()
                if score_value is None:
                    continue
                parsed_adjustments[key] = score_value
                if reason:
                    parsed_adjustment_reasons[key] = reason
        result.judge_entry_adjustments = parsed_adjustments
        result.judge_entry_adjustment_reasons = parsed_adjustment_reasons
        self.apply_judge_entry_adjustments(result)
        result.log_paths["judge_metric"] = self.rel(candidate)

    def apply_judge_entry_adjustments(self, result: ArmResult) -> None:
        result.judge_adjusted_score_breakdown = {}
        result.judge_adjusted_score = None
        if not result.judge_entry_adjustments or not result.score_breakdown:
            return

        adjusted = dict(result.score_breakdown)
        applied = False
        unknown_keys: list[str] = []
        for key, requested_score in result.judge_entry_adjustments.items():
            if key not in adjusted:
                unknown_keys.append(key)
                continue
            maximum = result.score_breakdown_max.get(key, max(adjusted[key], requested_score, 0.0))
            bounded = max(0.0, min(maximum, requested_score))
            if bounded == adjusted[key]:
                continue
            adjusted[key] = bounded
            applied = True

        if unknown_keys:
            result.issues.append(
                "Judge entry adjustments referenced unknown score keys: "
                + ", ".join(f"`{key}`" for key in sorted(unknown_keys))
                + "."
            )
        if not applied:
            return

        result.judge_adjusted_score_breakdown = adjusted
        result.judge_adjusted_score = max(0.0, sum(adjusted.values()) - result.hint_penalty)

    def effective_score_breakdown(self, result: ArmResult) -> dict[str, float]:
        return result.judge_adjusted_score_breakdown or result.score_breakdown

    def normalized_score(self, value: float | None, maximum: float) -> float | None:
        if value is None or maximum <= 0:
            return None
        return round((value / maximum) * DEFAULT_BENCHMARK_SCORE_MAX, 1)

    def format_entry_score(self, result: ArmResult, key: str) -> str:
        adjusted = self.effective_score_breakdown(result).get(key, 0.0)
        raw = result.score_breakdown.get(key)
        if raw is None or adjusted == raw:
            return f"`{format_score(adjusted)}`"
        return f"`{format_score(adjusted)} (raw {format_score(raw)})`"

    def describe_entry_adjustment(self, result: ArmResult, key: str, arm_label: str) -> str:
        if key not in result.judge_adjusted_score_breakdown or key not in result.score_breakdown:
            return ""
        adjusted = result.judge_adjusted_score_breakdown[key]
        raw = result.score_breakdown[key]
        if adjusted == raw:
            return ""
        reason = result.judge_entry_adjustment_reasons.get(key, "")
        detail = f"{arm_label} adjusted {format_score(raw)} -> {format_score(adjusted)}"
        return f"{detail} ({reason})" if reason else detail

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
            root_drift = ", ".join(result.recursive_root_product_drift) if result.recursive_root_product_drift else "none"
            missing_claimed = ", ".join(result.recursive_missing_claimed_files) if result.recursive_missing_claimed_files else "none"
            recursive_context = (
                "\nRecursive workflow context:\n"
                f"- Recursive workflow status: {result.recursive_workflow_status}\n"
                f"- Worktree isolation status: {result.recursive_isolation_status}\n"
                f"- Worktree location: {result.recursive_worktree_location or 'n/a'}\n"
                f"- Run id: {result.run_id or 'n/a'}\n"
                f"- Run root: {result.recursive_run_root or 'n/a'}\n"
                f"- Expected product root: {result.expected_product_root or 'n/a'}\n"
                f"- Product root: {product_root_display}\n"
                f"- Delivery integrity status: {result.recursive_delivery_status}\n"
                f"- Claimed product files: {', '.join(result.recursive_claimed_files) if result.recursive_claimed_files else 'none'}\n"
                f"- Changed product files in product root: {', '.join(result.recursive_product_change_paths) if result.recursive_product_change_paths else 'none'}\n"
                f"- Root-only product drift: {root_drift}\n"
                f"- Claimed files missing in worktree: {missing_claimed}\n"
                f"- Missing recursive artifacts: {', '.join(missing)}\n"
            )
            if product_root_display != ".":
                recursive_context += (
                    f"- Authoritative benchmark progress log: {product_benchmark_path}agent-log.md\n"
                    "- Judge note: when the product root differs from the repo root, treat the product-root "
                    "`benchmark/agent-log.md` as the primary timestamped progress log. The repo-root "
                    "`benchmark/agent-log.md` may contain controller metadata only and should not be penalized on "
                    "that basis alone.\n"
                )

        brief_text = (
            "You are the mandatory controller-side code-review judge for a recursive-mode benchmark.\n"
            "Review the repository in the current working directory against the requirements and rubric below.\n"
            "Do not modify product code or benchmark logs. Only write benchmark/judge-metric.json.\n"
            "If benchmark/judge-metric.json already exists, overwrite it.\n"
            "Use a 0-10 overall score where 10 means the implementation is highly faithful, robust, and benchmark-complete.\n"
            "Apply the evidence-form rule: if something is implemented but the required evidence form is incomplete, deduct half credit for that portion.\n"
            "If the raw heuristic entry breakdown overstates or understates the implementation, correct the specific entry scores in "
            "`entry_adjustments` using the exact entry keys listed below. Use final corrected scores, not deltas.\n"
            "Only adjust entry keys when your review found a concrete mismatch between the raw heuristic and the actual delivered outcome.\n"
            "Prefer concrete issues over generic comments. Return a short confirmation after writing the file.\n\n"
            "Write benchmark/judge-metric.json with this exact JSON shape:\n"
            "{\n"
            '  "score": 0,\n'
            f'  "max": {int(DEFAULT_JUDGE_MAX)},\n'
            '  "judge_runner": "<runner name>",\n'
            '  "judge_model": "<model name>",\n'
            '  "summary": "<1-2 sentence summary>",\n'
            '  "notes": ["<concrete finding>", "<concrete finding>"],\n'
            '  "entry_adjustments": {\n'
            '    "<entry key>": { "score": 0, "reason": "<short concrete reason>" }\n'
            "  }\n"
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
            "Current heuristic entry breakdown (use these exact keys if you correct any entry):\n"
            + (
                "".join(
                    f"- {key}: {format_score(value)}/{format_score(result.score_breakdown_max.get(key, value))}\n"
                    for key, value in sorted(result.score_breakdown.items())
                )
                if result.score_breakdown
                else "- none\n"
            )
            + "\n"
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
        result.judge_entry_adjustments = {}
        result.judge_entry_adjustment_reasons = {}
        result.judge_adjusted_score_breakdown = {}
        result.judge_adjusted_score = None

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

    def evaluate_recursive_run(self, repo_root: Path, logs_root: Path, result: ArmResult) -> None:
        if result.arm_name != "recursive-on":
            result.recursive_workflow_status = "n/a"
            result.recursive_isolation_status = "n/a"
            return
        self.clear_recursive_evaluation_issues(result)
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

        product_root_for_lint = self.resolve_product_root(repo_root, result)
        lint_repo_root = self.prepare_recursive_lint_root(repo_root, product_root_for_lint, logs_root, result)
        lint_result = self.run_command(
            [
                self.python_exe,
                str(self.script_dir / "lint-recursive-run.py"),
                "--repo-root",
                str(lint_repo_root),
                "--run-id",
                result.run_id,
                "--strict",
            ],
            cwd=lint_repo_root,
            timeout_seconds=min(self.command_timeout, 300),
            check=False,
        )
        self.write_command_log(logs_root / "recursive-lint.log", "recursive lint", lint_result)
        result.log_paths["recursive_lint"] = self.rel(logs_root / "recursive-lint.log")
        result.phase_durations["recursive_lint"] = round(lint_result.duration_seconds, 2)
        lint_failed = lint_result.returncode != 0 or lint_result.timed_out
        if lint_failed and self.lint_has_only_optional_missing_artifact_warnings(logs_root / "recursive-lint.log"):
            lint_failed = False
        if lint_result.timed_out:
            result.issues.append("Recursive run lint timed out before benchmark closeout could be confirmed.")
        elif lint_result.returncode != 0:
            if lint_failed:
                result.issues.append("Recursive run artifacts failed controller-side lint.")

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
        elif lint_failed:
            result.recursive_workflow_status = "lint-failed"

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
            self.normalize_result_lists(result)
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
                    f"| Delivery integrity | `{off.recursive_delivery_status}` | `{on.recursive_delivery_status}` | n/a |",
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
            off_adjusted_percentage = self.normalized_score(off.judge_adjusted_score, off.score_max)
            on_adjusted_percentage = self.normalized_score(on.judge_adjusted_score, on.score_max)
            if off_adjusted_percentage is not None or on_adjusted_percentage is not None:
                adjusted_delta = (
                    format_score((on_adjusted_percentage or 0) - (off_adjusted_percentage or 0))
                    if off_adjusted_percentage is not None and on_adjusted_percentage is not None
                    else "n/a"
                )
                off_adjusted_text = (
                    f"{format_score(off_adjusted_percentage)}/100" if off_adjusted_percentage is not None else "n/a"
                )
                on_adjusted_text = (
                    f"{format_score(on_adjusted_percentage)}/100" if on_adjusted_percentage is not None else "n/a"
                )
                summary_lines.append(
                    f"| `normalized:entry-adjusted` | `{off_adjusted_text}` | `{on_adjusted_text}` | `{adjusted_delta}` |"
                )
            score_keys = sorted(set(off.score_breakdown) | set(on.score_breakdown))
            for key in score_keys:
                off_value = self.effective_score_breakdown(off).get(key, 0.0)
                on_value = self.effective_score_breakdown(on).get(key, 0.0)
                note_parts = [format_score(on_value - off_value)]
                off_adjustment = self.describe_entry_adjustment(off, key, "off")
                on_adjustment = self.describe_entry_adjustment(on, key, "on")
                if off_adjustment:
                    note_parts.append(off_adjustment)
                if on_adjustment:
                    note_parts.append(on_adjustment)
                summary_lines.append(
                    f"| `score:{key}` | {self.format_entry_score(off, key)} | {self.format_entry_score(on, key)} | {'; '.join(note_parts)} |"
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
            self.normalize_result_lists(result)
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
            "- Entry-table feature rows may show judge-adjusted per-entry scores when the code-review judge supplied concrete corrections; the blended benchmark score still uses raw heuristic + judge overall score to avoid double-counting the judge.",
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
                "| Runner | Arm | Model | Outcome | Benchmark score | Agent status | Product outcome | Recursive workflow | Worktree isolation | Delivery integrity | Duration (s) | Build | Test | Preview | Heuristic score | Judge metric | Screenshots | Tokens |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: | --- |",
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
                "| {runner} | {arm} | `{model}` | {status} | {benchmark_score} | {agent_status} | {product_status} | {workflow} | {isolation} | {delivery} | {duration:.2f} | {build} | {test} | {preview} | {score}/{score_max} | {judge_metric} | {screenshots} | {tokens} |".format(
                    runner=result.runner_name,
                    arm=result.arm_name,
                    model=result.model,
                    status=result.status,
                    benchmark_score=benchmark_score_text,
                    agent_status=result.agent_status,
                    product_status=result.product_status,
                    workflow=result.recursive_workflow_status,
                    isolation=result.recursive_isolation_status,
                    delivery=result.recursive_delivery_status,
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
                    f"- Delivery integrity: `{result.recursive_delivery_status}`",
                    (
                        f"- Worktree location: `{result.recursive_worktree_location}`"
                        if result.recursive_worktree_location
                        else "- Worktree location: `n/a`"
                    ),
                    (
                        f"- Expected product root: `{result.expected_product_root}`"
                        if result.expected_product_root
                        else "- Expected product root: `n/a`"
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
                        f"- Judge-adjusted entry score: `{format_score(result.judge_adjusted_score or 0)}/{format_score(result.score_max)}`"
                        if result.judge_adjusted_score is not None
                        else "- Judge-adjusted entry score: `n/a`"
                    ),
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
                    "#### Raw heuristic score breakdown",
                    "",
                ]
            )
            if result.score_breakdown:
                for key, value in sorted(result.score_breakdown.items()):
                    summary_lines.append(f"- `{key}`: {format_score(value)}")
            else:
                summary_lines.append("- none")
            summary_lines.extend(["", "#### Judge-adjusted score breakdown", ""])
            if result.judge_adjusted_score_breakdown:
                for key, value in sorted(result.judge_adjusted_score_breakdown.items()):
                    raw = result.score_breakdown.get(key, value)
                    reason = result.judge_entry_adjustment_reasons.get(key, "")
                    line = f"- `{key}`: {format_score(value)} (raw {format_score(raw)})"
                    if reason:
                        line += f" - {reason}"
                    summary_lines.append(line)
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
            summary_lines.extend(["", "#### Recursive delivery evidence", ""])
            if result.arm_name != "recursive-on":
                summary_lines.append("- n/a")
            else:
                summary_lines.append(
                    f"- Claimed product files: `{', '.join(result.recursive_claimed_files) if result.recursive_claimed_files else 'none'}`"
                )
                summary_lines.append(
                    f"- Changed product files in product root: `{', '.join(result.recursive_product_change_paths) if result.recursive_product_change_paths else 'none'}`"
                )
                summary_lines.append(
                    f"- Root-only product drift: `{', '.join(result.recursive_root_product_drift) if result.recursive_root_product_drift else 'none'}`"
                )
                summary_lines.append(
                    f"- Claimed files missing in worktree: `{', '.join(result.recursive_missing_claimed_files) if result.recursive_missing_claimed_files else 'none'}`"
                )
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
