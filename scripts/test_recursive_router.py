#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


class RecursiveRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="recursive-router-test-"))
        self.repo_root = self.temp_dir / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        self.home_dir = self.temp_dir / "home"
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.bin_dir = self.temp_dir / "bin"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        python_dir = str(Path(sys.executable).resolve().parent)
        self.env = os.environ.copy()
        self.env["PATH"] = os.pathsep.join([str(self.bin_dir), python_dir])
        self.env["HOME"] = str(self.home_dir)
        self.env["USERPROFILE"] = str(self.home_dir)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_repo_script(
        self,
        script_name: str,
        *args: str,
        allowed_returncodes: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_ROOT / script_name), *args],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        if completed.returncode not in allowed_returncodes:
            self.fail(
                f"{script_name} failed with code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return completed

    def load_json(self, path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))

    def policy_path(self) -> Path:
        return self.repo_root / ".recursive" / "config" / "recursive-router.json"

    def discovery_path(self) -> Path:
        return self.repo_root / ".recursive" / "config" / "recursive-router-discovered.json"

    def install_bootstrap(self) -> None:
        self.run_repo_script("install-recursive-mode.py", "--repo-root", str(self.repo_root))

    def initialize_router(self) -> None:
        self.run_repo_script("recursive-router-init.py", "--repo-root", str(self.repo_root))

    def run_repo_powershell_script(
        self,
        script_name: str,
        *args: str,
        allowed_returncodes: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[str]:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            self.skipTest("PowerShell is required for router PowerShell wrapper tests")
        completed = subprocess.run(
            [powershell, "-NoProfile", "-File", str(SCRIPTS_ROOT / script_name), *args],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        if completed.returncode not in allowed_returncodes:
            self.fail(
                f"{script_name} failed with code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return completed

    def write_policy(self, payload: dict[str, object]) -> None:
        write_text(self.policy_path(), json.dumps(payload, indent=2))

    def write_home_file(self, relative_path: str, content: str) -> Path:
        path = self.home_dir / relative_path
        write_text(path, content)
        return path

    def make_fake_cli(
        self,
        name: str,
        *,
        version: str = "1.2.3",
        models: list[str] | None = None,
        app_server_models: list[str] | None = None,
        invoke_echo: bool = True,
        invoke_exit: int = 0,
        probe_exit: int = 0,
        model_exit: int = 0,
        probe_sleep_seconds: float = 0.0,
        require_structured_run: bool = False,
        record_invocations_path: Path | None = None,
        emit_output_before_failure: bool = False,
    ) -> Path:
        runner_path = self.bin_dir / f"{name}-runner.py"
        model_lines = "\\n".join(models or [])
        app_server_payload = json.dumps(list(app_server_models or []))
        script = textwrap.dedent(
            f"""
            import json
            import pathlib
            import sys
            import time

            invoke_echo = {invoke_echo!r}
            invoke_exit = {invoke_exit!r}
            emit_output_before_failure = {emit_output_before_failure!r}
            record_invocations_path = {str(record_invocations_path) if record_invocations_path else None!r}
            args = sys.argv[1:]

            def emit_prompt(prompt: str) -> None:
                if record_invocations_path:
                    with pathlib.Path(record_invocations_path).open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(args) + "\\n")
                if invoke_exit != 0:
                    print("invocation failed", file=sys.stderr)
                    raise SystemExit(invoke_exit)
                if invoke_echo:
                    print(prompt)
                else:
                    print("verification failed")
                raise SystemExit(0)

            def emit_stream_json(prompt: str) -> None:
                if record_invocations_path:
                    with pathlib.Path(record_invocations_path).open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(args) + "\\n")
                message = prompt if invoke_echo else "verification failed"
                if emit_output_before_failure:
                    print(json.dumps({{"role": "assistant", "content": message}}))
                if invoke_exit != 0:
                    print("invocation failed", file=sys.stderr)
                    raise SystemExit(invoke_exit)
                print(json.dumps({{"role": "assistant", "content": message}}))
                print("<choice>STOP</choice>")
                raise SystemExit(0)

            if args == ["--version"]:
                if {probe_sleep_seconds!r}:
                    time.sleep({probe_sleep_seconds!r})
                if {probe_exit} != 0:
                    print("probe failed", file=sys.stderr)
                    raise SystemExit({probe_exit})
                print({version!r})
                raise SystemExit(0)
            if args == ["models", "list"]:
                if {model_exit} != 0:
                    print("model list failed", file=sys.stderr)
                    raise SystemExit({model_exit})
                output = {model_lines!r}
                if output:
                    print(output)
                raise SystemExit(0)
            if args == ["models"]:
                if {model_exit} != 0:
                    print("model list failed", file=sys.stderr)
                    raise SystemExit({model_exit})
                output = {model_lines!r}
                if output:
                    print(output)
                raise SystemExit(0)
            if (
                len(args) >= 11
                and args[0] == "--model"
                and args[2:10] == [
                    "--allow-all",
                    "--no-ask-user",
                    "--output-format",
                    "json",
                    "--stream",
                    "off",
                    "--no-color",
                    "-p",
                ]
            ):
                emit_prompt(args[10])
            if args[:2] == ["--model", args[1]] and "--output-format" in args and args[args.index("--output-format") + 1] == "stream-json" and "--work-dir" in args and "--prompt" in args:
                emit_stream_json(args[args.index("--prompt") + 1])
            if args[:2] == ["--model", args[1]] and "--prompt" in args:
                emit_prompt(args[args.index("--prompt") + 1])
            if args == ["app-server", "--listen", "stdio://"]:
                app_models = json.loads({app_server_payload!r})
                if not app_models:
                    print("app-server disabled", file=sys.stderr)
                    raise SystemExit(2)
                for raw_line in sys.stdin:
                    line = raw_line.strip()
                    if not line:
                        continue
                    message = json.loads(line)
                    method = message.get("method")
                    if method == "initialize":
                        print(
                            json.dumps(
                                {{
                                    "id": message["id"],
                                    "result": {{
                                        "userAgent": "fake-codex/0.0.0",
                                        "platformFamily": "windows",
                                        "platformOs": "windows",
                                    }},
                                }}
                            ),
                            flush=True,
                        )
                        continue
                    if method == "initialized":
                        continue
                    if method == "model/list":
                        print(
                            json.dumps(
                                {{
                                    "id": message["id"],
                                    "result": {{
                                        "data": [
                                            {{
                                                "id": model,
                                                "model": model,
                                                "displayName": model,
                                                "hidden": False,
                                                "isDefault": index == 0,
                                            }}
                                            for index, model in enumerate(app_models)
                                        ],
                                        "nextCursor": None,
                                    }},
                                }}
                            ),
                            flush=True,
                        )
                        continue
                    if method == "thread/start":
                        model = message.get("params", {{}}).get("model")
                        print(
                            json.dumps(
                                {{
                                    "id": message["id"],
                                    "result": {{
                                        "thread": {{"id": "00000000-0000-0000-0000-000000000001", "status": {{"type": "idle"}}}},
                                        "model": model,
                                        "modelProvider": "openai",
                                        "cwd": "D:\\\\repo",
                                        "approvalPolicy": "never",
                                        "approvalsReviewer": "user",
                                        "sandbox": {{"type": "readOnly", "access": {{"type": "fullAccess"}}, "networkAccess": False}},
                                        "reasoningEffort": "high",
                                    }},
                                }}
                            ),
                            flush=True,
                        )
                        continue
                    if method == "turn/start":
                        params = message.get("params", {{}})
                        prompt = params.get("input", [{{}}])[0].get("text", "")
                        turn_id = "00000000-0000-0000-0000-000000000002"
                        print(
                            json.dumps(
                                {{
                                    "id": message["id"],
                                    "result": {{
                                        "turn": {{"id": turn_id, "items": [], "status": "inProgress", "error": None}}
                                    }},
                                }}
                            ),
                            flush=True,
                        )
                        print(
                            json.dumps(
                                {{
                                    "method": "item/completed",
                                    "params": {{
                                        "threadId": params.get("threadId"),
                                        "turnId": turn_id,
                                        "item": {{
                                            "type": "agentMessage",
                                            "id": "msg-1",
                                            "text": prompt if invoke_echo else "verification failed",
                                            "phase": "final_answer",
                                        }},
                                    }},
                                }}
                            ),
                            flush=True,
                        )
                        print(
                            json.dumps(
                                {{
                                    "method": "turn/completed",
                                    "params": {{
                                        "threadId": params.get("threadId"),
                                        "turn": {{"id": turn_id, "items": [], "status": "completed", "error": None}},
                                    }},
                                }}
                            ),
                            flush=True,
                        )
                        continue
                    print(
                        json.dumps(
                            {{
                                "id": message.get("id"),
                                "error": {{"code": -32601, "message": f"unsupported method: {{method}}"}},
                            }}
                        ),
                        flush=True,
                    )
                raise SystemExit(0)
            if args[:1] == ["exec"] and "--input-file" in args:
                prompt_file = pathlib.Path(args[args.index("--input-file") + 1])
                emit_prompt(prompt_file.read_text(encoding="utf-8"))
            if (
                len(args) >= 6
                and args[:3] == ["exec", "--model", args[2]]
                and "--json" in args
                and "-C" in args
                and args[-1]
            ):
                emit_prompt(args[-1])
            if args[:1] == ["run"]:
                if "--prompt-file" in args:
                    prompt_file = pathlib.Path(args[args.index("--prompt-file") + 1])
                    emit_prompt(prompt_file.read_text(encoding="utf-8"))
                if "--model" in args and args[-1]:
                    if {require_structured_run!r}:
                        if "--format" not in args or args[args.index("--format") + 1] != "json":
                            print("missing json format", file=sys.stderr)
                            raise SystemExit(2)
                        if "--dir" not in args:
                            print("missing explicit dir", file=sys.stderr)
                            raise SystemExit(2)
                    emit_prompt(args[-1])
                if "-m" in args and args[-1]:
                    if {require_structured_run!r}:
                        print("legacy -m invocation rejected", file=sys.stderr)
                        raise SystemExit(2)
                    emit_prompt(args[-1])
            if "--prompt" in args:
                emit_prompt(args[args.index("--prompt") + 1])
            print("unexpected args", args, file=sys.stderr)
            raise SystemExit(2)
            """
        ).strip()
        write_text(runner_path, script)

        if os.name == "nt":
            wrapper_path = self.bin_dir / f"{name}.cmd"
            wrapper = f'@echo off\r\n"{sys.executable}" "{runner_path}" %*\r\n'
            wrapper_path.write_text(wrapper, encoding="utf-8", newline="\r\n")
            ps1_path = self.bin_dir / f"{name}.ps1"
            ps1_wrapper = f'& "{sys.executable}" "{runner_path}" @args\r\nexit $LASTEXITCODE\r\n'
            ps1_path.write_text(ps1_wrapper, encoding="utf-8", newline="\r\n")
        else:
            wrapper_path = self.bin_dir / name
            wrapper = f'#!/bin/sh\n"{sys.executable}" "{runner_path}" "$@"\n'
            wrapper_path.write_text(wrapper, encoding="utf-8", newline="\n")
            wrapper_path.chmod(0o755)
        return wrapper_path

    def test_install_bootstrap_creates_router_policy_and_gitignores_local_discovery(self) -> None:
        self.install_bootstrap()

        policy = self.load_json(self.policy_path())
        gitignore = (self.repo_root / ".gitignore").read_text(encoding="utf-8")

        self.assertEqual(policy["version"], 1)
        self.assertIn("role_routes", policy)
        self.assertEqual(policy["defaults"]["probe_timeout_ms"], 50000)
        self.assertEqual(policy["role_routes"]["orchestrator"]["mode"], "local-only")
        self.assertEqual(policy["role_routes"]["orchestrator"]["fallback"], "local-controller")
        self.assertIsNone(policy["role_routes"]["analyst"]["cli"])
        self.assertIsNone(policy["role_routes"]["analyst"]["model"])
        self.assertFalse(self.discovery_path().exists())
        self.assertIn("/.recursive/config/recursive-router-discovered.json", gitignore)

    def test_init_does_not_overwrite_existing_policy(self) -> None:
        self.install_bootstrap()
        policy = self.load_json(self.policy_path())
        policy["defaults"]["when_role_unconfigured"] = "block"
        policy["role_routes"]["code-reviewer"]["cli"] = "codex"
        policy["role_routes"]["code-reviewer"]["model"] = "gpt-5"
        self.write_policy(policy)

        self.initialize_router()

        updated = self.load_json(self.policy_path())
        self.assertEqual(updated["defaults"]["when_role_unconfigured"], "block")
        self.assertEqual(updated["role_routes"]["code-reviewer"]["cli"], "codex")
        self.assertEqual(updated["role_routes"]["code-reviewer"]["model"], "gpt-5")

    def test_cli_init_python_wrapper_bootstraps_router_policy(self) -> None:
        self.run_repo_script("recursive-router-cli-init.py", "--repo-root", str(self.repo_root))

        policy = self.load_json(self.policy_path())
        self.assertEqual(policy["version"], 1)
        self.assertIn("role_routes", policy)

    def test_cli_init_powershell_wrapper_bootstraps_router_policy(self) -> None:
        self.run_repo_powershell_script("recursive-router-cli-init.ps1", "-RepoRoot", str(self.repo_root))

        policy = self.load_json(self.policy_path())
        self.assertEqual(policy["version"], 1)
        self.assertIn("role_routes", policy)

    def test_validate_rejects_unsupported_version(self) -> None:
        self.install_bootstrap()
        policy = self.load_json(self.policy_path())
        policy["version"] = 2
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-validate.py",
            "--repo-root",
            str(self.repo_root),
            allowed_returncodes=(1,),
        )

        self.assertIn("Unsupported config version", completed.stdout + completed.stderr)

    def test_validate_rejects_invalid_custom_cli_schema(self) -> None:
        self.install_bootstrap()
        policy = self.load_json(self.policy_path())
        policy["custom_clis"] = [
            {
                "id": "custom-one",
                "command": "custom-one",
                "probe_args": ["--version"],
                "invoke_template": ["run", "--model", "{model}"],
            }
        ]
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-validate.py",
            "--repo-root",
            str(self.repo_root),
            allowed_returncodes=(1,),
        )

        self.assertIn("invoke_template", completed.stdout + completed.stderr)

    def test_validate_accepts_legacy_policy_without_invoke_timeout(self) -> None:
        self.install_bootstrap()
        policy = self.load_json(self.policy_path())
        del policy["defaults"]["invoke_timeout_ms"]
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-validate.py",
            "--repo-root",
            str(self.repo_root),
        )

        self.assertEqual(completed.returncode, 0)

    def test_validate_rejects_invalid_cli_override_schema(self) -> None:
        self.install_bootstrap()
        policy = self.load_json(self.policy_path())
        policy["cli_overrides"]["codex"] = {
            "invoke_template": ["--model", "{model}"],
        }
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-validate.py",
            "--repo-root",
            str(self.repo_root),
            allowed_returncodes=(1,),
        )

        self.assertIn("cli_overrides.codex.invoke_template", completed.stdout + completed.stderr)

    def test_probe_discovers_builtin_codex_models_from_local_cache(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="9.9.9")
        self.write_home_file(
            ".codex/models_cache.json",
            json.dumps(
                {
                    "fetched_at": "2026-04-17T00:00:00Z",
                    "client_version": "0.115.0",
                    "models": [
                        {"slug": "gpt-5.4"},
                        {"slug": "gpt-5.4-mini"},
                        {"slug": "gpt-5.2"},
                    ],
                }
            ),
        )

        completed = self.run_repo_script(
            "recursive-router-probe.py",
            "--repo-root",
            str(self.repo_root),
            "--json",
        )
        payload = json.loads(completed.stdout)
        codex = next(entry for entry in payload["clis"] if entry["id"] == "codex")

        self.assertTrue(codex["available"])
        self.assertEqual(codex["version"], "9.9.9")
        self.assertEqual(codex["models"], ["gpt-5.4", "gpt-5.4-mini", "gpt-5.2"])
        self.assertEqual(codex["model_source"], "cache-file")
        self.assertEqual(self.load_json(self.discovery_path())["version"], 1)

    def test_probe_prefers_builtin_codex_app_server_model_list(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="9.9.9", app_server_models=["gpt-5.4-mini", "gpt-5.4"])
        self.write_home_file(
            ".codex/models_cache.json",
            json.dumps(
                {
                    "fetched_at": "2026-04-17T00:00:00Z",
                    "client_version": "0.115.0",
                    "models": [{"slug": "stale-cache-model"}],
                }
            ),
        )

        completed = self.run_repo_script(
            "recursive-router-probe.py",
            "--repo-root",
            str(self.repo_root),
            "--json",
        )
        payload = json.loads(completed.stdout)
        codex = next(entry for entry in payload["clis"] if entry["id"] == "codex")

        self.assertTrue(codex["available"])
        self.assertEqual(codex["models"], ["gpt-5.4-mini", "gpt-5.4"])
        self.assertEqual(codex["model_source"], "app-server-model-list")
        self.assertEqual(codex["transport"], "app-server")

    def test_probe_discovers_builtin_kimi_models_from_config_file(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("kimi", version="1.32.0")
        self.write_home_file(
            ".kimi/config.toml",
            """
default_model = "kimi-code/kimi-for-coding"

[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"

[models."preview"]
provider = "managed:kimi-code"
model = "kimi-k2.6-code-previews"
""",
        )

        completed = self.run_repo_script(
            "recursive-router-probe.py",
            "--repo-root",
            str(self.repo_root),
            "--json",
        )
        payload = json.loads(completed.stdout)
        kimi = next(entry for entry in payload["clis"] if entry["id"] == "kimi")

        self.assertTrue(kimi["available"])
        self.assertEqual(kimi["version"], "1.32.0")
        self.assertEqual(kimi["models"], ["kimi-code/kimi-for-coding", "preview"])
        self.assertEqual(kimi["model_source"], "config-file")

    def test_probe_handles_broken_probe_and_timeout(self) -> None:
        self.install_bootstrap()
        broken_wrapper = self.make_fake_cli("broken-cli", probe_exit=3)
        slow_wrapper = self.make_fake_cli("slow-cli", probe_sleep_seconds=1.0)
        policy = self.load_json(self.policy_path())
        policy["custom_clis"] = [
            {
                "id": "broken-cli",
                "command": str(broken_wrapper),
                "probe_args": ["--version"],
                "invoke_template": ["run", "--model", "{model}", "--prompt-file", "{prompt_file}"],
            },
            {
                "id": "slow-cli",
                "command": str(slow_wrapper),
                "probe_args": ["--version"],
                "invoke_template": ["run", "--model", "{model}", "--prompt-file", "{prompt_file}"],
            },
        ]
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-probe.py",
            "--repo-root",
            str(self.repo_root),
            "--json",
            "--timeout-ms",
            "500",
        )
        payload = json.loads(completed.stdout)
        broken_cli = next(entry for entry in payload["clis"] if entry["id"] == "broken-cli")
        slow_cli = next(entry for entry in payload["clis"] if entry["id"] == "slow-cli")

        self.assertFalse(broken_cli["available"])
        self.assertEqual(broken_cli["model_source"], "unknown")
        self.assertTrue(any("probe failed" in note.lower() for note in broken_cli["notes"]))
        self.assertFalse(slow_cli["available"])
        self.assertTrue(any("timed out" in note.lower() for note in slow_cli["notes"]))

    def test_probe_records_launcher_start_failure_without_aborting_inventory(self) -> None:
        self.install_bootstrap()
        blocked_command = self.temp_dir / "not-an-executable"
        blocked_command.mkdir()
        self.make_fake_cli("kimi", version="1.32.0")
        policy = self.load_json(self.policy_path())
        policy["custom_clis"] = [
            {
                "id": "blocked-cli",
                "command": str(blocked_command),
                "probe_args": ["--version"],
                "invoke_template": ["run", "--model", "{model}", "--prompt", "{prompt}"],
            }
        ]
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-probe.py",
            "--repo-root",
            str(self.repo_root),
            "--json",
        )
        payload = json.loads(completed.stdout)
        blocked = next(entry for entry in payload["clis"] if entry["id"] == "blocked-cli")
        kimi = next(entry for entry in payload["clis"] if entry["id"] == "kimi")

        self.assertFalse(blocked["available"])
        self.assertIn("Failed to start command", blocked["notes"][0])
        self.assertTrue(kimi["available"])

    def test_probe_discovers_custom_cli_with_model_listing(self) -> None:
        self.install_bootstrap()
        custom_wrapper = self.make_fake_cli("custom-router", models=["alpha", "beta"])
        policy = self.load_json(self.policy_path())
        policy["custom_clis"] = [
            {
                "id": "custom-router",
                "command": str(custom_wrapper),
                "probe_args": ["--version"],
                "invoke_template": ["run", "--model", "{model}", "--prompt-file", "{prompt_file}"],
                "model_list_template": ["models", "list"],
            }
        ]
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-probe.py",
            "--repo-root",
            str(self.repo_root),
            "--json",
        )
        payload = json.loads(completed.stdout)
        custom_cli = next(entry for entry in payload["clis"] if entry["id"] == "custom-router")

        self.assertTrue(custom_cli["available"])
        self.assertEqual(custom_cli["models"], ["alpha", "beta"])
        self.assertEqual(custom_cli["model_source"], "cli-list")

    def test_resolve_uses_builtin_codex_cached_models(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="9.9.9")
        self.write_home_file(
            ".codex/models_cache.json",
            json.dumps(
                {
                    "fetched_at": "2026-04-17T00:00:00Z",
                    "client_version": "0.115.0",
                    "models": [{"slug": "gpt-5.4"}, {"slug": "gpt-5.4-mini"}],
                }
            ),
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["code-reviewer"]["cli"] = "codex"
        policy["role_routes"]["code-reviewer"]["model"] = "gpt-5.4-mini"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "code-reviewer",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "external-cli")
        self.assertEqual(payload["cli"], "codex")
        self.assertEqual(payload["model"], "gpt-5.4-mini")

    def test_resolve_reports_codex_app_server_transport(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="9.9.9", app_server_models=["gpt-5.4-mini"])
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["code-reviewer"]["cli"] = "codex"
        policy["role_routes"]["code-reviewer"]["model"] = "gpt-5.4-mini"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "code-reviewer",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "external-cli")
        self.assertEqual(payload["cli"], "codex")
        self.assertEqual(payload["model"], "gpt-5.4-mini")
        self.assertEqual(payload["transport"], "app-server")

    def test_resolve_uses_builtin_kimi_configured_models(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("kimi", version="1.32.0")
        self.write_home_file(
            ".kimi/config.toml",
            """
default_model = "kimi-code/kimi-for-coding"

[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"

[models."preview"]
provider = "managed:kimi-code"
model = "kimi-k2.6-code-previews"
""",
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["analyst"]["cli"] = "kimi"
        policy["role_routes"]["analyst"]["model"] = "preview"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "external-cli")
        self.assertEqual(payload["cli"], "kimi")
        self.assertEqual(payload["model"], "preview")

    def test_resolve_uses_builtin_opencode_configured_models(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("opencode", version="1.3.3", models=["github-copilot/gpt-5.4-mini", "opencode/gpt-5-nano"])
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["analyst"]["cli"] = "opencode"
        policy["role_routes"]["analyst"]["model"] = "github-copilot/gpt-5.4-mini"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--json",
        )
        payload = json.loads(completed.stdout)
        discovery = self.load_json(self.discovery_path())
        opencode = next(entry for entry in discovery["clis"] if entry["id"] == "opencode")

        self.assertEqual(payload["decision"], "external-cli")
        self.assertEqual(payload["cli"], "opencode")
        self.assertEqual(payload["model"], "github-copilot/gpt-5.4-mini")
        self.assertEqual(opencode["models"], ["github-copilot/gpt-5.4-mini", "opencode/gpt-5-nano"])
        self.assertEqual(opencode["model_source"], "cli-list")

    def test_default_probe_timeout_allows_slower_builtin_opencode_probe(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli(
            "opencode",
            version="1.3.3",
            models=["github-copilot/gpt-5.4-mini"],
            probe_sleep_seconds=3.0,
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["analyst"]["cli"] = "opencode"
        policy["role_routes"]["analyst"]["model"] = "github-copilot/gpt-5.4-mini"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "external-cli")
        self.assertEqual(payload["cli"], "opencode")
        self.assertEqual(payload["model"], "github-copilot/gpt-5.4-mini")

    def test_resolve_returns_external_cli_when_configured_model_is_literal(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex")
        policy = self.load_json(self.policy_path())
        policy["defaults"]["when_model_unknown"] = "use-as-literal"
        policy["role_routes"]["code-reviewer"]["cli"] = "codex"
        policy["role_routes"]["code-reviewer"]["model"] = "gpt-5"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "code-reviewer",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "external-cli")
        self.assertEqual(payload["cli"], "codex")
        self.assertEqual(payload["model"], "gpt-5")
        self.assertFalse(payload["fallback_used"])

    def test_resolve_asks_when_role_is_unconfigured(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="1.0.0")

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "ask-user")
        self.assertIn("analyst", payload["prompt"])
        self.assertIn("codex", payload["prompt"])
        self.assertIn("/.recursive/config/recursive-router.json", payload["prompt"])
        self.assertIn("/.recursive/config/recursive-router-discovered.json", payload["prompt"])

    def test_resolve_auto_assigns_single_cli_but_still_asks_for_null_model(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex")
        policy = self.load_json(self.policy_path())
        policy["defaults"]["allow_auto_assign_if_single_cli"] = True
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "ask-user")
        self.assertEqual(payload["cli"], "codex")
        self.assertIsNone(payload["model"])
        self.assertIn("auto-assigned the only discovered CLI", payload["reason"])

    def test_resolve_falls_back_locally_when_selected_cli_is_unavailable(self) -> None:
        self.install_bootstrap()
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["analyst"]["cli"] = "codex"
        policy["role_routes"]["analyst"]["model"] = "gpt-5"
        self.write_policy(policy)

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "fallback-local")
        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["fallback"], "self-audit")
        self.assertIn("unavailable", payload["reason"])

    def test_resolve_keeps_orchestrator_local_by_default(self) -> None:
        self.install_bootstrap()

        completed = self.run_repo_script(
            "recursive-router-resolve.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "orchestrator",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["decision"], "local-only")
        self.assertEqual(payload["fallback"], "local-controller")
        self.assertEqual(payload["role"], "orchestrator")
        self.assertIn("local-only execution", payload["reason"])

    def test_configure_saves_only_after_codex_verification(self) -> None:
        self.install_bootstrap()
        invocation_log = self.temp_dir / "codex-invocations.jsonl"
        self.make_fake_cli(
            "codex",
            version="9.9.9",
            app_server_models=["gpt-5.4-mini"],
            record_invocations_path=invocation_log,
        )

        completed = self.run_repo_script(
            "recursive-router-configure.py",
            "--repo-root",
            str(self.repo_root),
            "--set",
            "analyst=codex:gpt-5.4-mini",
            "--json",
        )
        payload = json.loads(completed.stdout)
        policy = self.load_json(self.policy_path())

        self.assertTrue(payload["saved"])
        self.assertTrue(payload["verification_results"]["analyst"]["verified"])
        self.assertEqual(payload["verification_results"]["analyst"]["transport"], "app-server")
        self.assertEqual(policy["role_routes"]["analyst"]["cli"], "codex")
        self.assertEqual(policy["role_routes"]["analyst"]["model"], "gpt-5.4-mini")
        invocation = json.loads(invocation_log.read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("--skip-git-repo-check", invocation)
        self.assertIn("--ephemeral", invocation)
        self.assertIn("mcp_servers.playwright.enabled=false", invocation)
        self.assertIn('mcp_servers["subframe-docs"].enabled=false', invocation)

    def test_configure_accepts_legacy_role_alias_and_saves_canonical_stage_role(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="9.9.9", app_server_models=["gpt-5.4-mini"])

        completed = self.run_repo_script(
            "recursive-router-configure.py",
            "--repo-root",
            str(self.repo_root),
            "--set",
            "phase-auditor=codex:gpt-5.4-mini",
            "--json",
        )
        payload = json.loads(completed.stdout)
        policy = self.load_json(self.policy_path())

        self.assertTrue(payload["saved"])
        self.assertIn("analyst", payload["verification_results"])
        self.assertNotIn("phase-auditor", policy["role_routes"])
        self.assertEqual(policy["role_routes"]["analyst"]["cli"], "codex")
        self.assertEqual(policy["role_routes"]["analyst"]["model"], "gpt-5.4-mini")

    def test_configure_does_not_save_when_verification_fails(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("opencode", version="1.3.3", models=["github-copilot/gpt-5.4-mini"], invoke_echo=False)

        completed = self.run_repo_script(
            "recursive-router-configure.py",
            "--repo-root",
            str(self.repo_root),
            "--set",
            "planner=opencode:github-copilot/gpt-5.4-mini",
            "--json",
            allowed_returncodes=(1,),
        )
        payload = json.loads(completed.stdout)
        policy = self.load_json(self.policy_path())

        self.assertFalse(payload["saved"])
        self.assertFalse(payload["verification_results"]["planner"]["verified"])
        self.assertIsNone(policy["role_routes"]["planner"]["cli"])
        self.assertIsNone(policy["role_routes"]["planner"]["model"])

    def test_configure_verifies_opencode_with_structured_ping(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli(
            "opencode",
            version="1.3.3",
            models=["github-copilot/gpt-5.4-mini"],
            require_structured_run=True,
        )

        completed = self.run_repo_script(
            "recursive-router-configure.py",
            "--repo-root",
            str(self.repo_root),
            "--set",
            "memory-auditor=opencode:github-copilot/gpt-5.4-mini",
            "--json",
        )
        payload = json.loads(completed.stdout)
        policy = self.load_json(self.policy_path())

        self.assertTrue(payload["saved"])
        self.assertTrue(payload["verification_results"]["memory-auditor"]["verified"])
        self.assertEqual(policy["role_routes"]["memory-auditor"]["cli"], "opencode")
        self.assertEqual(policy["role_routes"]["memory-auditor"]["model"], "github-copilot/gpt-5.4-mini")

    def test_configure_reuses_verification_for_duplicate_cli_model_pairs(self) -> None:
        self.install_bootstrap()
        invocation_log = self.temp_dir / "opencode-invocations.jsonl"
        self.make_fake_cli(
            "opencode",
            version="1.3.3",
            models=["github-copilot/gpt-5.4-mini"],
            require_structured_run=True,
            record_invocations_path=invocation_log,
        )

        completed = self.run_repo_script(
            "recursive-router-configure.py",
            "--repo-root",
            str(self.repo_root),
            "--set",
            "memory-auditor=opencode:github-copilot/gpt-5.4-mini",
            "--set",
            "tester=opencode:github-copilot/gpt-5.4-mini",
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertTrue(payload["saved"])
        lines = invocation_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)

    def test_configure_verifies_kimi_alias_before_save(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("kimi", version="1.32.0")
        self.write_home_file(
            ".kimi/config.toml",
            """
default_model = "kimi-code/kimi-for-coding"

[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
""",
        )

        completed = self.run_repo_script(
            "recursive-router-configure.py",
            "--repo-root",
            str(self.repo_root),
            "--set",
            "code-reviewer=kimi:kimi-code/kimi-for-coding",
            "--json",
        )
        payload = json.loads(completed.stdout)
        policy = self.load_json(self.policy_path())

        self.assertTrue(payload["saved"])
        self.assertTrue(payload["verification_results"]["code-reviewer"]["verified"])
        self.assertEqual(policy["role_routes"]["code-reviewer"]["model"], "kimi-code/kimi-for-coding")

    def test_invoke_dispatches_prompt_bundle_through_kimi_stream_json(self) -> None:
        self.install_bootstrap()
        invocation_log = self.temp_dir / "kimi-invocations.jsonl"
        self.make_fake_cli("kimi", version="1.32.0", record_invocations_path=invocation_log)
        self.write_home_file(
            ".kimi/config.toml",
            """
default_model = "kimi-code/kimi-for-coding"

[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
""",
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["tester"]["cli"] = "kimi"
        policy["role_routes"]["tester"]["model"] = "kimi-code/kimi-for-coding"
        self.write_policy(policy)

        prompt_path = self.repo_root / ".recursive" / "run" / "run-123" / "router-prompts" / "tester.txt"
        prompt_text = "Review Phase 4 evidence and return only the tester verdict."
        write_text(prompt_path, prompt_text)

        completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "tester",
            "--prompt-file",
            str(prompt_path),
            "--json",
        )
        payload = json.loads(completed.stdout)
        invocation_args = json.loads(invocation_log.read_text(encoding="utf-8").splitlines()[0])

        self.assertTrue(payload["success"])
        self.assertEqual(payload["cli"], "kimi")
        self.assertEqual(payload["output_text"], prompt_text)
        self.assertIn("<choice>STOP</choice>", payload["raw_stdout"])
        self.assertIn("--work-dir", invocation_args)
        self.assertEqual(invocation_args[invocation_args.index("--work-dir") + 1], str(self.repo_root))
        self.assertIn("--output-format", invocation_args)
        self.assertEqual(invocation_args[invocation_args.index("--output-format") + 1], "stream-json")
        self.assertIn("--max-ralph-iterations", invocation_args)
        self.assertEqual(invocation_args[invocation_args.index("--max-ralph-iterations") + 1], "0")
        self.assertNotIn("--final-message-only", invocation_args)

    def test_invoke_marks_kimi_nonzero_exit_unsuccessful_even_with_output(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli(
            "kimi",
            version="1.32.0",
            invoke_exit=1,
            emit_output_before_failure=True,
        )
        self.write_home_file(
            ".kimi/config.toml",
            """
default_model = "kimi-code/kimi-for-coding"

[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
""",
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["tester"]["cli"] = "kimi"
        policy["role_routes"]["tester"]["model"] = "kimi-code/kimi-for-coding"
        self.write_policy(policy)

        prompt_path = self.repo_root / ".recursive" / "run" / "run-123" / "router-prompts" / "tester.txt"
        prompt_text = "Return TESTER_VERDICT: PASS."
        write_text(prompt_path, prompt_text)

        completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "tester",
            "--prompt-file",
            str(prompt_path),
            "--json",
            allowed_returncodes=(1,),
        )
        payload = json.loads(completed.stdout)

        self.assertFalse(payload["success"])
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["output_text"], prompt_text)
        self.assertIn("exit code 1", payload["reason"])

    def test_invoke_dispatches_prompt_bundle_through_opencode_route(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli(
            "opencode",
            version="1.3.3",
            models=["github-copilot/gpt-5.4-mini"],
            require_structured_run=True,
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["planner"]["cli"] = "opencode"
        policy["role_routes"]["planner"]["model"] = "github-copilot/gpt-5.4-mini"
        self.write_policy(policy)

        prompt_path = self.repo_root / ".recursive" / "run" / "run-123" / "router-prompts" / "planner.txt"
        output_path = self.repo_root / ".recursive" / "run" / "run-123" / "evidence" / "router" / "planner.md"
        metadata_path = self.repo_root / ".recursive" / "run" / "run-123" / "evidence" / "router" / "planner.json"
        prompt_text = "## Covered\n- benchmark/00-requirements.md\n- src/App.tsx"
        write_text(prompt_path, prompt_text)

        completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "planner",
            "--prompt-file",
            str(prompt_path),
            "--output-file",
            str(output_path),
            "--metadata-file",
            str(metadata_path),
            "--json",
        )
        payload = json.loads(completed.stdout)
        metadata = self.load_json(metadata_path)

        self.assertTrue(payload["success"])
        self.assertEqual(payload["decision"]["decision"], "external-cli")
        self.assertEqual(payload["cli"], "opencode")
        self.assertEqual(payload["output_text"], prompt_text)
        self.assertEqual(payload["prompt_bundle_path"], "/.recursive/run/run-123/router-prompts/planner.txt")
        self.assertEqual(output_path.read_text(encoding="utf-8").strip(), prompt_text)
        self.assertEqual(metadata["cli"], "opencode")
        self.assertEqual(metadata["output_text"], prompt_text)

    def test_invoke_rejects_raw_output_under_subagents_directory(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli(
            "opencode",
            version="1.3.3",
            models=["github-copilot/gpt-5.4-mini"],
            require_structured_run=True,
        )
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["planner"]["cli"] = "opencode"
        policy["role_routes"]["planner"]["model"] = "github-copilot/gpt-5.4-mini"
        self.write_policy(policy)

        prompt_path = self.repo_root / ".recursive" / "run" / "run-123" / "router-prompts" / "planner.txt"
        raw_output_path = self.repo_root / ".recursive" / "run" / "run-123" / "subagents" / "raw-kimi.md"
        metadata_path = self.repo_root / ".recursive" / "run" / "run-123" / "subagents" / "raw-kimi.json"
        write_text(prompt_path, "Planner prompt")
        raw_output_path.parent.mkdir(parents=True, exist_ok=True)

        output_completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "planner",
            "--prompt-file",
            str(prompt_path),
            "--output-file",
            str(raw_output_path),
            "--json",
            allowed_returncodes=(1,),
        )
        metadata_completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "planner",
            "--prompt-file",
            str(prompt_path),
            "--metadata-file",
            str(metadata_path),
            "--json",
            allowed_returncodes=(1,),
        )

        self.assertIn("not under subagents", output_completed.stdout + output_completed.stderr)
        self.assertIn("not under subagents", metadata_completed.stdout + metadata_completed.stderr)
        self.assertFalse(raw_output_path.exists())
        self.assertFalse(metadata_path.exists())

    def test_invoke_dispatches_prompt_bundle_through_codex_app_server(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="9.9.9", app_server_models=["gpt-5.4-mini"])
        policy = self.load_json(self.policy_path())
        policy["role_routes"]["analyst"]["cli"] = "codex"
        policy["role_routes"]["analyst"]["model"] = "gpt-5.4-mini"
        self.write_policy(policy)

        prompt_path = self.repo_root / ".recursive" / "run" / "run-123" / "router-prompts" / "analyst.txt"
        prompt_text = "Review Bundle Path: /.recursive/run/run-123/evidence/review-bundles/analyst.md"
        write_text(prompt_path, prompt_text)

        completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--prompt-file",
            str(prompt_path),
            "--json",
        )
        payload = json.loads(completed.stdout)

        self.assertTrue(payload["success"])
        self.assertEqual(payload["cli"], "codex")
        self.assertEqual(payload["transport"], "app-server")
        self.assertEqual(payload["output_text"], prompt_text)

    def test_invoke_fails_when_route_is_not_external_cli(self) -> None:
        self.install_bootstrap()
        self.make_fake_cli("codex", version="1.0.0")
        prompt_path = self.repo_root / ".recursive" / "run" / "run-123" / "router-prompts" / "analyst.txt"
        write_text(prompt_path, "Prompt bundle that should not be dispatched.")

        completed = self.run_repo_script(
            "recursive-router-invoke.py",
            "--repo-root",
            str(self.repo_root),
            "--role",
            "analyst",
            "--prompt-file",
            str(prompt_path),
            "--json",
            allowed_returncodes=(1,),
        )
        payload = json.loads(completed.stdout)

        self.assertFalse(payload["success"])
        self.assertEqual(payload["decision"]["decision"], "ask-user")
        self.assertIn("analyst", payload["decision"]["prompt"])


if __name__ == "__main__":
    unittest.main()
