#!/usr/bin/env bash
#
# Optional template - NOT auto-installed by Skills CLI.
# If your agent/runtime supports hooks, you may wire this up manually.
#
# Session Start Hook for recursive-mode

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo ""
echo "recursive-mode"
echo "====================="
echo ""

if git rev-parse --git-dir > /dev/null 2>&1; then
    REPO_ROOT=$(git rev-parse --show-toplevel)
    echo "Repository: $(basename "$REPO_ROOT")"
else
    echo "Warning: Not in a git repository. recursive-mode expects version control."
fi

echo ""
echo "Available Skills:"
echo "  - recursive-mode       - Main workflow orchestration"
echo "  - recursive-worktree   - Required worktree isolation"
echo "  - recursive-tdd        - TDD discipline for implementation"
echo "  - recursive-debugging  - Root-cause analysis"
echo "  - recursive-review-bundle - Canonical delegated review bundles"
echo "  - recursive-subagent   - Parallel execution with fallback"
echo ""

echo "Quick Start:"
echo "  1. Create run folder: mkdir -p .recursive/run/<run-id>"
echo "  2. Write requirements: .recursive/run/<run-id>/00-requirements.md"
echo "  3. Invoke: 'Implement requirement <run-id>'"
echo ""

if [ -d ".recursive/run" ] 2>/dev/null; then
    RUN_COUNT=$(find .recursive/run -maxdepth 1 -type d | wc -l)
    if [ "$RUN_COUNT" -gt 1 ]; then
        echo "Recent Activity:"
        find .recursive/run -maxdepth 1 -type d -not -path ".recursive/run" | while read -r run_dir; do
            run_name=$(basename "$run_dir")
            if [ -f "$run_dir/00-requirements.md" ]; then
                status=$(grep "^Status:" "$run_dir/"*.md 2>/dev/null | tail -1 | cut -d: -f2 | tr -d ' ' || echo "UNKNOWN")
                echo "  - $run_name - Status: $status"
            fi
        done
        echo ""
    fi
fi

echo "Documentation:"
echo "  - Canonical workflow: .recursive/RECURSIVE.md"
echo "  - Artifact templates: references/artifact-template.md"
echo ""

echo "====================="
echo ""

export RECURSIVE_MODE_ROOT="$PLUGIN_ROOT"
export RECURSIVE_MODE_VERSION="2.0.0"

echo "[OK] recursive-mode ready"
echo ""
