"""Run with --help. Importing this module never connects to instruments."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

from event_handler import EventHandler, positive


class SimulatedThermo:
    identity = 'SIMULATED SIM922 — NOT EXPERIMENTAL DATA'
    def get_V(self):
        return 0.4316 + 0.00001 * math.sin(time.monotonic())
    def get_T(self):
        return 336.1


class SimulatedLockIn:
    identity = 'SIMULATED 7270 — NOT EXPERIMENTAL DATA'
    last_status, last_overload = 1, 0
    def get_x(self):
        return 0.0016
    def get_y(self):
        return 0.0001
    def get_magnitude(self):
        return math.hypot(self.get_x(), self.get_y())
    def get_phase(self):
        return math.degrees(math.atan2(self.get_y(), self.get_x()))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--list-devices', action='store_true', help='List USB devices/serial ports; no queries')
    p.add_argument('--simulate', action='store_true', help='Use clearly labelled synthetic data')
    p.add_argument('--check', action='store_true', help='Identify instruments and print one sample')
    p.add_argument('--temperature-only', action='store_true', help='Record only the SIM922 while lock-in is unavailable')
    p.add_argument('--port', help='SIM900 serial port; auto-select only if exactly one USB serial port exists')
    p.add_argument('--baud', type=int, default=9600, help='SIM900 host baud rate (default: 9600)')
    p.add_argument('--module', type=int, choices=range(1, 9), default=7)
    p.add_argument('--channel', type=int, choices=range(1, 5), default=1)
    p.add_argument('--usb-terminator', choices=('status', 'null'), default='status',
                   help='Match the 7270 USB Status menu; normally status')
    p.add_argument('--lockin-port', help='7270 serial port; omitted means native USB')
    p.add_argument('--lockin-baud', type=int, default=9600)
    p.add_argument('--lockin-data-bits', type=int, choices=(7, 8), default=7)
    p.add_argument('--lockin-parity', choices=('N', 'E', 'O'), default='E')
    p.add_argument('--lockin-no-echo', action='store_true',
                   help='Use if echo is disabled in the 7270 RS232 settings; prompts must be enabled')
    p.add_argument('--duration', type=float, default=60, help='Acquisition duration in seconds')
    p.add_argument('--period', type=float, default=1, help='Requested sample interval in seconds')
    p.add_argument('--output', type=Path, help='New CSV path (never overwrites); default: data/<timestamp>.csv')
    p.add_argument('--current-a', type=float, help='Independently measured sample RMS current in A')
    p.add_argument('--voltage-component', choices=('x', 'magnitude'),
                   help='x needs correct phase alignment; magnitude measures impedance magnitude')
    p.add_argument('--voltage-gain', type=float, default=1, help='External voltage gain; default 1')
    p.add_argument('--area-m2', type=float, help='Uniform sample cross-sectional area in square metres')
    p.add_argument('--length-m', type=float, help='Voltage-contact spacing in metres')
    return p


def list_devices():
    from serial.tools import list_ports
    import usb.core
    import usb.util
    from lockin_7270 import usb_backend
    print('Serial ports:')
    for port in list_ports.comports():
        print(f'  {port.device}: {port.description}')
    print('USB devices (7270 expected VID:PID 0a2d:001b):')
    for dev in usb.core.find(find_all=True, backend=usb_backend()):
        try:
            name = usb.util.get_string(dev, dev.iProduct)
        except usb.core.USBError:
            name = '(description unavailable)'
        print(f'  {dev.idVendor:04x}:{dev.idProduct:04x} {name}')


def display(row):
    print(f"{row['elapsed_s']:.2f}s  diode={row['diode_voltage_mv']} mV  "
          f"T_reported={row['temperature_reported_k']} K  "
          f"X={row['lockin_x_v']} V  Y={row['lockin_y_v']} V  "
          f"{row['quality']}", flush=True)


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.list_devices:
        list_devices()
        return 0
    options = dict(current_a=args.current_a, voltage_component=args.voltage_component,
                   voltage_gain=args.voltage_gain, area_m2=args.area_m2,
                   length_m=args.length_m, simulated=args.simulate)
    try:
        positive(args.duration, 'Duration')
        positive(args.period, 'Period')
        if args.temperature_only and args.current_a is not None:
            raise ValueError('Temperature-only mode cannot calculate resistance.')
        EventHandler(None, None, **options)  # Validate before any connection.
    except ValueError as exc:
        p.error(str(exc))
    prefix = 'SIMULATED_' if args.simulate else ''
    path = args.output or Path('data') / (
        prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ') + '.csv')
    metadata_path = path.with_suffix(path.suffix + '.json')
    if not args.check and (path.exists() or metadata_path.exists()):
        p.error(f'Output already exists: {path} or {metadata_path}')
    metadata = {'started_utc': datetime.now(timezone.utc).isoformat(),
                'simulated': args.simulate, 'arguments': vars(args).copy(),
                'temperature_calibration': 'unverified instrument curve; no correction applied',
                'sampling': 'sequential queries; elapsed_s is sample start, read_duration_s is query span'}
    exit_code = 0
    metadata_file = None
    with ExitStack() as stack:
        try:
            if args.simulate:
                lockin, thermo = SimulatedLockIn(), SimulatedThermo()
                if args.temperature_only:
                    lockin = None
            else:
                from sim922 import SIM922
                from lockin_7270 import LockIn7270, SerialLockIn7270
                if args.temperature_only:
                    lockin = None
                elif args.lockin_port:
                    if args.lockin_port == args.port:
                        raise ValueError('The lock-in and SIM900 need different serial ports.')
                    lockin = stack.enter_context(SerialLockIn7270(args.lockin_port,
                        baud=args.lockin_baud, data_bits=args.lockin_data_bits,
                        parity=args.lockin_parity, echo=not args.lockin_no_echo))
                else:
                    lockin = stack.enter_context(LockIn7270(terminator=args.usb_terminator))
                if lockin is not None:
                    settings = lockin.get_settings()
                    metadata['lockin_settings'] = settings
                    if int(settings['REFMODE']) != 0 or int(settings['IMODE']) != 0:
                        raise RuntimeError('Acquisition requires single-reference voltage-input mode. '
                                           'Review the lock-in front-panel settings.')
                    if int(settings['VMODE']) == 0:
                        raise RuntimeError('Lock-in voltage input is grounded (VMODE 0). Review input selection.')
                thermo = stack.enter_context(SIM922(port=args.port, baud=args.baud,
                    module_no=args.module, channel=args.channel))
                excitation = thermo.get_excitation()
                if excitation.upper() not in ('1', 'ON'):
                    raise RuntimeError(f'SIM922 channel {args.channel} excitation is off.')
                metadata.update(sim900_identity=thermo.mainframe_id,
                    sim922_curve=thermo.get_curve(), sim922_excitation=excitation)
            lockin_identity = lockin.identity if lockin is not None else 'Not used (temperature-only mode)'
            metadata.update(lockin_identity=lockin_identity, thermo_identity=thermo.identity)
            handler = EventHandler(lockin, thermo, **options)
            print(f'{lockin_identity}\n{thermo.identity}')
            print('Temperature is the unverified instrument reading; diode voltage is saved separately.')
            if args.check:
                print(json.dumps(metadata, indent=2, default=str))
                display(handler.sample(time.monotonic()))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                metadata_file = stack.enter_context(metadata_path.open('x'))
                metadata['status'] = 'running'
                metadata['rows'] = 0
                json.dump(metadata, metadata_file, indent=2, default=str)
                metadata_file.flush()
                print(f'Saving to {path.resolve()} (Ctrl-C stops and preserves saved rows).')
                def saved_sample(row):
                    metadata['rows'] += 1
                    display(row)
                handler.run(path, args.duration, args.period, on_sample=saved_sample)
                metadata['status'] = 'complete'
        except KeyboardInterrupt:
            metadata['status'] = 'interrupted'
            print('\nStopped. Previously written CSV rows are preserved.')
            exit_code = 130
        except Exception as exc:
            metadata.update(status='error', error=f'{type(exc).__name__}: {exc}')
            print(f'Acquisition failed: {exc}', file=sys.stderr)
            exit_code = 1
        finally:
            if metadata_file is not None:
                metadata['finished_utc'] = datetime.now(timezone.utc).isoformat()
                metadata_file.seek(0)
                metadata_file.truncate()
                json.dump(metadata, metadata_file, indent=2, default=str)
                metadata_file.flush()
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
