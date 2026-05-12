#!/usr/bin/env python3
"""
Read-only startup guidance for recursive-mode experiential memory.

Reads ReasoningBank-structured memory from .recursive/memory/domains/
and .recursive/memory/training/, then prints what an agent should read or load
at the start of a run.

Usage:
    python recursive-training-sync.py --repo-root .
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List


class ReasoningBankReader:
    """Reads ReasoningBank-structured memory from the memory plane."""

    MEMORY_ROOT = ".recursive/memory"
    DOMAINS_DIR = ".recursive/memory/domains"
    TRAINING_DIR = ".recursive/memory/training"

    def __init__(self, repo_root: str):
        self.root = Path(repo_root)
        self.memory_root = self.root / self.MEMORY_ROOT
        self.domains_dir = self.root / self.DOMAINS_DIR
        self.training_dir = self.root / self.TRAINING_DIR

    def _parse_items_from_file(self, filepath: Path) -> List[dict]:
        """Parse ReasoningBank items from a memory markdown file."""
        if not filepath.exists():
            return []
        content = filepath.read_text(encoding="utf-8")
        if "Status: CURRENT" not in content:
            return []

        items = []
        # Match ReasoningBank item blocks
        pattern = re.compile(
            r'### (RB-\d+):\s*(.+?)\n\n'
            r'\*\*Description:\*\*\s*(.+?)\n\n'
            r'\*\*Content:\*\*\s*(.+?)(?=\n\n```|\n### |\Z)',
            re.DOTALL
        )
        for m in pattern.finditer(content):
            items.append({
                "rb_id": m.group(1),
                "title": m.group(2).strip(),
                "description": m.group(3).strip(),
                "content": m.group(4).strip(),
            })

        # Also parse YAML schema blocks for metadata
        schema_pattern = re.compile(
            r'```yaml\n'
            r'rb_id: "(RB-\d+)"\n'
            r'title: "([^"]+)"\n'
            r'description: "([^"]+)"\n'
            r'task_type: "([^"]*)"\n'
            r'subsystem: "([^"]*)"\n'
            r'source_runs: (.+?)\n'
            r'applies_to: (.+?)\n'
            r'success_rate: ([\d.]+)\n'
            r'status: (\w+)\n'
            r'created_at: "([^"]+)"\n'
            r'```',
            re.DOTALL
        )
        for m in schema_pattern.finditer(content):
            rb_id = m.group(1)
            for item in items:
                if item["rb_id"] == rb_id:
                    item["task_type"] = m.group(4)
                    item["subsystem"] = m.group(5)
                    item["success_rate"] = float(m.group(8))
                    item["status"] = m.group(9)
                    item["created_at"] = m.group(10)
                    break

        return items

    def load_all_items(self) -> List[dict]:
        """Load all ReasoningBank items from domain + training memory."""
        items = []
        for d in (self.domains_dir, self.training_dir):
            if not d.exists():
                continue
            for f in sorted(d.glob("*.md")):
                items.extend(self._parse_items_from_file(f))
        return items

    def list_training_docs(self) -> Dict[str, dict]:
        """List all training memory docs with metadata."""
        docs = {}
        for d in (self.domains_dir, self.training_dir):
            if not d.exists():
                continue
            for f in sorted(d.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                if "Status: CURRENT" not in content:
                    continue
                # Count items
                item_count = len(re.findall(r'### RB-\d+:', content))
                # Extract scope from frontmatter if present
                scope_match = re.search(r'Scope:\s*(.+)', content)
                scope = scope_match.group(1).strip() if scope_match else f.name.replace('.md', '')
                docs[f.name] = {
                    "path": str(f.relative_to(self.memory_root)).replace('\\', '/'),
                    "type": "domain" if "domains" in str(f) else "training",
                    "scope": scope,
                    "items": item_count,
                }
        return docs


class ExperienceSync:
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.rb_reader = ReasoningBankReader(repo_root)

    def build_startup_guidance(self) -> str:
        """Render non-mutating startup guidance for agents."""
        docs = self.rb_reader.list_training_docs()
        lines = ["## Recursive Training Startup Guidance\n"]
        lines.append(
            "At the start of a run, read `/.recursive/memory/MEMORY.md` first.\n"
        )
        lines.append(
            "If the task may benefit from prior experiential memory, run the loader with the current task context:\n\n"
            "```bash\n"
            "python .recursive/scripts/recursive-training-loader.py --repo-root . \\\n"
            "  --query \"your task description\" \\\n"
            "  --files \"path/to/file1.ts,path/to/file2.ts\"\n"
            "```\n"
        )
        lines.append("The loader resolves relevant memory docs from the memory plane and returns the most applicable learnings.\n")

        if not docs:
            lines.append("No current domain or training memory docs were found under `/.recursive/memory/`.\n")
            return "\n".join(lines)

        # Group by type
        domains = {k: v for k, v in docs.items() if v["type"] == "domain"}
        training = {k: v for k, v in docs.items() if v["type"] == "training"}

        if domains:
            lines.append("### Domain Memory (subsystem-specific)\n")
            lines.append("| Doc | Scope | Items | Description |")
            lines.append("|-----|-------|-------|-------------|")
            for name, info in sorted(domains.items()):
                lines.append(f"| `{info['path']}` | {info['scope']} | {info['items']} items | subsystem-specific learnings |")
            lines.append("")

        if training:
            lines.append("### Training Memory (task-type patterns)\n")
            lines.append("| Doc | Scope | Items | Description |")
            lines.append("|-----|-------|-------|-------------|")
            for name, info in sorted(training.items()):
                lines.append(f"| `{info['path']}` | {info['scope']} | {info['items']} items | cross-subsystem task patterns |")
            lines.append("")

        lines.append("---\n")
        lines.append("This output is advisory only. The canonical memory remains under `/.recursive/memory/`.\n")
        return "\n".join(lines)

    def sync_all(self):
        print(self.build_startup_guidance().strip())

def main():
    parser = argparse.ArgumentParser(description="Print startup guidance for recursive-mode experiential memory")
    parser.add_argument("--repo-root", type=str, required=True, help="Path to git repository root")
    args = parser.parse_args()

    sync = ExperienceSync(args.repo_root)
    print("Training sync is read-only. Startup guidance:")
    sync.sync_all()


if __name__ == "__main__":
    main()
