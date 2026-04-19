#!/usr/bin/env python3
"""
Shared helpers for recursive-router scripts.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import tomllib
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CANONICAL_ROLES = [
    "orchestrator",
    "analyst",
    "planner",
    "implementer",
    "code-reviewer",
    "tester",
    "memory-auditor",
]
LEGACY_ROLE_ALIASES = {
    "phase-auditor": "analyst",
    "traceability-auditor": "planner",
    "bounded-implementer": "implementer",
    "test-reviewer": "tester",
}
DEFAULT_ROLE_ROUTE_SPECS = {
    "orchestrator": {
        "enabled": True,
        "mode": "local-only",
        "cli": None,
        "model": None,
        "fallback": "local-controller",
    },
    "analyst": {
        "enabled": True,
        "mode": "external-cli",
        "cli": None,
        "model": None,
        "fallback": "self-audit",
    },
    "planner": {
        "enabled": True,
        "mode": "external-cli",
        "cli": None,
        "model": None,
        "fallback": "self-audit",
    },
    "implementer": {
        "enabled": False,
        "mode": "external-cli",
        "cli": None,
        "model": None,
        "fallback": "local-controller",
    },
    "code-reviewer": {
        "enabled": True,
        "mode": "external-cli",
        "cli": None,
        "model": None,
        "fallback": "self-audit",
    },
    "tester": {
        "enabled": True,
        "mode": "external-cli",
        "cli": None,
        "model": None,
        "fallback": "self-audit",
    },
    "memory-auditor": {
        "enabled": True,
        "mode": "external-cli",
        "cli": None,
        "model": None,
        "fallback": "self-audit",
    },
}
CONFIG_VERSION = 1
DISCOVERY_VERSION = 1
ROUTER_NAME = "recursive-router"
LEGACY_ROUTER_NAME = "recursive-router-cli"
ROUTER_POLICY_FILENAME = "recursive-router.json"
LEGACY_ROUTER_POLICY_FILENAME = "recursive-router-cli.json"
ROUTER_DISCOVERY_FILENAME = "recursive-router-discovered.json"
LEGACY_ROUTER_DISCOVERY_FILENAME = "recursive-router-cli-discovered.json"
ALLOWED_ROLE_UNCONFIGURED = {"ask", "fallback-local", "block"}
ALLOWED_CLI_UNAVAILABLE = {"fallback-local", "ask", "block"}
ALLOWED_MODEL_UNKNOWN = {"ask", "use-as-literal", "fallback-local"}
ALLOWED_ROLE_MODES = {"external-cli", "local-only"}
ALLOWED_ROLE_FALLBACKS = {"self-audit", "local-controller", "ask", "block"}
ALLOWED_PROBE_STATUS = {"ok", "partial", "failed"}
ALLOWED_MODEL_SOURCE = {
    "app-server-model-list",
    "cli-list",
    "adapter-defaults",
    "cache-file",
    "configured-static-list",
    "config-file",
    "unsupported",
    "failed",
    "unknown",
}


class RouterConfigError(ValueError):
    """Raised when the router policy is invalid."""


@dataclass(frozen=True)
class CLIAdapter:
    id: str
    command: str | tuple[str, ...]
    probe_args: tuple[str, ...] = ("--version",)
    model_list_template: tuple[str, ...] | None = None
    builtin: bool = True
    default_models: tuple[str, ...] = ()
    invoke_template: tuple[str, ...] = ()
    transport: str = "cli-template"


BUILTIN_ADAPTERS: tuple[CLIAdapter, ...] = (
    CLIAdapter(
        id="codex",
        command="codex",
        invoke_template=("exec", "--model", "{model}", "--input-file", "{prompt_file}"),
        transport="app-server",
    ),
    CLIAdapter(
        id="kimi",
        command="kimi",
        invoke_template=("--model", "{model}", "--print", "--final-message-only", "--prompt", "{prompt}"),
    ),
    CLIAdapter(
        id="opencode",
        command="opencode",
        model_list_template=("models",),
        invoke_template=("run", "--model", "{model}", "--prompt-file", "{prompt_file}"),
    ),
)
BUILTIN_ADAPTER_BY_ID = {adapter.id: adapter for adapter in BUILTIN_ADAPTERS}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_repo_path(raw_path: str) -> str:
    return "/" + raw_path.replace("\\", "/").strip().lstrip("/")


def canonicalize_router_role(role: str) -> str:
    normalized = role.strip()
    if normalized in CANONICAL_ROLES:
        return normalized
    legacy = LEGACY_ROLE_ALIASES.get(normalized)
    if legacy is not None:
        return legacy
    raise RouterConfigError(f"Unknown router role: {role}")


def default_role_routes() -> dict[str, dict[str, object]]:
    return {role: deepcopy(route) for role, route in DEFAULT_ROLE_ROUTE_SPECS.items()}


def router_config_dir(repo_root: Path) -> Path:
    return repo_root / ".recursive" / "config"


def router_policy_path(repo_root: Path) -> Path:
    return router_config_dir(repo_root) / ROUTER_POLICY_FILENAME


def legacy_router_policy_path(repo_root: Path) -> Path:
    return router_config_dir(repo_root) / LEGACY_ROUTER_POLICY_FILENAME


def router_discovery_path(repo_root: Path) -> Path:
    return router_config_dir(repo_root) / ROUTER_DISCOVERY_FILENAME


def legacy_router_discovery_path(repo_root: Path) -> Path:
    return router_config_dir(repo_root) / LEGACY_ROUTER_DISCOVERY_FILENAME


def default_router_policy() -> dict[str, object]:
    return {
        "version": CONFIG_VERSION,
        "defaults": {
            "when_role_unconfigured": "ask",
            "when_cli_unavailable": "fallback-local",
            "when_model_unknown": "ask",
            "allow_auto_assign_if_single_cli": False,
            "probe_timeout_ms": 50000,
            "invoke_timeout_ms": 180000,
        },
        "role_routes": default_role_routes(),
        "cli_overrides": {},
        "custom_clis": [],
    }


def empty_discovery_inventory(*, probe_tool: str, probe_status: str = "partial", clis: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "version": DISCOVERY_VERSION,
        "generated_at": utc_now_iso(),
        "probe_tool": probe_tool,
        "probe_status": probe_status,
        "clis": clis or [],
    }


def pretty_json(payload: object) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy(repo_root: Path) -> dict[str, object]:
    policy_path = router_policy_path(repo_root)
    if not policy_path.exists():
        legacy_policy = legacy_router_policy_path(repo_root)
        if legacy_policy.exists():
            policy_path = legacy_policy
        else:
            raise RouterConfigError(f"Missing routing policy file: {normalize_repo_path(str(policy_path.relative_to(repo_root)))}")
    try:
        policy = read_json(policy_path)
    except json.JSONDecodeError as exc:
        raise RouterConfigError(f"Routing policy file is not valid JSON: {exc}") from exc
    return validate_policy(policy)


def ensure_router_scaffold(repo_root: Path) -> tuple[Path, Path]:
    config_dir = router_config_dir(repo_root)
    config_dir.mkdir(parents=True, exist_ok=True)
    policy_path = router_policy_path(repo_root)
    discovery_path = router_discovery_path(repo_root)
    legacy_policy_path = legacy_router_policy_path(repo_root)
    legacy_discovery_path = legacy_router_discovery_path(repo_root)

    if policy_path.exists():
        try:
            existing_raw = read_json(policy_path)
        except json.JSONDecodeError as exc:
            raise RouterConfigError(f"Existing routing policy is invalid JSON and will not be overwritten: {exc}") from exc
        existing = validate_policy(existing_raw)
        if existing != existing_raw:
            write_json(policy_path, existing)
    elif legacy_policy_path.exists():
        try:
            existing_raw = read_json(legacy_policy_path)
        except json.JSONDecodeError as exc:
            raise RouterConfigError(f"Existing legacy routing policy is invalid JSON and will not be migrated: {exc}") from exc
        existing = validate_policy(existing_raw)
        write_json(policy_path, existing)
        legacy_policy_path.unlink(missing_ok=True)
    else:
        write_json(policy_path, default_router_policy())

    if discovery_path.exists():
        pass
    elif legacy_discovery_path.exists():
        legacy_discovery_path.replace(discovery_path)

    return policy_path, discovery_path


def _as_dict(payload: object, label: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise RouterConfigError(f"{label} must be a JSON object.")
    return payload


def _as_list_of_strings(value: object, field_name: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RouterConfigError(f"{field_name} must be a list of strings.")
    if not allow_empty and not value:
        raise RouterConfigError(f"{field_name} must not be empty.")
    return list(value)


def _normalize_command_spec(value: object, field_name: str) -> str | tuple[str, ...]:
    if isinstance(value, str):
        command = value.strip()
        if not command:
            raise RouterConfigError(f"{field_name} must be a non-empty string when provided.")
        return command
    if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
        return tuple(item.strip() for item in value)
    raise RouterConfigError(f"{field_name} must be a non-empty string or a non-empty list of strings.")


def _validate_invoke_template(template: list[str], field_name: str) -> None:
    if not any("{model}" in piece for piece in template):
        raise RouterConfigError(f"{field_name} must contain a {{model}} placeholder.")
    if not any("{prompt_file}" in piece or "{prompt}" in piece for piece in template):
        raise RouterConfigError(f"{field_name} must contain either a {{prompt_file}} or {{prompt}} placeholder.")


def normalize_role_routes(role_routes_payload: object) -> dict[str, object]:
    raw_role_routes = _as_dict(role_routes_payload, "role_routes")
    normalized_routes: dict[str, object] = default_role_routes()
    sources_by_canonical: dict[str, str] = {}
    for role_name, route_payload in raw_role_routes.items():
        if not isinstance(role_name, str):
            raise RouterConfigError("role_routes keys must be strings.")
        canonical_role = canonicalize_router_role(role_name)
        prior_source = sources_by_canonical.get(canonical_role)
        if prior_source is not None and prior_source != role_name:
            raise RouterConfigError(
                f"role_routes.{role_name} duplicates canonical role {canonical_role!r}; keep only {canonical_role!r}."
            )
        normalized_routes[canonical_role] = route_payload
        sources_by_canonical[canonical_role] = role_name
    return normalized_routes


def validate_policy(policy: object) -> dict[str, object]:
    payload = deepcopy(_as_dict(policy, "Router policy"))
    payload["role_routes"] = normalize_role_routes(payload.get("role_routes"))
    default_defaults = _as_dict(default_router_policy()["defaults"], "default defaults")

    version = payload.get("version")
    if version != CONFIG_VERSION:
        raise RouterConfigError(f"Unsupported config version: {version!r}. Expected {CONFIG_VERSION}.")

    defaults = _as_dict(payload.get("defaults"), "defaults")
    if defaults.get("when_role_unconfigured") not in ALLOWED_ROLE_UNCONFIGURED:
        raise RouterConfigError("defaults.when_role_unconfigured must be one of: ask, fallback-local, block.")
    if defaults.get("when_cli_unavailable") not in ALLOWED_CLI_UNAVAILABLE:
        raise RouterConfigError("defaults.when_cli_unavailable must be one of: fallback-local, ask, block.")
    if defaults.get("when_model_unknown") not in ALLOWED_MODEL_UNKNOWN:
        raise RouterConfigError("defaults.when_model_unknown must be one of: ask, use-as-literal, fallback-local.")
    if not isinstance(defaults.get("allow_auto_assign_if_single_cli"), bool):
        raise RouterConfigError("defaults.allow_auto_assign_if_single_cli must be a boolean.")
    probe_timeout_ms = defaults.get("probe_timeout_ms")
    if not isinstance(probe_timeout_ms, int) or probe_timeout_ms < 500 or probe_timeout_ms > 60000:
        raise RouterConfigError("defaults.probe_timeout_ms must be an integer between 500 and 60000.")
    invoke_timeout_ms = defaults.get("invoke_timeout_ms", default_defaults["invoke_timeout_ms"])
    if not isinstance(invoke_timeout_ms, int) or invoke_timeout_ms < 1000 or invoke_timeout_ms > 600000:
        raise RouterConfigError("defaults.invoke_timeout_ms must be an integer between 1000 and 600000.")

    role_routes = _as_dict(payload.get("role_routes"), "role_routes")
    for role in CANONICAL_ROLES:
        if role not in role_routes:
            raise RouterConfigError(f"role_routes is missing canonical role: {role}")

    for role_name, route_payload in role_routes.items():
        route = _as_dict(route_payload, f"role_routes.{role_name}")
        if not isinstance(route.get("enabled"), bool):
            raise RouterConfigError(f"role_routes.{role_name}.enabled must be a boolean.")
        if route.get("mode") not in ALLOWED_ROLE_MODES:
            raise RouterConfigError(f"role_routes.{role_name}.mode must be one of: external-cli, local-only.")
        cli_value = route.get("cli")
        if cli_value is not None and not isinstance(cli_value, str):
            raise RouterConfigError(f"role_routes.{role_name}.cli must be a string or null.")
        model_value = route.get("model")
        if model_value is not None and not isinstance(model_value, str):
            raise RouterConfigError(f"role_routes.{role_name}.model must be a string or null.")
        if route.get("fallback") not in ALLOWED_ROLE_FALLBACKS:
            raise RouterConfigError(f"role_routes.{role_name}.fallback must be one of: self-audit, local-controller, ask, block.")

    cli_overrides = payload.get("cli_overrides")
    if not isinstance(cli_overrides, dict):
        raise RouterConfigError("cli_overrides must be a JSON object.")
    builtin_ids = set(BUILTIN_ADAPTER_BY_ID)
    for cli_id, override_payload in cli_overrides.items():
        if cli_id not in builtin_ids:
            raise RouterConfigError(f"cli_overrides references unknown built-in CLI id: {cli_id}")
        override = _as_dict(override_payload, f"cli_overrides.{cli_id}")
        if "command" in override:
            _normalize_command_spec(override["command"], f"cli_overrides.{cli_id}.command")
        if "probe_args" in override:
            _as_list_of_strings(override["probe_args"], f"cli_overrides.{cli_id}.probe_args")
        if "invoke_template" in override:
            invoke_template = _as_list_of_strings(override["invoke_template"], f"cli_overrides.{cli_id}.invoke_template", allow_empty=False)
            _validate_invoke_template(invoke_template, f"cli_overrides.{cli_id}.invoke_template")
        if "model_list_template" in override and override["model_list_template"] is not None:
            _as_list_of_strings(override["model_list_template"], f"cli_overrides.{cli_id}.model_list_template")
        if "default_models" in override:
            _as_list_of_strings(override["default_models"], f"cli_overrides.{cli_id}.default_models")
        transport = override.get("transport")
        if transport is not None and (not isinstance(transport, str) or not transport.strip()):
            raise RouterConfigError(f"cli_overrides.{cli_id}.transport must be a non-empty string when provided.")

    custom_clis = payload.get("custom_clis")
    if not isinstance(custom_clis, list):
        raise RouterConfigError("custom_clis must be a list.")

    known_ids = {adapter.id for adapter in BUILTIN_ADAPTERS}
    for index, entry in enumerate(custom_clis):
        item = _as_dict(entry, f"custom_clis[{index}]")
        cli_id = item.get("id")
        if not isinstance(cli_id, str) or not cli_id.strip():
            raise RouterConfigError(f"custom_clis[{index}].id must be a non-empty string.")
        if cli_id in known_ids:
            raise RouterConfigError(f"custom_clis[{index}].id duplicates an existing CLI id: {cli_id}")
        known_ids.add(cli_id)

        command = _normalize_command_spec(item.get("command"), f"custom_clis[{index}].command")

        probe_args = _as_list_of_strings(item.get("probe_args"), f"custom_clis[{index}].probe_args")
        invoke_template = _as_list_of_strings(item.get("invoke_template"), f"custom_clis[{index}].invoke_template", allow_empty=False)
        _validate_invoke_template(invoke_template, f"custom_clis[{index}].invoke_template")
        model_list_template = item.get("model_list_template")
        if model_list_template is not None:
            _as_list_of_strings(model_list_template, f"custom_clis[{index}].model_list_template")
        _as_list_of_strings(probe_args, f"custom_clis[{index}].probe_args")

    valid_ids = known_ids
    for role_name, route_payload in role_routes.items():
        cli_value = route_payload.get("cli")
        if cli_value is not None and cli_value not in valid_ids:
            raise RouterConfigError(f"role_routes.{role_name}.cli references unknown CLI id: {cli_value}")
    return payload


def adapters_from_policy(policy: dict[str, object] | None) -> list[CLIAdapter]:
    adapters: list[CLIAdapter] = []
    override_map = policy.get("cli_overrides", {}) if policy else {}
    for adapter in BUILTIN_ADAPTERS:
        override = override_map.get(adapter.id, {})
        model_list_template = adapter.model_list_template
        if "model_list_template" in override:
            raw_model_list = override["model_list_template"]
            model_list_template = None if raw_model_list is None else tuple(raw_model_list)
        adapters.append(
            CLIAdapter(
                id=adapter.id,
                command=_normalize_command_spec(override["command"], f"cli_overrides.{adapter.id}.command")
                if "command" in override
                else adapter.command,
                probe_args=tuple(override.get("probe_args", list(adapter.probe_args))),
                model_list_template=model_list_template,
                builtin=adapter.builtin,
                default_models=tuple(override.get("default_models", list(adapter.default_models))),
                invoke_template=tuple(override.get("invoke_template", list(adapter.invoke_template))),
                transport=override.get("transport", adapter.transport),
            )
        )
    if not policy:
        return adapters
    for index, entry in enumerate(policy.get("custom_clis", [])):
        item = _as_dict(entry, "custom CLI")
        model_list_template = item.get("model_list_template")
        adapters.append(
            CLIAdapter(
                id=item["id"],
                command=_normalize_command_spec(item["command"], f"custom_clis[{index}].command"),
                probe_args=tuple(item["probe_args"]),
                model_list_template=tuple(model_list_template) if model_list_template is not None else None,
                builtin=False,
                invoke_template=tuple(item["invoke_template"]),
            )
        )
    return adapters


def _command_display(command: str | tuple[str, ...]) -> str | list[str]:
    return command if isinstance(command, str) else list(command)


def _resolve_executable_token(token: str) -> str | None:
    stripped = token.strip().strip('"')
    if not stripped:
        return None
    if os.path.isabs(stripped):
        return stripped if Path(stripped).exists() else None
    return shutil.which(stripped)


def _parse_windows_wrapper_command(wrapper_path: Path) -> list[str] | None:
    suffix = wrapper_path.suffix.lower()
    if suffix not in {".ps1", ".cmd", ".bat"}:
        return None
    try:
        text = wrapper_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if suffix == ".ps1":
        match = re.search(r"^\s*&\s+((?:\"[^\"]+\"|'[^']+')(?:(?:\s+)(?:\"[^\"]+\"|'[^']+'))*)\s+@args\b", text, re.MULTILINE)
    else:
        match = re.search(r"^\s*@?(?:echo off\s*)?[\r\n]+((?:\"[^\"]+\")(?:\s+\"[^\"]+\")*)\s+%\*\s*$", text, re.MULTILINE)
    if match is None:
        return None
    quoted = re.findall(r"\"([^\"]+)\"|'([^']+)'", match.group(1))
    tokens = [first or second for first, second in quoted if first or second]
    if not tokens:
        return None
    resolved = _resolve_executable_token(tokens[0])
    if resolved is None:
        return None
    return [resolved, *tokens[1:]]


def resolve_command_argv(command: str | tuple[str, ...]) -> list[str] | None:
    if isinstance(command, str):
        tokens = [command]
    else:
        tokens = list(command)
    if not tokens:
        return None
    stripped = tokens[0].strip().strip('"')
    if not stripped:
        return None
    resolved = _resolve_executable_token(stripped)
    if resolved is None:
        return None
    if os.name == "nt" and os.path.isabs(resolved):
        parsed = _parse_windows_wrapper_command(Path(resolved))
        if parsed is not None:
            return [*parsed, *tokens[1:]]
    return [resolved, *tokens[1:]]


def resolve_command_path(command: str | tuple[str, ...]) -> str | None:
    argv = resolve_command_argv(command)
    return argv[0] if argv else None


def _run_command(command: list[str], *, timeout_ms: int, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    if command and os.name == "nt" and command[0].lower().endswith(".ps1"):
        shell_path = resolve_command_path("pwsh") or resolve_command_path("powershell")
        if shell_path is not None:
            command = [shell_path, "-NoProfile", "-File", command[0], *command[1:]]
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=max(0.5, timeout_ms / 1000.0),
        check=False,
    )


def _normalize_version(stdout: str, stderr: str) -> str | None:
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            if line.strip():
                return line.strip()
    return None


def _parse_models(stdout: str) -> list[str]:
    text = stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        payload = json.loads(text)
        if isinstance(payload, list):
            return [str(item) for item in payload]
    if text.startswith("{"):
        payload = json.loads(text)
        if isinstance(payload, dict) and isinstance(payload.get("models"), list):
            return [str(item) for item in payload["models"]]
    normalized_text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    return [line.strip() for line in normalized_text.splitlines() if line.strip()]


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _discover_codex_cached_models() -> tuple[list[str], str | None, str | None]:
    cache_path = Path.home() / ".codex" / "models_cache.json"
    if not cache_path.exists():
        return [], None, f"Codex model cache not found at {cache_path}."
    try:
        payload = read_json(cache_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [], None, f"Failed to parse Codex model cache at {cache_path}: {exc}"

    model_entries: object
    if isinstance(payload, dict):
        model_entries = payload.get("models", [])
    else:
        model_entries = payload

    if not isinstance(model_entries, list):
        return [], None, f"Codex model cache at {cache_path} does not contain a models list."

    models: list[str] = []
    for entry in model_entries:
        if isinstance(entry, str) and entry.strip():
            models.append(entry.strip())
        elif isinstance(entry, dict):
            slug = entry.get("slug")
            if isinstance(slug, str) and slug.strip():
                models.append(slug.strip())
    return _dedupe_strings(models), "cache-file", None


def _discover_codex_app_server_models(command_argv: list[str], *, timeout_ms: int) -> tuple[list[str], str | None, str | None]:
    process = subprocess.Popen(
        [*command_argv, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdin is None or process.stdout is None:
        try:
            process.terminate()
        except OSError:
            pass
        return [], None, "Failed to open Codex app-server stdio streams."

    events: "queue.Queue[str | None]" = queue.Queue()
    transcript_lines: list[str] = []

    def reader() -> None:
        try:
            for raw_line in process.stdout:
                events.put(raw_line.rstrip("\r\n"))
        finally:
            events.put(None)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    def send(message: dict[str, object]) -> None:
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def read_until(predicate) -> dict[str, object]:
        deadline = time.monotonic() + max(0.5, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw = events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError from exc
            if raw is None:
                break
            transcript_lines.append(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if predicate(payload):
                return payload
        raise TimeoutError

    try:
        send(
            {
                "id": "initialize",
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": ROUTER_NAME,
                        "title": ROUTER_NAME,
                        "version": "1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            }
        )
        read_until(lambda payload: payload.get("id") == "initialize")
        send({"method": "initialized"})
        send({"id": "model-list", "method": "model/list", "params": {}})
        response_line = read_until(lambda payload: payload.get("id") == "model-list")
    except TimeoutError:
        message = "\n".join(transcript_lines).strip()
        if message:
            return [], None, f"Codex app-server model/list timed out after {timeout_ms}ms. Transcript: {message}"
        return [], None, f"Codex app-server model/list timed out after {timeout_ms}ms."
    finally:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    error = response_line.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        return [], None, f"Codex app-server model/list failed: {message or error!r}"

    result = response_line.get("result")
    if not isinstance(result, dict):
        return [], None, "Codex app-server model/list returned an invalid result payload."

    data = result.get("data", [])
    if not isinstance(data, list):
        return [], None, "Codex app-server model/list returned a non-list data payload."

    models: list[str] = []
    for entry in data:
        if isinstance(entry, dict):
            model_value = entry.get("model") or entry.get("id")
            if isinstance(model_value, str) and model_value.strip():
                models.append(model_value.strip())
        elif isinstance(entry, str) and entry.strip():
            models.append(entry.strip())
    return _dedupe_strings(models), "app-server-model-list", None


def _discover_codex_models(command_argv: list[str], *, timeout_ms: int) -> tuple[list[str], str | None, str | None]:
    app_server_models, app_server_source, app_server_note = _discover_codex_app_server_models(command_argv, timeout_ms=timeout_ms)
    if app_server_source is not None:
        return app_server_models, app_server_source, app_server_note

    cached_models, cached_source, cached_note = _discover_codex_cached_models()
    if cached_source is not None:
        fallback_note = app_server_note
        if cached_note:
            fallback_note = f"{fallback_note} Falling back to local cache. {cached_note}" if fallback_note else cached_note
        elif fallback_note:
            fallback_note = f"{fallback_note} Falling back to local cache."
        return cached_models, cached_source, fallback_note
    return [], None, app_server_note or cached_note


def _discover_kimi_configured_models() -> tuple[list[str], str | None, str | None]:
    config_path = Path.home() / ".kimi" / "config.toml"
    if not config_path.exists():
        return [], None, f"Kimi config file not found at {config_path}."
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [], None, f"Failed to parse Kimi config at {config_path}: {exc}"

    models_section = payload.get("models")
    if not isinstance(models_section, dict):
        return [], None, f"Kimi config at {config_path} does not contain a models table."

    models: list[str] = []
    for alias, entry in models_section.items():
        if isinstance(alias, str) and alias.strip() and isinstance(entry, dict):
            model_value = entry.get("model")
            if isinstance(model_value, str) and model_value.strip():
                models.append(alias.strip())
    return _dedupe_strings(models), "config-file", None


def _discover_local_models(adapter: CLIAdapter) -> tuple[list[str], str | None, str | None]:
    if adapter.id == "codex":
        return _discover_codex_cached_models()
    if adapter.id == "kimi":
        return _discover_kimi_configured_models()
    return [], None, None


def probe_adapter(adapter: CLIAdapter, *, timeout_ms: int) -> dict[str, object]:
    command_argv = resolve_command_argv(adapter.command)
    resolved_path = command_argv[0] if command_argv else None
    notes: list[str] = []
    entry: dict[str, object] = {
        "id": adapter.id,
        "available": False,
        "builtin": adapter.builtin,
        "command": _command_display(adapter.command),
        "resolved_path": resolved_path,
        "version": None,
        "models": [],
        "model_source": "unknown",
        "transport": adapter.transport,
        "notes": notes,
    }
    if resolved_path is None:
        notes.append("Executable not found on PATH or at the configured absolute path.")
        return entry

    try:
        probe_result = _run_command([*command_argv, *adapter.probe_args], timeout_ms=timeout_ms)
    except subprocess.TimeoutExpired:
        notes.append(f"Probe command timed out after {timeout_ms}ms.")
        return entry

    if probe_result.returncode != 0:
        message = (probe_result.stderr or probe_result.stdout).strip() or f"Probe command exited with code {probe_result.returncode}."
        notes.append(message)
        return entry

    entry["available"] = True
    entry["version"] = _normalize_version(probe_result.stdout, probe_result.stderr)

    if adapter.id == "codex" and adapter.transport == "app-server" and adapter.model_list_template is None:
        models, model_source, note = _discover_codex_models(command_argv, timeout_ms=timeout_ms)
        if model_source is not None:
            entry["models"] = models
            entry["model_source"] = model_source
            if note:
                notes.append(note)
            return entry
        if note:
            notes.append(note)

    if adapter.model_list_template:
        try:
            models_result = _run_command([*command_argv, *adapter.model_list_template], timeout_ms=timeout_ms)
        except subprocess.TimeoutExpired:
            entry["model_source"] = "failed"
            notes.append(f"Model-list command timed out after {timeout_ms}ms.")
            return entry

        if models_result.returncode != 0:
            entry["model_source"] = "failed"
            message = (models_result.stderr or models_result.stdout).strip() or f"Model-list command exited with code {models_result.returncode}."
            notes.append(message)
            return entry

        entry["models"] = _parse_models(models_result.stdout)
        entry["model_source"] = "cli-list"
        return entry

    if adapter.default_models:
        entry["models"] = list(adapter.default_models)
        entry["model_source"] = "adapter-defaults"
        return entry

    local_models, local_source, local_note = _discover_local_models(adapter)
    if local_source is not None:
        entry["models"] = local_models
        entry["model_source"] = local_source
        if local_note:
            notes.append(local_note)
    elif local_note:
        entry["model_source"] = "unknown"
        notes.append(local_note)
    else:
        entry["model_source"] = "unsupported"
        notes.append("Model discovery is not supported for this CLI adapter.")
    return entry


def probe_inventory(
    repo_root: Path,
    *,
    timeout_ms: int | None = None,
    probe_tool: str,
    write_discovery: bool = True,
    policy: dict[str, object] | None = None,
) -> dict[str, object]:
    effective_policy = policy
    if effective_policy is None:
        try:
            effective_policy = load_policy(repo_root)
        except RouterConfigError:
            effective_policy = None

    if effective_policy is not None and timeout_ms is None:
        timeout_ms = int(_as_dict(effective_policy["defaults"], "defaults")["probe_timeout_ms"])
    timeout_ms = 2500 if timeout_ms is None else timeout_ms

    clis = [probe_adapter(adapter, timeout_ms=timeout_ms) for adapter in adapters_from_policy(effective_policy)]
    if not clis:
        probe_status = "failed"
    elif all(entry["available"] for entry in clis):
        probe_status = "ok"
    elif any(entry["available"] for entry in clis):
        probe_status = "partial"
    else:
        probe_status = "failed"
    inventory = empty_discovery_inventory(probe_tool=probe_tool, probe_status=probe_status, clis=clis)
    if write_discovery:
        discovery_path = router_discovery_path(repo_root)
        discovery_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(discovery_path, inventory)
    return inventory


def _available_cli_entries(inventory: dict[str, object]) -> list[dict[str, object]]:
    return [entry for entry in inventory["clis"] if entry["available"]]


def _cli_entry_by_id(inventory: dict[str, object], cli_id: str) -> dict[str, object] | None:
    for entry in inventory["clis"]:
        if entry["id"] == cli_id:
            return entry
    return None


def _probe_timeout_ms_from_policy(policy: dict[str, object]) -> int:
    return int(_as_dict(policy["defaults"], "defaults")["probe_timeout_ms"])


def _invoke_timeout_ms_from_policy(policy: dict[str, object]) -> int:
    defaults = _as_dict(policy["defaults"], "defaults")
    return int(defaults.get("invoke_timeout_ms", _as_dict(default_router_policy()["defaults"], "default defaults")["invoke_timeout_ms"]))


def adapter_by_id(policy: dict[str, object] | None, cli_id: str) -> CLIAdapter | None:
    for adapter in adapters_from_policy(policy):
        if adapter.id == cli_id:
            return adapter
    return None


def _verification_prompt(token: str) -> str:
    return f"Reply with exactly this token and no extra text: {token}"


def _token_found(token: str, *streams: str | None) -> bool:
    return any(token in stream for stream in streams if stream)


def _run_template_invocation(
    *,
    command_argv: list[str],
    adapter: CLIAdapter,
    repo_root: Path,
    model: str,
    prompt: str,
    timeout_ms: int,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="recursive-router-verify-") as temp_dir:
        prompt_path = Path(temp_dir) / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        command_path = command_argv[0]
        if (
            os.name == "nt"
            and "\n" in prompt
            and any("{prompt}" in piece for piece in adapter.invoke_template)
            and command_path.lower().endswith((".cmd", ".bat", ".ps1"))
        ):
            shell_path = resolve_command_path("pwsh") or resolve_command_path("powershell")
            if shell_path is not None:
                powershell_command_argv = list(command_argv)
                if command_path.lower().endswith((".cmd", ".bat")):
                    companion_ps1 = Path(command_path).with_suffix(".ps1")
                    if companion_ps1.exists():
                        powershell_command_argv = [str(companion_ps1), *command_argv[1:]]
                return _run_template_invocation_via_powershell(
                    shell_path=shell_path,
                    command_argv=powershell_command_argv,
                    adapter=adapter,
                    repo_root=repo_root,
                    model=model,
                    prompt_path=prompt_path,
                    timeout_ms=timeout_ms,
                )
        args = [piece.format(model=model, prompt_file=str(prompt_path), prompt=prompt) for piece in adapter.invoke_template]
        return _run_command([*command_argv, *args], timeout_ms=timeout_ms, cwd=repo_root)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _normalize_kimi_output(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip() and line.strip() != "<choice>STOP</choice>"]
    return "\n".join(lines).strip()


def _normalize_opencode_output(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    fragments: list[str] = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("type") != "text":
            continue
        part = payload.get("part")
        if not isinstance(part, dict):
            continue
        message = part.get("text")
        if isinstance(message, str) and message.strip():
            fragments.append(message.strip())
    if fragments:
        return "\n".join(fragments).strip()
    return stripped


def _single_quote_for_powershell(value: str) -> str:
    return value.replace("'", "''")


def _run_template_invocation_via_powershell(
    *,
    shell_path: str,
    command_argv: list[str],
    adapter: CLIAdapter,
    repo_root: Path,
    model: str,
    prompt_path: Path,
    timeout_ms: int,
) -> subprocess.CompletedProcess[str]:
    script_path = prompt_path.with_name("invoke-router-template.ps1")
    command_lines = [f"    '{_single_quote_for_powershell(part)}'" for part in command_argv]
    args_lines: list[str] = []
    prompt_expression = f"(Get-Content -Raw -LiteralPath '{_single_quote_for_powershell(str(prompt_path))}')"
    for piece in adapter.invoke_template:
        if "{prompt}" in piece:
            before, after = piece.split("{prompt}", 1)
            expression_parts: list[str] = []
            if before:
                formatted_before = before.format(model=model, prompt_file=str(prompt_path), prompt="")
                expression_parts.append(f"'{_single_quote_for_powershell(formatted_before)}'")
            expression_parts.append(prompt_expression)
            if after:
                formatted_after = after.format(model=model, prompt_file=str(prompt_path), prompt="")
                expression_parts.append(f"'{_single_quote_for_powershell(formatted_after)}'")
            if len(expression_parts) == 1:
                args_lines.append(f"    {expression_parts[0]}")
            else:
                args_lines.append(f"    ({' + '.join(expression_parts)})")
            continue
        formatted = piece.format(model=model, prompt_file=str(prompt_path), prompt="")
        args_lines.append(f"    '{_single_quote_for_powershell(formatted)}'")
    script = "\n".join(
        [
            '$ErrorActionPreference = "Stop"',
            "$command = @(",
            *command_lines,
            ")",
            "if ($command.Length -gt 1) {",
            "    $commandPrefix = $command[1..($command.Length - 1)]",
            "} else {",
            "    $commandPrefix = @()",
            "}",
            "$argsList = @(",
            *args_lines,
            ")",
            "& $command[0] @commandPrefix @argsList",
            "exit $LASTEXITCODE",
        ]
    )
    script_path.write_text(script, encoding="utf-8", newline="\n")
    return _run_command([shell_path, "-NoProfile", "-File", str(script_path)], timeout_ms=timeout_ms, cwd=repo_root)


def _invoke_codex_app_server(
    *,
    command_argv: list[str],
    repo_root: Path,
    model: str,
    prompt: str,
    timeout_ms: int,
) -> dict[str, object]:
    process = subprocess.Popen(
        [*command_argv, "app-server", "--listen", "stdio://"],
        cwd=str(repo_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdin is None or process.stdout is None:
        try:
            process.terminate()
        except OSError:
            pass
        return {
            "success": False,
            "transport": "app-server",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "reason": "Failed to open Codex app-server stdio streams.",
            "transcript": "",
        }

    events: "queue.Queue[str | None]" = queue.Queue()
    transcript_lines: list[str] = []

    def reader() -> None:
        try:
            for raw_line in process.stdout:
                events.put(raw_line.rstrip("\r\n"))
        finally:
            events.put(None)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    def send(message: dict[str, object]) -> None:
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def read_until(predicate) -> dict[str, object]:
        deadline = time.monotonic() + max(0.5, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw = events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError from exc
            if raw is None:
                break
            transcript_lines.append(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if predicate(payload):
                return payload
        raise TimeoutError

    final_message = ""
    try:
        send(
            {
                "id": "initialize",
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": ROUTER_NAME,
                        "title": ROUTER_NAME,
                        "version": "1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            }
        )
        read_until(lambda payload: payload.get("id") == "initialize")
        send({"method": "initialized"})
        send(
            {
                "id": "thread-start",
                "method": "thread/start",
                "params": {
                    "model": model,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "cwd": str(repo_root),
                },
            }
        )
        thread_start = read_until(lambda payload: payload.get("id") == "thread-start")
        if isinstance(thread_start.get("error"), dict):
            message = thread_start["error"].get("message") or repr(thread_start["error"])
            return {
                "success": False,
                "transport": "app-server",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "reason": f"Codex thread/start failed: {message}",
                "transcript": "\n".join(transcript_lines),
            }
        thread_id = str(_as_dict(thread_start["result"], "thread/start result")["thread"]["id"])

        send(
            {
                "id": "turn-start",
                "method": "turn/start",
                "params": {
                    "threadId": thread_id,
                    "model": model,
                    "input": [{"type": "text", "text": prompt, "text_elements": []}],
                },
            }
        )
        turn_start = read_until(lambda payload: payload.get("id") == "turn-start")
        if isinstance(turn_start.get("error"), dict):
            message = turn_start["error"].get("message") or repr(turn_start["error"])
            return {
                "success": False,
                "transport": "app-server",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "reason": f"Codex turn/start failed: {message}",
                "transcript": "\n".join(transcript_lines),
            }
        turn_id = str(_as_dict(turn_start["result"], "turn/start result")["turn"]["id"])

        deadline = time.monotonic() + max(0.5, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw = events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError from exc
            if raw is None:
                break
            transcript_lines.append(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if payload.get("method") == "item/completed":
                params = payload.get("params", {})
                item = params.get("item", {})
                if (
                    params.get("threadId") == thread_id
                    and params.get("turnId") == turn_id
                    and item.get("type") == "agentMessage"
                    and item.get("phase") == "final_answer"
                ):
                    final_message = str(item.get("text", ""))
            if payload.get("method") == "turn/completed":
                params = payload.get("params", {})
                turn = params.get("turn", {})
                if params.get("threadId") == thread_id and turn.get("id") == turn_id:
                    return {
                        "success": bool(final_message.strip()),
                        "transport": "app-server",
                        "exit_code": 0,
                        "stdout": final_message,
                        "stderr": "",
                        "reason": "Prompt completed via Codex app-server." if final_message.strip() else "Codex returned no final answer text.",
                        "transcript": "\n".join(transcript_lines),
                    }
        raise TimeoutError
    except TimeoutError:
        return {
            "success": False,
            "transport": "app-server",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "reason": f"Codex app-server invocation timed out after {timeout_ms}ms.",
            "transcript": "\n".join(transcript_lines),
        }
    finally:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _verify_codex_app_server(
    *,
    command_argv: list[str],
    repo_root: Path,
    model: str,
    prompt: str,
    timeout_ms: int,
) -> dict[str, object]:
    process = subprocess.Popen(
        [*command_argv, "app-server", "--listen", "stdio://"],
        cwd=str(repo_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdin is None or process.stdout is None:
        try:
            process.terminate()
        except OSError:
            pass
        return {
            "verified": False,
            "transport": "app-server",
            "exit_code": None,
            "token_found": False,
            "stdout": "",
            "stderr": "",
            "reason": "Failed to open Codex app-server stdio streams.",
        }

    events: "queue.Queue[str | None]" = queue.Queue()
    transcript_lines: list[str] = []

    def reader() -> None:
        try:
            for raw_line in process.stdout:
                events.put(raw_line.rstrip("\r\n"))
        finally:
            events.put(None)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    def send(message: dict[str, object]) -> None:
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def read_until(predicate) -> dict[str, object]:
        deadline = time.monotonic() + max(0.5, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw = events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError from exc
            if raw is None:
                break
            transcript_lines.append(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if predicate(payload):
                return payload
        raise TimeoutError

    final_message = ""
    try:
        send(
            {
                "id": "initialize",
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": ROUTER_NAME,
                        "title": ROUTER_NAME,
                        "version": "1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            }
        )
        read_until(lambda payload: payload.get("id") == "initialize")
        send({"method": "initialized"})
        send(
            {
                "id": "thread-start",
                "method": "thread/start",
                "params": {
                    "model": model,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "cwd": str(repo_root),
                },
            }
        )
        thread_start = read_until(lambda payload: payload.get("id") == "thread-start")
        if isinstance(thread_start.get("error"), dict):
            message = thread_start["error"].get("message") or repr(thread_start["error"])
            return {
                "verified": False,
                "transport": "app-server",
                "exit_code": None,
                "token_found": False,
                "stdout": "\n".join(transcript_lines),
                "stderr": "",
                "reason": f"Codex thread/start failed: {message}",
            }
        thread_id = str(_as_dict(thread_start["result"], "thread/start result")["thread"]["id"])

        send(
            {
                "id": "turn-start",
                "method": "turn/start",
                "params": {
                    "threadId": thread_id,
                    "model": model,
                    "input": [{"type": "text", "text": prompt, "text_elements": []}],
                },
            }
        )
        turn_start = read_until(lambda payload: payload.get("id") == "turn-start")
        if isinstance(turn_start.get("error"), dict):
            message = turn_start["error"].get("message") or repr(turn_start["error"])
            return {
                "verified": False,
                "transport": "app-server",
                "exit_code": None,
                "token_found": False,
                "stdout": "\n".join(transcript_lines),
                "stderr": "",
                "reason": f"Codex turn/start failed: {message}",
            }
        turn_id = str(_as_dict(turn_start["result"], "turn/start result")["turn"]["id"])

        deadline = time.monotonic() + max(0.5, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw = events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError from exc
            if raw is None:
                break
            transcript_lines.append(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if payload.get("method") == "item/completed":
                params = payload.get("params", {})
                item = params.get("item", {})
                if (
                    params.get("threadId") == thread_id
                    and params.get("turnId") == turn_id
                    and item.get("type") == "agentMessage"
                    and item.get("phase") == "final_answer"
                ):
                    final_message = str(item.get("text", ""))
            if payload.get("method") == "turn/completed":
                params = payload.get("params", {})
                turn = params.get("turn", {})
                if params.get("threadId") == thread_id and turn.get("id") == turn_id:
                    transcript = "\n".join(transcript_lines)
                    token = prompt.rsplit(":", 1)[-1].strip()
                    token_found = _token_found(token, final_message, transcript)
                    return {
                        "verified": token_found,
                        "transport": "app-server",
                        "exit_code": 0,
                        "token_found": token_found,
                        "stdout": final_message,
                        "stderr": "",
                        "reason": "Verification prompt completed via Codex app-server." if token_found else "Verification token not found in Codex response.",
                        "transcript": transcript,
                    }
        raise TimeoutError
    except TimeoutError:
        transcript = "\n".join(transcript_lines)
        return {
            "verified": False,
            "transport": "app-server",
            "exit_code": None,
            "token_found": False,
            "stdout": transcript,
            "stderr": "",
            "reason": f"Codex app-server verification timed out after {timeout_ms}ms.",
        }
    finally:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            exit_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait(timeout=5)
        # Preserve a best-effort process exit code in the transcript for callers that need it.
        transcript_lines.append(f"[process-exit:{exit_code}]")


def verify_route_binding(
    repo_root: Path,
    *,
    role: str,
    cli_id: str,
    model: str,
    timeout_ms: int | None = None,
    policy: dict[str, object] | None = None,
) -> dict[str, object]:
    effective_policy = load_policy(repo_root) if policy is None else policy
    resolved_role = canonicalize_router_role(role)
    if not model.strip():
        raise RouterConfigError("Configured model must be a non-empty string.")

    adapter = adapter_by_id(effective_policy, cli_id)
    if adapter is None:
        raise RouterConfigError(f"Unknown CLI id: {cli_id}")

    effective_timeout_ms = _probe_timeout_ms_from_policy(effective_policy) if timeout_ms is None else timeout_ms
    command_argv = resolve_command_argv(adapter.command)
    command_path = command_argv[0] if command_argv else None
    token = f"ROUTER_VERIFY_{uuid.uuid4().hex[:12].upper()}"
    prompt = _verification_prompt(token)
    result: dict[str, object] = {
        "role": resolved_role,
        "cli": cli_id,
        "model": model,
        "transport": adapter.transport,
        "verified": False,
        "token": token,
        "token_found": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "reason": "",
    }

    if command_path is None:
        result["reason"] = f"Executable for CLI {cli_id!r} was not found."
        return result

    builtin_adapter = BUILTIN_ADAPTER_BY_ID.get(adapter.id)
    template_overridden = builtin_adapter is not None and adapter.invoke_template != builtin_adapter.invoke_template
    transport_overridden = builtin_adapter is not None and adapter.transport != builtin_adapter.transport

    if adapter.id == "codex" and adapter.transport == "app-server":
        completed = _run_command(
            [
                *command_argv,
                "exec",
                "--model",
                model,
                "--json",
                "--skip-git-repo-check",
                "--ephemeral",
                "-c",
                "mcp_servers.playwright.enabled=false",
                "-c",
                "mcp_servers.subframe.enabled=false",
                "-c",
                'mcp_servers["subframe-docs"].enabled=false',
                "-c",
                "mcp_servers.pencil.enabled=false",
                "-C",
                str(repo_root),
                prompt,
            ],
            timeout_ms=effective_timeout_ms,
            cwd=repo_root,
        )
        token_found = _token_found(token, completed.stdout, completed.stderr)
        verification = {
            "verified": token_found and completed.returncode == 0,
            "transport": adapter.transport,
            "exit_code": completed.returncode,
            "token_found": token_found,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "reason": (
                "Verification token observed in Codex exec output."
                if token_found and completed.returncode == 0
                else f"Codex verification failed with exit code {completed.returncode}."
            ),
        }
    elif adapter.id == "kimi" and not template_overridden and not transport_overridden:
        completed = _run_command(
            [
                *command_argv,
                "--model",
                model,
                "--print",
                "--final-message-only",
                "--prompt",
                prompt,
            ],
            timeout_ms=effective_timeout_ms,
            cwd=repo_root,
        )
        combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
        token_found = _token_found(token, completed.stdout, completed.stderr)
        verification = {
            "verified": token_found,
            "transport": adapter.transport,
            "exit_code": completed.returncode,
            "token_found": token_found,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "reason": (
                "Verification token observed in Kimi output."
                if token_found
                else f"Kimi verification failed with exit code {completed.returncode}."
            ),
            "combined_output": combined,
        }
    elif adapter.id == "opencode" and not template_overridden and not transport_overridden:
        completed = _run_command(
            [
                *command_argv,
                "run",
                "--model",
                model,
                "--format",
                "json",
                "--dir",
                str(repo_root),
                prompt,
            ],
            timeout_ms=effective_timeout_ms,
            cwd=repo_root,
        )
        token_found = _token_found(token, completed.stdout, completed.stderr)
        verification = {
            "verified": token_found and completed.returncode == 0,
            "transport": adapter.transport,
            "exit_code": completed.returncode,
            "token_found": token_found,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "reason": (
                "Verification token observed in Opencode output."
                if token_found and completed.returncode == 0
                else f"Opencode verification failed with exit code {completed.returncode}."
            ),
        }
    else:
        completed = _run_template_invocation(
            command_argv=command_argv,
            adapter=adapter,
            repo_root=repo_root,
            model=model,
            prompt=prompt,
            timeout_ms=effective_timeout_ms,
        )
        token_found = _token_found(token, completed.stdout, completed.stderr)
        verification = {
            "verified": token_found and completed.returncode == 0,
            "transport": adapter.transport,
            "exit_code": completed.returncode,
            "token_found": token_found,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "reason": (
                f"Verification token observed in {cli_id} output."
                if token_found and completed.returncode == 0
                else f"{cli_id} verification failed with exit code {completed.returncode}."
            ),
        }

    result.update(verification)
    return result


def invoke_route_binding(
    repo_root: Path,
    *,
    role: str,
    prompt: str,
    timeout_ms: int | None = None,
    policy: dict[str, object] | None = None,
    write_discovery: bool = True,
) -> dict[str, object]:
    effective_policy = load_policy(repo_root) if policy is None else policy
    resolved_role = canonicalize_router_role(role)
    decision = resolve_route(repo_root, role=resolved_role, timeout_ms=timeout_ms, write_discovery=write_discovery)
    effective_timeout_ms = _invoke_timeout_ms_from_policy(effective_policy) if timeout_ms is None else timeout_ms
    payload: dict[str, object] = {
        "role": resolved_role,
        "decision": decision,
        "cli": decision.get("cli"),
        "model": decision.get("model"),
        "transport": decision.get("transport"),
        "resolved_command": None,
        "output_text": "",
        "raw_stdout": "",
        "raw_stderr": "",
        "exit_code": None,
        "success": False,
        "reason": "",
        "transcript": "",
    }

    if decision.get("decision") != "external-cli":
        payload["reason"] = f"Route did not resolve to external-cli: {decision.get('decision')}"
        return payload

    cli_id = str(decision["cli"])
    model = str(decision["model"])
    adapter = adapter_by_id(effective_policy, cli_id)
    if adapter is None:
        raise RouterConfigError(f"Unknown CLI id: {cli_id}")
    command_argv = resolve_command_argv(adapter.command)
    command_path = command_argv[0] if command_argv else None
    payload["resolved_command"] = _command_display(tuple(command_argv)) if command_argv and len(command_argv) > 1 else command_path
    if command_path is None:
        payload["reason"] = f"Executable for CLI {cli_id!r} was not found."
        return payload

    builtin_adapter = BUILTIN_ADAPTER_BY_ID.get(adapter.id)
    template_overridden = builtin_adapter is not None and adapter.invoke_template != builtin_adapter.invoke_template
    transport_overridden = builtin_adapter is not None and adapter.transport != builtin_adapter.transport

    if adapter.id == "codex" and adapter.transport == "app-server":
        invocation = _invoke_codex_app_server(
            command_argv=command_argv,
            repo_root=repo_root,
            model=model,
            prompt=prompt,
            timeout_ms=effective_timeout_ms,
        )
        payload.update(
            {
                "transport": invocation["transport"],
                "output_text": str(invocation["stdout"]).strip(),
                "raw_stdout": str(invocation["stdout"]),
                "raw_stderr": str(invocation["stderr"]),
                "exit_code": invocation["exit_code"],
                "success": invocation["success"],
                "reason": invocation["reason"],
                "transcript": invocation["transcript"],
            }
        )
        return payload

    if adapter.id == "kimi" and not template_overridden and not transport_overridden:
        completed = _run_command(
            [
                *command_argv,
                "--model",
                model,
                "--print",
                "--final-message-only",
                "--prompt",
                prompt,
            ],
            timeout_ms=effective_timeout_ms,
            cwd=repo_root,
        )
        output_text = _normalize_kimi_output(completed.stdout)
        payload.update(
            {
                "output_text": output_text,
                "raw_stdout": completed.stdout,
                "raw_stderr": _strip_ansi(completed.stderr),
                "exit_code": completed.returncode,
                "success": bool(output_text),
                "reason": (
                    "Prompt completed through Kimi."
                    if output_text and completed.returncode == 0
                    else f"Kimi returned output with exit code {completed.returncode}."
                    if output_text
                    else f"Kimi invocation failed with exit code {completed.returncode}."
                ),
            }
        )
        return payload

    if adapter.id == "opencode" and not template_overridden and not transport_overridden:
        completed = _run_command(
            [
                *command_argv,
                "run",
                "--model",
                model,
                "--format",
                "json",
                "--dir",
                str(repo_root),
                prompt,
            ],
            timeout_ms=effective_timeout_ms,
            cwd=repo_root,
        )
        output_text = _normalize_opencode_output(completed.stdout)
        payload.update(
            {
                "output_text": output_text,
                "raw_stdout": completed.stdout,
                "raw_stderr": _strip_ansi(completed.stderr),
                "exit_code": completed.returncode,
                "success": bool(output_text) and completed.returncode == 0,
                "reason": (
                    "Prompt completed through opencode."
                    if output_text and completed.returncode == 0
                    else f"opencode returned output with exit code {completed.returncode}."
                    if output_text
                    else f"opencode invocation failed with exit code {completed.returncode}."
                ),
            }
        )
        return payload

    completed = _run_template_invocation(
        command_argv=command_argv,
        adapter=adapter,
        repo_root=repo_root,
        model=model,
        prompt=prompt,
        timeout_ms=effective_timeout_ms,
    )
    output_text = completed.stdout.strip()
    payload.update(
        {
            "output_text": output_text,
            "raw_stdout": completed.stdout,
            "raw_stderr": _strip_ansi(completed.stderr),
            "exit_code": completed.returncode,
            "success": bool(output_text),
            "reason": (
                f"Prompt completed through {cli_id}."
                if output_text and completed.returncode == 0
                else f"{cli_id} returned output with exit code {completed.returncode}."
                if output_text
                else f"{cli_id} invocation failed with exit code {completed.returncode}."
            ),
        }
    )
    return payload


def configure_verified_routes(
    repo_root: Path,
    *,
    assignments: dict[str, dict[str, str]],
    timeout_ms: int | None = None,
) -> dict[str, object]:
    policy = load_policy(repo_root)
    normalized_assignments: dict[str, dict[str, str]] = {}
    for role, binding in assignments.items():
        canonical_role = canonicalize_router_role(role)
        if canonical_role in normalized_assignments:
            raise RouterConfigError(f"Duplicate role assignment provided for {canonical_role}.")
        normalized_assignments[canonical_role] = binding
    verification_results: dict[str, dict[str, object]] = {}
    verification_cache: dict[tuple[str, str], dict[str, object]] = {}
    for role, binding in normalized_assignments.items():
        cli_id = binding["cli"]
        model = binding["model"]
        cache_key = (cli_id, model)
        cached_result = verification_cache.get(cache_key)
        if cached_result is None:
            cached_result = verify_route_binding(
                repo_root,
                role=role,
                cli_id=cli_id,
                model=model,
                timeout_ms=timeout_ms,
                policy=policy,
            )
            verification_cache[cache_key] = cached_result
        role_result = deepcopy(cached_result)
        role_result["role"] = role
        verification_results[role] = role_result

    all_verified = all(result["verified"] for result in verification_results.values())
    if all_verified:
        updated_policy = deepcopy(policy)
        for role, binding in normalized_assignments.items():
            route = _as_dict(updated_policy["role_routes"][role], f"role_routes.{role}")
            route["cli"] = binding["cli"]
            route["model"] = binding["model"]
        write_json(router_policy_path(repo_root), validate_policy(updated_policy))

    return {
        "saved": all_verified,
        "policy_path": normalize_repo_path(str(router_policy_path(repo_root).relative_to(repo_root))),
        "verification_results": verification_results,
    }


def build_unresolved_prompt(*, roles: list[str], inventory: dict[str, object], reason: str, config_path: str, discovery_path: str) -> str:
    lines = ["I found these CLIs in this environment:"]
    for entry in inventory["clis"]:
        version = entry["version"] or "unknown version"
        models = entry["models"]
        model_suffix = f"; models: {', '.join(models)}" if models else ""
        lines.append(f"- {entry['id']} ({'available' if entry['available'] else 'unavailable'}, version {version}{model_suffix})")
    if len(lines) == 1:
        lines.append("- none discovered")
    lines.extend(
        [
            "",
            reason,
            f"Please choose a CLI and model for these roles in {config_path}.",
            f"For valid CLI ids and model ids, check {discovery_path}.",
            "",
            "Unresolved roles:",
        ]
    )
    lines.extend(f"- {role}" for role in roles)
    lines.extend(
        [
            "",
            "You can answer in a compact mapping like:",
            "analyst=codex:gpt-5",
            "code-reviewer=kimi:kimi-code/kimi-for-coding",
        ]
    )
    return "\n".join(lines)


def resolve_route(
    repo_root: Path,
    *,
    role: str,
    timeout_ms: int | None = None,
    write_discovery: bool = True,
) -> dict[str, object]:
    resolved_role = canonicalize_router_role(role)
    config_path = normalize_repo_path(str(router_policy_path(repo_root).relative_to(repo_root)))
    discovery_path = normalize_repo_path(str(router_discovery_path(repo_root).relative_to(repo_root)))
    policy_error = ""
    try:
        policy = load_policy(repo_root)
    except RouterConfigError as exc:
        policy = None
        policy_error = str(exc)

    inventory = probe_inventory(
        repo_root,
        timeout_ms=timeout_ms,
        probe_tool="recursive-router-probe",
        write_discovery=write_discovery,
        policy=policy,
    )

    if policy is None:
        reason = policy_error or f"Missing routing policy file at {config_path}."
        return {
            "role": resolved_role,
            "decision": "ask-user",
            "cli": None,
            "model": None,
            "available": False,
            "fallback_used": False,
            "fallback": "ask",
            "reason": reason,
            "config_path": config_path,
            "discovery_path": discovery_path,
            "prompt": build_unresolved_prompt(
                roles=[resolved_role],
                inventory=inventory,
                reason=reason,
                config_path=config_path,
                discovery_path=discovery_path,
            ),
        }

    if resolved_role not in policy["role_routes"]:
        raise RouterConfigError(f"Unknown router role: {role}")

    defaults = policy["defaults"]
    route = policy["role_routes"][resolved_role]
    if not route["enabled"] or route["mode"] == "local-only":
        return {
            "role": resolved_role,
            "decision": "local-only",
            "cli": None,
            "model": None,
            "available": True,
            "fallback_used": False,
            "fallback": route["fallback"],
            "reason": f"role_routes.{resolved_role} is configured for local-only execution.",
            "config_path": config_path,
            "discovery_path": discovery_path,
        }

    selected_cli = route["cli"]
    selected_model = route["model"]
    reason_parts: list[str] = [f"resolved from role_routes.{resolved_role}"]
    available_entries = _available_cli_entries(inventory)

    if selected_cli is None:
        if defaults["allow_auto_assign_if_single_cli"] and len(available_entries) == 1:
            selected_cli = available_entries[0]["id"]
            reason_parts = ["auto-assigned the only discovered CLI for the unresolved role route"]
        else:
            policy_choice = defaults["when_role_unconfigured"]
            if policy_choice == "fallback-local":
                return {
                    "role": resolved_role,
                    "decision": "fallback-local",
                    "cli": None,
                    "model": None,
                    "available": False,
                    "fallback_used": True,
                    "fallback": route["fallback"],
                    "reason": f"role_routes.{resolved_role}.cli is unconfigured and defaults.when_role_unconfigured=fallback-local.",
                    "config_path": config_path,
                    "discovery_path": discovery_path,
                }
            if policy_choice == "block":
                return {
                    "role": resolved_role,
                    "decision": "blocked",
                    "cli": None,
                    "model": None,
                    "available": False,
                    "fallback_used": False,
                    "fallback": route["fallback"],
                    "reason": f"role_routes.{resolved_role}.cli is unconfigured and defaults.when_role_unconfigured=block.",
                    "config_path": config_path,
                    "discovery_path": discovery_path,
                }
            prompt_reason = f"role_routes.{resolved_role}.cli is unresolved."
            return {
                "role": resolved_role,
                "decision": "ask-user",
                "cli": None,
                "model": None,
                "available": False,
                "fallback_used": False,
                "fallback": "ask",
                "reason": prompt_reason,
                "config_path": config_path,
                "discovery_path": discovery_path,
                "prompt": build_unresolved_prompt(
                    roles=[resolved_role],
                    inventory=inventory,
                    reason=prompt_reason,
                    config_path=config_path,
                    discovery_path=discovery_path,
                ),
            }

    cli_entry = _cli_entry_by_id(inventory, selected_cli)
    if cli_entry is None or not cli_entry["available"]:
        policy_choice = defaults["when_cli_unavailable"]
        reason = f"Configured CLI {selected_cli!r} is unavailable in the current environment."
        if policy_choice == "ask":
            return {
                "role": resolved_role,
                "decision": "ask-user",
                "cli": selected_cli,
                "model": selected_model,
                "available": False,
                "fallback_used": False,
                "fallback": "ask",
                "reason": reason,
                "config_path": config_path,
                "discovery_path": discovery_path,
                "prompt": build_unresolved_prompt(
                    roles=[resolved_role],
                    inventory=inventory,
                    reason=reason,
                    config_path=config_path,
                    discovery_path=discovery_path,
                ),
            }
        if policy_choice == "block":
            return {
                "role": resolved_role,
                "decision": "blocked",
                "cli": selected_cli,
                "model": selected_model,
                "available": False,
                "fallback_used": False,
                "fallback": route["fallback"],
                "reason": reason,
                "config_path": config_path,
                "discovery_path": discovery_path,
            }
        return {
            "role": resolved_role,
            "decision": "fallback-local",
            "cli": selected_cli,
            "model": selected_model,
            "available": False,
            "fallback_used": True,
            "fallback": route["fallback"],
            "reason": reason,
            "config_path": config_path,
            "discovery_path": discovery_path,
        }

    models = list(cli_entry["models"])
    if selected_model is None:
        policy_choice = defaults["when_model_unknown"]
        reason = f"{'; '.join(reason_parts)}; model is unresolved for role {resolved_role}."
        if policy_choice == "fallback-local":
            return {
                "role": resolved_role,
                "decision": "fallback-local",
                "cli": selected_cli,
                "model": None,
                "available": True,
                "fallback_used": True,
                "fallback": route["fallback"],
                "reason": reason,
                "config_path": config_path,
                "discovery_path": discovery_path,
            }
        return {
            "role": resolved_role,
            "decision": "ask-user" if policy_choice in {"ask", "use-as-literal"} else "blocked",
            "cli": selected_cli,
            "model": None,
            "available": True,
            "fallback_used": False,
            "fallback": "ask" if policy_choice in {"ask", "use-as-literal"} else route["fallback"],
            "reason": reason,
            "config_path": config_path,
            "discovery_path": discovery_path,
            "prompt": build_unresolved_prompt(
                roles=[resolved_role],
                inventory=inventory,
                reason=reason,
                config_path=config_path,
                discovery_path=discovery_path,
            ),
        }

    if models and selected_model not in models:
        policy_choice = defaults["when_model_unknown"]
        reason = f"{'; '.join(reason_parts)}; configured model {selected_model!r} was not listed by CLI {selected_cli!r}."
        if policy_choice == "use-as-literal":
            return {
                "role": resolved_role,
                "decision": "external-cli",
                "cli": selected_cli,
                "model": selected_model,
                "transport": cli_entry.get("transport"),
                "available": True,
                "fallback_used": False,
                "fallback": route["fallback"],
                "reason": reason + " Using the configured model string literally per policy.",
                "config_path": config_path,
                "discovery_path": discovery_path,
            }
        if policy_choice == "fallback-local":
            return {
                "role": resolved_role,
                "decision": "fallback-local",
                "cli": selected_cli,
                "model": selected_model,
                "available": True,
                "fallback_used": True,
                "fallback": route["fallback"],
                "reason": reason,
                "config_path": config_path,
                "discovery_path": discovery_path,
            }
        return {
            "role": resolved_role,
            "decision": "ask-user",
            "cli": selected_cli,
            "model": selected_model,
            "available": True,
            "fallback_used": False,
            "fallback": "ask",
            "reason": reason,
            "config_path": config_path,
            "discovery_path": discovery_path,
            "prompt": build_unresolved_prompt(
                roles=[resolved_role],
                inventory=inventory,
                reason=reason,
                config_path=config_path,
                discovery_path=discovery_path,
            ),
        }

    if not models and defaults["when_model_unknown"] == "ask":
        reason = f"{'; '.join(reason_parts)}; model {selected_model!r} could not be verified because CLI {selected_cli!r} does not advertise models."
        return {
            "role": resolved_role,
            "decision": "ask-user",
            "cli": selected_cli,
            "model": selected_model,
            "available": True,
            "fallback_used": False,
            "fallback": "ask",
            "reason": reason,
            "config_path": config_path,
            "discovery_path": discovery_path,
            "prompt": build_unresolved_prompt(
                roles=[resolved_role],
                inventory=inventory,
                reason=reason,
                config_path=config_path,
                discovery_path=discovery_path,
            ),
        }

    return {
        "role": resolved_role,
        "decision": "external-cli",
        "cli": selected_cli,
        "model": selected_model,
        "transport": cli_entry.get("transport"),
        "available": True,
        "fallback_used": False,
        "fallback": route["fallback"],
        "reason": "; ".join(reason_parts),
        "config_path": config_path,
        "discovery_path": discovery_path,
    }
