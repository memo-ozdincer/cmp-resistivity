import copy
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import daq_example
from event_handler import EventHandler, SampleError
from sensor_calibration import DEFAULT_PROFILE, load_profile, main, named_reading


class BothDiodes:
    def __init__(self, primary=1):
        self.primary = primary
    def get_V(self, channel=None):
        return {1: .43318815384615385, 2: .02808}[channel or self.primary]
    def get_T(self, channel=None):
        return 338.0  # Deliberately unverified instrument curve.


class SensorCalibrationTests(unittest.TestCase):
    def test_each_physical_sensor_gets_its_own_curve_endpoints(self):
        profile = load_profile()
        for channel, name, warm, cold in [(1, 'base_plate', 433.18815384615385, 981.166),
                                          (2, 'sample', 28.08, 619.0)]:
            for voltage, expected in [(warm, 296.65), (cold, 77), ((warm+cold)/2, 186.825)]:
                row = named_reading(profile, channel, voltage)
                self.assertAlmostEqual(row[f'{name}_temperature_calibrated_k'], expected)
                self.assertEqual(row[f'{name}_calibration_quality'], 'provisional_linear')

    def test_linear_extrapolation_and_invalid_voltage(self):
        profile = load_profile()
        for channel, name, voltage, warm, cold in [
                (1, 'base_plate', 431.594, 433.18815384615385, 981.166),
                (2, 'sample', 27.461, 28.08, 619.0),
                (2, 'sample', 693, 28.08, 619.0)]:
            row = named_reading(profile, channel, voltage)
            expected = 296.65 + (voltage-warm)*(77-296.65)/(cold-warm)
            self.assertAlmostEqual(row[f'{name}_temperature_calibrated_k'], expected)
            self.assertEqual(row[f'{name}_calibration_quality'], 'extrapolated')
        self.assertEqual(named_reading(profile, 2, float('nan'))['sample_calibration_quality'], 'invalid_voltage')

    def test_reversed_primary_and_raw_instrument_values_preserved(self):
        for primary, extra in [(1, 2), (2, 1)]:
            row = EventHandler(daq_example.SimulatedLockIn(), BothDiodes(primary),
                primary_channel=primary, extra_channels=[extra], calibration=load_profile()).sample(0)
            self.assertAlmostEqual(row['base_plate_temperature_calibrated_k'], 296.65)
            self.assertAlmostEqual(row['sample_temperature_calibrated_k'], 296.65)
            self.assertEqual(row['temperature_reported_k'], 338.)
            self.assertEqual(row[f'temperature_ch{extra}_reported_k'], 338.)
            self.assertAlmostEqual(row['sample_diode_voltage_mv'], 28.08)

    def test_partial_errors_keep_valid_sensor_temperature_and_missing_channel_is_blank(self):
        thermo = BothDiodes()
        with patch.object(thermo, 'get_T', side_effect=TimeoutError('lost temperature reply')):
            with self.assertRaises(SampleError) as error:
                EventHandler(None, thermo, calibration=load_profile(), extra_channels=[2]).sample(0)
        row = error.exception.row
        self.assertAlmostEqual(row['base_plate_temperature_calibrated_k'], 296.65)
        self.assertEqual(row['sample_temperature_calibrated_k'], '')
        self.assertEqual(row['sample_calibration_quality'], 'not_read')

    def test_offline_export_preserves_original_and_records_profile(self):
        with TemporaryDirectory() as directory:
            source = Path(directory)/'run.csv'
            source.write_text('diode_voltage_mv,diode_ch2_voltage_mv,temperature_reported_k\n981.166,619,116\n')
            before = source.read_bytes()
            self.assertEqual(main([str(source), '--primary-channel', '1']), 0)
            output = source.with_name('run.sensors.calibrated.csv')
            with output.open() as stream:
                row = next(csv.DictReader(stream))
            self.assertAlmostEqual(float(row['sample_temperature_calibrated_k']), 77)
            self.assertAlmostEqual(float(row['base_plate_temperature_calibrated_k']), 77)
            self.assertEqual(row['temperature_reported_k'], '116')
            self.assertEqual(source.read_bytes(), before)
            metadata = json.loads(output.with_suffix('.csv.calibration.json').read_text())
            self.assertEqual(metadata['profile']['sensors']['sample']['warm']['voltage_mv'], 28.08)
            with self.assertRaises(SystemExit):
                main([str(source), '--primary-channel', '1'])

    def test_invalid_profile_rejected_and_live_cli_defaults_to_saved_profile(self):
        with TemporaryDirectory() as directory:
            invalid = Path(directory)/'invalid.json'
            profile = copy.deepcopy(load_profile())
            profile['sensors']['sample']['channel'] = 1
            invalid.write_text(json.dumps(profile))
            with self.assertRaises(ValueError):
                load_profile(invalid)
            output = Path(directory)/'SIMULATED.csv'
            self.assertEqual(daq_example.main(['--simulate', '--duration', '.001', '--extra-channels', '2',
                                              '--output', str(output)]), 0)
            metadata = json.loads(output.with_suffix('.csv.json').read_text())
            self.assertEqual(metadata['schema_version'], 3)
            self.assertEqual(metadata['sensor_calibration']['profile']['id'], load_profile()['id'])
            self.assertEqual(metadata['arguments']['sensor_name'], 'base_plate')

    def test_live_csv_can_be_recalibrated_to_new_file_without_changing_source(self):
        with TemporaryDirectory() as directory:
            source = Path(directory)/'live.csv'
            source.write_text('diode_voltage_mv,diode_ch2_voltage_mv,sample_temperature_calibrated_k\n981.166,619,999\n')
            before = source.read_bytes()
            self.assertEqual(main([str(source), '--primary-channel', '1']), 0)
            with source.with_name('live.sensors.calibrated.csv').open() as stream:
                row = next(csv.DictReader(stream))
            self.assertAlmostEqual(float(row['sample_temperature_calibrated_k']), 77)
            self.assertEqual(source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
