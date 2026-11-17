"""Synchronous experiment acquisition; no threads or barrier deadlocks.

Pass connected instruments to EventHandler(lock_in, thermo). Values are read
sequentially, not simultaneously. All complete and partial samples are saved.
"""
import csv
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    'timestamp_utc', 'elapsed_s', 'read_duration_s', 'simulated',
    'diode_voltage_mv', 'temperature_reported_k', 'temperature_calibration',
    'lockin_x_v', 'lockin_y_v', 'lockin_magnitude_v', 'lockin_phase_deg',
    'lockin_status', 'lockin_overload', 'quality', 'error',
    'current_rms_a', 'voltage_component', 'voltage_gain',
    'area_m2', 'voltage_contact_spacing_m', 'resistance_ohm', 'resistivity_ohm_m',
]


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be positive and finite.')
    return value


class SampleError(RuntimeError):
    def __init__(self, row, cause):
        super().__init__(str(cause))
        self.row = row


class EventHandler:
    def __init__(self, lock_in, thermo, *, current_a=None, voltage_component=None,
                 voltage_gain=1.0, area_m2=None, length_m=None, simulated=False):
        positive(voltage_gain, 'Voltage gain')
        if current_a is not None:
            positive(current_a, 'RMS current')
            if voltage_component not in ('x', 'magnitude'):
                raise ValueError('With current, choose voltage_component=x or magnitude.')
        elif voltage_component is not None:
            raise ValueError('Voltage component requires a measured RMS current.')
        if (area_m2 is None) != (length_m is None):
            raise ValueError('Specify both cross-sectional area and voltage-contact spacing.')
        if area_m2 is not None:
            if current_a is None:
                raise ValueError('Resistivity requires a measured RMS current.')
            positive(area_m2, 'Cross-sectional area')
            positive(length_m, 'Voltage-contact spacing')
        self.lock_in, self.thermo = lock_in, thermo
        self.current_a, self.component = current_a, voltage_component
        self.gain, self.area, self.length = voltage_gain, area_m2, length_m
        self.simulated = simulated

    def sample(self, start):
        sample_start = time.monotonic()
        row = dict.fromkeys(FIELDS, '')
        row.update(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                   elapsed_s=sample_start - start, simulated=self.simulated,
                   temperature_calibration='unverified_instrument_curve',
                   current_rms_a=self.current_a if self.current_a is not None else '',
                   voltage_component=self.component or '', voltage_gain=self.gain,
                   area_m2=self.area if self.area is not None else '',
                   voltage_contact_spacing_m=self.length if self.length is not None else '')
        try:
            row['diode_voltage_mv'] = 1000 * self.thermo.get_V()
            row['temperature_reported_k'] = self.thermo.get_T()
            if self.lock_in is None:
                row['quality'] = 'temperature_only'
                if not 0 < row['diode_voltage_mv'] < 2500:
                    row['quality'] += ';diode_voltage_out_of_range'
                if row['temperature_reported_k'] <= 0:
                    row['quality'] += ';temperature_out_of_range'
                row['read_duration_s'] = time.monotonic() - sample_start
                return row
            status, overload = 0, 0
            for field, method in (
                ('lockin_x_v', self.lock_in.get_x),
                ('lockin_y_v', self.lock_in.get_y),
                ('lockin_magnitude_v', self.lock_in.get_magnitude),
                ('lockin_phase_deg', self.lock_in.get_phase),
            ):
                row[field] = method()
                status |= self.lock_in.last_status or 0
                overload |= self.lock_in.last_overload or 0
            if self.lock_in.last_status is None:
                status = int(self.lock_in.query_safe('ST'))
                overload = int(self.lock_in.query_safe('N'))
            row.update(lockin_status=status, lockin_overload=overload)
            warnings = []
            if status & 0x08:
                warnings.append('reference_unlocked')
            if status & 0x50 or overload:
                warnings.append('lockin_overload')
            if not 0 < row['diode_voltage_mv'] < 2500:
                warnings.append('diode_voltage_out_of_range')
            if row['temperature_reported_k'] <= 0:
                warnings.append('temperature_out_of_range')
            row['quality'] = ';'.join(warnings) or 'ok'
            if self.current_a is not None and not (status & 0x58 or overload):
                voltage = row[f'lockin_{self.component}_v'] / self.gain
                row['resistance_ohm'] = voltage / self.current_a
                if self.area is not None:
                    row['resistivity_ohm_m'] = row['resistance_ohm'] * self.area / self.length
        except (Exception, KeyboardInterrupt) as exc:
            row['quality'] = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'error'
            row['error'] = f'{type(exc).__name__}: {exc}'
            row['read_duration_s'] = time.monotonic() - sample_start
            raise SampleError(row, exc) from exc
        row['read_duration_s'] = time.monotonic() - sample_start
        return row

    def run(self, filename, duration=60, sample_period=1, *, on_sample=None):
        positive(duration, 'Duration')
        positive(sample_period, 'Sample period')
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        # Exclusive creation prevents accidentally overwriting another run.
        with path.open('x', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            output.flush()
            os.fsync(output.fileno())
            start = time.monotonic()
            while time.monotonic() - start < duration:
                sample_start = time.monotonic()
                failure = None
                try:
                    row = self.sample(start)
                except SampleError as exc:
                    row, failure = exc.row, exc
                writer.writerow(row)
                output.flush()
                os.fsync(output.fileno())
                count += 1
                if on_sample:
                    on_sample(row)
                if failure:
                    if failure.row['quality'] == 'interrupted':
                        raise KeyboardInterrupt from failure
                    raise failure
                next_time = min(sample_start + sample_period, start + duration)
                time.sleep(max(0, next_time - time.monotonic()))
        return count
