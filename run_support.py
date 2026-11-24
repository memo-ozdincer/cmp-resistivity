"""Durable metadata updates and temporary Windows idle-sleep prevention."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys


def write_metadata(path, metadata):
    """Replace an owned metadata file atomically, keeping the last valid snapshot."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(metadata, stream, indent=2, default=str, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def keep_awake(enabled=True):
    """Prevent automatic idle sleep on Windows only; restore the thread's state."""
    if not enabled or sys.platform != 'win32':
        yield False
        return
    import ctypes
    continuous, system_required = 0x80000000, 0x00000001
    previous = ctypes.windll.kernel32.SetThreadExecutionState(continuous | system_required)
    if not previous:
        raise RuntimeError('Windows idle-sleep prevention failed. Check power settings '
                           'or explicitly use --allow-sleep after configuring the PC.')
    try:
        yield True
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(previous)
