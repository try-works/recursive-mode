#!/usr/bin/env python3
"""
Tests for recursive_phase_rules.py – phase ordering, prerequisites, lock
validation, receipt I/O, stale-chain detection, and reopen-adjacent helpers.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
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


rules = load_module("recursive_phase_rules", "recursive_phase_rules.py")


# ---------------------------------------------------------------------------
# Minimal artifact content helpers
# ---------------------------------------------------------------------------

def _draft_content(phase_file: str) -> str:
    return f"Status: `DRAFT`\nPhase: `{phase_file}`\n\n## TODO\n\n- [ ] placeholder\n"


def _locked_content(phase_file: str) -> str:
    raw = f"Status: `LOCKED`\nPhase: `{phase_file}`\nLockedAt: `2024-01-01T00:00:00Z`\n\n## TODO\n\n- [x] done\n"
    lock_hash = rules.lock_hash_from_content(raw)
    return raw + f"LockHash: `{lock_hash}`\n"


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _setup_run(tmp_path: Path) -> Path:
    """Return a fresh run directory under tmp_path."""
    run_dir = tmp_path / ".recursive" / "run" / "test-run-001"
    run_dir.mkdir(parents=True)
    return run_dir


# ---------------------------------------------------------------------------
# PHASE_SEQUENCE / constants
# ---------------------------------------------------------------------------

class TestPhaseSequence(unittest.TestCase):
    def test_sequence_order(self):
        seq = rules.PHASE_SEQUENCE
        self.assertIn("00-requirements.md", seq)
        self.assertIn("08-memory-impact.md", seq)
        self.assertLess(seq.index("00-requirements.md"), seq.index("00-worktree.md"))
        self.assertLess(seq.index("02-to-be-plan.md"), seq.index("03-implementation-summary.md"))
        self.assertLess(seq.index("06-decisions-update.md"), seq.index("07-state-update.md"))

    def test_optional_phases_subset(self):
        self.assertTrue(rules.OPTIONAL_PHASES.issubset(set(rules.PHASE_SEQUENCE)))

    def test_mandatory_phases_in_sequence(self):
        for phase in rules.MANDATORY_PHASES:
            self.assertIn(phase, rules.PHASE_SEQUENCE)

    def test_phase_index(self):
        self.assertEqual(rules.phase_index("00-requirements.md"), 0)
        self.assertEqual(rules.phase_index("00-worktree.md"), 1)
        self.assertEqual(rules.phase_index("08-memory-impact.md"), len(rules.PHASE_SEQUENCE) - 1)
        self.assertEqual(rules.phase_index("not-a-phase.md"), -1)

    def test_is_core_artifact(self):
        self.assertTrue(rules.is_core_artifact("00-requirements.md"))
        self.assertTrue(rules.is_core_artifact("08-memory-impact.md"))
        self.assertFalse(rules.is_core_artifact("random-file.md"))


# ---------------------------------------------------------------------------
# Lock-hash helpers
# ---------------------------------------------------------------------------

class TestLockHash(unittest.TestCase):
    def test_normalize_strips_lockhash_line(self):
        content = "Status: `LOCKED`\nLockHash: `abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890`\nsome text\n"
        normalized = rules.normalize_for_lock_hash(content)
        self.assertNotIn("LockHash", normalized)

    def test_lock_hash_deterministic(self):
        content = "hello world"
        h1 = rules.lock_hash_from_content(content)
        h2 = rules.lock_hash_from_content(content)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_lock_hash_excludes_lockhash_field(self):
        base = "Status: `LOCKED`\nsome content\n"
        content_with_hash = base + "LockHash: `" + "0" * 64 + "`\n"
        self.assertEqual(
            rules.lock_hash_from_content(base),
            rules.lock_hash_from_content(content_with_hash),
        )


# ---------------------------------------------------------------------------
# get_lock_status / is_lock_valid
# ---------------------------------------------------------------------------

class TestGetLockStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.td = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing(self):
        path = self.td / "nonexistent.md"
        self.assertEqual(rules.get_lock_status(path), "MISSING")
        self.assertFalse(rules.is_lock_valid(path))

    def test_draft(self):
        path = self.td / "f.md"
        _write(path, _draft_content("00-requirements.md"))
        self.assertEqual(rules.get_lock_status(path), "DRAFT")
        self.assertFalse(rules.is_lock_valid(path))

    def test_locked_valid(self):
        path = self.td / "f.md"
        _write(path, _locked_content("00-requirements.md"))
        self.assertEqual(rules.get_lock_status(path), "LOCKED")
        self.assertTrue(rules.is_lock_valid(path))

    def test_stale_lock_bad_hash(self):
        path = self.td / "f.md"
        _write(path, "Status: `LOCKED`\nLockedAt: `2024-01-01T00:00:00Z`\nLockHash: `" + "0" * 64 + "`\n")
        self.assertEqual(rules.get_lock_status(path), "STALE_LOCK")

    def test_stale_lock_missing_metadata(self):
        path = self.td / "f.md"
        _write(path, "Status: `LOCKED`\n")
        self.assertEqual(rules.get_lock_status(path), "STALE_LOCK")


# ---------------------------------------------------------------------------
# get_prerequisites / get_prerequisite_blockers
# ---------------------------------------------------------------------------

class TestPrerequisites(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = _setup_run(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_phase_has_no_prerequisites(self):
        prereqs = rules.get_prerequisites("00-requirements.md", self.run_dir)
        self.assertEqual(prereqs, [])

    def test_worktree_requires_requirements_if_present(self):
        _write(self.run_dir / "00-requirements.md", _draft_content("00-requirements.md"))
        prereqs = rules.get_prerequisites("00-worktree.md", self.run_dir)
        self.assertIn("00-requirements.md", prereqs)

    def test_worktree_no_prerequisite_if_requirements_absent(self):
        prereqs = rules.get_prerequisites("00-worktree.md", self.run_dir)
        self.assertEqual(prereqs, [])

    def test_later_phase_requires_all_existing_earlier_phases(self):
        _write(self.run_dir / "00-requirements.md", _locked_content("00-requirements.md"))
        _write(self.run_dir / "00-worktree.md", _draft_content("00-worktree.md"))
        prereqs = rules.get_prerequisites("02-to-be-plan.md", self.run_dir)
        self.assertIn("00-requirements.md", prereqs)
        self.assertIn("00-worktree.md", prereqs)

    def test_no_blockers_when_prerequisites_locked(self):
        _write(self.run_dir / "00-requirements.md", _locked_content("00-requirements.md"))
        blockers = rules.get_prerequisite_blockers("00-worktree.md", self.run_dir)
        self.assertEqual(blockers, [])

    def test_blocker_when_prerequisite_is_draft(self):
        _write(self.run_dir / "00-requirements.md", _draft_content("00-requirements.md"))
        blockers = rules.get_prerequisite_blockers("00-worktree.md", self.run_dir)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["artifact"], "00-requirements.md")
        self.assertEqual(blockers[0]["status"], "DRAFT")

    def test_blocker_when_prerequisite_missing_but_other_earlier_exists(self):
        # 00-requirements locked, 00-worktree locked, but 01-as-is is DRAFT;
        # 02-to-be-plan should report 01-as-is as a blocker.
        _write(self.run_dir / "00-requirements.md", _locked_content("00-requirements.md"))
        _write(self.run_dir / "00-worktree.md", _locked_content("00-worktree.md"))
        _write(self.run_dir / "01-as-is.md", _draft_content("01-as-is.md"))
        blockers = rules.get_prerequisite_blockers("02-to-be-plan.md", self.run_dir)
        artifact_names = [b["artifact"] for b in blockers]
        self.assertIn("01-as-is.md", artifact_names)

    def test_no_blocker_for_skipped_optional_phases(self):
        # Optional 01-as-is.md not present → not a blocker for 02-to-be-plan.md
        _write(self.run_dir / "00-requirements.md", _locked_content("00-requirements.md"))
        _write(self.run_dir / "00-worktree.md", _locked_content("00-worktree.md"))
        blockers = rules.get_prerequisite_blockers("02-to-be-plan.md", self.run_dir)
        self.assertEqual(blockers, [])


# ---------------------------------------------------------------------------
# get_next_legal_phase
# ---------------------------------------------------------------------------

class TestNextLegalPhase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = _setup_run(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_phase_when_run_is_empty(self):
        # No files at all → 00-requirements.md is the first legal phase
        next_phase = rules.get_next_legal_phase(self.run_dir)
        self.assertEqual(next_phase, "00-requirements.md")

    def test_advances_after_requirements_locked(self):
        _write(self.run_dir / "00-requirements.md", _locked_content("00-requirements.md"))
        next_phase = rules.get_next_legal_phase(self.run_dir)
        self.assertEqual(next_phase, "00-worktree.md")

    def test_blocks_when_earlier_phase_is_draft(self):
        _write(self.run_dir / "00-requirements.md", _draft_content("00-requirements.md"))
        _write(self.run_dir / "00-worktree.md", _draft_content("00-worktree.md"))
        # 00-requirements is DRAFT → 00-worktree is blocked
        next_phase = rules.get_next_legal_phase(self.run_dir)
        # The next phase is 00-requirements (first unlocked, unblocked)
        self.assertEqual(next_phase, "00-requirements.md")

    def test_returns_none_when_all_locked(self):
        # Lock the entire mandatory sequence
        for phase in ["00-requirements.md", "00-worktree.md", "06-decisions-update.md", "07-state-update.md", "08-memory-impact.md"]:
            _write(self.run_dir / phase, _locked_content(phase))
        result = rules.get_next_legal_phase(self.run_dir)
        # All mandatory phases locked, optional phases absent → complete
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Receipt I/O
# ---------------------------------------------------------------------------

class TestReceiptIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = _setup_run(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_receipt_returns_none_when_missing(self):
        result = rules.read_receipt(self.run_dir, "00-requirements.md")
        self.assertIsNone(result)

    def test_write_and_read_receipt(self):
        artifact_path = self.run_dir / "00-requirements.md"
        _write(artifact_path, _locked_content("00-requirements.md"))
        receipt = rules.write_receipt(self.run_dir, "00-requirements.md", artifact_path)
        self.assertEqual(receipt["artifact"], "00-requirements.md")
        self.assertIn("artifact_hash", receipt)
        self.assertIn("locked_at", receipt)
        self.assertIn("receipt_hash", receipt)
        # Round-trip
        read_back = rules.read_receipt(self.run_dir, "00-requirements.md")
        self.assertIsNotNone(read_back)
        self.assertEqual(read_back["artifact_hash"], receipt["artifact_hash"])

    def test_receipt_records_prerequisite_hashes(self):
        req_path = self.run_dir / "00-requirements.md"
        wt_path = self.run_dir / "00-worktree.md"
        _write(req_path, _locked_content("00-requirements.md"))
        _write(wt_path, _locked_content("00-worktree.md"))
        receipt = rules.write_receipt(self.run_dir, "00-worktree.md", wt_path)
        self.assertIn("00-requirements.md", receipt["prerequisite_hashes"])

    def test_invalidate_receipt(self):
        artifact_path = self.run_dir / "00-requirements.md"
        _write(artifact_path, _locked_content("00-requirements.md"))
        rules.write_receipt(self.run_dir, "00-requirements.md", artifact_path)
        self.assertIsNotNone(rules.read_receipt(self.run_dir, "00-requirements.md"))
        removed = rules.invalidate_receipt(self.run_dir, "00-requirements.md")
        self.assertTrue(removed)
        self.assertIsNone(rules.read_receipt(self.run_dir, "00-requirements.md"))

    def test_write_receipt_rejects_unlocked_prerequisite(self):
        """write_receipt must raise if a prerequisite exists but is not LOCKED."""
        req_path = self.run_dir / "00-requirements.md"
        wt_path = self.run_dir / "00-worktree.md"
        # Write requirements as DRAFT (not locked)
        _write(req_path, _draft_content("00-requirements.md"))
        # Write worktree as LOCKED
        _write(wt_path, _locked_content("00-worktree.md"))
        with self.assertRaises(RuntimeError) as ctx:
            rules.write_receipt(self.run_dir, "00-worktree.md", wt_path)
        self.assertIn("00-requirements.md", str(ctx.exception))
        self.assertIn("DRAFT", str(ctx.exception))

    def test_write_receipt_allows_absent_optional_prerequisites(self):
        """write_receipt must not raise for optional phases that don't exist."""
        req_path = self.run_dir / "00-requirements.md"
        wt_path = self.run_dir / "00-worktree.md"
        _write(req_path, _locked_content("00-requirements.md"))
        rules.write_receipt(self.run_dir, "00-requirements.md", req_path)
        _write(wt_path, _locked_content("00-worktree.md"))
        # 01-as-is is optional and absent → should not block 02-to-be-plan receipt
        # First write worktree receipt
        rules.write_receipt(self.run_dir, "00-worktree.md", wt_path)
        plan_path = self.run_dir / "02-to-be-plan.md"
        _write(plan_path, _locked_content("02-to-be-plan.md"))
        # Should succeed since 01-as-is (optional) is absent — not a prereq
        receipt = rules.write_receipt(self.run_dir, "02-to-be-plan.md", plan_path)
        self.assertNotIn("01-as-is.md", receipt["prerequisite_hashes"])

    def test_invalidate_nonexistent_returns_false(self):
        self.assertFalse(rules.invalidate_receipt(self.run_dir, "00-requirements.md"))


