#!/usr/bin/env python3
"""
Progressive memory loader for recursive-mode experiential knowledge.

Reads the memory router plus the repository memory plane, scores memory docs by
relevance to the current task, reads the most relevant docs, scores individual
items, and returns formatted context for the agent.

This script lives at `.recursive/scripts/recursive-training-loader.py` in the
target repository. It is copied there during recursive-mode installation.

This is the canonical way to load repo-specific experiential knowledge.
Run it directly when a task may benefit from repo-specific experiential memory.

Usage:
    # From repo root
    python .recursive/scripts/recursive-training-loader.py --repo-root . \
        --query "implementing frontend feature with react" \
        --files "apps/web/src/App.tsx,apps/web/src/stores/ui-store.ts"

    # Load all memories for a subsystem
    python .recursive/scripts/recursive-training-loader.py --repo-root . \
        --subsystem "web" --max-docs 5

    # Load specific task-type memories
    python .recursive/scripts/recursive-training-loader.py --repo-root . \
        --task-type "commit-workflow" --max-items 20

    # Dry run: show what would be loaded without returning content
    python .recursive/scripts/recursive-training-loader.py --repo-root . \
        --query "frontend rebuild" --dry-run

Progressive disclosure levels:
    Level 1: MEMORY.md (lightweight registry)
    Level 2: This loader + filesystem discovery (selective doc loading based on task context)
    Level 3: Agent applies specific items from loaded docs
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Memory doc discovery
# ---------------------------------------------------------------------------

class MemoryDoc:
    """Represents a single memory document (domain or training)."""

    def __init__(self, rel_path: str, doc_type: str, scope: str, item_count: int,
                 description: str = "", full_path: Optional[Path] = None):
        self.rel_path = rel_path
        self.doc_type = doc_type  # "domain" or "training"
        self.scope = scope
        self.item_count = item_count
        self.description = description
        self.full_path = full_path
        self._items: Optional[List[dict]] = None

    @property
    def items(self) -> List[dict]:
        """Lazy-load items from disk."""
        if self._items is None and self.full_path:
            self._items = self._parse_items()
        return self._items or []

    def _parse_items(self) -> List[dict]:
        """Parse ReasoningBank items from the markdown file."""
        if not self.full_path or not self.full_path.exists():
            return []
        content = self.full_path.read_text(encoding="utf-8")

        items = []
        # Match item blocks: ### RB-N: Title
        item_pattern = re.compile(
            r'### (RB-\d+):\s*(.+?)\n\n'
            r'\*\*Description:\*\*\s*(.+?)\n\n'
            r'\*\*Content:\*\*\s*(.+?)(?=\n\n```|\n### |\Z)',
            re.DOTALL
        )

        # Also parse schema metadata
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

        # Build a map of schema metadata by rb_id
        schema_by_id: Dict[str, dict] = {}
        for m in schema_pattern.finditer(content):
            rb_id = m.group(1)
            schema_by_id[rb_id] = {
                "task_type": m.group(4),
                "subsystem": m.group(5),
                "success_rate": float(m.group(8)),
                "status": m.group(9),
                "source_runs": _parse_json_array(m.group(6)),
                "applies_to": _parse_json_array(m.group(7)),
            }

        for m in item_pattern.finditer(content):
            rb_id = m.group(1)
            item = {
                "rb_id": rb_id,
                "title": m.group(2).strip(),
                "description": m.group(3).strip(),
                "content": m.group(4).strip(),
            }
            # Merge schema metadata if available
            if rb_id in schema_by_id:
                item.update(schema_by_id[rb_id])
            else:
                item.update({
                    "task_type": "",
                    "subsystem": self.scope,
                    "success_rate": 0.0,
                    "status": "active",
                    "source_runs": [],
                    "applies_to": [],
                })

            if item.get("status") != "deprecated":
                items.append(item)

        return items


def _parse_json_array(text: str) -> List[str]:
    """Parse a JSON array string like ['a', 'b'] or ["a", "b"]."""
    text = text.strip()
    if not text or text == "[]":
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: parse comma-separated list
        items = re.findall(r'["\']([^"\']+)["\']', text)
        return items if items else []


# ---------------------------------------------------------------------------
# Registry discovery
# ---------------------------------------------------------------------------

class MemoryRegistry:
    """Discovers memory docs from the filesystem."""

    DOMAINS_DIR = ".recursive/memory/domains"
    TRAINING_DIR = ".recursive/memory/training"

    def __init__(self, repo_root: str):
        self.root = Path(repo_root).resolve()
        self.docs: List[MemoryDoc] = []

    def discover(self) -> List[MemoryDoc]:
        """Discover all memory docs from the filesystem."""
        self.docs = sorted(self._scan_filesystem().values(), key=lambda d: (d.doc_type, d.scope))
        return self.docs

    def _scan_filesystem(self) -> Dict[str, MemoryDoc]:
        """Scan .recursive/memory/ and exclude stale/deprecated docs by default."""
        docs: Dict[str, MemoryDoc] = {}

        for base_dir, doc_type in (
            (self.root / self.DOMAINS_DIR, "domain"),
            (self.root / self.TRAINING_DIR, "training"),
        ):
            if not base_dir.exists():
                continue
            for f in sorted(base_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                if "Status: STALE" in content or "Status: DEPRECATED" in content:
                    continue
                rel_path = str(f.relative_to(self.root / ".recursive/memory")).replace("\\", "/")
                if rel_path in docs:
                    continue  # Already discovered from registry
                item_count = len(re.findall(r'### RB-\d+:', content))
                docs[rel_path] = MemoryDoc(
                    rel_path=rel_path,
                    doc_type=doc_type,
                    scope=f.stem,
                    item_count=item_count,
                    full_path=f,
                )

        return docs

    def get_doc_by_scope(self, scope: str) -> Optional[MemoryDoc]:
        """Find a doc by its scope name (exact match)."""
        for doc in self.docs:
            if doc.scope.lower() == scope.lower():
                return doc
        return None


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

class RelevanceScorer:
    """Scores memory docs and items by relevance to the current task."""

    def __init__(self, query: str, file_paths: List[str], subsystem: str = "",
                 task_type: str = ""):
        self.query = query.lower()
        self.query_parts = [p for p in re.split(r'[^a-zA-Z0-9]', self.query) if len(p) > 2]
        self.file_paths = [p.lower() for p in file_paths]
        self.subsystem = subsystem.lower()
        self.task_type = task_type.lower()

    def score_doc(self, doc: MemoryDoc) -> float:
        """Score a memory doc by relevance (0-100)."""
        score = 0.0
        scope_lower = doc.scope.lower()

        # Direct subsystem match (strong signal)
        if self.subsystem and self.subsystem in scope_lower:
            score += 30
        if self.subsystem and scope_lower in self.subsystem:
            score += 25

        # Direct task_type match for training docs
        if self.task_type and doc.doc_type == "training":
            if self.task_type in scope_lower:
                score += 25
            if scope_lower in self.task_type:
                score += 20

        # Query keyword overlap with scope
        for part in self.query_parts:
            if part in scope_lower:
                score += 8

        # File path overlap with doc scope (for domain docs)
        if doc.doc_type == "domain":
            for fp in self.file_paths:
                parts = fp.split("/")
                for part in parts:
                    if len(part) > 2 and part in scope_lower:
                        score += 10
                        break

        # Query keyword overlap with doc description
        desc_lower = doc.description.lower()
        for part in self.query_parts:
            if part in desc_lower:
                score += 5

        # Prefer docs with more items (more signal)
        score += min(doc.item_count * 0.5, 5)

        return score

    def score_item(self, item: dict) -> float:
        """Score an individual memory item by relevance (0-100)."""
        score = 0.0
        title = item.get("title", "").lower()
        desc = item.get("description", "").lower()
        content = item.get("content", "").lower()
        applies_to = [a.lower() for a in item.get("applies_to", [])]
        item_task = item.get("task_type", "").lower()
        item_subsystem = item.get("subsystem", "").lower()
        success_rate = item.get("success_rate", 0.0)

        all_text = f"{title} {desc} {content}"

        # Direct task_type match
        if self.task_type:
            if self.task_type in item_task:
                score += 20
            if item_task in self.task_type:
                score += 15

        # Direct subsystem match
        if self.subsystem:
            if self.subsystem in item_subsystem:
                score += 15
            if item_subsystem in self.subsystem:
                score += 10

        # Query keyword overlap
        for part in self.query_parts:
            if part in title:
                score += 10
            if part in desc:
                score += 5
            if part in content:
                score += 3

        # File path overlap with applies_to
        for fp in self.file_paths:
            fp_parts = fp.split("/")
            for fp_part in fp_parts:
                if len(fp_part) <= 2:
                    continue
                for tag in applies_to:
                    if fp_part in tag or tag in fp_part:
                        score += 8
                        break

        # Success rate bonus (prefer proven items)
        if isinstance(success_rate, float) and success_rate > 0.8:
            score += 3
        if isinstance(success_rate, float) and success_rate > 0.95:
            score += 2

        # Penalize very long content (less focused)
        if len(content) > 300:
            score -= 2

        return score


# ---------------------------------------------------------------------------
# Memory loader
# ---------------------------------------------------------------------------

class MemoryLoader:
    """Main loader: discovers docs, scores relevance, returns formatted context."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
        self.registry = MemoryRegistry(repo_root)
        self.docs = self.registry.discover()

    def load(self, query: str = "", file_paths: List[str] = None,
             subsystem: str = "", task_type: str = "",
             max_docs: int = 3, max_items: int = 10,
             dry_run: bool = False) -> str:
        """Load the most relevant memory items for the given task context.

        Args:
            query: Description of the current task
            file_paths: Files being modified
            subsystem: Target subsystem (optional, stronger signal)
            task_type: Target task type (optional, stronger signal)
            max_docs: Max memory docs to read
            max_items: Max items to return
            dry_run: If True, only report what would be loaded

        Returns:
            Formatted memory context string ready to inject into agent prompt
        """
        file_paths = file_paths or []
        scorer = RelevanceScorer(query, file_paths, subsystem, task_type)

        # --- Level 2: Score and select docs ---
        scored_docs = []
        for doc in self.docs:
            score = scorer.score_doc(doc)
            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        selected_docs = scored_docs[:max_docs]

        if dry_run:
            return self._format_dry_run(selected_docs, max_items)

        # --- Level 3: Read selected docs, score items ---
        all_items: List[Tuple[float, dict, str]] = []  # (score, item, doc_path)
        for doc_score, doc in selected_docs:
            for item in doc.items:
                item_score = scorer.score_item(item)
                # Blend doc relevance with item relevance
                blended = item_score + (doc_score * 0.3)
                all_items.append((blended, item, doc.rel_path))

        all_items.sort(key=lambda x: x[0], reverse=True)
        top_items = all_items[:max_items]

        return self._format_output(top_items, selected_docs, query)

    def _format_output(self, items: List[Tuple[float, dict, str]],
                       docs: List[Tuple[float, MemoryDoc]],
                       query: str) -> str:
        """Format the loaded items as context for the agent."""
        lines = [
            "=" * 60,
            "REPOSITORY EXPERIENTIAL KNOWLEDGE (Loaded via Memory Loader)",
            "=" * 60,
            "",
            f"Query: {query or '(none)'}" if query else "",
        ]

        if docs:
            lines.append("Sources loaded:")
            for score, doc in docs:
                lines.append(f"  - {doc.rel_path} ({doc.item_count} items, relevance: {score:.1f})")
            lines.append("")

        if not items:
            lines.append("No relevant experiences found for this task and file set.")
            lines.append("")
            lines.append("Tip: If you're starting a new task type, run training first:")
            lines.append("  python .recursive/scripts/recursive-training-grpo.py --repo-root .")
            return "\n".join(lines)

        lines.append(f"Top {len(items)} relevant learnings (ordered by relevance):\n")

        for idx, (score, item, doc_path) in enumerate(items, 1):
            rb_id = item["rb_id"]
            title = item["title"]
            desc = item["description"]
            content = item["content"]
            task_type = item.get("task_type", "")
            applies_to = item.get("applies_to", [])
            success = item.get("success_rate", 0.0)
            source_runs = item.get("source_runs", [])

            sr_str = f" [success: {success:.0%}]" if isinstance(success, float) and success > 0 else ""
            tt_str = f" [{task_type}]" if task_type else ""
            applies_str = ", ".join(applies_to) if applies_to else ""
            runs_str = f" (from: {', '.join(source_runs[:3])}{'...' if len(source_runs) > 3 else ''})" if source_runs else ""

            lines.append(f"{idx}. [{rb_id}{tt_str}]{sr_str} {title}")
            lines.append(f"   {desc}")
            lines.append(f"   {content}")
            if applies_str:
                lines.append(f"   Applies to: {applies_str}")
            if runs_str:
                lines.append(f"   Source runs{runs_str}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("Apply these learnings when relevant. They are scoped to THIS repository.")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _format_dry_run(self, docs: List[Tuple[float, MemoryDoc]], max_items: int) -> str:
        """Format dry-run output showing what would be loaded."""
        lines = [
            "=" * 60,
            "DRY RUN: Memory Loader Preview",
            "=" * 60,
            "",
        ]

        if not docs:
            lines.append("No memory docs match the current task context.")
            return "\n".join(lines)

        lines.append(f"Would load top {len(docs)} memory doc(s):")
        for score, doc in docs:
            lines.append(f"  - {doc.rel_path} ({doc.item_count} items, score: {score:.1f})")

        lines.append("")
        lines.append(f"Would return top {max_items} items across all selected docs.")
        lines.append("Run without --dry-run to load the actual content.")
        return "\n".join(lines)

    def load_all_flat(self) -> str:
        """Load ALL memory items as a flat list (for README/IDE files)."""
        items = []
        for doc in self.docs:
            for item in doc.items:
                items.append(item)

        if not items:
            return ""

        lines = ["## Repository Experiential Knowledge (ReasoningBank)\n"]
        lines.append("Lessons learned from prior recursive-mode runs in THIS repository:\n")
        for item in sorted(items, key=lambda x: x.get("rb_id", "")):
            rb_id = item["rb_id"]
            title = item["title"]
            desc = item["description"]
            content = item["content"]
            applies = ", ".join(item.get("applies_to", []))
            lines.append(f"- [{rb_id}] **{title}**: {desc} {content}")
            if applies:
                lines.append(f"  (applies to: {applies})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Progressive memory loader for recursive-mode experiential knowledge"
    )
    parser.add_argument("--repo-root", type=str, required=True,
                        help="Path to git repository root")
    parser.add_argument("--query", type=str, default="",
                        help="Description of the current task (e.g., 'implementing frontend feature')")
    parser.add_argument("--files", type=str, default="",
                        help="Comma-separated list of file paths being modified")
    parser.add_argument("--subsystem", type=str, default="",
                        help="Target subsystem (e.g., 'web', 'artifacts', 'api-worker')")
    parser.add_argument("--task-type", type=str, default="",
                        help="Target task type (e.g., 'commit-workflow', 'test-validation')")
    parser.add_argument("--max-docs", type=int, default=3,
                        help="Maximum memory docs to load (default: 3)")
    parser.add_argument("--max-items", type=int, default=10,
                        help="Maximum items to return (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be loaded without returning content")
    parser.add_argument("--all", action="store_true",
                        help="Load all items as flat list (for README generation)")
    args = parser.parse_args()

    loader = MemoryLoader(args.repo_root)

    if args.all:
        output = loader.load_all_flat()
        if output:
            print(output)
        else:
            print("No memory items found.")
        return

    file_paths = [f.strip() for f in args.files.split(",") if f.strip()] if args.files else []

    output = loader.load(
        query=args.query,
        file_paths=file_paths,
        subsystem=args.subsystem,
        task_type=args.task_type,
        max_docs=args.max_docs,
        max_items=args.max_items,
        dry_run=args.dry_run,
    )
    print(output)


if __name__ == "__main__":
    main()
