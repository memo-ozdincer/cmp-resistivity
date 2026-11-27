"""Opt-in native-USB reconnection. Never replay stale values or change settings."""
import time
import usb.core


class LockInCommunicationError(TimeoutError):
    """A missing lock-in reading; temperature values in the row may still be valid."""


class RecoveringLockIn:
    def __init__(self, device, reconnect, expected_settings, retry_seconds=15):
        self.device = device
        self.reconnect = reconnect
        self.expected_settings = dict(expected_settings)
        self.retry_seconds = retry_seconds
        self.next_attempt = 0
        self.last_error = ''
        self.reconnections = 0
        self.failures = 0
        self.last_status = self.last_overload = None
        self.identity = device.identity

    def _close_device(self):
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass  # Do not hide the original communication failure.
            self.device = None

    def _ready(self):
        if self.device is not None:
            return
        if time.monotonic() < self.next_attempt:
            raise LockInCommunicationError('Lock-in offline; next reconnect pending. ' + self.last_error)
        self.next_attempt = time.monotonic() + self.retry_seconds
        candidate = None
        try:
            candidate = self.reconnect()
            actual = candidate.get_settings()
            if actual != self.expected_settings:
                differences = {key: {'start': self.expected_settings.get(key), 'now': actual.get(key)}
                               for key in set(actual) | set(self.expected_settings)
                               if actual.get(key) != self.expected_settings.get(key)}
                raise RuntimeError(f'Lock-in settings changed; refusing to resume: {differences}')
            self.device = candidate
            self.reconnections += 1
            self.last_error = ''
        except Exception as exc:
            if candidate is not None:
                try:
                    candidate.close()
                except Exception:
                    pass
            self.last_error = f'{type(exc).__name__}: {exc}'
            raise LockInCommunicationError('Reconnect failed: ' + self.last_error) from exc

    def _call(self, method, *args):
        self._ready()
        try:
            result = getattr(self.device, method)(*args)
            self.last_status = self.device.last_status
            self.last_overload = self.device.last_overload
            return result
        except (TimeoutError, usb.core.USBError) as exc:
            self.failures += 1
            self.last_error = f'{type(exc).__name__}: {exc}'
            self.last_status = self.last_overload = None
            self._close_device()
            self.next_attempt = time.monotonic() + self.retry_seconds
            raise LockInCommunicationError(self.last_error) from exc

    def get_x(self):
        return self._call('get_x')

    def get_y(self):
        return self._call('get_y')

    def get_magnitude(self):
        return self._call('get_magnitude')

    def get_phase(self):
        return self._call('get_phase')

    def query_safe(self, command):
        return self._call('query_safe', command)

    def close(self):
        self._close_device()
