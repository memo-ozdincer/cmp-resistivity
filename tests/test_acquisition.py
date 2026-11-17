import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from daq_example import SimulatedLockIn, SimulatedThermo
from event_handler import EventHandler, SampleError
from lockin_7270 import LockIn7270, SerialLockIn7270
from sim922 import SIM922
from temp_calibration import fit_two_points, temperature_from_mv


class FakeUSB:
    def __init__(self, packets):
        self.packets = iter(packets)
        self.writes = []
    def write(self, endpoint, data, timeout):
        self.writes.append(bytes(data))
    def read(self, endpoint, size, timeout):
        return next(self.packets)


def fake_lockin(packets, terminator='status'):
    lockin = object.__new__(LockIn7270)
    lockin.dev = FakeUSB(packets)
    lockin.ep_out = SimpleNamespace(bEndpointAddress=1)
    lockin.ep_in = SimpleNamespace(bEndpointAddress=129, wMaxPacketSize=64)
    lockin.timeout_ms = 1000
    lockin.terminator = terminator
    lockin.last_status = lockin.last_overload = None
    return lockin


class ProtocolTests(unittest.TestCase):
    def test_serial_echo_handshake_and_status_prompt(self):
        class FakeSerial:
            def __init__(self):
                self.incoming = bytearray()
                self.command = bytearray()
            def write(self, data):
                self.incoming.extend(data)  # Byte-by-byte echo.
                if data == b'\r':
                    reply = {b'X.': b'0.0016\r\n?',
                             b'ST': b'65\r\n?', b'N': b'0\r\n*'}[bytes(self.command)]
                    self.incoming.extend(reply)
                    self.command.clear()
                else:
                    self.command.extend(data)
            def read(self, count):
                if not self.incoming:
                    return b''
                result = bytes(self.incoming[:count])
                del self.incoming[:count]
                return result
        lockin = object.__new__(SerialLockIn7270)
        lockin.serial = FakeSerial()
        lockin.echo = True
        lockin.timeout_ms = 1000
        self.assertEqual(lockin.get_x(), 0.0016)
        self.assertEqual(lockin.last_status, 65)
        self.assertEqual(lockin.last_overload, 0)

    def test_split_binary_trailer_and_next_query(self):
        lockin = fake_lockin([b'-1.6E-3\0', b'\x01', b'\x00', b'1E-4\0\x01\x00'])
        self.assertEqual(lockin.get_x(), -0.0016)
        self.assertEqual(lockin.get_y(), 0.0001)
        self.assertEqual(lockin.dev.writes, [b'X.\0', b'Y.\0'])
        self.assertEqual(lockin.last_overload, 0)

    def test_set_command_ack_is_consumed(self):
        lockin = fake_lockin([b'\0\x01\x00', b'0.01\0\x01\x00'])
        lockin.send('TC 12')
        self.assertEqual(lockin.get_x(), 0.01)

    def test_rejected_command_is_not_silenced(self):
        lockin = fake_lockin([b'\0\x03\x00'])
        with self.assertRaisesRegex(RuntimeError, 'rejected'):
            lockin.query('BAD')

    def test_null_only_and_nonfinite(self):
        lockin = fake_lockin([b'1.25\0'], 'null')
        self.assertEqual(lockin.get_x(), 1.25)
        self.assertIsNone(lockin.last_status)
        with self.assertRaises(RuntimeError):
            fake_lockin([b'nan\0\x01\x00']).get_x()

    def test_serial_crlf_and_volts(self):
        chars = iter(bytes([byte]) for byte in b'\n0.4316\r\n')
        fake = SimpleNamespace(timeout=1, port='fake', send=lambda cmd: None,
                               read=lambda n: next(chars, b''))
        self.assertEqual(SIM922.send_receive(fake, 'VOLT? 1'), b'0.4316')
        fake = SimpleNamespace(channel=1, _number=lambda command: 0.4316)
        self.assertEqual(SIM922.get_V(fake), 0.4316)


