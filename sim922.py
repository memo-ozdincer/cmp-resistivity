"""Four-channel SIM922 readout via SIM900; preserves sensor settings.

VOLT? returns volts (verified against the mV front panel on this lab's SIM922).
get_T() returns the instrument's unverified temperature.
"""
import math
import time
import serial
from serial.tools import list_ports


def discover_port():
    ports = [p.device for p in list_ports.comports() if p.vid is not None]
    if len(ports) != 1:
        raise RuntimeError(f'Expected one USB serial adapter; found {ports}. '
                           'Connect the SIM900 or supply --port explicitly.')
    return ports[0]


class SIM922(serial.Serial):
    def __init__(self, port=None, module_no=7, term_string='xxyyzz',
                 baud=9600, timeout=2.0, channel=1):
        if module_no not in range(1, 9) or channel not in range(1, 5):
            raise ValueError('Module must be 1–8 and channel must be 1–4.')
        if not term_string.isalnum() or len(term_string) > 8:
            raise ValueError('Escape string must contain 1–8 alphanumeric characters.')
        self._term_string = term_string
        self._connected_to_module = False
        self.channel = channel
        super().__init__(port or discover_port(), baud, timeout=timeout,
                         write_timeout=timeout)
        try:
            try:
                identity = self.send_receive('*IDN?')
            except TimeoutError:
                # Recover a pass-through left open by this lab's original driver.
                self.send(self._term_string)
                time.sleep(0.1)
                self.reset_input_buffer()
                identity = self.send_receive('*IDN?')
            self.mainframe_id = identity.decode('ascii').strip()
            if 'SIM900' not in self.mainframe_id:
                raise RuntimeError(f'Expected SIM900; received {self.mainframe_id!r}.')
            self.send(f'CONN {module_no}, "{self._term_string}"')
            self._connected_to_module = True
            time.sleep(0.1)
            self.identity = self.send_receive('*IDN?').decode('ascii').strip()
            if self.identity.split(',')[1:2] != ['SIM922']:
                raise RuntimeError(f'Slot {module_no}: expected SIM922, got {self.identity!r}.')
        except BaseException:
            self.close()
            raise

    def send(self, command):
        self.write(self.sanitize(command))
        self.flush()

    def send_receive(self, command):
        self.send(command)
        deadline = time.monotonic() + self.timeout
        reply = bytearray()
        while time.monotonic() < deadline:
            char = self.read(1)
            if char in (b'\r', b'\n'):
                if reply:
                    return bytes(reply)
            elif char:
                reply.extend(char)
                if len(reply) > 4096:
                    raise RuntimeError(f'Oversized SIM922 reply to {command!r}.')
        raise TimeoutError(f'No complete reply to {command!r} on {self.port}; '
                           'check cable, baud rate, and module slot.')

    def _number(self, command):
        reply = self.send_receive(command)
        try:
            value = float(reply)
        except ValueError as exc:
            raise RuntimeError(f'Invalid SIM922 reply to {command}: {reply!r}') from exc
        if not math.isfinite(value):
            raise RuntimeError(f'Non-finite SIM922 reply to {command}: {reply!r}')
        return value

    def get_T(self, channel=None):
        channel = self.channel if channel is None else channel
        if channel not in range(1, 5):
            raise ValueError('Channel must be 1–4.')
        return self._number(f'TVAL? {channel}')

    def get_V(self, channel=None):
        """Return diode voltage in volts; multiply by 1000 for front-panel mV."""
        channel = self.channel if channel is None else channel
        if channel not in range(1, 5):
            raise ValueError('Channel must be 1–4.')
        return self._number(f'VOLT? {channel}')

    def get_curve(self):
        return self.send_receive(f'CURV? {self.channel}').decode('ascii').strip()

    def get_excitation(self):
        return self.send_receive(f'EXON? {self.channel}').decode('ascii').strip()

    def send_list(self, commands):
        for command in commands:
            self.send(command)

    def send_receive_list(self, commands):
        return [self.send_receive(command) for command in commands]

    @staticmethod
    def sanitize(command):
        if isinstance(command, str):
            command = command.encode('ascii')
        return command.strip() + b'\r\n'

    def close(self):
        try:
            if self.is_open and self._connected_to_module:
                self.send(self._term_string)
        finally:
            self._connected_to_module = False
            super().close()
