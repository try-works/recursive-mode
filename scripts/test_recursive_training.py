#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(module_name: str, filename: str):
    module_path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


training_sync = load_module("recursive_training_sync", "recursive-training-sync.py")
training_loader = load_module("recursive_training_loader", "recursive-training-loader.py")
training_grpo = load_module("recursive_training_grpo", "recursive-training-grpo.py")
recursive_init = load_module("recursive_init", "recursive-init.py")
recursive_closeout = load_module("recursive_closeout", "recursive-closeout.py")


MEMORY_ROUTER = """# MEMORY.md

<!-- RECURSIVE-MODE-MEMORY:START -->
## Memory Router

Use this file as the memory index.
<!-- RECURSIVE-MODE-MEMORY:END -->
"""


TRAINING_DOC = """Type: training
Status: CURRENT
Scope: commit-workflow
Owns-Paths:
Watch-Paths:
- git workflow
Source-Runs: run-a, run-b
Validated-At-Commit:
Last-Validated: 2026-05-12T00:00:00Z
Tags: training, reasoningbank

# Training Memory: commit-workflow

## Extracted Reasoning Items (2026-05-12T00:00:00Z)

### RB-0: Branch before commit

**Description:** Create a feature branch first

**Content:** Create a branch before remediation work and verify before commit.

```yaml
rb_id: "RB-0"
title: "Branch before commit"
description: "Create a feature branch first"
task_type: "commit-workflow"
subsystem: "git-workflow"
source_runs: ["run-a", "run-b"]
applies_to: ["git workflow", ".worktrees/"]
success_rate: 1.00
status: active
created_at: "2026-05-12T00:00:00Z"
```
"""

STALE_TRAINING_DOC = """Type: training
Status: STALE
Scope: stale-workflow
Owns-Paths:
Watch-Paths:
- stale workflow
Source-Runs: run-z
Validated-At-Commit:
Last-Validated: 2026-05-12T00:00:00Z
Tags: training, reasoningbank

# Training Memory: stale-workflow

## Extracted Reasoning Items (2026-05-12T00:00:00Z)

### RB-0: Ignore this stale doc

**Description:** This should not load by default

**Content:** Stale docs should be excluded from default retrieval.

```yaml
rb_id: "RB-0"
title: "Ignore this stale doc"
description: "This should not load by default"
task_type: "stale-workflow"
subsystem: "legacy"
source_runs: ["run-z"]
applies_to: ["legacy workflow"]
success_rate: 0.10
status: active
created_at: "2026-05-12T00:00:00Z"
```
"""


