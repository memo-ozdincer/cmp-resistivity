"""Append a timestamped event from a second terminal on the acquisition PC."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path, help='Existing raw CSV for this run')
    parser.add_argument('label', help='E.g. warm-start, warm-end, cold-start, cold-end, heating-start')
    parser.add_argument('--note', default='', help='Surface thermometer, pressure, current, wiring or heater changes')
    args = parser.parse_args(argv)
    if not args.run.is_file() or args.run.suffix.lower() != '.csv':
        parser.error('Run must be an existing CSV file.')
    event = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
             'label': args.label, 'note': args.note}
    path = args.run.with_suffix(args.run.suffix + '.events.jsonl')
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(f"Marked {event['label']} at {event['timestamp_utc']} in {path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
