"""Run with --help. Importing this module never connects to instruments."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
import platform
from pathlib import Path
import sys
import time

from event_handler import EventHandler, positive
from run_support import keep_awake, write_metadata
from sensor_calibration import DEFAULT_PROFILE, SENSORS, load_profile, profile_metadata


class SimulatedThermo:
    identity = 'SIMULATED SIM922 — NOT EXPERIMENTAL DATA'
    def get_V(self, channel=None):
        return 0.4316 + 0.00001 * math.sin(time.monotonic())
    def get_T(self, channel=None):
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
    p.add_argument('--timeout-ms', type=int, default=2000,
                   help='7270 query timeout in milliseconds (default: 2000)')
    p.add_argument('--recover-lockin', action='store_true',
                   help='Native USB: log gaps and retry after timeouts, without changing settings')
    p.add_argument('--reconnect-seconds', type=float, default=15,
                   help='Minimum interval between lock-in reconnect attempts (default: 15)')
    p.add_argument('--lockin-port', help='7270 serial port; omitted means native USB')
    p.add_argument('--lockin-baud', type=int, default=9600)
    p.add_argument('--lockin-data-bits', type=int, choices=(7, 8), default=7)
    p.add_argument('--lockin-parity', choices=('N', 'E', 'O'), default='E')
    p.add_argument('--lockin-no-echo', action='store_true',
                   help='Use if echo is disabled in the 7270 RS232 settings; prompts must be enabled')
    timing = p.add_mutually_exclusive_group()
    timing.add_argument('--duration', type=float, default=60, help='Duration in seconds (default: 60)')
    timing.add_argument('--continuous', action='store_true', help='Run until Ctrl-C; no duration limit')
    p.add_argument('--sensor-name', default='unidentified', help='Physical location of primary diode')
    p.add_argument('--calibration-file', type=Path, default=DEFAULT_PROFILE,
                   help='Sensor profile JSON; default is the provisional ch1 base plate/ch2 sample profile')
    p.add_argument('--raw-temperatures', action='store_true', help='Disable derived sensor temperatures')
    p.add_argument('--extra-channels', nargs='+', type=int, choices=range(1, 5), default=[],
                   help='Additional connected/excited SIM922 channels to log')
    p.add_argument('--notes', default='', help='Sample, terminal map, pressure, phase and current notes')
    p.add_argument('--console-every', type=float, default=10, help='Console update interval in seconds')
    p.add_argument('--allow-sleep', action='store_true', help='Disable automatic Windows idle-sleep prevention')
    p.add_argument('--period', type=float, default=1, help='Requested sample interval in seconds')
    p.add_argument('--output', type=Path, help='New CSV path (never overwrites); default: data/runs/<timestamp>.csv')
    p.add_argument('--github-backup', action='store_true',
                   help='Upload run snapshots to GitHub in the background (requires gh auth login)')
    p.add_argument('--github-repo', default='memo-ozdincer/cmp-resistivity', help='Backup OWNER/REPO')
    p.add_argument('--github-backup-seconds', type=float, default=300,
                   help='Seconds between GitHub snapshots, minimum 30 (default: 300)')
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
    try:
        devices = list(usb.core.find(find_all=True, backend=usb_backend()))
    except Exception as exc:
        print(f'  Native USB unavailable: {exc}')
        return
    for dev in devices:
        try:
            name = usb.util.get_string(dev, dev.iProduct)
        except usb.core.USBError:
            name = '(description unavailable)'
        print(f'  {dev.idVendor:04x}:{dev.idProduct:04x} {name}')


def display(row):
    if any(row.get(f'{name}_calibration_quality') not in ('disabled', None) for name in SENSORS):
        readings = []
        for name in SENSORS:
            voltage = row.get(f'{name}_diode_voltage_mv', '')
            temperature = row.get(f'{name}_temperature_calibrated_k', '')
            readings.append(f"{name}[ch{row.get(f'{name}_diode_channel', '')}]="
                f"{f'{float(voltage):.3f}' if voltage != '' else '--'} mV, "
                f"{f'{temperature:.2f}' if temperature != '' else '--'} K "
                f"({row.get(f'{name}_calibration_quality', '')})")
        print(f"{row['elapsed_s']:.2f}s  " + ' | '.join(readings) +
              f"  X={row['lockin_x_v']} V Y={row['lockin_y_v']} V {row['quality']}", flush=True)
        return
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
                   length_m=args.length_m, simulated=args.simulate, extra_channels=args.extra_channels,
                   primary_channel=args.channel)
    try:
        profile = None if args.raw_temperatures else load_profile(args.calibration_file)
        options['calibration'] = profile
        if args.sensor_name == 'unidentified' and profile is not None:
            args.sensor_name = next((name for name, sensor in profile['sensors'].items()
                                     if sensor['channel'] == args.channel), 'unidentified')
        positive(args.duration, 'Duration')
        positive(args.period, 'Period')
        positive(args.console_every, 'Console interval')
        positive(args.timeout_ms, 'Lock-in timeout')
        positive(args.reconnect_seconds, 'Reconnect interval')
        if not math.isfinite(args.github_backup_seconds) or args.github_backup_seconds < 30:
            raise ValueError('GitHub backup interval must be at least 30 seconds.')
        if args.github_backup and args.check:
            raise ValueError('--github-backup needs a saved run, not --check.')
        if args.recover_lockin and (args.lockin_port or args.temperature_only or args.simulate):
            raise ValueError('--recover-lockin requires actual native USB lock-in acquisition.')
        if args.channel in args.extra_channels:
            raise ValueError('Primary channel must not be repeated in --extra-channels.')
        if args.temperature_only and args.current_a is not None:
            raise ValueError('Temperature-only mode cannot calculate resistance.')
        EventHandler(None, None, **options)  # Validate before any connection.
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.error(str(exc))
    prefix = 'SIMULATED_' if args.simulate else ''
    path = args.output or Path('data/runs') / (
        prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ') + '.csv')
    metadata_path = path.with_suffix(path.suffix + '.json')
    if not args.check and (path.exists() or metadata_path.exists()):
        p.error(f'Output already exists: {path} or {metadata_path}')
    backup = None
    if args.github_backup:
        from github_backup import GitHubBackup, GitHubError, validate_access
        try:
            validate_access(args.github_repo)  # Fail clearly before connecting to hardware.
            backup = GitHubBackup(path, repo=args.github_repo, interval=args.github_backup_seconds)
        except (GitHubError, ValueError) as exc:
            p.error(str(exc))
    metadata = {'started_utc': datetime.now(timezone.utc).isoformat(),
                'simulated': args.simulate, 'arguments': vars(args).copy(),
                'platform': platform.platform(), 'python_version': sys.version,
                'current_source': 'fixed_user_assumption' if args.current_a is not None else 'not_logged',
                'temperature_calibration': 'temperature_reported_k fields retain unverified instrument curve; named temperatures use sensor_calibration profile',
                'sensor_calibration': profile_metadata(profile, args.calibration_file) if profile is not None else None,
                'sampling': 'sequential queries; elapsed_s is sample start, read_duration_s is query span'}
    exit_code = 0
    owns_metadata = False
    last_console = last_heartbeat = float('-inf')
    with ExitStack() as stack:
        try:
            metadata['windows_idle_sleep_prevented'] = stack.enter_context(
                keep_awake(not args.allow_sleep))
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
                        parity=args.lockin_parity, echo=not args.lockin_no_echo,
                        timeout_ms=args.timeout_ms))
                else:
                    lockin = stack.enter_context(LockIn7270(terminator=args.usb_terminator,
                                                          timeout_ms=args.timeout_ms))
                if lockin is not None:
                    settings = lockin.get_settings()
                    metadata['lockin_settings'] = settings
                    if int(settings['REFMODE']) != 0 or int(settings['IMODE']) != 0:
                        raise RuntimeError('Acquisition requires single-reference voltage-input mode. '
                                           'Review the lock-in front-panel settings.')
                    if int(settings['VMODE']) == 0:
                        raise RuntimeError('Lock-in voltage input is grounded (VMODE 0). Review input selection.')
                    if args.recover_lockin:
                        from lockin_recovery import RecoveringLockIn
                        lockin = RecoveringLockIn(lockin,
                            reconnect=lambda: LockIn7270(terminator=args.usb_terminator,
                                timeout_ms=args.timeout_ms, drain_before_identity=True),
                            expected_settings=settings, retry_seconds=args.reconnect_seconds)
                        stack.callback(lockin.close)
                thermo = stack.enter_context(SIM922(port=args.port, baud=args.baud,
                    module_no=args.module, channel=args.channel))
                excitation = thermo.get_excitation()
                if excitation.upper() not in ('1', 'ON'):
                    raise RuntimeError(f'SIM922 channel {args.channel} excitation is off.')
                for channel in args.extra_channels:
                    excitation_reply = thermo.send_receive(f'EXON? {channel}').decode('ascii').strip()
                    if excitation_reply.upper() not in ('1', 'ON'):
                        raise RuntimeError(f'Extra SIM922 channel {channel} excitation is off.')
                metadata.update(sim900_identity=thermo.mainframe_id,
                    sim922_curve=thermo.get_curve(), sim922_excitation=excitation)
            lockin_identity = lockin.identity if lockin is not None else 'Not used (temperature-only mode)'
            metadata.update(lockin_identity=lockin_identity, thermo_identity=thermo.identity)
            handler = EventHandler(lockin, thermo, **options)
            print(f'{lockin_identity}\n{thermo.identity}')
            print('temperature_reported_k fields preserve the unverified SIM922 curve; raw diode voltages are saved.')
            if profile is not None:
                print(f"Named sensor temperatures use {profile['id']}: PROVISIONAL linear calibration.")
                for name, sensor in profile['sensors'].items():
                    print(f"{name} ch{sensor['channel']}: {sensor['warm']['voltage_mv']:.6g} mV at "
                          f"{sensor['warm']['temperature_k']:.2f} K; {sensor['cold']['voltage_mv']:.6g} mV at "
                          f"{sensor['cold']['temperature_k']:.2f} K (provisional; see metadata assumptions).")
                print('Values outside reference ranges are blank and flagged; raw readings are retained.')
            print('Current is not automatically read from the scope; document MON OUT checks separately.')
            if args.check:
                print(json.dumps(metadata, indent=2, default=str))
                display(handler.sample(time.monotonic()))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                # Claim the metadata name exclusively before replacing our own snapshots.
                with metadata_path.open('x', encoding='utf-8'):
                    pass
                owns_metadata = True
                metadata.update(status='running', rows=0, output=str(path.resolve()),
                                schema_version=3)
                write_metadata(metadata_path, metadata)
                print(f'Saving to {path.resolve()} (Ctrl-C stops and preserves saved rows).')
                print('Use mark_run.py in a SECOND terminal to timestamp reference intervals and events.')
                def saved_sample(row):
                    nonlocal last_console, last_heartbeat
                    metadata['rows'] += 1
                    metadata['last_sample_utc'] = row['timestamp_utc']
                    metadata['last_quality'] = row['quality']
                    metadata['last_elapsed_s'] = row['elapsed_s']
                    if backup is not None and backup.thread is None:
                        backup.start()  # Network and ZIP work run off the sampling thread.
                    if args.recover_lockin:
                        metadata['lockin_reconnections'] = lockin.reconnections
                        metadata['lockin_communication_failures'] = lockin.failures
                    now = time.monotonic()
                    if now - last_heartbeat >= 10 or row['quality'] in ('error', 'interrupted', 'lockin_unavailable'):
                        write_metadata(metadata_path, metadata)
                        last_heartbeat = now
                    if now - last_console >= args.console_every or row['quality'] in ('error', 'interrupted'):
                        display(row)
                        last_console = now
                handler.run(path, None if args.continuous else args.duration,
                            args.period, on_sample=saved_sample)
                metadata['status'] = 'complete'
        except KeyboardInterrupt:
            metadata['status'] = 'interrupted'
            print('\nStopped. Previously written CSV rows are preserved.')
            exit_code = 130
        except Exception as exc:
            metadata.update(status='error', error=f'{type(exc).__name__}: {exc}')
            print(f'\aAcquisition failed: {exc}', file=sys.stderr)
            exit_code = 1
        finally:
            if owns_metadata:
                metadata['finished_utc'] = datetime.now(timezone.utc).isoformat()
                write_metadata(metadata_path, metadata)
                if backup is not None and backup.thread is not None:
                    backup.finish()  # Final metadata is on disk before the last snapshot.
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