class RecursiveTrainingTests(unittest.TestCase):
    def create_repo(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory(prefix="recursive-training-")
        self.addCleanup(temp_dir.cleanup)
        repo_root = Path(temp_dir.name) / "repo"
        (repo_root / ".recursive" / "memory" / "training").mkdir(parents=True, exist_ok=True)
        (repo_root / ".recursive" / "memory" / "domains").mkdir(parents=True, exist_ok=True)
        (repo_root / ".github").mkdir(parents=True, exist_ok=True)
        (repo_root / ".recursive" / "memory" / "MEMORY.md").write_text(
            MEMORY_ROUTER,
            encoding="utf-8",
            newline="\n",
        )
        (repo_root / ".recursive" / "memory" / "training" / "commit-workflow.md").write_text(
            TRAINING_DOC,
            encoding="utf-8",
            newline="\n",
        )
        (repo_root / "AGENTS.md").write_text(
            "# Existing AGENTS\n\nKeep this content.\n",
            encoding="utf-8",
            newline="\n",
        )
        (repo_root / ".cursorrules").write_text(
            "# Existing Cursor rules\n",
            encoding="utf-8",
            newline="\n",
        )
        (repo_root / "CLAUDE.md").write_text(
            "# Existing Claude notes\n",
            encoding="utf-8",
            newline="\n",
        )
        (repo_root / ".github" / "copilot-instructions.md").write_text(
            "# Existing Copilot notes\n",
            encoding="utf-8",
            newline="\n",
        )
        return repo_root

    def test_sync_prints_startup_guidance_without_touching_memory_or_pointer_files(self) -> None:
        repo_root = self.create_repo()
        original_agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
        original_cursorrules = (repo_root / ".cursorrules").read_text(encoding="utf-8")
        original_claude = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
        original_copilot = (repo_root / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        original_memory_md = (repo_root / ".recursive" / "memory" / "MEMORY.md").read_text(encoding="utf-8")

        sync = training_sync.ExperienceSync(str(repo_root))
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            sync.sync_all()

        updated_agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
        memory_md = (repo_root / ".recursive" / "memory" / "MEMORY.md").read_text(encoding="utf-8")

        self.assertEqual(original_agents, updated_agents)
        self.assertEqual(original_cursorrules, (repo_root / ".cursorrules").read_text(encoding="utf-8"))
        self.assertEqual(original_claude, (repo_root / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertEqual(
            original_copilot,
            (repo_root / ".github" / "copilot-instructions.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(original_memory_md, memory_md)
        self.assertIn("read `/.recursive/memory/memory.md` first", stdout.getvalue().lower())
        self.assertIn("training/commit-workflow.md", stdout.getvalue())
        self.assertFalse((repo_root / ".recursive" / "memory" / "TRAINING-REGISTRY.md").exists())
        self.assertFalse((repo_root / "README-EXPERIENCES.md").exists())

    def test_loader_discovers_training_docs_from_filesystem(self) -> None:
        repo_root = self.create_repo()

        registry = training_loader.MemoryRegistry(str(repo_root))
        docs = registry.discover()

        self.assertTrue(any(doc.rel_path == "training/commit-workflow.md" for doc in docs))
        self.assertTrue(any(doc.doc_type == "training" for doc in docs))

    def test_loader_excludes_stale_docs_from_default_discovery(self) -> None:
        repo_root = self.create_repo()
        (repo_root / ".recursive" / "memory" / "training" / "stale-workflow.md").write_text(
            STALE_TRAINING_DOC,
            encoding="utf-8",
            newline="\n",
        )

        registry = training_loader.MemoryRegistry(str(repo_root))
        docs = registry.discover()

        self.assertFalse(any(doc.rel_path == "training/stale-workflow.md" for doc in docs))

    def test_loader_dry_run_returns_preview(self) -> None:
        repo_root = self.create_repo()
        sync = training_sync.ExperienceSync(str(repo_root))
        sync.sync_all()

        loader = training_loader.MemoryLoader(str(repo_root))
        output = loader.load(query="commit workflow", dry_run=True)

        self.assertIn("DRY RUN: Memory Loader Preview", output)
        self.assertIn("training/commit-workflow.md", output)

    def test_recursive_init_runs_training_loader_when_installed(self) -> None:
        repo_root = self.create_repo()
        scripts_dir = repo_root / ".recursive" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        capture_path = repo_root / "loader-args.txt"
        (scripts_dir / "recursive-training-loader.py").write_text(
            "\n".join(
                [
                    "import pathlib",
                    "import sys",
                    f"pathlib.Path(r\"{capture_path}\").write_text(' '.join(sys.argv[1:]), encoding='utf-8')",
                    "print('loader ran')",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

        result = recursive_init.run_training_loader(repo_root, "phase-1_commit-fix", "bugfix", "#123")

        self.assertEqual(result, 0)
        captured = capture_path.read_text(encoding="utf-8")
        self.assertIn("--repo-root", captured)
        self.assertIn("--query", captured)
        self.assertIn("bugfix recursive run phase 1 commit fix #123", captured)

    def test_recursive_init_continues_when_training_loader_fails(self) -> None:
        repo_root = self.create_repo()
        scripts_dir = repo_root / ".recursive" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "recursive-training-loader.py").write_text(
            "import sys\nprint('loader failed intentionally')\nsys.exit(2)\n",
            encoding="utf-8",
            newline="\n",
        )

        result = recursive_init.run_training_loader(repo_root, "phase-1_commit-fix", "bugfix", "#123")

        self.assertEqual(result, 0)

    def test_recursive_closeout_runs_phase8_trigger_when_installed(self) -> None:
        repo_root = self.create_repo()
        scripts_dir = repo_root / ".recursive" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        capture_path = repo_root / "trigger-args.txt"
        (scripts_dir / "recursive-training-phase8-trigger.py").write_text(
            "\n".join(
                [
                    "import pathlib",
                    "import sys",
                    f"pathlib.Path(r\"{capture_path}\").write_text(' '.join(sys.argv[1:]), encoding='utf-8')",
                    "print('trigger ran')",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

        result = recursive_closeout.run_phase8_training_trigger(repo_root, "run-123")

        self.assertEqual(result, 0)
        captured = capture_path.read_text(encoding="utf-8")
        self.assertIn("--repo-root", captured)
        self.assertIn("--run-id run-123", captured)
        self.assertIn("--auto", captured)

    def test_training_extract_script_skips_cleanly_by_default(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "recursive-training-extract.py"),
                "--repo-root",
                str(SCRIPT_DIR.parent),
                "--prompt-file",
                str(SCRIPT_DIR / "recursive-training-extract.py"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Training extractor is not available", completed.stderr)

    def test_training_grpo_uses_generic_extractor_contract(self) -> None:
        source = (SCRIPT_DIR / "recursive-training-grpo.py").read_text(encoding="utf-8")
        skill_doc = (SCRIPT_DIR.parent / "skills" / "recursive-training" / "SKILL.md").read_text(encoding="utf-8")

        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("OPENAI_BASE_URL", source)
        self.assertNotIn("AsyncOpenAI", source)
        self.assertNotIn("OPENAI_API_KEY", skill_doc)
        self.assertNotIn("OPENAI_BASE_URL", skill_doc)
        self.assertNotIn("API key", skill_doc)
        self.assertNotIn("extraction runtime", source)

    def test_training_memory_writer_includes_subsystem_schema_field(self) -> None:
        repo_root = self.create_repo()
        rb_memory = training_grpo.ReasoningBankMemory(repo_root)

        rb_memory.write_training_memory(
            "commit-workflow",
            "git-workflow",
            [{
                "title": "Branch before commit",
                "description": "Create a feature branch first",
                "content": "Create a branch before remediation work and verify before commit.",
                "applies_to": ["git workflow", ".worktrees/"],
            }],
            ["run-a", "run-b"],
            ["run-a", "run-b"],
        )

        content = (repo_root / ".recursive" / "memory" / "training" / "commit-workflow.md").read_text(encoding="utf-8")
        self.assertIn('subsystem: "git-workflow"', content)


if __name__ == "__main__":
    unittest.main()
