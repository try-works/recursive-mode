#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("install-recursive-mode.py")
SPEC = importlib.util.spec_from_file_location("install_recursive_mode", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load install module from {MODULE_PATH}")
install = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = install
SPEC.loader.exec_module(install)

ROUTER_LIB_PATH = Path(__file__).with_name("recursive_router_lib.py")
ROUTER_SPEC = importlib.util.spec_from_file_location("recursive_router_lib", ROUTER_LIB_PATH)
if ROUTER_SPEC is None or ROUTER_SPEC.loader is None:
    raise RuntimeError(f"Unable to load router module from {ROUTER_LIB_PATH}")
router_lib = importlib.util.module_from_spec(ROUTER_SPEC)
sys.modules[ROUTER_SPEC.name] = router_lib
ROUTER_SPEC.loader.exec_module(router_lib)


class InstallRecursiveModeTests(unittest.TestCase):
    def test_package_surface_includes_recursive_training(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        installable_skills = {path.parent.name for path in (repo_root / "skills").glob("*/SKILL.md")}

        self.assertEqual(
            {
                "recursive-debugging",
                "recursive-review-bundle",
                "recursive-router",
                "recursive-spec",
                "recursive-subagent",
                "recursive-tdd",
                "recursive-training",
                "recursive-worktree",
            },
            installable_skills,
        )
        root_skill = (repo_root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("skills/recursive-training/SKILL.md", root_skill)

    def test_bootstrap_workflow_copy_matches_canonical(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        canonical = (repo_root / ".recursive" / "RECURSIVE.md").read_text(encoding="utf-8")
        bootstrap = (repo_root / "references" / "bootstrap" / "RECURSIVE.md").read_text(encoding="utf-8")

        self.assertEqual(canonical, bootstrap)

    def test_resolve_canonical_workflow_path_prefers_repo_recursive_doc(self) -> None:
        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-workflow-") as temp_dir:
            skill_root = Path(temp_dir)
            bootstrap_path = skill_root / "references" / "bootstrap" / "RECURSIVE.md"
            repo_recursive_path = skill_root / ".recursive" / "RECURSIVE.md"
            bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
            repo_recursive_path.parent.mkdir(parents=True, exist_ok=True)
            bootstrap_path.write_text("bootstrap", encoding="utf-8")
            repo_recursive_path.write_text("repo-recursive", encoding="utf-8")

            resolved = install.resolve_canonical_workflow_path(skill_root)

            self.assertEqual(repo_recursive_path, resolved)

    def test_powershell_installer_prefers_repo_recursive_doc(self) -> None:
        ps1_script = MODULE_PATH.with_suffix(".ps1").read_text(encoding="utf-8")
        repo_index = ps1_script.index('(Join-Path (Join-Path $SkillRoot ".recursive") "RECURSIVE.md")')
        bootstrap_index = ps1_script.index(
            '(Join-Path (Join-Path $SkillRoot "references") "bootstrap\\RECURSIVE.md")'
        )

        self.assertLess(repo_index, bootstrap_index)

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

    def test_recursive_agents_router_avoids_missing_source_repo_paths(self) -> None:
        body = install.recursive_agents_router_body()

        self.assertIn("the installed `recursive-spec` skill", body)
        self.assertIn("the installed `recursive-training` skill", body)
        for forbidden in (
            "`/.recursive/README.md`",
            "`/skills/recursive-spec/SKILL.md`",
            "`/scripts/install-recursive-mode.py`",
            "`/references/artifact-template.md`",
            "`/skills/recursive-router/SKILL.md`",
            "`/skills/recursive-training/SKILL.md`",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, body)

    def test_plans_bridge_treats_benchmark_as_opt_in(self) -> None:
        body = install.plans_bridge_body()

        self.assertIn("separate optional `recursive-benchmark` add-on", body)
        self.assertIn("<recursive-benchmark-package-or-repo>", body)
        self.assertNotIn("should use the packaged benchmark fixture", body)
        self.assertEqual(1, body.count("If the user asks to route delegated work through another transport/model"))

    def test_gitattributes_excludes_benchmark_add_on_from_default_exports(self) -> None:
        gitattributes = Path(__file__).resolve().parent.parent / ".gitattributes"
        content = gitattributes.read_text(encoding="utf-8")

        self.assertIn("references/benchmark-addon export-ignore", content)
        self.assertIn("references/benchmarks export-ignore", content)
        self.assertIn("scripts/run-recursive-benchmark.py export-ignore", content)

    def test_benchmark_add_on_is_not_a_default_skill_entrypoint(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self.assertFalse((repo_root / "skills" / "recursive-benchmark" / "SKILL.md").exists())
        self.assertFalse((repo_root / "skills" / "recursive-benchmark" / "recursive-benchmark" / "SKILL.md").exists())
        self.assertTrue(
            (repo_root / "references" / "benchmark-addon" / "recursive-benchmark" / "BENCHMARK-ADDON.md").exists()
        )
        self.assertTrue(
            (
                repo_root
                / "references"
                / "benchmark-addon"
                / "recursive-benchmark"
                / "recursive-benchmark"
                / "BENCHMARK-ADDON.md"
            ).exists()
        )

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

    def test_root_docs_list_recursive_router_and_config_surface(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        readme = (repo_root / "README.md").read_text(encoding="utf-8")
        skill = (repo_root / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("recursive-router", readme)
        self.assertIn("/.recursive/config/recursive-router.json", readme)
        self.assertIn("recursive-router", skill)
        self.assertIn("/.recursive/config/recursive-router.json", skill)
        self.assertIn("recursive-training", readme)

    def test_root_readme_workflow_overview_uses_phase_zero_worktree_gate(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        readme = (repo_root / "README.md").read_text(encoding="utf-8")

        self.assertIn("Phase 0: requirements and worktree setup", readme)
        self.assertIn("Phase 1-2: AS-IS and plan", readme)
        self.assertNotIn("Phase 0-2: requirements, AS-IS, plan", readme)

    def test_templates_include_routing_metadata_for_routed_delegation(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        expectations = {
            Path("docs/templates/commands/recursive-review-bundle.md"): (
                "Routing Config Path",
                "Routing Discovery Path",
                "Routed CLI",
                "Routed Model",
            ),
            Path("docs/templates/commands/recursive-subagent-action.md"): (
                "Routing Config Path",
                "Routing Discovery Path",
                "Routed CLI",
                "Routed Model",
            ),
            Path("references/artifact-template.md"): (
                "Routing Config Path",
                "Routing Discovery Path",
                "Routed CLI",
                "Routed Model",
            ),
        }

        for relative_path, required_snippets in expectations.items():
            content = (repo_root / relative_path).read_text(encoding="utf-8")
            for snippet in required_snippets:
                with self.subTest(path=str(relative_path), snippet=snippet):
                    self.assertIn(snippet, content)

    def test_subskill_docs_use_repo_root_script_examples(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        expectations = {
            Path("skills/recursive-router/SKILL.md"): (
                "./scripts/recursive-router-init.py",
                "./scripts/recursive-router-invoke.py",
                "./.recursive/run/<run-id>/router-prompts/code-reviewer-bundle.md",
            ),
            Path("skills/recursive-review-bundle/SKILL.md"): (
                "./scripts/recursive-review-bundle.py",
                "./scripts/recursive-review-bundle.ps1",
            ),
        }
        forbidden = {
            Path("skills/recursive-router/SKILL.md"): (
                "<SKILL_DIR>/scripts/recursive-router-",
                "/" "tmp" "/code-reviewer-bundle.md",
            ),
            Path("skills/recursive-review-bundle/SKILL.md"): ("../../scripts/recursive-review-bundle",),
        }

        for relative_path, required_snippets in expectations.items():
            content = (repo_root / relative_path).read_text(encoding="utf-8")
            for snippet in required_snippets:
                with self.subTest(path=str(relative_path), snippet=snippet):
                    self.assertIn(snippet, content)
            for snippet in forbidden[relative_path]:
                with self.subTest(path=str(relative_path), forbidden=snippet):
                    self.assertNotIn(snippet, content)

    def test_mirrored_benchmark_add_on_source_doc_matches_primary_copy(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        primary = (
            repo_root / "references" / "benchmark-addon" / "recursive-benchmark" / "BENCHMARK-ADDON.md"
        ).read_text(encoding="utf-8")
        mirror = (
            repo_root
            / "references"
            / "benchmark-addon"
            / "recursive-benchmark"
            / "recursive-benchmark"
            / "BENCHMARK-ADDON.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(primary, mirror)

    def test_agents_block_uses_helper_names_not_missing_root_script_paths(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        content = (repo_root / "references" / "agents-block.md").read_text(encoding="utf-8")

        self.assertIn("Invoke these helper names", content)
        self.assertIn("`install-recursive-mode`", content)
        self.assertNotIn("`scripts/install-recursive-mode.py`", content)
        self.assertNotIn("`scripts/recursive-status.py`", content)

    def test_training_and_router_skill_manifests_exist(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self.assertTrue((repo_root / "skills" / "recursive-training" / "agents" / "openai.yaml").exists())
        self.assertTrue((repo_root / "skills" / "recursive-router" / "agents" / "openai.yaml").exists())

    def test_recursive_training_skill_is_split_into_reference_docs(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        skill_path = repo_root / "skills" / "recursive-training" / "SKILL.md"
        line_count = len(skill_path.read_text(encoding="utf-8").splitlines())

        self.assertLess(line_count, 500)
        self.assertTrue((repo_root / "skills" / "recursive-training" / "references" / "memory-architecture.md").exists())
        self.assertTrue((repo_root / "skills" / "recursive-training" / "references" / "phase8-and-loading.md").exists())

    def test_subagent_skill_references_repo_root_paths(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        content = (repo_root / "skills" / "recursive-subagent" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("/references/artifact-template.md", content)
        self.assertIn("/skills/recursive-subagent/agents/code-reviewer.md", content)
        self.assertIn("/skills/recursive-subagent/agents/implementer.md", content)
        self.assertNotIn("`references/artifact-template.md`", content)
        self.assertNotIn("`agents/code-reviewer.md`", content)
        self.assertNotIn("`agents/implementer.md`", content)

    def test_phase_oriented_skills_reflect_current_artifact_contract(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        expectations = {
            Path("skills/recursive-spec/SKILL.md"): ("## TODO", "Workflow version: `recursive-mode-audit-v2`"),
            Path("skills/recursive-worktree/SKILL.md"): ("## TODO", "Normalized diff command"),
            Path("skills/recursive-debugging/SKILL.md"): (
                "Subagent Capability Probe",
                "Delegation Decision Basis",
                "## Requirement Completion Status",
            ),
            Path("skills/recursive-tdd/SKILL.md"): (
                "## TODO",
                "Subagent Capability Probe",
                "Delegation Decision Basis",
                "## Requirement Completion Status",
            ),
        }

        for relative_path, required_snippets in expectations.items():
            content = (repo_root / relative_path).read_text(encoding="utf-8")
            for snippet in required_snippets:
                with self.subTest(path=str(relative_path), snippet=snippet):
                    self.assertIn(snippet, content)

        debugging = (repo_root / "skills" / "recursive-debugging" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("Return to Phase 2", debugging)

    def test_installer_gitignores_device_local_router_discovery_inventory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            completed = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--repo-root", str(repo_root)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"installer failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            self.assertTrue((repo_root / ".recursive" / "config" / "recursive-router.json").exists())
            self.assertFalse((repo_root / ".recursive" / "config" / "recursive-router-discovered.json").exists())
            gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("/.recursive/config/recursive-router-discovered.json", gitignore)

    def test_installer_bootstraps_training_memory_and_scripts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-training-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            completed = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--repo-root", str(repo_root)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"installer failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            self.assertTrue((repo_root / ".recursive" / "memory" / "training" / ".gitkeep").exists())
            self.assertTrue((repo_root / ".recursive" / "scripts" / "recursive-training-loader.py").exists())
            self.assertTrue((repo_root / ".recursive" / "scripts" / "recursive-training-sync.py").exists())
            self.assertTrue((repo_root / ".recursive" / "scripts" / "recursive-training-extract.py").exists())
            self.assertIn(
                "RECURSIVE-MODE-MEMORY-POINTERS:START",
                (repo_root / ".cursorrules").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "recursive-mode memory pointers",
                (repo_root / "CLAUDE.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "recursive-mode memory pointers",
                (repo_root / ".github" / "copilot-instructions.md").read_text(encoding="utf-8"),
            )

    def test_installer_upserts_assistant_memory_pointers_without_removing_existing_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-pointers-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            github_root = repo_root / ".github"
            github_root.mkdir(parents=True, exist_ok=True)
            (repo_root / ".cursorrules").write_text("# Custom cursor notes\n", encoding="utf-8", newline="\n")
            (repo_root / "CLAUDE.md").write_text("# Team Claude notes\n", encoding="utf-8", newline="\n")
            (github_root / "copilot-instructions.md").write_text(
                "# Team Copilot notes\n",
                encoding="utf-8",
                newline="\n",
            )

            completed = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--repo-root", str(repo_root)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"installer failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            self.assertIn("Custom cursor notes", (repo_root / ".cursorrules").read_text(encoding="utf-8"))
            self.assertIn("Team Claude notes", (repo_root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn(
                "Team Copilot notes",
                (github_root / "copilot-instructions.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "RECURSIVE-MODE-MEMORY-POINTERS:START",
                (repo_root / ".cursorrules").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "RECURSIVE-MODE-MEMORY-POINTERS:START",
                (repo_root / "CLAUDE.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "RECURSIVE-MODE-MEMORY-POINTERS:START",
                (github_root / "copilot-instructions.md").read_text(encoding="utf-8"),
            )

    def test_installer_upserts_root_agents_without_removing_existing_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-agents-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            agents_path = repo_root / "AGENTS.md"
            agents_path.write_text("# Team Notes\n\nKeep this custom content.\n", encoding="utf-8", newline="\n")

            completed = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--repo-root", str(repo_root)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"installer failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            updated = agents_path.read_text(encoding="utf-8")
            self.assertIn("Keep this custom content.", updated)
            self.assertIn("<!-- RECURSIVE-MODE-AGENTS:START -->", updated)

    def test_powershell_installer_migrates_legacy_router_policy(self) -> None:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            self.skipTest("PowerShell is required for installer parity tests")

        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-ps1-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            config_root = repo_root / ".recursive" / "config"
            config_root.mkdir(parents=True, exist_ok=True)
            legacy_policy_path = config_root / "recursive-router-cli.json"
            legacy_discovery_path = config_root / "recursive-router-cli-discovered.json"
            policy = router_lib.default_router_policy()
            role_routes = policy["role_routes"]
            assert isinstance(role_routes, dict)
            code_reviewer = role_routes["code-reviewer"]
            assert isinstance(code_reviewer, dict)
            code_reviewer["cli"] = "codex"
            code_reviewer["model"] = "gpt-5.4-mini"
            cli_overrides = policy["cli_overrides"]
            assert isinstance(cli_overrides, dict)
            cli_overrides["codex"] = {"command": "codex-router.exe"}
            legacy_policy_path.write_text(router_lib.pretty_json(policy), encoding="utf-8", newline="\n")
            legacy_discovery_path.write_text(
                router_lib.pretty_json(
                    router_lib.empty_discovery_inventory(
                        probe_tool="recursive-router-probe",
                        probe_status="complete",
                        clis=[{"id": "codex", "resolved_path": "C:/tools/codex-router.exe", "models": ["gpt-5.4-mini"]}],
                    )
                ),
                encoding="utf-8",
                newline="\n",
            )

            completed = subprocess.run(
                [powershell, "-NoProfile", "-File", str(MODULE_PATH.with_suffix(".ps1")), "-RepoRoot", str(repo_root)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"PowerShell installer failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            canonical_policy = json.loads((config_root / "recursive-router.json").read_text(encoding="utf-8"))
            self.assertEqual(canonical_policy["role_routes"]["code-reviewer"]["cli"], "codex")
            self.assertEqual(canonical_policy["role_routes"]["code-reviewer"]["model"], "gpt-5.4-mini")
            self.assertEqual(canonical_policy["cli_overrides"]["codex"]["command"], "codex-router.exe")
            self.assertFalse(legacy_policy_path.exists())
            self.assertFalse(legacy_discovery_path.exists())
            self.assertTrue((config_root / "recursive-router-discovered.json").exists())

    def test_powershell_installer_bootstraps_canonical_router_policy_defaults(self) -> None:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            self.skipTest("PowerShell is required for installer parity tests")

        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-ps1-defaults-") as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            completed = subprocess.run(
                [powershell, "-NoProfile", "-File", str(MODULE_PATH.with_suffix(".ps1")), "-RepoRoot", str(repo_root)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"PowerShell installer failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            canonical_policy = json.loads((repo_root / ".recursive" / "config" / "recursive-router.json").read_text(encoding="utf-8"))
            self.assertEqual(router_lib.default_router_policy(), canonical_policy)

    def test_powershell_installer_source_includes_training_scaffold(self) -> None:
        ps1_script = MODULE_PATH.with_suffix(".ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $memoryRoot "training"', ps1_script)
        self.assertIn("recursive-training-loader.py", ps1_script)
        self.assertIn("recursive-training-extract.py", ps1_script)
        self.assertIn('Join-Path $recursiveRoot "scripts"', ps1_script)

    def test_skills_cli_local_install_and_bootstrap_include_training_scaffold(self) -> None:
        if os.environ.get("RUN_SKILLS_CLI_INTEGRATION") != "1":
            self.skipTest("Set RUN_SKILLS_CLI_INTEGRATION=1 to enable local Skills CLI integration coverage")

        npx = shutil.which("npx")
        if npx is None:
            self.skipTest("npx is required for Skills CLI integration coverage")

        repo_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory(prefix="install-recursive-mode-skills-cli-") as temp_dir:
            workspace = Path(temp_dir)
            try:
                install_completed = subprocess.run(
                    [
                        npx,
                        "skills",
                        "add",
                        str(repo_root),
                        "--skill",
                        "*",
                        "--full-depth",
                    ],
                    cwd=workspace,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=180,
                )
            except subprocess.TimeoutExpired as exc:
                self.skipTest(f"Skills CLI integration timed out: {exc}")
            combined_output = f"{install_completed.stdout}\n{install_completed.stderr}"
            if "ENOSPC" in combined_output or "no space left on device" in combined_output.lower():
                self.skipTest("Insufficient disk space for Skills CLI integration coverage")

            self.assertEqual(
                install_completed.returncode,
                0,
                f"skills add failed\nSTDOUT:\n{install_completed.stdout}\nSTDERR:\n{install_completed.stderr}",
            )

            installed_root_skill = workspace / ".agents" / "skills" / "recursive-mode"
            self.assertTrue(
                installed_root_skill.exists(),
                f"installed root skill missing\nSTDOUT:\n{install_completed.stdout}\nSTDERR:\n{install_completed.stderr}",
            )
            self.assertTrue((installed_root_skill / "skills" / "recursive-training" / "SKILL.md").exists())
            self.assertTrue((workspace / ".agents" / "skills" / "recursive-training" / "SKILL.md").exists())

            bootstrap_completed = subprocess.run(
                [
                    sys.executable,
                    str(installed_root_skill / "scripts" / "install-recursive-mode.py"),
                    "--repo-root",
                    str(workspace),
                ],
                cwd=workspace,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                bootstrap_completed.returncode,
                0,
                f"installed bootstrap failed\nSTDOUT:\n{bootstrap_completed.stdout}\nSTDERR:\n{bootstrap_completed.stderr}",
            )

            self.assertTrue((workspace / ".recursive" / "memory" / "training" / ".gitkeep").exists())
            self.assertTrue((workspace / ".recursive" / "scripts" / "recursive-training-loader.py").exists())
            self.assertTrue((workspace / ".recursive" / "scripts" / "recursive-training-sync.py").exists())
            self.assertTrue((workspace / ".recursive" / "scripts" / "recursive-training-extract.py").exists())
            self.assertTrue((workspace / ".cursorrules").exists())
            self.assertTrue((workspace / "CLAUDE.md").exists())
            self.assertTrue((workspace / ".github" / "copilot-instructions.md").exists())

            installed_recursive = (workspace / ".recursive" / "RECURSIVE.md").read_text(encoding="utf-8")
            self.assertIn("/.recursive/memory/training/", installed_recursive)
            self.assertIn("recursive-training-loader.py", installed_recursive)

    def test_repo_root_router_policy_is_not_personalized(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        policy_path = repo_root / ".recursive" / "config" / "recursive-router.json"
        self.assertTrue(policy_path.exists())
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(router_lib.default_router_policy(), policy)

    def test_repo_root_router_discovery_inventory_is_not_bootstrapped(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        discovery_path = repo_root / ".recursive" / "config" / "recursive-router-discovered.json"
        self.assertFalse(discovery_path.exists())

    def test_root_lockfile_requires_root_package_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        if (repo_root / "package-lock.json").exists():
            self.assertTrue((repo_root / "package.json").exists())


if __name__ == "__main__":
    unittest.main()
