# Verification and remaining limits

## Preparation on 2026-11-23

**23 tests passed locally on Python 3.12 and 3.14.** Hardware-free tests cover:

- USB null termination, split binary trailers and set-command acknowledgements.
- Invalid command and nonfinite reply handling, serial echo/status protocol.
- SIM922 serial terminators and volts-to-millivolts conversion.
- Resistance/gain/geometry arithmetic, overload suppression, blank unknown-current fields.
- Saved complete/partial rows after timeout, Ctrl-C, exclusive output protection.
- Additional diode channels with explicit fields and units.
- A six-hour run using a simulated clock: 2160 samples at a 10-second cadence,
  each with 0.4-second simulated query latency, no accumulated scheduling drift.
- Continuous CLI run interrupted during a read: partial row and final metadata saved.
- Failed atomic metadata replacement retains previous readable JSON.
- Windows idle-sleep state request/restoration using a mocked Windows API.
- Event appending without altering raw data.
- End-to-end synthetic warm/cold reference selection and derived CSV export,
  correct reference endpoints, out-of-range blanks, raw file unchanged.
- Fixed-log model inversion and rejecting missing markers/underdetermined fitting.

A real-time 60-second synthetic acquisition completed with **60 rows**, three
diode channels, all synthetic quality flags OK, and matching final metadata. It exercised periodic
heartbeat updates, three diode channels and filesystem saving with actual sleeps.
This does not prove hardware stability or Windows driver access.

CI runs the hardware-free suite on Windows, macOS and Linux with Python 3.12.
A configured workflow is not evidence of a passed CI run; check GitHub Actions.
Native Windows hardware and idle-sleep behaviour must be tested on the lab PC.

## Earlier physical hardware evidence

On the Mac on Nov 17:

- SIM900 identity: serial 152660, firmware 3.6; FTDI BG02V860, 9600 baud.
- SIM922 identity: serial 024301, firmware 2.70; slot 7, channel 1.
- Channel excitation 1 and curve selection 0 were queried successfully.
- Native USB 7270 identity and voltage-mode settings queried successfully.
- Keysight DSOX1204G identity queried successfully.
- Five-row SIM922-only and five-row combined runs saved, metadata completed.
- A later native USB --check also succeeded through uv.

These are connection/recording checks, not calibration or a long-run electrical
validation. Raw data reside in data/preliminary and have not been changed.

## Not yet verified

- Windows COM-port assignment, FTDI/native 7270 driver access, USB power management.
- Actual sample numbered terminal map, sensor identity and thermal equilibrium.
- Final floating-load differential voltage wiring and grounding.
- Cause of coil-driver clipping/time-dependent waveform deterioration.
- Stable sample current for a full cooling/heating cycle.
- A new cold calibration reference or a validated voltage-temperature curve.
- Automated scope RMS current logging (not implemented in the main loop).
- Hardware auto-reconnect (not implemented; error stops with a preserved partial row).
- Heating/control safety: logger does not operate or shut down heater equipment.
