# Lab setup and work completed — 2026-11-17

## Verified hardware connections

- SIM900 mainframe: FTDI serial adapter `/dev/cu.usbserial-BG02V860`, 9600 baud.
- SIM922: mainframe slot 7, channel 1. Identified as serial 024301, firmware 2.70.
- AMETEK / Signal Recovery 7270: native USB connection `0a2d:001b` now works.
- Keysight DSOX1204G: USB identity query succeeded.
- A Prolific serial adapter had been connected to the 7270 AUX port. Its official
  v2.2.11 driver was installed and activated on the Mac, but serial communication
  was not verified. Use the working native USB connection.
- Photographed 7270 serial settings: 19200 baud, 7 data bits, even parity,
  echo ON, prompt ON.

## Temperature calibration — deferred

The user confirmed the sample was settled at room temperature and independently
measured 26.2 °C. The SIM922 front-panel diode reading was 431.6 mV, giving one
reference point: **299.35 K, 431.6 mV**. The instrument itself reported roughly
336–338 K using its standard curve (CURV 0). The old software calibration predicts
approximately room temperature at that voltage, but has not been validated across
the experiment's range. A second independent reference is needed before fitting
a new two-point calibration. No sensor curve was uploaded or changed.

Live serial measurements established that VOLT? returns volts, despite the old
Python docstring claiming mV. Acquisition converts to mV once and records the
instrument temperature separately as unverified.

## Live verification

- `data/20261117T170236_852605Z.csv`: five temperature-only readings,
  approximately 431.651–431.654 mV.
- `data/20261117T171932_299681Z.csv`: five combined readings, approximately
  431.60 mV diode voltage, −0.0255 V lock-in X, +0.0002 V lock-in Y.
  All quality flags were OK; JSON metadata reports successful completion.
- Files prefixed `SIMULATED_` contain synthetic test data, not experimental data.
- Fourteen automated tests passed, and the live instrument check passed with uv.

## Remaining experiment work

Identify the sample excitation circuit and measure its RMS current. If a known
series resistor is used, current can be determined from its measured RMS voltage
and resistance. Record external voltage-amplifier gain if present. Confirm phase
alignment before interpreting X as the resistive voltage component; magnitude
represents impedance magnitude.

Obtain the sample geometry and voltage-contact spacing from the handout or direct
measurement. For a uniform sample, rho = (V / I) * A / L. Other sample geometries
may need a different method. Current and dimensions have not been guessed.

## Issues found in the original code

- Invalid extra `else` in the event handler, plus misspelled `sope_id`.
- Oscilloscope module/class spellings disagreed with their imports.
- Python lists used `.push()` instead of `.append()`.
- Windows COM4, module 4, and 57600-baud defaults did not match the lab setup.
- Temperature voltage units were documented incorrectly.
- Lock-in USB command null termination and binary response trailers were omitted.
- Set-command acknowledgments could remain queued and corrupt subsequent reads.
- Broad exception handling silently swallowed communication errors.
- Missing devices and endpoint assumptions produced unclear failures.
- `REMODE` was an invalid setup command; the command is `REFMODE`.
- Documentation claimed setup defaults were applied by construction, but they were not.
- Thread event clearing and barrier resetting could miss signals or deadlock.
- Curve-buffer code used unverified trailer assumptions and left raw data unscaled.
- Scope setup configured channel 2 while collecting channel 1 and disabled its own averaging.
- Data were saved only after the run; a fixed filename overwrote prior results.
- Sleep-after-query timing added query time to each interval.
- Importing the acquisition example connected hardware and started a run.
- Calibration used old hard-coded reference points and fitted on import.
- The so-called three-point calibration used two measured points with a fixed log term.
- Original acquisition did not calculate resistance or resistivity.

The original source is preserved in `backups/original/`. Its known defects remain
there for comparison; use the top-level modules for acquisition.