class AcquisitionTests(unittest.TestCase):
    def test_temperature_only_has_no_invented_lockin_values(self):
        row = EventHandler(None, SimulatedThermo()).sample(0)
        self.assertEqual(row['quality'], 'temperature_only')
        self.assertAlmostEqual(row['diode_voltage_mv'], 431.6, delta=0.02)
        self.assertEqual(row['lockin_x_v'], '')
        self.assertEqual(row['resistance_ohm'], '')

    def test_voltage_current_geometry_and_temperature_label(self):
        handler = EventHandler(SimulatedLockIn(), SimulatedThermo(),
            current_a=0.001, voltage_component='x', area_m2=1e-6,
            length_m=0.01, voltage_gain=2)
        row = handler.sample(0)
        self.assertAlmostEqual(row['resistance_ohm'], 0.8)
        self.assertAlmostEqual(row['resistivity_ohm_m'], 8e-5)
        self.assertEqual(row['temperature_reported_k'], 336.1)
        self.assertAlmostEqual(row['diode_voltage_mv'], 431.6, delta=0.02)
        self.assertEqual(row['temperature_calibration'], 'unverified_instrument_curve')

    def test_unknown_current_leaves_derived_values_blank(self):
        row = EventHandler(SimulatedLockIn(), SimulatedThermo()).sample(0)
        self.assertEqual(row['resistance_ohm'], '')
        self.assertEqual(row['resistivity_ohm_m'], '')

    def test_overload_prevents_derived_values(self):
        lockin = SimulatedLockIn()
        lockin.last_status = 0x41
        row = EventHandler(lockin, SimulatedThermo(), current_a=0.001,
                           voltage_component='x').sample(0)
        self.assertIn('overload', row['quality'])
        self.assertEqual(row['resistance_ohm'], '')
        self.assertEqual(row['lockin_x_v'], 0.0016)

    def test_completed_and_partial_rows_survive_disconnect(self):
        class FailingThermo(SimulatedThermo):
            calls = 0
            def get_T(self):
                self.calls += 1
                if self.calls > 1:
                    raise TimeoutError('disconnected')
                return super().get_T()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'run.csv'
            handler = EventHandler(SimulatedLockIn(), FailingThermo())
            with self.assertRaises(SampleError):
                handler.run(path, duration=1, sample_period=0.001)
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['quality'], 'ok')
            self.assertEqual(rows[1]['quality'], 'error')
            self.assertNotEqual(rows[1]['diode_voltage_mv'], '')
            self.assertEqual(rows[1]['lockin_x_v'], '')
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                handler.run(path, duration=0.01, sample_period=0.01)
            self.assertEqual(path.read_bytes(), before)

    def test_interrupt_during_sample_preserves_partial_row(self):
        class InterruptedThermo(SimulatedThermo):
            def get_T(self):
                raise KeyboardInterrupt
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'run.csv'
            with self.assertRaises(KeyboardInterrupt):
                EventHandler(SimulatedLockIn(), InterruptedThermo()).run(path)
            with path.open() as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row['quality'], 'interrupted')
            self.assertNotEqual(row['diode_voltage_mv'], '')

    def test_bad_configuration_rejected(self):
        for options in ({'current_a': 0}, {'area_m2': 1},
                        {'current_a': 1}, {'voltage_gain': float('nan')},
                        {'area_m2': 1, 'length_m': 1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                EventHandler(None, None, **options)

    def test_two_point_calibration_and_degenerate_points(self):
        points = ((299.35, 431.6), (100.0, 900.0))
        params = fit_two_points(*points)
        for temperature, voltage in points:
            self.assertAlmostEqual(temperature_from_mv(voltage, *params), temperature)
        with self.assertRaises(ValueError):
            fit_two_points(points[0], points[0])


if __name__ == '__main__':
    unittest.main()
