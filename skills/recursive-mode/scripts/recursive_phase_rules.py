#!/usr/bin/env python3
"""
Shared phase-ordering rules, prerequisite enforcement, and lock-receipt helpers
for recursive-mode.

All gate-related scripts import this module so that phase sequencing, prerequisite
checks, and receipt I/O follow a single canonical model.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical phase sequence
# ---------------------------------------------------------------------------

PHASE_SEQUENCE: list[str] = [
    "00-requirements.md",
    "00-worktree.md",
    "01-as-is.md",
    "01.5-root-cause.md",
    "02-to-be-plan.md",
    "03-implementation-summary.md",
    "03.5-code-review.md",
    "04-test-summary.md",
    "05-manual-qa.md",
    "06-decisions-update.md",
    "07-state-update.md",
    "08-memory-impact.md",
]

OPTIONAL_PHASES: frozenset[str] = frozenset(
    {
        "01-as-is.md",
        "01.5-root-cause.md",
        "02-to-be-plan.md",
        "03-implementation-summary.md",
        "03.5-code-review.md",
        "04-test-summary.md",
        "05-manual-qa.md",
    }
)

MANDATORY_PHASES: frozenset[str] = frozenset(set(PHASE_SEQUENCE) - OPTIONAL_PHASES)

# Lock receipts live in this subdirectory of the run directory.
LOCKS_SUBDIR = "locks"
RECEIPT_SUFFIX = ".receipt.json"

# ---------------------------------------------------------------------------
# Lock-hash helpers (kept here so callers don't need to duplicate them)
# ---------------------------------------------------------------------------

_LOCK_HASH_LINE_RE = re.compile(r"(?m)^[ \t]*LockHash:.*(?:\n|$)")
_STATUS_RE = re.compile(r'(?m)^[ \t]*Status:\s*(?:`|")?(\w+)(?:`|")?\s*$')
_LOCK_HASH_RE = re.compile(r'(?m)^[ \t]*LockHash:\s*(?:`|")?([a-fA-F0-9]{64})(?:`|")?\s*$')
_LOCKED_AT_RE = re.compile(r'(?m)^[ \t]*LockedAt:\s*(?:`|")?([^`"\r\n]+)(?:`|")?\s*$')


def normalize_for_lock_hash(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return _LOCK_HASH_LINE_RE.sub("", normalized)


def lock_hash_from_content(content: str) -> str:
    normalized = normalize_for_lock_hash(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phase index helpers
# ---------------------------------------------------------------------------


def phase_index(artifact_file: str) -> int:
    """Return the position of an artifact in PHASE_SEQUENCE, or -1 if not found."""
    try:
        return PHASE_SEQUENCE.index(artifact_file)
    except ValueError:
        return -1


def is_core_artifact(artifact_file: str) -> bool:
    """Return True if artifact_file is a known core phase artifact."""
    return artifact_file in PHASE_SEQUENCE


# ---------------------------------------------------------------------------
# Lock-validity helpers
# ---------------------------------------------------------------------------


def get_lock_status(artifact_path: Path) -> str:
    """
    Return one of:
      "MISSING"    – file does not exist
      "DRAFT"      – file exists but Status is not LOCKED
      "STALE_LOCK" – Status is LOCKED but hash or metadata is invalid
      "LOCKED"     – Status is LOCKED and hash is valid
    """
    if not artifact_path.exists():
        return "MISSING"
    content = artifact_path.read_text(encoding="utf-8")
    status_match = _STATUS_RE.search(content)
    if not status_match or status_match.group(1) != "LOCKED":
        return "DRAFT"
    hash_match = _LOCK_HASH_RE.search(content)
    locked_at_match = _LOCKED_AT_RE.search(content)
    if not hash_match or not locked_at_match:
        return "STALE_LOCK"
    stored_hash = hash_match.group(1).lower()
    actual_hash = lock_hash_from_content(content)
    if stored_hash != actual_hash:
        return "STALE_LOCK"
    return "LOCKED"


def is_lock_valid(artifact_path: Path) -> bool:
    """Return True only when get_lock_status returns "LOCKED"."""
    return get_lock_status(artifact_path) == "LOCKED"


# ---------------------------------------------------------------------------
# Prerequisite model
# ---------------------------------------------------------------------------


def get_prerequisites(artifact_file: str, run_dir: Path) -> list[str]:
    """
    Return the ordered list of phase artifact file names that must be LOCKED
    before ``artifact_file`` may be scaffolded or locked.

    The rule is simple: every phase that appears earlier in PHASE_SEQUENCE AND
    is already present on disk in ``run_dir`` must be LOCKED first.  Optional
    phases that have not been created yet are not prerequisites.
    """
    idx = phase_index(artifact_file)
    if idx <= 0:
        return []
    return [phase for phase in PHASE_SEQUENCE[:idx] if (run_dir / phase).exists()]


def get_prerequisite_blockers(
    artifact_file: str, run_dir: Path
) -> list[dict[str, str]]:
    """
    Return a list of prerequisite artifacts that are currently blocking
    ``artifact_file`` from being scaffolded or locked.

    Each entry is a dict with keys:
      "artifact" – filename (e.g. "00-requirements.md")
      "status"   – "MISSING", "DRAFT", or "STALE_LOCK"
      "path"     – absolute path as string
    """
    blockers: list[dict[str, str]] = []
    for prereq in get_prerequisites(artifact_file, run_dir):
        prereq_path = run_dir / prereq
        status = get_lock_status(prereq_path)
        if status != "LOCKED":
            blockers.append(
                {
                    "artifact": prereq,
                    "status": status,
                    "path": str(prereq_path),
                }
            )
    return blockers


def get_next_legal_phase(run_dir: Path) -> str | None:
    """
    Return the file name of the first phase in PHASE_SEQUENCE that is not yet
    LOCKED and whose prerequisites are all LOCKED, or None if the run is
    complete or blocked.

    Optional phases that were never created are treated as intentionally
    skipped — they are invisible to this function unless they exist on disk.
    """
    for phase in PHASE_SEQUENCE:
        phase_path = run_dir / phase
        # Optional phases that don't exist were intentionally omitted; skip them.
        if phase in OPTIONAL_PHASES and not phase_path.exists():
            continue
        lock_status = get_lock_status(phase_path)
        if lock_status == "LOCKED":
            continue
        # Phase is not locked; check whether prerequisites are satisfied.
        blockers = get_prerequisite_blockers(phase, run_dir)
        if not blockers:
            return phase
        # Phase (mandatory or existing optional) has unresolved prerequisites.
        return None
    return None


# ---------------------------------------------------------------------------
# Lock receipt I/O
# ---------------------------------------------------------------------------


def receipt_path(run_dir: Path, artifact_file: str) -> Path:
    stem = Path(artifact_file).stem
    return run_dir / LOCKS_SUBDIR / f"{stem}{RECEIPT_SUFFIX}"


def read_receipt(run_dir: Path, artifact_file: str) -> dict | None:
    """Read the JSON lock receipt for an artifact, or None if not found/invalid."""
    path = receipt_path(run_dir, artifact_file)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_receipt(
    run_dir: Path, artifact_file: str, artifact_path: Path
) -> dict:
    """
    Write a lock receipt for ``artifact_file`` recording:
      - artifact path and content hash
      - ISO-8601 locked_at timestamp
      - prerequisite file names and their current content hashes
      - hash of the previous receipt (for chaining)
      - self-hash of the receipt JSON

    Raises RuntimeError if any prerequisite is not LOCKED at the time of
    writing, ensuring the receipt chain is internally consistent.

    Returns the written receipt dict.
    """
    content = artifact_path.read_text(encoding="utf-8")
    artifact_hash = lock_hash_from_content(content)

    prereq_hashes: dict[str, str] = {}
    for prereq in get_prerequisites(artifact_file, run_dir):
        prereq_path = run_dir / prereq
        if prereq_path.exists():
            prereq_status = get_lock_status(prereq_path)
            if prereq_status != "LOCKED":
                raise RuntimeError(
                    f"Cannot write receipt for {artifact_file!r}: "
                    f"prerequisite {prereq!r} is not LOCKED (status: {prereq_status})"
                )
            prereq_content = prereq_path.read_text(encoding="utf-8")
            prereq_hashes[prereq] = lock_hash_from_content(prereq_content)

    existing = read_receipt(run_dir, artifact_file)
    prev_receipt_hash: str | None = existing.get("receipt_hash") if existing else None

    receipt: dict = {
        "artifact": artifact_file,
        "artifact_path": str(artifact_path),
        "artifact_hash": artifact_hash,
        "locked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prerequisite_hashes": prereq_hashes,
        "previous_receipt_hash": prev_receipt_hash,
    }
    receipt_content = json.dumps(receipt, sort_keys=True)
    receipt["receipt_hash"] = hashlib.sha256(receipt_content.encode("utf-8")).hexdigest()

    locks_dir = run_dir / LOCKS_SUBDIR
    locks_dir.mkdir(exist_ok=True)
    rpath = receipt_path(run_dir, artifact_file)
    rpath.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return receipt


def invalidate_receipt(run_dir: Path, artifact_file: str) -> bool:
    """Remove the lock receipt for ``artifact_file``. Returns True if a receipt existed."""
    rpath = receipt_path(run_dir, artifact_file)
    if rpath.exists():
        rpath.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Stale-chain detection
# ---------------------------------------------------------------------------


def get_stale_downstream_phases(
    artifact_file: str, run_dir: Path
) -> list[dict[str, str]]:
    """
    Return phases that have receipts referencing ``artifact_file`` as a
    prerequisite but whose stored hash no longer matches the current content.

    Each entry: {"artifact": str, "reason": str}
    """
    idx = phase_index(artifact_file)
    if idx < 0:
        return []

    current_hash: str | None = None
    artifact_path = run_dir / artifact_file
    if artifact_path.exists():
        current_hash = lock_hash_from_content(
            artifact_path.read_text(encoding="utf-8")
        )

    stale: list[dict[str, str]] = []
    for downstream in PHASE_SEQUENCE[idx + 1 :]:
        receipt = read_receipt(run_dir, downstream)
        if receipt is None:
            continue
        prereq_hashes = receipt.get("prerequisite_hashes", {})
        if artifact_file not in prereq_hashes:
            continue
        stored_hash = prereq_hashes[artifact_file]
        if current_hash is None or stored_hash != current_hash:
            stale.append(
                {
                    "artifact": downstream,
                    "reason": f"prerequisite {artifact_file!r} hash changed",
                }
            )
    return stale


def get_all_stale_receipts(run_dir: Path) -> list[dict[str, str]]:
    """
    Scan all lock receipts in ``run_dir`` and return entries where a
    prerequisite's current content hash differs from the hash recorded at
    lock time.

    Each entry: {"artifact": str, "stale_prereq": str, "reason": str}
    """
    stale: list[dict[str, str]] = []
    for phase in PHASE_SEQUENCE:
        receipt = read_receipt(run_dir, phase)
        if receipt is None:
            continue
        prereq_hashes = receipt.get("prerequisite_hashes", {})
        locked_at = receipt.get("locked_at", "unknown")
        for prereq, stored_hash in prereq_hashes.items():
            prereq_path = run_dir / prereq
            if not prereq_path.exists():
                stale.append(
                    {
                        "artifact": phase,
                        "stale_prereq": prereq,
                        "reason": f"prerequisite {prereq!r} no longer exists",
                    }
                )
                continue
            current_hash = lock_hash_from_content(
                prereq_path.read_text(encoding="utf-8")
            )
            if stored_hash != current_hash:
                stale.append(
                    {
                        "artifact": phase,
                        "stale_prereq": prereq,
                        "reason": (
                            f"prerequisite {prereq!r} content changed since lock at {locked_at}"
                        ),
                    }
                )
    return stale
