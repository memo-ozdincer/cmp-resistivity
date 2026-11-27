"""Bounded front-panel USB queries for the Signal Recovery 7270.

Connection preserves instrument settings. set_up() must be called explicitly.
The old unverified high-speed curve code is preserved in backups/original.
"""
import math
import time
from pathlib import Path
import usb.core
import usb.util
import usb.backend.libusb1

SETUP_CMDS = {
    'REFMODE': 0, 'IMODE': 0, 'VMODE': 3, 'IE': 0,
    'DCCOUPLE': 0, 'FLOAT': 1, 'TC': 12, 'FET': 0,
}


def usb_backend():
    backend = usb.backend.libusb1.get_backend()
    if backend is None:
        try:
            import libusb_package
            backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
        except ImportError:
            pass
    if backend is None:
        for path in ('/opt/homebrew/lib/libusb-1.0.dylib', '/usr/local/lib/libusb-1.0.dylib'):
            if Path(path).exists():
                backend = usb.backend.libusb1.get_backend(find_library=lambda _: path)
                if backend is not None:
                    break
    if backend is None:
        raise RuntimeError('libusb is missing. Run uv sync (Windows DLL included); '
                           'on macOS: brew install libusb. See docs/windows-setup.md.')
    return backend


class LockIn7270:
    ID_VENDOR = 2605
    ID_PRODUCT = 27

    def __init__(self, cmds=None, timeout_ms=2000, terminator='status', drain_before_identity=False):
        if terminator not in ('status', 'null'):
            raise ValueError('terminator must be status or null')
        self.timeout_ms = timeout_ms
        self.terminator = terminator
        self.parameters = dict(SETUP_CMDS if cmds is None else cmds)
        self.last_status = self.last_overload = None
        self.dev = None
        devices = list(usb.core.find(find_all=True, idVendor=self.ID_VENDOR,
                                    idProduct=self.ID_PRODUCT, backend=usb_backend()))
        if len(devices) != 1:
            raise RuntimeError(f'Expected one 7270 USB device; found {len(devices)}. '
                               'Connect its rear USB port to this computer.')
        self.dev = devices[0]
        try:
            interface = self.dev.get_active_configuration()[(0, 0)]
            self.ep_in = usb.util.find_descriptor(interface, custom_match=lambda e:
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK)
            self.ep_out = usb.util.find_descriptor(interface, custom_match=lambda e:
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK)
            if self.ep_in is None or self.ep_out is None:
                raise RuntimeError('7270 bulk USB endpoints were not found.')
            if drain_before_identity:
                # A timed-out response may still be queued. Never use it as a new reading.
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    try:
                        self.dev.read(self.ep_in.bEndpointAddress, self.ep_in.wMaxPacketSize,
                                      timeout=250)
                    except usb.core.USBTimeoutError:
                        break
                else:
                    raise RuntimeError('USB input did not become quiet; refusing to reconnect.')
            self.identity = self.query_safe('ID')
            if self.identity != '7270':
                raise RuntimeError(f'Unexpected lock-in identity: {self.identity!r}')
        except BaseException:
            self.close()
            raise

    def query_safe(self, command):
        """Consume the entire response, including its binary status trailer."""
        if any(c in command for c in '\0\n\r'):
            raise ValueError('Send a command without terminators.')
        self.dev.write(self.ep_out.bEndpointAddress,
                       command.encode('ascii') + b'\0', timeout=self.timeout_ms)
        response = bytearray()
        deadline = time.monotonic() + self.timeout_ms / 1000
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'Incomplete 7270 reply to {command!r}; '
                                   'check --usb-terminator against the USB Status menu.')
            try:
                response.extend(self.dev.read(self.ep_in.bEndpointAddress,
                    self.ep_in.wMaxPacketSize, timeout=max(1, int(remaining * 1000))))
            except usb.core.USBTimeoutError as exc:
                detail = ('No response bytes were received.' if not response else
                          f'Received {len(response)} bytes before timeout; '
                          f'prefix={bytes(response[:32])!r}.')
                raise TimeoutError(f'7270 timed out on {command!r}. '
                                   f'{detail} Timeout={self.timeout_ms} ms. '
                                   'Stop other instrument software, return the front panel to '
                                   'Main Display, and check the USB connection. '
                                   'Change --usb-terminator only to match its USB menu.') from exc
            if len(response) > 65536:
                raise RuntimeError('Oversized 7270 response.')
            end = response.find(0)
            trailer_length = 3 if self.terminator == 'status' else 1
            if end >= 0 and len(response) >= end + trailer_length:
                if len(response) != end + trailer_length:
                    raise RuntimeError('Unexpected extra bytes in 7270 reply; '
                                       'check --usb-terminator and reconnect.')
                if self.terminator == 'status':
                    self.last_status, self.last_overload = response[end + 1:end + 3]
                    if self.last_status & 0x06:
                        raise RuntimeError(f'7270 rejected {command!r}: '
                                           f'status=0x{self.last_status:02x}')
                else:
                    self.last_status = self.last_overload = None
                return response[:end].decode('ascii').strip()

    def query(self, command, silent=True):
        result = self.query_safe(command)
        if not silent:
            print(result)
        return result

    def send(self, command):
        # Set commands also return a trailer; consume it before the next query.
        self.query_safe(command)

    def send_list(self, commands):
        for command in commands:
            self.send(command)

    def set_up(self):
        """Apply legacy defaults explicitly; review wiring before calling."""
        self.send_list(f'{key} {value}' for key, value in self.parameters.items())
        self.send('AS')

    def _get_float(self, command):
        value = float(self.query_safe(command))
        if not math.isfinite(value):
            raise RuntimeError(f'Non-finite 7270 response to {command!r}.')
        return value

    def get_x(self):
        return self._get_float('X.')

    def get_y(self):
        return self._get_float('Y.')

    def get_magnitude(self):
        return self._get_float('MAG.')

    def get_phase(self):
        return self._get_float('PHA.')

    def get_settings(self):
        return {cmd: self.query_safe(cmd) for cmd in
                ('REFMODE', 'IMODE', 'VMODE', 'IE', 'DCCOUPLE', 'FLOAT',
                 'REFP.', 'TC.', 'SEN.', 'OF.', 'OA.')}

    def close(self):
        if self.dev is not None:
            usb.util.dispose_resources(self.dev)
            self.dev = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class SerialLockIn7270(LockIn7270):
    """7270 via USB-to-RS232. Match baud/data/parity/echo to the front panel.

    The RS232 prompt must be enabled. No instrument settings are changed.
    """
    def __init__(self, port, baud=9600, data_bits=7, parity='E', echo=True,
                 timeout_ms=2000):
        import serial
        self.timeout_ms = timeout_ms
        self.parameters = dict(SETUP_CMDS)
        self.last_status = self.last_overload = None
        self.echo = echo
        self.dev = None
        self.serial = serial.Serial(port, baudrate=baud, bytesize=data_bits,
                                    parity=parity, timeout=0.05,
                                    write_timeout=timeout_ms / 1000)
        try:
            self.identity = self.query_safe('ID')
            if self.identity != '7270':
                raise RuntimeError(f'Expected 7270; received {self.identity!r}.')
        except BaseException:
            self.close()
            raise

    def _exchange(self, command):
        if any(c in command for c in '\0\r\n'):
            raise ValueError('Send a command without terminators.')
        deadline = time.monotonic() + self.timeout_ms / 1000

        def read_byte():
            while time.monotonic() < deadline:
                char = self.serial.read(1)
                if char:
                    return char
            raise TimeoutError(f'7270 serial timeout on {command!r}; check baud, '
                               'data bits, parity, echo, and enable RS232 prompts.')

        payload = command.encode('ascii') + b'\r'
        if self.echo:
            for value in payload:
                expected = bytes([value])
                self.serial.write(expected)
                actual = read_byte()
                # A previous response may leave an LF after its prompt.
                while expected not in (b'\r', b'\n') and actual in (b'\r', b'\n'):
                    actual = read_byte()
                if actual != expected:
                    raise RuntimeError(f'7270 serial echo mismatch: {actual!r} != {expected!r}. '
                                       'Check RS232 settings or use --lockin-no-echo.')
        else:
            # Without echo, pace characters so the device can process each byte.
            for value in payload:
                self.serial.write(bytes([value]))
                time.sleep(0.01)
        response = bytearray()
        while True:
            char = read_byte()
            if char in (b'*', b'?'):
                return response.decode('ascii').strip(), char
            response.extend(char)
            if len(response) > 4096:
                raise RuntimeError('Oversized 7270 serial response.')

    def query_safe(self, command):
        response, prompt = self._exchange(command)
        self.last_status, self.last_overload = 1, 0
        if prompt == b'?':
            status, _ = self._exchange('ST')
            self.last_status = int(status)
            overload, _ = self._exchange('N')
            self.last_overload = int(overload)
            if self.last_status & 0x06:
                raise RuntimeError(f'7270 rejected {command!r}: status={self.last_status}')
        return response

    def close(self):
        if getattr(self, 'serial', None) is not None:
            self.serial.close()
