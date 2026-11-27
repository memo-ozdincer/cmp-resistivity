import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from daq_example import SimulatedLockIn, SimulatedThermo
from event_handler import EventHandler
from lockin_recovery import RecoveringLockIn, LockInCommunicationError


class Device(SimulatedLockIn):
    def __init__(self, fail=False, settings=None):
        self.fail, self.closed = fail, False
        self.settings = settings or {'SEN.': 0.5}
    def get_settings(self):
        return self.settings
    def close(self):
        self.closed = True
    def get_y(self):
        if self.fail:
            raise TimeoutError('Y timed out')
        return super().get_y()


class RecoveryTests(unittest.TestCase):
    def test_lost_y_not_replayed_and_settings_checked_before_resuming(self):
        initial, replacement = Device(fail=True), Device()
        recovery = RecoveringLockIn(initial, lambda: replacement, {'SEN.': 0.5})
        handler = EventHandler(recovery, SimulatedThermo())
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'run.csv'
            def saved(row):
                recovery.next_attempt = 0
            handler.run(path, duration=.025, sample_period=.01, on_sample=saved)
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['quality'], 'lockin_unavailable')
        self.assertNotEqual(rows[0]['diode_voltage_mv'], '')
        self.assertEqual(rows[0]['lockin_y_v'], '')
        self.assertEqual(rows[0]['resistance_ohm'], '')
        self.assertEqual(rows[-1]['quality'], 'ok')
        self.assertTrue(initial.closed)
        self.assertEqual(recovery.reconnections, 1)

    def test_changed_settings_refuse_resume_and_close_candidate(self):
        initial, changed = Device(fail=True), Device(settings={'SEN.': .1})
        recovery = RecoveringLockIn(initial, lambda: changed, {'SEN.': .5})
        with self.assertRaises(LockInCommunicationError):
            recovery.get_y()
        recovery.next_attempt = 0
        with self.assertRaisesRegex(LockInCommunicationError, 'settings changed'):
            recovery.get_x()
        self.assertTrue(changed.closed)
        self.assertEqual(recovery.reconnections, 0)

    def test_backoff_does_not_reconnect_every_sample(self):
        initial = Device(fail=True)
        with patch('lockin_recovery.time.monotonic', return_value=100):
            attempts = []
            recovery = RecoveringLockIn(initial, lambda: attempts.append(True), {'SEN.': .5})
            with self.assertRaises(LockInCommunicationError):
                recovery.get_y()
            with self.assertRaises(LockInCommunicationError):
                recovery.get_x()
            self.assertEqual(attempts, [])
