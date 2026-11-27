"""Named, provisional temperature calibration. Preserves original instrument readings."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from temp_calibration import fit_two_points, temperature_from_mv

DEFAULT_PROFILE = Path(__file__).resolve().parent / 'calibrations/recooldown-provisional.json'
SENSORS = ('base_plate', 'sample')
SENSOR_FIELDS = ['sensor_calibration_id'] + [f'{sensor}_{suffix}' for sensor in SENSORS for suffix in (
    'diode_channel', 'diode_voltage_mv', 'temperature_calibrated_k', 'calibration_quality')]


def load_profile(path=DEFAULT_PROFILE):
    profile = json.loads(Path(path).read_text(encoding='utf-8'))
    if profile.get('model') != 'linear' or profile.get('status') != 'provisional':
        raise ValueError('Expected a provisional linear sensor profile.')
    if set(profile.get('sensors', {})) != set(SENSORS) or not profile.get('id'):
        raise ValueError('Profile must name base_plate and sample and have an id.')
    channels = []
    for sensor in profile['sensors'].values():
        channel = sensor['channel']
        if type(channel) is not int or channel not in range(1, 5):
            raise ValueError('Sensor channels must be integers 1–4.')
        channels.append(channel)
        warm, cold = sensor['warm'], sensor['cold']
        values = [warm['temperature_k'], cold['temperature_k'], warm['voltage_mv'], cold['voltage_mv']]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
            raise ValueError('Calibration references must be finite numbers.')
        if not (0 < cold['temperature_k'] < warm['temperature_k'] and
                0 < warm['voltage_mv'] < cold['voltage_mv'] < 2500):
            raise ValueError('Require increasing diode voltage for decreasing temperature.')
    if len(set(channels)) != len(channels):
        raise ValueError('Sensors must use different channels.')
    return profile


def named_reading(profile, channel, voltage_mv):
    """Return one sensor's raw alias, temperature and explicit calibration status."""
    if profile is None:
        return {}
    result = {}
    for name, sensor in profile['sensors'].items():
        if sensor['channel'] != channel:
            continue
        warm, cold = sensor['warm'], sensor['cold']
        temperature, quality = '', 'invalid_voltage'
        try:
            voltage = float(voltage_mv)
            if math.isfinite(voltage):
                # Tiny endpoint tolerance covers volts -> millivolts round-off only.
                tolerance = 1e-9
                if warm['voltage_mv']-tolerance <= voltage <= cold['voltage_mv']+tolerance:
                    params = fit_two_points((warm['temperature_k'], warm['voltage_mv']),
                                            (cold['temperature_k'], cold['voltage_mv']))
                    temperature = temperature_from_mv(voltage, *params)
                    quality = 'provisional_linear'
                else:
                    quality = 'outside_reference_range'
        except (ValueError, TypeError):
            pass
        result.update({f'{name}_diode_channel': channel,
                       f'{name}_diode_voltage_mv': voltage_mv,
                       f'{name}_temperature_calibrated_k': temperature,
                       f'{name}_calibration_quality': quality})
    return result


def empty_readings(profile):
    row = dict.fromkeys(SENSOR_FIELDS, '')
    row['sensor_calibration_id'] = profile['id'] if profile is not None else 'disabled'
    for name in SENSORS:
        row[f'{name}_calibration_quality'] = 'not_read' if profile is not None else 'disabled'
        if profile is not None:
            row[f'{name}_diode_channel'] = profile['sensors'][name]['channel']
    return row


def profile_metadata(profile, path):
    return {'profile': profile, 'source': str(Path(path)),
            'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'temperature_columns': [f'{name}_temperature_calibrated_k' for name in SENSORS]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--profile', type=Path, default=DEFAULT_PROFILE)
    parser.add_argument('--primary-channel', type=int, choices=range(1, 5))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        profile = load_profile(args.profile)
        primary = args.primary_channel
        if primary is None:
            metadata = json.loads(args.csv.with_suffix(args.csv.suffix+'.json').read_text(encoding='utf-8'))
            primary = metadata['arguments']['channel']
        if primary not in range(1, 5):
            raise ValueError('Supply the actual primary SIM922 channel with --primary-channel.')
        output = args.output or args.csv.with_name(args.csv.stem+'.sensors.calibrated.csv')
        sidecar = output.with_suffix(output.suffix+'.calibration.json')
        if output.exists() or sidecar.exists():
            raise ValueError('Derived output already exists; choose a new --output.')
        counts = {sensor: {} for sensor in SENSORS}
        with args.csv.open(newline='', encoding='utf-8') as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames or []
            if 'diode_voltage_mv' not in fields:
                raise ValueError('Input must contain raw diode_voltage_mv.')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', newline='', encoding='utf-8') as target:
                writer = csv.DictWriter(target, fieldnames=fields+[f for f in SENSOR_FIELDS if f not in fields])
                writer.writeheader()
                for row in reader:
                    named = empty_readings(profile)
                    for name, sensor in profile['sensors'].items():
                        channel = sensor['channel']
                        column = 'diode_voltage_mv' if channel == primary else f'diode_ch{channel}_voltage_mv'
                        if row.get(column, '') != '':
                            named.update(named_reading(profile, channel, row[column]))
                        flag = named[f'{name}_calibration_quality']
                        counts[name][flag] = counts[name].get(flag, 0)+1
                    row.update(named)
                    writer.writerow(row)
        summary = dict(profile_metadata(profile, args.profile), primary_channel=primary,
                       source_csv=str(args.csv), source_sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest(),
                       recomputed_columns=[field for field in SENSOR_FIELDS if field in fields],
                       quality_counts=counts)
        with sidecar.open('x', encoding='utf-8') as stream:
            json.dump(summary, stream, indent=2, allow_nan=False)
            stream.write('\n')
        print(f'Saved provisional sensor temperatures: {output}')
        print(json.dumps(counts, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Sensor calibration failed: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
