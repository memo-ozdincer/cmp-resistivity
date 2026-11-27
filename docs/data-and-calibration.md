# Data, calibration and analysis

## Files saved for each run

- `run.csv`: raw readings; one fsync per row; never overwritten.
- `run.csv.json`: arguments, hardware identities, initial settings, status and
  approximately 10-second heartbeat. Updated using temporary-file + atomic replace.
- `run.csv.events.jsonl`: human event markers, one JSON object per line, optional.
- `run.ch1.calibrated.csv`: derived output made after the run, example channel 1.
- `run.ch1.calibrated.csv.calibration.json`: reference intervals, spread, model,
  coefficients and limits. Preserve with the derived output.

Raw readings do not depend on having completed calibration. Start at room
 temperature and keep logging through the cold plateau and heating. Each diode
needs its own independently identified reference pairs.

## Units and interpretation

| Column | Meaning |
|---|---|
| sample_index | Zero-based index of each saved row, including partial errors |
| timestamp_utc | Time at start of sample, timezone included |
| elapsed_s | Monotonic time since THIS process/run started |
| read_duration_s | Span of sequential queries, not simultaneous measurements |
| simulated | True only for synthetic data |
| diode_voltage_mv | Primary channel voltage in mV; serial VOLT? returns V |
| temperature_reported_k | SIM922's unverified curve result, not calibrated temperature |
| diode_chN_voltage_mv | Optional additional diode voltage, same sample row |
| temperature_chN_reported_k | Optional additional unverified Kelvin reading |
| lockin_x_v, lockin_y_v | Signed in-phase/quadrature voltage components in V |
| lockin_magnitude_v | Instrument's detected voltage magnitude in V |
| lockin_phase_deg | Phase relative to the instrument reference |
| lockin_status, lockin_overload | Instrument status bytes |
| quality, error | Conditions detected by SOFTWARE, not all physical faults |
| current_rms_a | Fixed supplied assumption, not a live current-monitor reading |
| voltage_component, voltage_gain | Selected component and externally specified gain |
| area_m2, voltage_contact_spacing_m | Optional uniform-sample geometry |
| resistance_ohm, resistivity_ohm_m | Derived only if current/component were supplied and lock-in status permits |

`quality=ok` does not establish correct current, waveform, grounding, phase,
calibration or sensor identity. Overload/reference warnings suppress derived
resistance but preserve measured values. By default a communication error stops
acquisition with a partial error row. Opt-in native USB `--recover-lockin` keeps
diode data with `lockin_unavailable` electrical quality flags while reconnecting;
settings must match before electrical readings resume. Missing
samples/interruptions must remain visible in analysis.

Current is checked at CURR MON: I_RMS = V_MON_RMS / 1 ohm. Scope AC RMS on a
distorted waveform includes harmonics; the lock-in measures a reference-frequency
component. Do not divide those to infer a valid resistance when the current clips.
If current changes, don't apply one fixed --current-a to the entire run without
justification. Mark current checks and analyze only appropriately characterized intervals.

## Two reference temperatures

The handout model is V(T) = c1 - c2*T - c3*ln(T/1 K). With TWO temperatures you
cannot determine THREE independent coefficients. The software makes the choice
explicit:

- `--model linear`: c3 = 0; fit c1 and c2. Simple two-point interpolation, not a claim
  of accurate diode behaviour throughout the entire cryogenic range.
- `--model log-fixed --c3 VALUE`: fix c3 using an independently justified lab model
  and fit c1/c2. The old code used 0.405 mV, but this is not silently adopted as a
  new measured constant. Have the TA confirm the model/coefficient and its units.

Example with the next run's actual values substituted:

```powershell
uv run python calibrate_run.py data/runs/run_20261124.csv --warm-c 22.2 --cold-k 77 --model linear
```

Use the SAME physical diode at both references. The warm reference is its relevant
surface temperature measured with an independent thermometer. The cold reference
requires equilibrium with the established LN2 boiling reference; it is not whatever
number the uncalibrated SIM922 displays. Reservoir equilibrium is not automatic
sample equilibrium. Boiling point depends on pressure; 77 K is the handout's
nominal value. Record pressure, uncertainties and thermal lag.

The command takes the mean of valid readings between exactly one warm-start/end
and cold-start/end marker. It prints count, standard deviation, min and max for
both intervals. Inspect those statistics for drift; software does not certify a
plateau from a mean. At least three readings per interval are required by default;
30-60 seconds or more is preferable for assessing stability. Extra diode channels
can be processed with `--channel N`, but that channel's actual warm/cold temperatures
must be supplied and the marked intervals must apply to it. If it equilibrates at
other times, prepare its own explicitly reviewed markers/analysis copy.

Derived output preserves raw columns and adds calibrated temperature, channel,
and a range flag. Outside the bracketed reference temperatures, calibrated values
are left blank rather than silently extrapolated. Heating above the warm reference
therefore needs additional references/model justification. One selected run is
processed at a time. No sensor curve is uploaded to the shared SIM922.

## Calibration history and corrections

- **26.2 C / 431.6 mV was explicitly invalidated by the user. Never use it.**
- **22.2 C (295.35 K) / 435.4 mV** was later reported without vacuum, with the
  apparatus settled. It remains a historical candidate: channel/location and surface
  thermometer pairing were not traced. Do not use it automatically for tomorrow.
- Old supplied points **297.6 K / 435.9 mV** and **77 K / 992 mV** belong to previous
  data/code; they are not references collected by this team in this session.
- About 990 mV at 77 K is the handout's expectation, not a measured cold point.
- On 2026-11-27, the user confirmed channel 1 = base plate and channel 2 = sample,
  and requested a provisional offline curve for the recooldown data. Warm reference:
  23.5 C (296.65 K), mean 433.188154 mV in run _1. Cold reference: highest recorded
  channel-1 voltage, 981.166 mV in run _3, assigned nominal 77 K per instruction.
  Linear model: V_mV = 1173.263856 - 2.494777356*T_K. This assumes base plate LN2
  equilibrium and is not an independently validated temperature scale. It does
  not calibrate channel 2. Raw readings and instrument settings are unchanged.
  Reproduce with [analysis instructions](../analysis/README.md); results and
  reference provenance are in `results/recooldown/`.

## Long-run storage

Optional [GitHub backups](github-backup.md) upload run-only snapshots in the
background. They preserve local-first recording and retry after network failure.

Memory remains bounded: rows are written as collected, and calibration streams
through the CSV. At ~1 Hz even a day is normally only tens of MB; actual size
varies. Keep ample disk space and backups. Atomic metadata protects the last valid
snapshot, not against drive failure. Abrupt power loss can leave a partial final
CSV line. Never modify the original to hide gaps; work on a documented analysis copy.
