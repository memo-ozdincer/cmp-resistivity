# CMP resistivity experiment — complete working notes

Consolidated 27 November 2026. This is the experiment's working reference: apparatus,
physics, actual bench observations, calibration, code repairs, data collection,
analysis and outstanding questions. Later confirmed observations override earlier
setup assumptions. Reported observations are distinguished from independently
verified wiring and measurements. Original handouts, raw data and supplied code
remain in the repository.

## Contents

- [Experiment aim and theory](#aim-and-theory)
- [Instruments and signal path](#what-each-instrument-does)
- [Lock-in X, Y and phase](#x-y-magnitude-and-phase)
- [Four-wire method and connections](#four-wire-method-and-actual-terminals)
- [Practice resistor and clipping](#known-resistor-observations-reported-nov-18)
- [Actual sample measurements](#actual-sample-measurements)
- [Modules and sensor map](#modules-and-sensor-map)
- [Temperature calibration](#temperature-calibration)
- [Cryostat and thermal behaviour](#cryostat-and-thermal-behaviour)
- [Original code and bugs](#supplied-versus-added)
- [Current acquisition code](#current-acquisition-code)
- [Computer and USB setup](#computer-and-usb-setup)
- [Running the experiment](#running-the-experiment)
- [Data storage and GitHub](#data-storage-and-github)
- [Graphing and earlier results](#graphing-and-earlier-results)
- [Outstanding questions](#outstanding-questions)
- [Source material and repository map](#source-material-and-repository-map)

## Aim and theory

The aim is to measure electrical resistance versus temperature for BSCCO
(bismuth strontium calcium copper oxide), a high-temperature superconductor,
between approximately 77 and 300 K. The superconducting transition is observed as
resistance falls toward zero. Examine transition temperature and width, cooling
versus warming curves, sampling/time-constant effects and thermal equilibration.
Where appropriate, compare sample-chamber pressure conditions following the TA's
procedure. Resistance is the direct measurement; uniform-sample resistivity
requires cross-sectional area A and voltage-contact spacing L: rho = R*A/L.
Sample dimensions and a continuously verified current have not yet been supplied.

The handout uses AC excitation at 37 Hz and ideally a 0.1-ohm practice resistor.
A known current passes through the sample, while a lock-in detects the resulting
small voltage at the reference frequency. For a sinusoidal signal, RMS = peak /
sqrt(2) = peak-to-peak / (2*sqrt(2)). Always compare consistent conventions.
The scope's AC RMS statistic removes DC; DC input coupling is a separate choice
that preserves the displayed waveform. "AC RMS - Cyc(4)" means channel FOUR,
not four volts or four cycles. The numeric value and unit are shown separately.

## What each instrument does

| Item | Role |
|---|---|
| 7270 OSC OUT | Generates sine-wave VOLTAGE controlling the driver; also reference |
| Hartshorn OSC IN -> rear TO LOAD | Converts input voltage to CURRENT through external load |
| Hartshorn CURR MON | Buffered ground-referenced voltage representing actual load current |
| Lock-in signal inputs | Measure sample VOLTAGE, not the sample current |
| Scope on OSC OUT | Shows excitation waveform voltage |
| Scope on CURR MON | Shows voltage representing current; I = V_MON / 1 ohm |
| SIM900 | Powers modules and relays computer communication |
| SIM922 | Excites diodes at 10 microampere and reads V / nominal temperature |
| PI controller and heaters | Control thermal evolution, separately from Python logger |
| Cryostat and pump | LN2 cooling and reduced heat transfer; inner sample and outer vacuum spaces differ |

The internal 1-ohm current-sense resistor is inside the Hartshorn driver, not the
scope and not the test sample. The scope always measures voltage at MON OUT;
100 mV represents 100 mA, 39.5 mV represents 39.5 mA. It does not measure the
sample's voltage there. Compute sample resistance from lock-in voltage / current.
The oscillator voltage is NOT the resistor voltage. For example 1 V OSC OUT ideally
commands 100 mA; 1 V ACROSS A RESISTOR at 100 mA would imply 10 ohm. A 0.1-ohm
resistor carrying 100 mA should have only 10 mV across it.

## X, Y, magnitude and phase

X and Y are two components of ONE detected voltage, relative to orthogonal
reference phases: X = Vmag*cos(phi), Y = Vmag*sin(phi). Voltage magnitude is
sqrt(X^2+Y^2). Some lock-ins label magnitude R, which must not be confused with
resistance in ohms. Rotating the reference changes X/Y but not ideal magnitude.
At 0 degrees a 1 mV signal has X=1 mV/Y=0; at 90 degrees X=0/Y=1 mV;
at 180 degrees X=-1 mV/Y=0.

For resistance specifically, align phase with the actual sample CURRENT and use
X/I. Y then represents quadrature voltage (reactive response plus phase errors).
Vmag/I is impedance magnitude and equals resistance only for a resistive sample
under the relevant conditions. A small lag from oscillator to actual current was
seen on the scope; it explains why reference phase can need adjustment even for
a resistor. Negative X with tiny Y is consistent with reversed sense polarity or
~180-degree phase; it is not negative passive resistance. A displayed zero Y is
only zero at the displayed resolution. Do not auto-phase a sample repeatedly and
thereby erase a physical quadrature response.

The handout's Z=R+jX uses X to denote REACTANCE in ohms. That X is not the same
quantity as the lock-in's X voltage channel; use distinct notation in analysis.

## Four-wire method and actual terminals

Current flows into outer contact A and out of D. Separate inner contacts B and C
sense voltage across the intervening sample section. A/B/C/D are diagram labels,
not established connector numbers. Current flows through the B-C region too;
B and C are not components inside the driver.

A two-wire resistance measurement includes current-lead/contact voltage drops.
Four-wire sensing puts the voltage boundary on the sample, excluding outer
current-wire/contact drops; very little current flows in sense wires. The sense
contacts should be close to the practice resistor body, with current contacts
farther out on its leads. Branching the sense pair at the driver posts still
includes the intervening wire drops. A 0.1-ohm sample plus 0.2-ohm leads can read
0.3 ohm in two-wire mode but 0.1 ohm with properly placed voltage contacts.

The breakout box has BANANA JACKS, TERMINALS and BNC banks with overlapping
numbering, and D-SUB/feedthrough connections. We have NOT traced which numbered
pair is sample current, sample voltage or a diode. Never infer 3/4 or 5/6 from the
four-wire cartoon. Use [the worksheet](docs/wiring-worksheet.md) and handout section 3.1.

## Known-resistor observations (reported Nov 18)

| Condition | Reported observation | Interpretation / limit |
|---|---|---|
| Resistor colours | Brown, black, silver; gap; gold, green body | Nominal 0.1 ohm +/-5%, not 10 ohm |
| Multimeter | About 17 ohm reported | Not validated; circuit state, lead/contact resistance and mode unknown |
| Initial MON OUT | 99.6 mV AC RMS | Nominally 99.6 mA if monitor path/waveform valid |
| Initial lock-in | X=-0.0169 V, Y=+0.0001 V | Magnitude ~16.9 mV; apparent ~0.170 ohm, not a validated resistor value |
| Higher drive | MON OUT sine became stepped/flat with sloping transitions | Clipping/limiting hypothesis, cause unproven |
| Scope AC coupling | Curved droop on red trace | Changed with coupling; input filtering contributed |
| Scope DC coupling | More square/trapezoidal trace, flat plateaus | Physical/signal-path distortion still present |
| One scope photo | OSC ~1.007 V RMS; MON ~42.09 mV RMS; ~27 ms periods | ~37 Hz fundamental; not merely phase shift |
| Next photo | OSC ~1.009 V RMS; MON ~40.90 mV RMS | Distortion persisted under DC input coupling |
| 0.1 V drive | Nice sine reported | Lower drive helped; resistor wiring also simplified |
| 0.5 V drive | MON 49.0 mV RMS | ~49 mA; near expected 0.1 A/V conversion |
| Above ~0.5 V drive | Clipping reported | Setup-specific threshold, not manufacturer's specification |
| Temporal behaviour | Started sine then deteriorated over seconds | Drift/protection/heating hypotheses; not diagnosed |
| 0.4 V drive, 37 Hz | MON 39.5 mV RMS; reference ~400 mV RMS | ~39.5 mA, expected conversion |
| Same lower-drive check | X=-0.0045 V, Y=0.0000 V | Apparent R~0.114 ohm, 14% high; outside nominal 5% tolerance |
| X percentage | About -0.91% | Fraction of sensitivity full scale; ~-4.5 mV / 500 mV, not error percent |

Treat the last result as a preliminary practice reading only. Its usefulness
depends on waveform stability during both measurements. The 14% discrepancy may
include wiring/contact error, grounding, reference phase, instrument settings or
actual component value; none was conclusively established. A current meter must
be IN SERIES; putting it across a resistor bypasses the resistor and changes the
circuit. Ohms checks require excitation off and an isolated resistor. A normal
two-lead DMM may not resolve 0.1 ohm reliably; first short its probes to assess
lead/contact resistance.

## Corrections to earlier advice

1. The driver manual states that front-panel attenuation, frequency band, In-Phase
   and Quadrature knobs affect only rear BALANCE OUT. They cannot set or fix TO LOAD
   current. Earlier suggestions that the band control might fix clipping were
   superseded by this evidence.
2. The driver requires a floating load. Earlier approval of single-ended A input
   centre/shield sensing was incomplete. Neither load terminal may be grounded by
   shield/earth. Differential sensing and grounding must be checked with the TA.
   This is a plausible disturbance mechanism, not a proven cause of the distortion.
3. Reducing drive restored a sine, supporting limiting, but wiring also changed;
   that trial did not isolate one cause. Time-dependent deterioration remains open.
4. The manual describes the direct current converter as DC-coupled through above
   5 kHz. Its 50-5000 Hz front-page range relates to intended use; the balance-band
   selector does not invalidate the handout's 37 Hz current-converter operation.
5. Do not treat a 100 mA front-panel range/knob on a different module as measured
   current. Use the Hartshorn's actual CURR MON. Scope RMS on distorted current is
   not directly comparable to a single-frequency lock-in voltage.

Source for driver behaviour and floating-load requirement:
[TeachSpin Hartshorn manual](https://www.teachspin.com/_files/ugd/3c5c71_e1c3f65faa484d029c694fdc9a133ebb.pdf).


## Actual sample measurements

The practice resistor was temporarily used in place of the cryogenic sample.
The intended BSCCO experiment sends a 37 Hz AC current through the outer contacts
and measures the potential difference between the inner contacts. The computer
reads voltage and temperature sensors; it does not drive the sample, regulate
the heater, or automatically measure the sample current from the oscilloscope.

Reported practice wiring: two resistor leads to the Hartshorn load output, with
a connection in parallel to the 7270 A input. OSC OUT was split between the
driver input and scope channel 1; the current monitor was viewed on scope channel
4 (red trace). A small lag between reference and monitor signals was visible.
The resistor was subsequently attached directly across the driver's load terminals
during waveform checks. Exact final cryogenic numbered terminal assignments and
sense shield connections have not been established. The 7270 A-only configuration
is documented as observed, not as a verified floating-load four-wire connection.

```text
7270 OSC OUT (37 Hz sine voltage) ----+----> Hartshorn OSC IN
                                    +----> scope CH1 reference

                         Hartshorn TO LOAD
                         +               -
                         |               |
                         A --- B === C --- D    BSCCO sample
                               |     |
                        voltage sense pair
                               |     |
                          7270 voltage input
                    (differential wiring to be verified)

Hartshorn CURR MON ----------------------> scope CH4 (current proxy)
SIM922 diode channels -------------------> base plate / sample temperatures
SIM900 + 7270 USB -----------------------> Windows logger
```

In the later pre-run check, oscillator amplitude was 0.8 V, MON OUT measured
79.8 mV AC RMS (79.8 mA if the monitor and sine waveform are valid), X=0.0009 V,
Y approximately zero, X=0.18% full scale. Apparent resistance X/I was
0.0009/0.0798 = 0.01128 ohm = 11.28 milliohm. This was a reported check of
whether the actual sample leads were sensible, not a measured current throughout
all future runs. Do not apply the current to a different run automatically.
For comparison, a 0.1-ohm calibration resistor at 79.8 mA would give 7.98 mV.

During the 27 November session the user reported X approximately 0.750 mV and
Y approximately 0.057 mV (units interpreted as mV). Magnitude = 0.75216 mV,
phase = atan2(Y,X) = 4.35 degrees, Y/X = 7.6%. Y does not arrive after X;
both are projections of the same AC voltage onto orthogonal reference phases.
Cable/amplifier phase, inductance, capacitance and the sample can all contribute.
A small nonzero Y is not proof that there is an independent voltage from the
electronics. The magnitude is only about 0.29% larger than X in this example.

### Resistance and resistivity calculation

- Correct external voltage gain G first: V_sample = V_lockin/G.
- With the reference aligned to the actual current, R = X/(G I_RMS).
- With magnitude, |Z| = sqrt(X^2+Y^2)/(G I_RMS), and phase contains information
  about the reactive component. This equals R only for a resistive response.
- For uniform geometry, rho = R A/L, with cross-sectional area A in square m and
  inner voltage-contact spacing L in m. Resistivity has units ohm m.
- At a constant 79.8 mA and unity gain, 0.750 mV would imply 9.40 milliohm,
  but the actual current must be confirmed for that reading.
- Preserve actual current checks, phase, sample dimensions and any gain changes.
  A lock-in voltage trend alone cannot distinguish changes in R from changes
  in current or measurement configuration.

## Modules and sensor map

A photographed SIM900 front panel shows:

| Slot | Module | Function |
|---|---|---|
| 5 | TeachSpin CMP Current Source | Separate selectable DC current source, polarity and local/remote controls; 1 V compliance monitor marking; not the current monitor of the AC experiment |
| 6 | TeachSpin CMP Hartshorn-Coil Drive | AC current converter, in-phase/quadrature balance controls, attenuation and frequency-band selector |
| 7 | SRS SIM922 diode temperature monitor | Four diode channels, 10 microampere excitation, mV/K selection |
| Other slots | PI controller/heater-related equipment present in cryostat system | Exact slot assignments not documented |

SIM900 is a mainframe, not itself a four-channel thermometer. The temperature
module is SIM922 in slot 7. SIM900 computer communications select the module
and pass serial commands through to it. The DC current source in slot 5 is
distinct from the AC Hartshorn module in slot 6. The photographed 100 mA knob
on the DC module is not evidence of the current in the Hartshorn load.

User-confirmed sensor map on 27 November:

| SIM922 channel | Physical sensor | Calibration |
|---|---|---|
| 1 | Base plate | Separate linear curve |
| 2 | Sample | Separate linear curve |
| 3 | Unidentified; now giving readings | Raw V and nominal SIM922 K only |
| 4 | Unidentified; now giving readings | Raw V and nominal SIM922 K only |

Channels 3 and 4 were initially HOT on the photograph; that did not establish
their identities. User later reported both now show readings, but their
locations are not known. Existing logger supports all four with
`--channel 1 --extra-channels 2 3 4`. The code checks channel excitation before
starting and does not enable it automatically. Restart is required to change
which channels are acquired; keep the previous run. Current live graphs show
ch1 and ch2; extra channels are preserved in the CSV, not calibrated or
automatically added to the existing graph.

## Temperature calibration

### Why the initial display was wrong

The SIM922 showed approximately 336–338 K while the apparatus was at room
temperature (one photograph 334.7 K). It was using its standard curve, CURV 0,
which does not match the installed TeachSpin transdiodes. The instrument's
VOLT? reply is in volts, whereas the front panel shows millivolts. The logger
multiplies by 1000 exactly once. The SIM922 temperature-reported fields remain
unverified; do not confuse them with the software-calculated temperatures.
We have not rewritten any instrument curve or adjusted diode excitation.

### Reference history

| Reference | Observation and decision |
|---|---|
| 26.2 C / 431.6 mV | Explicitly invalidated by user; discarded |
| 22.2 C / 435.4 mV | Settled ambient-pressure observation, no vacuum; historical candidate, not current calibration |
| Supplied code 297.6 K / 435.9 mV and 77 K / 992 mV | Historical constants, not new measured points |
| 23.5 C, run _1 | Warm marker 14:50:31–14:50:44 UTC on Nov 24; 13 ch1 samples, mean 433.188153846 mV, SD 0.001994 mV |
| Marked cold interval, run _1 | 15:10:15–15:16:34 UTC; 379 readings from 769.892 to 838.257 mV, mean 806.457 mV, SD 19.762 mV; still cooling, rejected as a stable reference |
| 990 mV remembered/expected | Not substituted for recorded value |
| 981.166 mV, run _3 | Highest recorded base plate voltage, 12:13:50 EST; 60 nearby readings mean 981.161883 mV, SD 0.001497 mV. Assigned nominal 77 K at user's request |
| 28.08 mV sample, ~431.9 mV base plate | User's later warm observation. Use earlier 23.5 C provisionally for sample; actual temperature not separately specified |
| ~619 mV sample during LN2 cooldown | Approximate user-reported cold anchor, assigned nominal 77 K; not an independently established stable sample plateau |

### Current calibration model

The handout's general form is V(T) = c1 - c2 T - c3 ln(T/1 K). Two
temperature points determine only two independent parameters. The old
logarithmic fit fixed c3=0.405 mV; it was not an independent three-point fit.
Our current calibration uses the ordinary linear form c3=0 independently for
each diode:

```text
T = T_warm + (V - V_warm) * (T_cold - T_warm)/(V_cold - V_warm)
```

| Sensor | Warm anchor | Cold anchor |
|---|---|---|
| Base plate | 433.188153846 mV at 296.65 K | 981.166 mV at 77 K |
| Sample | 28.08 mV at assumed 296.65 K | approximate 619 mV at nominal 77 K |

Base plate V_mV = 1173.263856 - 2.494777356 T_K.
Sample V_mV = 28.08 + (619 - 28.08)(296.65 - T_K)/(296.65 - 77).
The stored profile is [calibrations/recooldown-provisional.json](calibrations/recooldown-provisional.json),
currently ID recooldown-provisional-linear-v2. Use Kelvin in calculation;
Celsius = K - 273.15.

The initial implementation blanked temperatures outside the warm/cold reference
interval; the user requested normal linear calibration instead. That cutoff
was removed on 27 November. The same equation now extrapolates, labelled
`extrapolated` instead of blanking values; invalid or missing readings remain
blank. For the actual warm readings 431.594 mV and 27.461 mV, the revised
software gives 297.289 K (24.139 C) base plate and 296.880 K (23.730 C) sample.
The older offline both-sensor export was generated before this correction and
contains blank out-of-range values; re-export using the current profile for
ordinary linear calculations. The separate marked-interval tool
`calibrate_run.py` still restricts its own fit to its reference interval.

These are usable provisional temperature estimates, not independently validated
absolute temperatures. Assigning the maximum voltage to 77 K sets that endpoint
by definition. A sample may be warmer than the base plate. Extrapolated
below-77 K estimates do not establish that the sample really cooled below LN2
temperature. There is no measured full-range diode transfer function or
statistical absolute-temperature uncertainty. Keep reference provenance and
improve each curve with independent stable reference intervals.

## Cryostat and thermal behaviour

The outer evacuated space is insulation around the LN2 reservoir. An inner
sample chamber provides a distinct environment; its pressure may influence
thermal conductance. The user previously reported that warm-up was almost
stationary over hours, with a possible leak between inner and outer chambers,
and asked about leaving the pump running overnight. No leak test, pressure
history or valve map was supplied, and we did not establish that the chambers
were leaking. Use the actual cryostat handout and TA instructions for vacuum,
valves, overnight operation, nitrogen fill and heaters. Reservoir vent and
chamber vacuum are different; vacuum gauge reading is not LN2 boiling pressure.
The instrument software is only a logger, not a cryostat safety controller.

The handout permits room-temperature reference measurements without vacuum
but requires outer-space insulation vacuum for cryogenic operation. For an
ambient-pressure inner chamber it specifies dry nitrogen instead of room air.
Do not infer sample temperature from reservoir equilibrium. Thermal contact,
heat capacity and heat transfer give lag between base plate and sample. Cooling
and warming branches may differ because of lag rather than intrinsic hysteresis.
The aim was to acquire continuously for hours, particularly on warming, and
capture the two calibration reference temperatures during the same experiment.

## Supplied versus added

The lab supplied six files: `lockin_7270.py`, `sim922.py`, `event_handler.py`,
`daq_example.py`, `temp_calibration.py`, and misspelled `oscilliscope.py`. Their
original contents are preserved unchanged in `backups/original/`.

Active versions were substantially repaired or rewritten. Added files include the
correctly spelled `oscilloscope.py` (old spelling now imports it), automated tests,
uv configuration/lock, dependency list, Git ignore rules and documentation.
For continuous collection, `run_support.py`, `mark_run.py` and `calibrate_run.py`
were added. Later additions: `lockin_recovery.py`, `sensor_calibration.py`,
`github_backup.py`, calibration profiles, and analysis/plotting scripts. Third-party Python packages and hardware drivers were installed,
not written by us.

## Original faults identified

- Extra `else` made event_handler.py syntactically invalid; `sope_id` was misspelled.
- Class/module spellings disagreed between oscilloscope imports and implementation.
- Python list examples used nonexistent `.push()` instead of `.append()`.
- COM4/slot4/57600-baud defaults mismatched the observed Mac setup.
- get_V's docstring said mV, but live VOLT? replies were V.
- USB commands omitted null terminators; binary status/overload trailers were not parsed.
- Set-command acknowledgements could remain unread and corrupt subsequent replies.
- Broad exceptions hid communication failures; missing devices produced poor errors.
- Endpoint indexing assumed descriptor order rather than direction/type.
- Invalid `REMODE` setup command should be `REFMODE`; voltage/current mode was unclear.
- Documentation said defaults were applied on construction, but setup was not called.
- Thread events/barrier reset could miss signals or deadlock.
- Curve parsing stripped an assumed trailer length and left raw values unscaled.
- Scope setup configured channel2 while reading channel1 and disabled its own averaging.
- End-of-run-only saving lost data after interruption; fixed filenames overwrote runs.
- Sleep-after-query timing added query duration to each requested period.
- Importing the example connected hardware and started acquisition.
- Calibration used old hard-coded reference data and fitted on import.
- A so-called three-point fit used only two measured points with a fixed log term.
- The original example did not compute resistance/resistivity or preserve quality flags.


## Current acquisition code

| File | Responsibility |
|---|---|
| daq_example.py | CLI, device connections, settings audit, run metadata, console, continuous mode |
| event_handler.py | Sequential measurements, quality flags, timing, calculations, per-row saving |
| sim922.py | SIM900 serial pass-through and SIM922 diode queries |
| lockin_7270.py | Native USB and optional serial lock-in communications |
| lockin_recovery.py | Optional native USB recovery without settings changes |
| oscilloscope.py | Separate scope helper; not automatic current acquisition |
| oscilliscope.py | Compatibility for original misspelled module |
| temp_calibration.py | Linear and historical log-model helpers |
| sensor_calibration.py | Named live sensor estimates and offline reprocessing |
| calibrate_run.py | Offline fit from explicitly marked reference intervals |
| run_support.py | Atomic JSON writes and Windows idle-sleep state |
| mark_run.py | Timestamped notes from another terminal |
| github_backup.py | Periodic ZIP snapshots and direct GitHub token/gh uploads |
| analysis/analyze_recooldown.py | Reproducible analysis of Nov 24 runs _2–_6 |
| analysis/plot_live_backup.py | Fetch latest real GitHub run and render/publish graphs on Mac |

Changes after the original bug fixes:

- USB endpoint discovery now uses direction/type; native replies consume null
  and status/overload trailer. Queries time out rather than hanging forever.
- Connection checks inspect instrument mode/settings rather than resetting
  the lock-in or changing oscillator frequency, gain or phase.
- Sequential sampling replaces original threaded curve capture. A sample's
  timestamp is its start time, with read_duration_s indicating sequential query
  duration. It is not a set of simultaneous readings.
- Monotonic sampling deadlines prevent query duration accumulating as scheduling
  drift. Missed slots are skipped. Adding diode channels takes longer.
- CSV created exclusively and saved immediately (flush/fsync per row).
  Timestamped default names prevent accidental overwrites. Partial error rows
  survive timeouts and Ctrl-C. JSON sidecar is atomically replaced with heartbeat.
- Requested continuous mode runs until Ctrl-C. The Windows idle-sleep request
  is restored on exit; it cannot prevent manual sleep, power loss or reboot.
- Lock-in overload/reference warnings suppress derived resistance, preserving raw.
- Current and geometry are only used when explicitly supplied. Scope current
  readings and clip detection are not automatic.
- Temperature-only mode can continue when electrical acquisition is unavailable.
- Opt-in --recover-lockin logs lockin_unavailable rows while attempting native
  USB reconnection at intervals (default 15 s); drains stale input, confirms
  identity and requires original settings to match before accepting new values.
  Does not silently replay readings. Default still saves partial row and stops.
  Recovery tested with synthetic devices; not independently verified on hardware.
- Per-sensor named calibration, raw values and full profile metadata; revised
  linear v2 model extrapolates instead of blocking out-of-reference readings.
- Background GitHub snapshots add cloud redundancy while preserving local files;
  no automatic Git pull/merge inside logger.

### Recorded software/hardware settings and verification

Nov 24 runs _2–_6 recorded initial lock-in settings REFMODE=0, IMODE=0,
VMODE=1 (A only), IE=0, DCCOUPLE=0, FLOAT=1, REFP=0, TC.=0.2 seconds,
SEN.=0.5 V, OF.=37 Hz, OA.=0.800004 V. Settings were captured at start;
these fields do not prove that each physical setting stayed unchanged.
The 500 mV sensitivity explains why the small readings were poorly resolved
relative to their magnitude; exactly 50 microvolt voltage steps appear in
those data. Later Nov 27 voltage values have finer reported increments.

Two original connection checks on Nov 17 recorded five samples each: temperature
only ~431.651–431.654 mV; combined ~431.60 mV, X~-25.5 mV and Y~+0.2 mV.
These were setup checks, not the later resistor calibration.
SIM900 serial 152660 firmware 3.6; SIM922 serial 024301 firmware 2.70, excitation
on and CURV 0; native 7270 and Keysight scope identities queried. Windows
subsequently collected real runs, establishing that the USB path worked on
that machine, although intermittent timeouts occurred.

Hardware-free suite progressed from 14 to 23, 31, 38 and 40 tests. Earlier
31- and 38-test versions passed Windows, Linux and Mac CI. Latest recorded
local 40-test suite passed; actual GitHub create/update/download verified via
both gh and direct HTTPS (latter without invoking gh for the upload).
Tests cover protocol framing/acks, serial echo, units, invalid settings,
calculations, status flags, partial rows, six-hour mocked clock scheduling,
metadata durability, event marking, separate sensor curves, swapped channel
mapping, extrapolation, recovery/backoff, backup byte integrity and offline retry.
These do not prove physical wiring or absolute calibration.

## Computer and USB setup

The lab supplied Python files (preserved under backups/original); we set up
uv (Python 3.12 recommended; local Python 3.14 also tested). Dependencies:
pyserial 3.x, pyusb 1.x, numpy 2.x, pyvisa 1.x, pyvisa-py 0.x,
and Windows-only libusb-package. Plotting uses pandas, numpy and matplotlib
on the Mac. These third-party libraries and drivers were not written by us.

Three independent instrument links:

| Instrument | Connection | Evidence |
|---|---|---|
| SIM900 | Rear COMPUTER RS232 via FTDI USB serial; 9600 baud | Mac /dev/cu.usbserial-BG02V860; Windows COM port must be checked |
| 7270 | Native rear USB-B; VID:PID 0a2d:001b | Successfully queried on Mac and later Windows |
| Keysight DSOX1204G | USBTMC, PyVISA-py | Identity tested; scope readings for current recorded manually |

Initial difficulty: adapter/lock-in disappeared from device list when disconnected.
One Prolific adapter (067b:23a3) had been plugged into AUX RS232, not the correct
rear RS232 port. User tried an older PL2303HXD_G_Driver_v2_0_0_20191204.zip; newer
official Mac driver v2.2.11 was installed, producing a serial device. Final
successful lock-in communication used native USB, not this unverified serial
fallback. App Store connectivity had been problematic; no App Store software
needed for the final logger.

Photographed alternate 7270 RS232 settings: 19200 baud, 7 data bits, even parity,
echo ON, prompt ON, address 0. Use correct RS232 rather than AUX port, distinct
COM ports and appropriate cable. Optional serial check:
```powershell
uv run python daq_example.py --port COM4 --lockin-port COM5 --lockin-baud 19200 --lockin-data-bits 7 --lockin-parity E --check
```

Windows uv installs Python user-space dependencies, not the kernel USB driver.
The native 7270 needs a driver compatible with PyUSB/libusb (e.g. WinUSB);
the FTDI needs its COM driver. Existing driver worked for actual Windows runs.
If future issues occur, inspect Device Manager and consult lab staff before
replacing any shared-PC driver; Zadig can change a specific driver and affect
other lab programs. Do not replace unrelated device drivers.
See [Windows setup](docs/windows-setup.md) for vendor links and details.

## Running the experiment

Windows PowerShell (native Windows rather than WSL), inside repository folder:
```powershell
uv sync --locked --python 3.12
uv run python -m unittest discover -s tests -v
uv run python -m serial.tools.list_ports -v
uv run python daq_example.py --list-devices
uv run python daq_example.py --port COM4 --check
```

COM4 is a placeholder, not verified as actual current port. Use the discovered
port. Stop the logger before any code update or new channel configuration.
Git pulls may download more backup files; a running process retains the old
code and loaded calibration profile until restarted.

Normal actual run, with both identified sensors:
```powershell
uv run python daq_example.py --port COM4 --channel 1 --extra-channels 2 --continuous --github-backup
```
To record also unidentified but connected/excited channels:
```powershell
uv run python daq_example.py --port COM4 --channel 1 --extra-channels 2 3 4 --continuous --github-backup
```

Default period 1 s, console every 10 s, backup every 300 s, lock-in timeout
2000 ms. Can set --timeout-ms 10000 as a diagnostic for delayed replies.
If "7270 timed out on MAG." or "Y", the command did not complete; cable and
terminator are possible causes, not proven diagnosis. Native USB status reply
mode default is --usb-terminator status; null-only is appropriate only if the
instrument menu matches. Earlier long-run timeouts were not a fixed 10,000 s
limit: runs stopped after widely different row counts. Bare default stops on
communication failures; optional --recover-lockin may preserve diode acquisition
during missing voltage. Do not reset shared equipment merely to fix the PC link.

For a known and stable sample RMS current, correct phase and external gain,
add --current-a VALUE --voltage-component x; add --voltage-gain VALUE if needed.
For resistivity also supply both --area-m2 and --length-m. Without independent
current and geometry, retain voltage rather than inventing those inputs.
Use --simulate for tests (synthetic data clearly marked); --temperature-only
for diode measurements if lock-in unavailable. Use --duration N for timed runs.

Start continuous recording before the room-temperature interval, mark cooldown,
LN2 references, temperature plateaus, current checks and heating. Keep the
terminal open with AC power. Log noteworthy changes and uncertainties in notebook.
Use a second terminal pointing to the actual active run (example name only):
```powershell
uv run python mark_run.py data/runs/YOUR_RUN.csv warm-start --note "Independent thermometer and location"
uv run python mark_run.py data/runs/YOUR_RUN.csv warm-end
uv run python mark_run.py data/runs/YOUR_RUN.csv cold-start --note "Reference temperature and equilibrium evidence"
uv run python mark_run.py data/runs/YOUR_RUN.csv cold-end
uv run python mark_run.py data/runs/YOUR_RUN.csv current-check --note "MON OUT AC RMS, waveform, phase and settings"
uv run python mark_run.py data/runs/YOUR_RUN.csv heating-start
```
Collect stable intervals (preferably 30–60 s or longer) with independent known
temperature. The separate marker-fit tool requires exactly one start/end pair
for warm and cold for the chosen sensor. Sensor reference times may differ.
Stop with Ctrl-C once; check CSV and sidecar metadata. Do not open active CSV
in Excel if it takes an exclusive file lock.

## Data storage and GitHub

Private repository: [memo-ozdincer/cmp-resistivity](https://github.com/memo-ozdincer/cmp-resistivity).
User requested only one branch, main. A temporary acquisition-data branch was
merged and deleted. All automatic uploads are to main/live/<run-id>/snapshot.zip.
Every snapshot contains only the run CSV, metadata JSON, optional events JSONL
and SHA-256 manifest. Local files are authoritative. Backups start after first
saved sample, every five minutes by default, and at completion/interruption.
Network failures are retried without stopping local sampling once the run starts.
Preflight authentication happens before hardware connection; final wait bounded
to 30 s. Snapshot input cap 40 MiB; very large runs need new segments.
Existing ZIP is updated with its current SHA; previous revisions remain in Git
history. Backup-only commits do not trigger code CI.

Windows could not install gh. We implemented Python standard-library HTTPS
directly using GITHUB_TOKEN (or GH_TOKEN); existing gh login remains fallback
on Mac. Token read from environment, not copied into metadata or CSVs.
One-time [fine-grained token creation](https://github.com/settings/personal-access-tokens/new):
owner memo-ozdincer, only cmp-resistivity, Contents read/write, suitable expiry.
In Windows PowerShell, set session token via hidden prompt:
```powershell
$env:GITHUB_TOKEN = [System.Net.NetworkCredential]::new('', (Read-Host "GitHub token" -AsSecureString)).Password
uv run python daq_example.py --simulate --duration 10 --extra-channels 2 --github-backup
```
Token is not printed; never share in chat or commit it. Repeat for new terminal.
Clear when finished with Remove-Item Env:GITHUB_TOKEN. A Windows token-auth
upload was explicitly confirmed during the Nov 27 session (real run with
431.594 mV base plate and 27.461 mV sample). Later automatic backups arrived.
If final upload fails, retry a saved run from same authenticated terminal:
```powershell
uv run python github_backup.py data/runs/YOUR_RUN.csv
```
Keep its .csv.backup.json so same remote UUID is reused. Do not concurrently
retry a run whose automatic backup worker is active.

### Files and columns

- run.csv: sample_index, timestamp_utc, elapsed_s, read_duration_s, simulated;
  raw primary diode_voltage_mv, temperature_reported_k, additional diode_chN_voltage_mv
  and temperature_chN_reported_k; lockin_x_v, lockin_y_v, lockin_magnitude_v,
  lockin_phase_deg, lockin_status, lockin_overload, quality and error.
- schema 3 includes sensor_calibration_id, base_plate/sample_diode_channel,
  base_plate/sample_diode_voltage_mv, base_plate/sample_temperature_calibrated_k,
  and per-sensor calibration_quality. These derived K values differ from original
  SIM922 curve. v2 profile uses provisional_linear/extrapolated/invalid_voltage/
  not_read/disabled flags. Electrical quality and calibration quality are separate.
- Optional current_rms_a, voltage_component, voltage_gain, area_m2,
  voltage_contact_spacing_m, resistance_ohm, resistivity_ohm_m.
- run.csv.json: argument snapshot, instrument identities, initial lock-in settings,
  full calibration profile and hash, times, row count, status/heartbeat.
- run.csv.events.jsonl: event marker stream; optional.
- run.csv.backup.zip and .backup.json: last local backup snapshot and status,
  last success time, commit, URL and pending retry indication.
- status running is not proof of current activity; check latest timestamp.
  Complete/interrupted/error indicate process outcome; Ctrl-C is normal stop.
  No fabricated values for missing electrical readings.

## Graphing and earlier results

### Nov 24 recooldown archive

Original user archive recooldown.zip extracted unchanged to data/recooldown/raw;
22 source files. The main analysis selects _2 through _6; _1 provides reference
markers; early setup and simulated runs excluded. Snapshot SHA-256:
ab2abb4d30cbfaa118ea09e312bfc87aa3ceb167b2e27c1b9b460fd617b4c998.

| Run | Rows | Complete OK electrical rows | Notes |
|---|---:|---:|---|
| _2 | 1,252 | 1,251 | Y timeout |
| _3 | 9,500 | 9,499 | Y timeout; redo-vacuum marker 11:28:17 EST |
| _4 | 12 | 11 | PHA timeout |
| _5 | 397 | 396 | I/O failure |
| _6 | 40 | 40 | CSV captured with stale running metadata (32 rows) |

11,201 total rows, 11,197 complete electrical rows, four partial errors. All
recorded data between 10:43:33 and 15:07:43 EST (15:43:33–20:07:43 UTC).
4.403 h wall-time, 3.110 h within recorded segments. Gaps _2→_3 24.52 s,
_3→_4 75.74 min, _4→_5 56.46 s, _5→_6 27.83 s. No overlap or duplicated
timestamps. Gaps left blank; cannot reconstruct lost heating branch.
Typical ~1 Hz sample cadence; ~0.75 s query duration.

Base plate voltage starts 940.447 mV, peaks 981.166 mV at 12:13:50 EST,
then drifts to ~980.1 mV. With current provisional curve: initial 93.32 K,
minimum 77 K, final 77.43 K. Ch2 ranged 610.22–693.019 mV with substantially
different fluctuations. The old sample calibration cutoff allowed only 133
of those rows inside 28.08–619 mV; 11,068 were outside. Current linear profile
extrapolates, but this does not validate temperatures below the cold anchor.

Typical first X 0.75 mV and final X 0.35 mV, 53.3% decrease.
Y exactly 0.05 mV in every valid electrical row; X levels spaced 0.05 mV.
If current stayed 79.8 mA, X/I would decrease ~9.40→4.39 milliohm. That is a
conditional estimate only; no logged current or dimensions. No demonstrated
zero-voltage/zero-resistance state and no defensible Tc extracted. A drop in
voltage alone does not establish superconductivity if current or wiring varied.

[Archived analysis results](results/recooldown/) include PNG/SVG graphs,
HTML report, calibrated CSVs, numerical audits/source hashes and ZIP.
[Voltage versus base plate temperature](results/recooldown/07_voltage_vs_base_plate_temperature.png)
plots X in mV against base plate kelvin, not time, with separate run colours.
This graph is not sample temperature or resistivity. For proper final resistance
vs sample temperature use its own calibration, actual current and phase.
An additional display version with zero vertical-axis baseline was generated
locally at output/recooldown/voltage_vs_temperature.png (also SVG, PDF, CSV).
Analysis intentionally preserves discrete measurement levels without smoothing.

Reproduce the offline analysis (plot dependencies isolated from acquisition):
```sh
uv run --no-project --with pandas --with numpy --with matplotlib python analysis/analyze_recooldown.py
```
Recompute both named sensor estimates in a new file using current profile:
```sh
uv run python sensor_calibration.py results/recooldown/merged_runs_2_to_6.csv --primary-channel 1 --output output/recooldown/recalibrated_v2.csv
```

### Nov 27 real-time monitoring

Separate Mac graphing keeps Windows acquisition untouched. Reads GitHub through
git fetch origin main and reads ZIP blobs from origin/main (no checkout or
instrument calls). Selects most recent real run by last recorded timestamp,
excludes simulated backups, recalculates ch1 and ch2 using current calibration,
then displays temperature over time, both diode voltages, and X/Y over time.
It does not connect across runs or fill sampling gaps; its most recent run
may begin after a restart, so preserve all prior segments for final analysis.
Local plot and download files:
- output/live-monitor/index.html (refresh every 60 s)
- output/live-monitor/latest.png
- output/live-monitor/latest_snapshot.zip
- output/live-monitor/latest_readings.csv and latest_summary.json

Mac process launched with python3 analysis/plot_live_backup.py --watch --publish.
Checks remote each minute; new data typically arrives every five minutes.
Uploads to [live/latest.png](https://github.com/memo-ozdincer/cmp-resistivity/blob/main/live/latest.png)
on main. Source snapshot/profile/script hash prevents uploading again just
because the graph itself made a commit. Published PNG verified byte-for-byte.
Keep this Mac process running for automated graph publication; stop/restart
it independently of Windows. Credentials are Mac gh or environment token;
Windows does not need graph dependencies. For fresh environments:
```sh
uv run --no-project --with pandas --with numpy --with matplotlib python analysis/plot_live_backup.py --watch --publish
```

Early Nov 27 backup at 10:59:30 EST had 301 real rows over about five minutes;
base plate estimate 297.32→281.96 K, sample 297.05→294.88 K, X
1.377→1.352 mV. Consistent with base plate cooling first and sample thermal lag.
Later run started 11:03:55 EST; snapshot through 11:34:04 EST had 905 rows
over 30.13 min, base plate estimate 240.82→101.08 K, sample 288.78→186.05 K,
X 1.329→0.727 mV. Additional channels supported if logged, but sample time
interval may lengthen as queries increase. These are snapshots of ongoing
data, not final experiment results. Use current GitHub timestamp for latest.

## Outstanding questions

- Trace actual numbered current and sense terminal pairs (3/4 vs 5/6 and banks),
  verify inner vs outer contacts, differential/floating load and grounding.
- Identify ch3 and ch4 physical sensors. Record excitation, independent reference
  temperatures and voltages before assigning calibration.
- Confirm sample identity/geometry, current monitor transfer and clean waveform
  during actual long-run measurement, reference phase and external gain.
- Determine cause of time-dependent current clipping and USB timeouts; optional
  reconnect is not proof of a fixed fault.
- Establish independent equilibrium and refined sensor calibration anchors;
  identify whether sample, base plate or reservoir actually reached nominal 77 K.
- Clarify vacuum leak suspicion, pressure history, valve state and temperature lag
  with TA. Preserve cooling and warming data and all event timings.
- Compute final R(T), rho(T) and transition temperature/width only with justified
  current/phase, geometry, sample temperature and sufficient measurement resolution.
- Compare cooling/warming traces without inventing missing measurements;
  investigate possible residual signal and distinguish instrument resolution,
  reactive voltage, thermal lag and sample behaviour.

## Source material and repository map

This file is the central summary. Detailed source documentation remains useful
for exact tool options and historical evidence, but some early statements in
those files predate corrections that are recorded above.

- [CMP course handout](docs/handouts/cmp-lab-handout.pdf)
- [Cryostat orientation](docs/handouts/cryostat-getting-started.pdf)
- [TeachSpin Hartshorn manual](https://www.teachspin.com/_files/ugd/3c5c71_e1c3f65faa484d029c694fdc9a133ebb.pdf)
- [Wiring worksheet](docs/wiring-worksheet.md)
- [Windows and USB setup](docs/windows-setup.md)
- [Collection runbook](docs/collection-runbook.md)
- [GitHub backup instructions](docs/github-backup.md)
- [Calibration details](docs/sensor-calibration.md)
- [Data schema and reference history](docs/data-and-calibration.md)
- [Original code history](docs/code-history.md)
- [Bench observations](docs/experiment-notes.md)
- [Verification record](docs/verification.md)
- [Nov 17 session archive](docs/archive/session-notes-2026-11-17.md)
- [Original supplied code](backups/original/)
- [Preliminary raw checks](data/preliminary/)
- [Synthetic examples](data/simulated/)
- [Nov 24 raw archive](data/recooldown/raw/)
- [Calibration profile](calibrations/recooldown-provisional.json)
- [Analysis and scripts](analysis/)
- [Saved results](results/recooldown/)
- [Live backups on GitHub](https://github.com/memo-ozdincer/cmp-resistivity/tree/main/live)

Local checkout: /Users/memoozdincer/Documents/3f/APL/resistivity.
Local-generated output/ is ignored by Git. Source, tests, documented results
and snapshots live on main. No secret access tokens are part of the notes.
