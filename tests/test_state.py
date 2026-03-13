#!/usr/bin/env python3
"""Tests for DEFCON state management — persistence and transitions."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

sys.modules["tweepy"] = MagicMock()

from lib import config, state
from lib.state import save_state, load_state


class TestStatePersistence(unittest.TestCase):
    """Test save_state() and load_state()."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.tmpfile.close()
        self._orig = config.STATE_FILE
        config.STATE_FILE = self.tmpfile.name

    def tearDown(self):
        config.STATE_FILE = self._orig
        try:
            os.unlink(self.tmpfile.name)
        except OSError:
            pass

    def test_save_and_load_idle(self):
        save_state("idle")
        self.assertEqual(load_state(), "idle")

    def test_save_and_load_defcon2(self):
        save_state("defcon2")
        self.assertEqual(load_state(), "defcon2")

    def test_save_and_load_defcon4(self):
        save_state("defcon4")
        self.assertEqual(load_state(), "defcon4")

    def test_load_missing_file_returns_idle(self):
        config.STATE_FILE = "/tmp/nonexistent-test-state-file"
        self.assertEqual(load_state(), "idle")


class TestAtomicStateWrite(unittest.TestCase):
    """save_state must use atomic write (temp file + rename) to prevent corruption."""

    def test_save_state_is_atomic(self):
        """save_state should write to a temp file and rename, not write directly."""
        path = os.path.join(_root, "lib", "state.py")
        with open(path) as f:
            source = f.read()
        fn_start = source.find("def save_state(")
        fn_end = source.find("\ndef ", fn_start + 1)
        if fn_end == -1:
            fn_end = len(source)
        fn_body = source[fn_start:fn_end]
        has_atomic = "os.replace(" in fn_body or "os.rename(" in fn_body
        self.assertTrue(has_atomic,
                        "save_state writes directly to state file — "
                        "should use temp file + os.replace for atomicity")


class TestStateMachine(unittest.TestCase):
    """Test state transitions in main loop logic."""

    def setUp(self):
        self.state_file = tempfile.NamedTemporaryFile(delete=False)
        self.state_file.close()
        self._orig_state = config.STATE_FILE
        config.STATE_FILE = self.state_file.name

    def tearDown(self):
        config.STATE_FILE = self._orig_state
        try:
            os.unlink(self.state_file.name)
        except OSError:
            pass

    def _run_one_cycle(self, result):
        """Simulate one iteration of the main loop's state handling."""
        if result == "ended":
            if state.state != "idle":
                state.state = "idle"
                save_state("idle")
        elif result == "preemptive":
            if state.state == "idle":
                state.state = "defcon4"
                save_state("defcon4")
        elif result == "actual":
            if state.state in ("idle", "defcon4"):
                state.state = "defcon2"
                save_state("defcon2")

    def test_idle_to_defcon4(self):
        state.state = "idle"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon4")
        self.assertEqual(load_state(), "defcon4")

    def test_idle_to_defcon2(self):
        state.state = "idle"
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")
        self.assertEqual(load_state(), "defcon2")

    def test_defcon4_to_defcon2(self):
        state.state = "defcon4"
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")

    def test_defcon2_to_idle_on_ended(self):
        state.state = "defcon2"
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")
        self.assertEqual(load_state(), "idle")

    def test_defcon4_to_idle_on_ended(self):
        state.state = "defcon4"
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")

    def test_idle_stays_idle_on_ended(self):
        state.state = "idle"
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")

    def test_idle_stays_idle_on_none(self):
        state.state = "idle"
        self._run_one_cycle(None)
        self.assertEqual(state.state, "idle")

    def test_defcon2_ignores_preemptive(self):
        """Once in DEFCON 2, preemptive alerts should not change state."""
        state.state = "defcon2"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon2")

    def test_defcon2_ignores_repeated_actual(self):
        """Already in DEFCON 2, another actual should not re-trigger."""
        state.state = "defcon2"
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")

    def test_defcon4_ignores_repeated_preemptive(self):
        """Already in DEFCON 4, repeated preemptive should not re-trigger."""
        state.state = "defcon4"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon4")

    def test_full_cycle_idle_defcon4_defcon2_idle(self):
        state.state = "idle"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon4")
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")


class TestStateResume(unittest.TestCase):
    """Test that startup correctly resumes from persisted state."""

    def setUp(self):
        self.state_file = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.state_file.close()
        self._orig = config.STATE_FILE
        config.STATE_FILE = self.state_file.name

    def tearDown(self):
        config.STATE_FILE = self._orig
        try:
            os.unlink(self.state_file.name)
        except OSError:
            pass

    def test_resumes_defcon2(self):
        save_state("defcon2")
        self.assertEqual(load_state(), "defcon2")

    def test_resumes_defcon4(self):
        save_state("defcon4")
        self.assertEqual(load_state(), "defcon4")

    def test_unknown_state_treated_as_idle(self):
        """The main() function treats unknown states as idle."""
        save_state("bogus")
        loaded = load_state()
        self.assertNotIn(loaded, ("defcon2", "defcon4"))


if __name__ == "__main__":
    unittest.main()
