# Collection runbook — planned session 2026-11-24

Goal: one continuous raw-voltage record spanning room-temperature reference,
cooldown, stable cold reference, and slow warm-up. Apply calibration afterward.
Collecting data does not itself validate the electrical circuit or thermal equilibrium.

## 1. Before cooling

1. Follow [Windows setup](windows-setup.md), including a simulation and actual
   connection check on THAT computer. Mac success does not prove Windows drivers work.
2. Fill in [the wiring worksheet](wiring-worksheet.md). Identify the physical diode
   on each logged SIM922 channel; identify sample current and voltage terminals.
   Terminal pairs 1/2, 3/4, 5/6 have NOT been assigned from evidence yet.
3. Confirm coil-driver load remains floating. The prior single-ended A/shield
   connection may disturb it. Have the TA verify differential sensing and input
   grounding. Do not ground either TO LOAD terminal with a scope ground clip.
4. Confirm a stable sinusoidal CURR MON waveform for several minutes, not merely
   immediately after setting amplitude. Previously distortion developed with time
   and above about 0.5 V RMS drive; its cause is still unknown.
5. Record oscillator frequency/amplitude, actual MON OUT AC RMS voltage, channel
   coupling/probe factor, lock-in input selection, phase, sensitivity, time constant,
   gain and sample details. A 37 Hz reference and internal mode were used previously;
   do not change wiring/settings blindly to match old measurements.
6. Connect the SIM900 at 9600 baud, slot 7. Confirm USB identity and diode voltage
   agree with the front panel (V in serial response; mV in saved CSV).
7. Close other programs that control the instruments. Save locally, outside OneDrive
   or network folders during collection. Keep power connected, lid open, USB cables
   secured, and automatic updates/restarts managed according to lab-PC policy.

Cryogenic assembly, pumping, LN2 filling and heater operation follow the course
handout and TA instructions, not this software guide. Outer insulating space must
be evacuated before filling; an ambient-pressure inner sample chamber uses dry
nitrogen, not room air. Keep the reservoir vent unobstructed. Never vent cold
hardware. The handout's cold-calibration arrangement mentions the sample not
attached: confirm the intended arrangement and which sensors can be treated as
77 K with the TA when combining calibration and sample collection in one cooldown.

## 2. Establish a short baseline

In PowerShell, from the project folder, substitute the actual COM port:

```powershell
uv run python daq_example.py --port COM4 --check
uv run python daq_example.py --port COM4 --duration 300 --period 1 --sensor-name "sample plate" --output data/runs/baseline_20261124.csv
```

Inspect the CSV and JSON and compare values to front panels. Allow stable readings
for five minutes. Do not use the historical 22.2 C value as tomorrow's reference.

If more than one connected diode is available, add e.g. `--extra-channels 2 3`.
Enable/identify those sensors first; the program checks excitation but does not
turn it on. Record each location in `--notes`. The primary channel defaults to 1;
use `--channel 2` if the verified sample sensor is on 2. Disconnected channels must
not be included; they can invalidate/stop a row. Readout times increase with channels.

## 3. Start the continuous run BEFORE recording the warm reference

Choose a new filename for every attempt; never reuse an existing file:

```powershell
uv run python daq_example.py --port COM4 --continuous --period 1 --sensor-name "sample plate" --notes "Fill in terminal map, sample ID, pressure and electrical settings" --output data/runs/run_20261124.csv
```

This runs until Ctrl-C, including the long heating period. A one-second requested
period is a starting choice, not proof of independent samples; the lock-in time
constant and actual `read_duration_s` matter. No arrays grow with run length.

The terminal prints an update about every 10 seconds. The CSV is flushed and
synced after every row. The JSON heartbeat updates about every 10 seconds, with
row count and last sample time. It need not show the last few CSV rows after a
crash. Do not open the active CSV in Excel if it locks the file. Use the terminal
or read it in a tool that does not take an exclusive write lock.

## 4. Mark reference intervals and events from a SECOND terminal

Use another PowerShell in the same project folder on the SAME PC. These commands
append to a separate events file and do not interrupt acquisition. Mark intervals
only when readings are stable, and collect at least 30-60 seconds per reference.
Measure the actual relevant surface temperature with the independent thermometer;
write the value, uncertainty and sensor identity in the note and notebook.

