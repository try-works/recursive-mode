#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_python_installer() {
  local candidate="$1"
  shift
  if ! command -v "$candidate" >/dev/null 2>&1; then
    return 1
  fi
  "$candidate" "$SCRIPT_DIR/install-recursive-mode.py" "$@" && return 0
  return 1
}

translate_args_for_powershell() {
  POWERSHELL_ARGS=()
  while (($#)); do
    case "$1" in
      --skip-recursive-update)
        POWERSHELL_ARGS+=("-SkipRecursiveUpdate")
        shift
        ;;
      --repo-root)
        if (($# < 2)); then
          echo "Missing value for --repo-root." >&2
          return 1
        fi
        POWERSHELL_ARGS+=("-RepoRoot" "$2")
        shift 2
        ;;
      --repo-root=*)
        POWERSHELL_ARGS+=("-RepoRoot" "${1#*=}")
        shift
        ;;
      *)
        echo "Unsupported argument for PowerShell fallback: $1" >&2
        return 1
        ;;
    esac
  done
}

run_powershell_installer() {
  local candidate="$1"
  shift
  if ! command -v "$candidate" >/dev/null 2>&1; then
    return 1
  fi
  translate_args_for_powershell "$@" || return 1
  "$candidate" -NoProfile -File "$SCRIPT_DIR/install-recursive-mode.ps1" "${POWERSHELL_ARGS[@]}" && return 0
  return 1
}

if run_python_installer python3 "$@"; then
  exit 0
fi
if run_python_installer python "$@"; then
  exit 0
fi
if command -v py >/dev/null 2>&1; then
  if py -3 "$SCRIPT_DIR/install-recursive-mode.py" "$@"; then
    exit 0
  fi
fi
if run_powershell_installer pwsh "$@"; then
  exit 0
fi
if run_powershell_installer powershell "$@"; then
  exit 0
fi

echo "Could not run install-recursive-mode via python3, python, py -3, pwsh, or powershell." >&2
exit 1
