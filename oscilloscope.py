"""Optional Keysight scope helper. Core acquisition reads the SIM922 directly."""
import math
import pyvisa


class Oscilloscope:
    def __init__(self, resource=None, backend='@py', timeout_ms=3000):
        # Load Homebrew's libusb when it is outside the default loader search path.
        if backend == '@py':
            from lockin_7270 import usb_backend
            usb_backend()
        self.rm = pyvisa.ResourceManager(backend)
        self.dev = None
        try:
            if resource is None:
                candidates = []
                for name in self.rm.list_resources('USB?*::INSTR'):
                    vendor = name.split('::')[1]
                    if int(vendor, 0) in (10893, 2391):
                        candidates.append(name)
                if len(candidates) != 1:
                    raise RuntimeError(f'Expected one Keysight USB scope; found {candidates}. '
                                       'Pass its VISA resource explicitly.')
                resource = candidates[0]
            self.dev = self.rm.open_resource(resource)
            self.dev.timeout = timeout_ms
            self.dev.write_termination = '\n'
            self.dev.read_termination = '\n'
            self.identity = self.query('*IDN?').strip()
            if 'DSO' not in self.identity.upper():
                raise RuntimeError(f'Expected Keysight scope; got {self.identity!r}.')
        except BaseException:
            self.close()
            raise

    def write(self, command):
        return self.dev.write(command)

    def query(self, command):
        return self.dev.query(command)

    def get_voltage(self, channel=1):
        """Read displayed mean voltage. Probe scaling must already be correct."""
        if channel not in range(1, 5):
            raise ValueError('Channel must be 1–4.')
        value = float(self.query(f':MEASure:VAVerage? DISPlay,CHANnel{channel}'))
        if not math.isfinite(value) or abs(value) >= 1e30:
            raise RuntimeError('Scope measurement unavailable; check channel/display settings.')
        return value

    def close(self):
        try:
            if self.dev is not None:
                self.dev.close()
                self.dev = None
        finally:
            self.rm.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


Oscilliscope = Oscilloscope  # Compatibility with the original spelling.
