import csv
import ctypes
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import calibrate_run
import daq_example
from event_handler import EventHandler
from mark_run import main as mark
from run_support import keep_awake, write_metadata


class Clock:
    def __init__(self):
        self.value = 0.0
    def monotonic(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class LongRunTests(unittest.TestCase):
    def test_six_hours_deadline_schedule_and_row_count_without_waiting(self):
        clock = Clock()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'long.csv'
            handler = EventHandler(daq_example.SimulatedLockIn(), daq_example.SimulatedThermo())
            original = handler.sample
            def slow_sample(start):
                row = original(start)
                clock.value += 0.4  # Query latency must not accumulate into period.
                return row
            with patch('event_handler.time.monotonic', clock.monotonic), patch(
                    'event_handler.time.sleep', clock.sleep), patch(
                    'event_handler.os.fsync'), patch.object(handler, 'sample', slow_sample):
                count = handler.run(path, duration=6 * 3600, sample_period=10)
            self.assertEqual(count, 2160)
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[-1]['sample_index'], '2159')
            self.assertAlmostEqual(float(rows[-1]['elapsed_s']), 21590)
            self.assertEqual(clock.value, 21600)

    def test_extra_channels_and_raw_units(self):
        handler = EventHandler(daq_example.SimulatedLockIn(), daq_example.SimulatedThermo(), extra_channels=(2, 3))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'extra.csv'
            handler.run(path, duration=0.01, sample_period=0.01)
            with path.open() as stream:
                row = next(csv.DictReader(stream))
            self.assertAlmostEqual(float(row['diode_ch2_voltage_mv']), 431.6, delta=0.02)
            self.assertEqual(row['temperature_ch3_reported_k'], '336.1')

    def test_continuous_cli_interrupt_updates_metadata_and_restores_output(self):
        original = EventHandler.sample
        count = 0
        def interrupted_sample(handler, start):
            nonlocal count
            count += 1
            if count == 3:
                # Inject Ctrl-C from a device read so its partial row is recorded.
                with patch.object(handler.thermo, 'get_T', side_effect=KeyboardInterrupt):
                    return original(handler, start)
            return original(handler, start)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'continuous.csv'
            with patch.object(EventHandler, 'sample', interrupted_sample):
                code = daq_example.main(['--simulate', '--continuous', '--period', '0.01', '--output', str(path)])
            self.assertEqual(code, 130)
            metadata = json.loads(path.with_suffix('.csv.json').read_text())
            self.assertEqual(metadata['status'], 'interrupted')
            self.assertEqual(metadata['rows'], 3)
            self.assertEqual(metadata['last_quality'], 'interrupted')
            before = path.read_bytes()
            with self.assertRaises(SystemExit):
                daq_example.main(['--simulate', '--output', str(path)])
            self.assertEqual(before, path.read_bytes())

    def test_metadata_replacement_failure_preserves_old_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'metadata.json'
            write_metadata(path, {'rows': 10})
            with patch('run_support.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    write_metadata(path, {'rows': 20})
            self.assertEqual(json.loads(path.read_text()), {'rows': 10})
            self.assertFalse(path.with_name(path.name + '.tmp').exists())

    def test_windows_keep_awake_restored_after_exception(self):
        calls = []
        def execution_state(flags):
            calls.append(flags)
            return 0x80000000
        fake = SimpleNamespace(kernel32=SimpleNamespace(SetThreadExecutionState=execution_state))
        with patch('run_support.sys.platform', 'win32'), patch.object(ctypes, 'windll', fake, create=True):
            with self.assertRaises(ValueError):
                with keep_awake() as active:
                    self.assertTrue(active)
                    raise ValueError('experiment stopped')
        self.assertEqual(calls, [0x80000001, 0x80000000])


class CalibrationWorkflowTests(unittest.TestCase):
    def fixture(self, directory):
        path = Path(directory) / 'run.csv'
        origin = datetime(2026, 11, 24, tzinfo=timezone.utc)
        fields = ['timestamp_utc', 'quality', 'diode_voltage_mv', 'simulated']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for index, value in enumerate([400, 400, 400, 650, 900, 900, 900, 950]):
                writer.writerow(dict(timestamp_utc=(origin + timedelta(seconds=index)).isoformat(),
                                     quality='ok', diode_voltage_mv=value, simulated=True))
        path.with_suffix('.csv.json').write_text(json.dumps(
            {'arguments': {'channel': 1}, 'simulated': True}))
        events = []
        for label, seconds in [('warm-start', 0), ('warm-end', 2), ('cold-start', 4), ('cold-end', 6)]:
            events.append({'label': label, 'timestamp_utc': (origin + timedelta(seconds=seconds)).isoformat()})
        path.with_suffix('.csv.events.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
        return path

    def test_full_export_preserves_raw_and_reference_endpoints(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(directory)
            before = path.read_bytes()
            arguments = [str(path), '--warm-c', '26.85', '--cold-k', '100', '--model', 'linear']
            self.assertEqual(calibrate_run.main(arguments), 0)
            self.assertEqual(before, path.read_bytes())
            output = path.with_name('run.ch1.calibrated.csv')
            with output.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertAlmostEqual(float(rows[0]['temperature_calibrated_k']), 300)
            self.assertAlmostEqual(float(rows[4]['temperature_calibrated_k']), 100)
            self.assertEqual(rows[-1]['temperature_calibrated_k'], '')
            self.assertEqual(rows[-1]['calibration_quality'], 'outside_reference_range')
            summary = json.loads(output.with_suffix('.csv.calibration.json').read_text())
            self.assertTrue(summary['simulated'])
            self.assertEqual(summary['warm']['count'], 3)
            with self.assertRaises(SystemExit):
                calibrate_run.main(arguments)

    def test_fixed_log_coefficient_recovers_synthetic_model(self):
        c1, c2, c3 = 1200, 2.5, 0.405
        def voltage(t):
            return c1 - c2*t - c3*math.log(t)
        params = calibrate_run.coefficients(300, voltage(300), 77, voltage(77), c3)
        recovered, flag = calibrate_run.convert_voltage(voltage(150), params, 77, 300)
        self.assertAlmostEqual(recovered, 150)
        self.assertEqual(flag, 'within_reference_range')

    def test_missing_markers_and_free_three_parameter_fit_rejected(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(directory)
            with self.assertRaises(SystemExit):
                calibrate_run.main([str(path), '--warm-c', '22.2', '--cold-k', '77', '--model', 'log-fixed'])
            path.with_suffix('.csv.events.jsonl').write_text('')
            with self.assertRaises(SystemExit):
                calibrate_run.main([str(path), '--warm-c', '22.2', '--cold-k', '77', '--model', 'linear'])

    def test_event_appending_preserves_existing_run(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'run.csv'
            path.write_text('raw content\n')
            mark([str(path), 'heating-start', '--note', 'heater setting noted'])
            mark([str(path), 'current-check', '--note', '39.5 mV'])
            self.assertEqual(path.read_text(), 'raw content\n')
            events = [json.loads(line) for line in path.with_suffix('.csv.events.jsonl').read_text().splitlines()]
            self.assertEqual([event['label'] for event in events], ['heating-start', 'current-check'])
            self.assertIsNotNone(datetime.fromisoformat(events[0]['timestamp_utc']).tzinfo)


if __name__ == '__main__':
    unittest.main()