```powershell
uv run python mark_run.py data/runs/run_20261124.csv warm-start --note "Surface thermometer: ENTER C +/- uncertainty; channel/location verified; heater off"
# Wait while the logger collects the stable warm interval.
uv run python mark_run.py data/runs/run_20261124.csv warm-end
uv run python mark_run.py data/runs/run_20261124.csv cooldown-start --note "Pressure, TA procedure and time of first LN2 addition"
```

Once the cold reference is demonstrably equilibrated with the boiling LN2
reference, rather than merely passing through a low displayed temperature:

```powershell
uv run python mark_run.py data/runs/run_20261124.csv cold-start --note "LN2 plateau established; pressure and sensor location; reference temperature justification"
# Wait while logging the stable cold interval.
uv run python mark_run.py data/runs/run_20261124.csv cold-end
uv run python mark_run.py data/runs/run_20261124.csv heating-start --note "Heater settings and pressure"
```

Nominal boiling LN2 is about 77 K near atmospheric pressure; its actual boiling
point depends on pressure. Chamber vacuum and reservoir pressure are different.
Approximately 990 mV is an expected diode value, NOT a substitute measured reference.
The sample sensor may lag behind the reservoir sensor. Do not assign all sensors
77 K simply because the reservoir contains LN2. If the sample never reaches a
known reference, its two-point calibration remains incomplete.

Use each of `warm-start`, `warm-end`, `cold-start`, `cold-end` exactly once in this
file for the analysis command. Other descriptive labels can be repeated.

Mark every current/phase/wiring/pressure/heater change or LN2 top-up, e.g.:

```powershell
uv run python mark_run.py data/runs/run_20261124.csv current-check --note "MON OUT = ENTER mV AC RMS; sine clean; scope channel 4 DC coupled"
```

## 5. During the hours-long warm-up

- Leave the logger running across cooling, cold reference and heating. Temperature
  values in `temperature_reported_k` are still uncalibrated. Raw mV are authoritative.
- Check heartbeat, file growth, lock-in warnings and MON OUT periodically. Software
  cannot detect coil-driver waveform clipping; `quality=ok` is not a clean-sine guarantee.
- Current is NOT automatically logged from the scope. Check it regularly and mark
  results. Omitting `--current-a` keeps derived resistance blank, which is preferable
  to assuming a drifting current. A fixed `--current-a` value is recorded as an
  assumption for every row; it is never a live current measurement.
- Do not auto-phase repeatedly on the sample: it could rotate a physical quadrature
  signal into X. Establish phase relative to current and document the convention.
- No automatic instrument reset or heater changes are made. The logger is not the
  thermal controller, and closing it does not shut down heaters or the cryostat.

## 6. Stop and check

Press Ctrl-C ONCE and allow the process to close connections. Check final metadata
for `status: interrupted` (normal manual stop), saved row count and last time.
Copy the CSV, `.csv.json` and `.csv.events.jsonl` together to a second location.

If a communication error occurs, a partial error row is saved, metadata reports
`error`, the process exits nonzero, and Windows emits a terminal bell (audibility
is not guaranteed). It does NOT silently reconnect/reuse stale measurements.
Inspect the error, fix the connection, run `--check`, and start a NEW filename.
Mark the interruption in the notebook. To calibrate multiple run segments, derive
coefficients from the segment containing both references, then handle later
segments explicitly in analysis; this tool currently calibrates a single raw run.

A power failure may leave `status: running` with an old heartbeat. That is not
proof the logger is alive; read the actual timestamp. A final partial CSV line
may need removing in an analysis copy after abrupt power loss. Keep the raw file.

## 7. Calibrate afterward

See [data and calibration](data-and-calibration.md). Example only (replace 22.2
with tomorrow's measured surface temperature and 77 with the justified cold value):

```powershell
uv run python calibrate_run.py data/runs/run_20261124.csv --warm-c 22.2 --cold-k 77 --model linear
```

This writes a separate calibrated CSV and JSON containing coefficients, selected
intervals and their voltage spread. It does not overwrite raw data or change the
SIM922's stored curve. Discuss the chosen two-point model with the TA.