# ---------------------------------------------------------------------------
# Stale-chain detection
# ---------------------------------------------------------------------------

class TestStaleChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = _setup_run(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _lock_and_receipt(self, phase: str) -> None:
        path = self.run_dir / phase
        _write(path, _locked_content(phase))
        rules.write_receipt(self.run_dir, phase, path)

    def test_no_stale_receipts_when_nothing_changed(self):
        self._lock_and_receipt("00-requirements.md")
        self._lock_and_receipt("00-worktree.md")
        stale = rules.get_all_stale_receipts(self.run_dir)
        self.assertEqual(stale, [])

    def test_stale_detected_after_upstream_content_change(self):
        req_path = self.run_dir / "00-requirements.md"
        wt_path = self.run_dir / "00-worktree.md"
        _write(req_path, _locked_content("00-requirements.md"))
        rules.write_receipt(self.run_dir, "00-requirements.md", req_path)
        _write(wt_path, _locked_content("00-worktree.md"))
        rules.write_receipt(self.run_dir, "00-worktree.md", wt_path)
        # Now mutate 00-requirements.md
        _write(req_path, _locked_content("00-requirements.md") + "\n<!-- mutated -->\n")
        stale = rules.get_all_stale_receipts(self.run_dir)
        stale_artifacts = [e["artifact"] for e in stale]
        self.assertIn("00-worktree.md", stale_artifacts)

    def test_get_stale_downstream_phases(self):
        req_path = self.run_dir / "00-requirements.md"
        wt_path = self.run_dir / "00-worktree.md"
        _write(req_path, _locked_content("00-requirements.md"))
        rules.write_receipt(self.run_dir, "00-requirements.md", req_path)
        _write(wt_path, _locked_content("00-worktree.md"))
        rules.write_receipt(self.run_dir, "00-worktree.md", wt_path)
        # Mutate requirements
        _write(req_path, _locked_content("00-requirements.md") + "\n<!-- changed -->\n")
        stale = rules.get_stale_downstream_phases("00-requirements.md", self.run_dir)
        self.assertTrue(any(e["artifact"] == "00-worktree.md" for e in stale))

    def test_no_stale_for_phase_with_no_receipt(self):
        # If a downstream phase has no receipt, it is not stale (not yet locked)
        req_path = self.run_dir / "00-requirements.md"
        _write(req_path, _locked_content("00-requirements.md"))
        rules.write_receipt(self.run_dir, "00-requirements.md", req_path)
        _write(req_path, _locked_content("00-requirements.md") + "\n<!-- changed -->\n")
        stale = rules.get_all_stale_receipts(self.run_dir)
        # requirements receipt itself has no prerequisites → not stale
        self.assertEqual(stale, [])


# ---------------------------------------------------------------------------
# End-to-end: prerequisite ordering through lock + receipt cycle
# ---------------------------------------------------------------------------

class TestEndToEndLockOrder(unittest.TestCase):
    """
    Smoke-level test that walks through locking a few phases in order and
    verifies that out-of-order attempts are blocked and that the receipt chain
    accurately detects staleness after a reopen/mutation.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = _setup_run(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _write_draft(self, phase: str) -> Path:
        path = self.run_dir / phase
        _write(path, _draft_content(phase))
        return path

    def _write_locked(self, phase: str) -> Path:
        path = self.run_dir / phase
        _write(path, _locked_content(phase))
        return path

    def _lock_with_receipt(self, phase: str) -> Path:
        path = self._write_locked(phase)
        rules.write_receipt(self.run_dir, phase, path)
        return path

    def test_forward_locking_succeeds(self):
        """Phase 00-requirements locked → 00-worktree has no blockers."""
        self._lock_with_receipt("00-requirements.md")
        blockers = rules.get_prerequisite_blockers("00-worktree.md", self.run_dir)
        self.assertEqual(blockers, [])

    def test_skipping_phase_creates_blocker(self):
        """Create 00-worktree DRAFT without locking 00-requirements → blocker."""
        self._write_draft("00-requirements.md")
        blockers = rules.get_prerequisite_blockers("00-worktree.md", self.run_dir)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["artifact"], "00-requirements.md")

    def test_backfill_all_drafts_blocks_later_phases(self):
        """Write all phases as DRAFT at once → each phase reports earlier DRAFT as blocker."""
        for phase in ["00-requirements.md", "00-worktree.md", "02-to-be-plan.md"]:
            self._write_draft(phase)
        # 02-to-be-plan should report both earlier drafts as blockers
        blockers = rules.get_prerequisite_blockers("02-to-be-plan.md", self.run_dir)
        blocker_names = [b["artifact"] for b in blockers]
        self.assertIn("00-requirements.md", blocker_names)
        self.assertIn("00-worktree.md", blocker_names)

    def test_stale_chain_after_upstream_reopen(self):
        """
        Lock 00-requirements → lock 00-worktree with receipt →
        then mutate 00-requirements → 00-worktree receipt becomes stale.
        """
        req_path = self._lock_with_receipt("00-requirements.md")
        wt_path = self._lock_with_receipt("00-worktree.md")
        # Simulate reopen/mutation of requirements
        _write(req_path, _draft_content("00-requirements.md"))
        rules.invalidate_receipt(self.run_dir, "00-requirements.md")
        stale = rules.get_all_stale_receipts(self.run_dir)
        # 00-worktree receipt still references old requirements hash
        stale_artifacts = [e["artifact"] for e in stale]
        self.assertIn("00-worktree.md", stale_artifacts)

    def test_next_legal_phase_advances_correctly(self):
        self.assertEqual(rules.get_next_legal_phase(self.run_dir), "00-requirements.md")
        self._lock_with_receipt("00-requirements.md")
        self.assertEqual(rules.get_next_legal_phase(self.run_dir), "00-worktree.md")
        self._lock_with_receipt("00-worktree.md")
        # Optional phases not present → next mandatory phase scan
        next_phase = rules.get_next_legal_phase(self.run_dir)
        # 01-as-is is optional and absent; 02-to-be-plan is optional and absent
        # next available unblocked phase is the first optional that would be unlocked
        # OR the mandatory 06-decisions-update (since optionals are absent)
        self.assertIsNotNone(next_phase)


if __name__ == "__main__":
    unittest.main()
