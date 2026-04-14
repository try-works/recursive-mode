#!/usr/bin/env bash
#
# Optional template - NOT auto-installed by Skills CLI.
# If your agent/runtime supports hooks, you may wire this up manually.
#
# Session Start Hook for recursive-mode

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

bootstrap_recursive_mode() {
    local repo_root="$1"

    if [ -f "$repo_root/.recursive/RECURSIVE.md" ]; then
        return 0
    fi

    echo "Bootstrapping recursive-mode scaffold in $repo_root ..."

    if command -v python3 >/dev/null 2>&1; then
        python3 "$PLUGIN_ROOT/scripts/install-recursive-mode.py" --repo-root "$repo_root" && return 0
    fi
    if command -v python >/dev/null 2>&1; then
        python "$PLUGIN_ROOT/scripts/install-recursive-mode.py" --repo-root "$repo_root" && return 0
    fi
    if command -v pwsh >/dev/null 2>&1; then
        pwsh -NoProfile -File "$PLUGIN_ROOT/scripts/install-recursive-mode.ps1" -RepoRoot "$repo_root" && return 0
    fi
    if command -v powershell >/dev/null 2>&1; then
        powershell -ExecutionPolicy Bypass -File "$PLUGIN_ROOT/scripts/install-recursive-mode.ps1" -RepoRoot "$repo_root" && return 0
    fi

    echo "Warning: Could not auto-bootstrap recursive-mode. Run one of the install-recursive-mode scripts manually."
    return 1
}

echo ""
echo "recursive-mode"
echo "====================="
echo ""

if git rev-parse --git-dir > /dev/null 2>&1; then
    REPO_ROOT=$(git rev-parse --show-toplevel)
    echo "Repository: $(basename "$REPO_ROOT")"
    bootstrap_recursive_mode "$REPO_ROOT" || true
else
    echo "Warning: Not in a git repository. recursive-mode expects version control."
fi

echo ""
echo "Available Skills:"
echo "  - recursive-mode       - Main workflow orchestration"
echo "  - recursive-spec       - Repo-aware requirements/spec authoring"
echo "  - recursive-benchmark  - Paired recursive benchmark runs"
echo "  - recursive-worktree   - Required worktree isolation"
echo "  - recursive-tdd        - TDD discipline for implementation"
echo "  - recursive-debugging  - Root-cause analysis"
echo "  - recursive-review-bundle - Canonical delegated review bundles"
echo "  - recursive-subagent   - Parallel execution with fallback"
echo ""

echo "Quick Start:"
echo "  1. Use recursive-spec to draft requirements, or identify the source plan"
echo "  2. Use recursive-benchmark to compare recursive-off vs recursive-on"
echo "  3. Invoke: 'Implement the run' or 'Implement requirement <run-id>'"
echo "  4. recursive-mode should bootstrap missing scaffold automatically before proceeding"
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
