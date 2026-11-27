"""Calibrate a raw run after acquisition, using marked stable reference intervals.

Requires warm-start/warm-end and cold-start/cold-end events in <run>.events.jsonl.
Writes a NEW derived CSV and calibration JSON; never modifies the raw run.
"""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path

from temp_calibration import fit_two_points


def utc(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Timestamps must include their timezone.')
    return date


def reference_stats(run, events, name, column, minimum):
    def event_time(label):
        matches = [event for event in events if event['label'] == label]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one {label!r} marker, found {len(matches)}.')
        return utc(matches[0]['timestamp_utc'])
    start, end = event_time(name + '-start'), event_time(name + '-end')
    if start >= end:
        raise ValueError(f'{name} interval must have increasing timestamps.')
    count, mean, squared_deviation = 0, 0.0, 0.0
    minimum_mv, maximum_mv = float('inf'), float('-inf')
    with run.open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            if start <= utc(row['timestamp_utc']) <= end:
                if row['quality'] not in ('ok', 'temperature_only', 'lockin_unavailable'):
                    continue
                try:
                    value = float(row[column])
                except (ValueError, KeyError):
                    continue
                if math.isfinite(value) and 0 < value < 2500:
                    count += 1
                    delta = value - mean
                    mean += delta / count
                    squared_deviation += delta * (value - mean)
                    minimum_mv, maximum_mv = min(minimum_mv, value), max(maximum_mv, value)
    if count < minimum:
        raise ValueError(f'{name}: only {count} valid readings; need {minimum}.')
    return dict(start_utc=start.isoformat(), end_utc=end.isoformat(), count=count,
                mean_mv=mean, stdev_mv=math.sqrt(max(0, squared_deviation / (count - 1))),
                min_mv=minimum_mv, max_mv=maximum_mv)


def coefficients(warm_k, warm_mv, cold_k, cold_mv, c3):
    if not 0 < cold_k < warm_k or not 0 < warm_mv < cold_mv < 2500:
        raise ValueError('Require 0 < cold T < warm T and 0 < warm mV < cold mV < 2500.')
    # Two fitted coefficients with an independently FIXED log term.
    c1, c2 = fit_two_points((warm_k, warm_mv + c3 * math.log(warm_k)),
                           (cold_k, cold_mv + c3 * math.log(cold_k)))
    if min(c2 + c3 / cold_k, c2 + c3 / warm_k) <= 0:
        raise ValueError('Calibration is not monotonic over the reference interval.')
    return c1, c2, c3


def convert_voltage(voltage, params, cold_k, warm_k):
    c1, c2, c3 = params
    def model(temperature):
        return c1 - c2 * temperature - c3 * math.log(temperature)
    if not math.isfinite(voltage):
        return '', 'invalid_voltage'
    if not model(warm_k) - 1e-9 <= voltage <= model(cold_k) + 1e-9:
        return '', 'outside_reference_range'
    low, high = cold_k, warm_k
    for _ in range(70):
        mid = (low + high) / 2
        if model(mid) > voltage:
            low = mid
        else:
            high = mid
    return (low + high) / 2, 'within_reference_range'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--warm-c', required=True, type=float, help='Independent surface temperature in Celsius')
    parser.add_argument('--cold-k', required=True, type=float, help='Established cold reference temperature in Kelvin')
    parser.add_argument('--model', choices=('linear', 'log-fixed'), required=True)
    parser.add_argument('--c3', type=float, help='Fixed coefficient in mV for log-fixed; obtain from lab model/TA')
    parser.add_argument('--channel', type=int, choices=range(1, 5), help='Default: primary diode in run metadata')
    parser.add_argument('--minimum-samples', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.minimum_samples < 2:
            raise ValueError('At least two readings per reference are required for spread statistics.')
        warm_k = args.warm_c + 273.15
        if not all(math.isfinite(x) for x in (warm_k, args.cold_k)):
            raise ValueError('Reference temperatures must be finite.')
        if args.model == 'log-fixed' and args.c3 is None:
            raise ValueError('The log-fixed model requires --c3; two points cannot fit three free coefficients.')
        if args.model == 'linear' and args.c3 is not None:
            raise ValueError('--c3 is only valid with --model log-fixed.')
        c3 = args.c3 if args.c3 is not None else 0.0
        if not math.isfinite(c3):
            raise ValueError('c3 must be finite.')
        run = args.run
        metadata = json.loads(run.with_suffix(run.suffix + '.json').read_text(encoding='utf-8'))
        primary = metadata['arguments']['channel']
        channel = args.channel or primary
        column = 'diode_voltage_mv' if channel == primary else f'diode_ch{channel}_voltage_mv'
        events = [json.loads(line) for line in run.with_suffix(run.suffix + '.events.jsonl').read_text(
            encoding='utf-8').splitlines() if line.strip()]
        warm = reference_stats(run, events, 'warm', column, args.minimum_samples)
        cold = reference_stats(run, events, 'cold', column, args.minimum_samples)
        params = coefficients(warm_k, warm['mean_mv'], args.cold_k, cold['mean_mv'], c3)
        output = args.output or run.with_name(run.stem + f'.ch{channel}.calibrated.csv')
        summary_path = output.with_suffix(output.suffix + '.calibration.json')
        if output.exists() or summary_path.exists():
            raise ValueError('Derived output or calibration JSON already exists; choose a new --output.')
        summary = dict(raw_file=str(run.resolve()), simulated=metadata.get('simulated'),
                       channel=channel, voltage_column=column, model=args.model,
                       equation='V_mV = c1 - c2*T_K - c3*ln(T_K/1K)',
                       c1_mv=params[0], c2_mv_per_k=params[1], c3_mv=params[2],
                       warm_temperature_k=warm_k, cold_temperature_k=args.cold_k,
                       warm=warm, cold=cold,
                       limitation='Two-point model; interpolation is not independent validation. No extrapolation.')
        output.parent.mkdir(parents=True, exist_ok=True)
        # Streaming keeps memory bounded for hour-long runs.
        with run.open(newline='', encoding='utf-8') as source, output.open('x', newline='', encoding='utf-8') as target:
            reader = csv.DictReader(source)
            if column not in (reader.fieldnames or []):
                raise ValueError(f'Channel {channel} was not logged in this run.')
            added = ['temperature_calibrated_k', 'calibration_quality', 'calibrated_channel']
            if any(name in reader.fieldnames for name in added):
                raise ValueError('Input already contains calibrated columns; use the raw CSV.')
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames + added, lineterminator='\n')
            writer.writeheader()
            for row in reader:
                try:
                    temperature, quality = convert_voltage(float(row[column]), params, args.cold_k, warm_k)
                except (ValueError, TypeError):
                    temperature, quality = '', 'invalid_voltage'
                row.update(temperature_calibrated_k=temperature, calibration_quality=quality,
                           calibrated_channel=channel)
                writer.writerow(row)
        with summary_path.open('x', encoding='utf-8') as stream:
            json.dump(summary, stream, indent=2, allow_nan=False)
            stream.write('\n')
        print(json.dumps(summary, indent=2))
        print(f'Derived data: {output}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Calibration failed: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
