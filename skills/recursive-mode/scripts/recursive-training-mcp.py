#!/usr/bin/env python3
"""
Optional MCP (Model Context Protocol) server for repository experiences.

Provides a get_repo_experiences tool that any MCP-compatible client can call
to dynamically retrieve ReasoningBank-structured experiences relevant to the
current task, file paths, and task type.

Usage:
    python recursive-training-mcp.py --repo-root /path/to/repo

Compatible clients: Claude Desktop, Cline, Cursor (with MCP), Continue.dev.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List


class ReasoningBankReader:
    """Reads ReasoningBank-structured memory from the memory plane."""

    DOMAINS_DIR = ".recursive/memory/domains"
    TRAINING_DIR = ".recursive/memory/training"

    def __init__(self, repo_root: str):
        self.root = Path(repo_root)
        self.domains_dir = self.root / self.DOMAINS_DIR
        self.training_dir = self.root / self.TRAINING_DIR

    def _parse_items_from_file(self, filepath: Path) -> List[dict]:
        if not filepath.exists():
            return []
        content = filepath.read_text(encoding="utf-8")
        if "Status: CURRENT" not in content and "Status: SUSPECT" not in content:
            return []

        items = []
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

        # Enrich with schema metadata
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
                    # Parse JSON arrays
                    try:
                        sr = m.group(6)
                        item["source_runs"] = json.loads(sr) if sr.strip() else []
                    except Exception:
                        item["source_runs"] = []
                    try:
                        at = m.group(7)
                        item["applies_to"] = json.loads(at) if at.strip() else []
                    except Exception:
                        item["applies_to"] = []
                    break
        return items

    def load_all_items(self) -> List[dict]:
        items = []
        for d in (self.domains_dir, self.training_dir):
            if not d.exists():
                continue
            for f in sorted(d.glob("*.md")):
                items.extend(self._parse_items_from_file(f))
        return [item for item in items if item.get("status") != "deprecated"]

    def get_relevant(self, task_type: str = "", file_paths: List[str] = None, subsystem: str = "") -> List[dict]:
        """Score and filter items by relevance. Returns sorted list with scores."""
        all_items = self.load_all_items()
        file_paths = file_paths or []
        scored = []

        for item in all_items:
            score = 0
            applies_to = item.get("applies_to", [])
            item_task = item.get("task_type", "")
            item_subsystem = item.get("subsystem", "")

            # Task type match (strong signal)
            if task_type and item_task and task_type.lower() in item_task.lower():
                score += 5

            # Subsystem match (strong signal)
            if subsystem and item_subsystem and subsystem.lower() in item_subsystem.lower():
                score += 4

            # File path overlap (medium signal)
            for f in file_paths:
                parts = f.split("/")
                for part in parts:
                    if len(part) > 2:
                        for tag in applies_to:
                            if part.lower() in tag.lower():
                                score += 2
                                break

            # Content overlap (weak signal)
            for f in file_paths:
                content = f"{item.get('title', '')} {item.get('description', '')} {item.get('content', '')}"
                if f.lower() in content.lower():
                    score += 1

            # Success rate bonus
            sr = item.get("success_rate", 0)
            if isinstance(sr, (int, float)) and sr > 0.8:
                score += 1

            if score > 0:
                item["_relevance_score"] = score
                scored.append(item)

        scored.sort(key=lambda x: x["_relevance_score"], reverse=True)
        return scored


def main():
    parser = argparse.ArgumentParser(description="MCP server for repo experiences")
    parser.add_argument("--repo-root", type=str, required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    rb = ReasoningBankReader(repo_root)

    print("MCP server (ReasoningBank) starting...", file=sys.stderr)
    print(f"Repo root: {repo_root}", file=sys.stderr)

    while True:
        try:
            line = input()
            msg = json.loads(line)
            method = msg.get("method", "")
            msg_id = msg.get("id")

            if method == "initialize":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "recursive-training-mcp", "version": "2.0.0"},
                    },
                }), flush=True)

            elif method == "tools/list":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "tools": [
                            {
                                "name": "get_repo_experiences",
                                "description": "Get ReasoningBank-structured experiences for the current repository",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "task_type": {
                                            "type": "string",
                                            "description": "Type of task (e.g., commit-remediation, add-api-endpoint)",
                                        },
                                        "file_paths": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of file paths being modified",
                                        },
                                        "subsystem": {
                                            "type": "string",
                                            "description": "Target subsystem (e.g., packages/artifacts)",
                                        },
                                    },
                                },
                            }
                        ]
                    },
                }), flush=True)

            elif method == "tools/call":
                params = msg.get("params", {})
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                if tool_name == "get_repo_experiences":
                    task_type = arguments.get("task_type", "")
                    file_paths = arguments.get("file_paths", [])
                    subsystem = arguments.get("subsystem", "")
                    items = rb.get_relevant(task_type, file_paths, subsystem)

                    if items:
                        lines = ["# Repository Experiential Knowledge (ReasoningBank)\n"]
                        for item in items[:20]:  # top 20
                            rb_id = item["rb_id"]
                            title = item["title"]
                            desc = item["description"]
                            content = item["content"]
                            score = item.get("_relevance_score", 0)
                            sr = item.get("success_rate")
                            sr_str = f" [success: {sr:.0%}]" if isinstance(sr, float) else ""
                            applies = ", ".join(item.get("applies_to", []))
                            lines.append(
                                f"## [{rb_id}] {title}{sr_str} (score: {score})\n"
                                f"{desc}\n\n{content}\n"
                                f"*Applies to: {applies}*\n"
                            )
                        result_text = "\n".join(lines)
                    else:
                        result_text = "No relevant experiences found for this task and file set."

                    print(json.dumps({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {"content": [{"type": "text", "text": result_text}]},
                    }), flush=True)

                else:
                    print(json.dumps({
                        "jsonrpc": "2.0", "id": msg_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                    }), flush=True)

        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
