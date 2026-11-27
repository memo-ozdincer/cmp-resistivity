# Named sample and base plate temperatures

The logger now loads `calibrations/recooldown-provisional.json` automatically.
It records and displays distinct **base_plate (channel 1)** and **sample
(channel 2)** readings. Both curves are provisional two-point linear models.

| Sensor | Warm voltage | Warm temperature | Cold voltage | Cold temperature |
|---|---:|---:|---:|---:|
| Base plate, ch1 | 433.188154 mV | 23.5 C / 296.65 K | 981.166 mV | nominal 77 K |
| Sample, ch2 | 28.08 mV | assumed 23.5 C / 296.65 K | approximately 619 mV | nominal 77 K |

The sample voltages are the user's reported warm and LN2 readings. The earlier
23.5 C room temperature is assumed for the newly reported 28.08 mV reading;
its actual temperature was not independently specified. 619 mV is approximate,
not an average from a verified stable interval. Neither cold reference verifies
physical equilibrium or pressure independently. These assumptions are in the
profile and every run's metadata. Edit the profile when improved references are
available. The later observed base plate reading of about 431.9 mV is not
substituted for the independently marked warm reference from the archive.

## Windows collection

After stopping the old process, update the existing checkout on main:

```powershell
git pull --ff-only
uv sync --locked
uv run python daq_example.py --port COM4 --channel 1 --extra-channels 2 --continuous --github-backup
```

Replace COM4 with the actual SIM900 port. `--extra-channels 2` is necessary to
read the sample along with the primary base plate diode. No instrument curve is
rewritten. Calibration is applied in software to named columns and console
output. Missing/unlogged channels remain blank, rather than copying the other
sensor's temperature. `--channel 2 --extra-channels 1` also maps correctly.

The GitHub backup includes the raw readings, derived columns and metadata with
the complete calibration profile and its SHA-256. Existing runs are not modified.
Restart after updating to use the new code and profile. A running process cannot
be changed by pulling code; it keeps the profile loaded at startup.

## CSV columns

`sensor_calibration_id` identifies the applied profile on each row.

For each `base_plate` and `sample` prefix:

- `_diode_channel`: physical SIM922 channel.
- `_diode_voltage_mv`: named copy of the measured diode voltage.
- `_temperature_calibrated_k`: provisional calibrated temperature, in kelvin.
- `_calibration_quality`: `provisional_linear`, `extrapolated`,
  `invalid_voltage`, `not_read` or `disabled`.

Original `diode_voltage_mv`, `diode_ch2_voltage_mv`, and `temperature*_reported_k`
remain unchanged. Reported-temperature columns still contain the instrument's
unverified curve; use the explicitly named calibrated columns for this profile.
Electrical `quality=ok` does not establish temperature-calibration validity;
check each sensor's `_calibration_quality` as well.

The same linear equation is evaluated outside the reference interval. These
temperatures are labelled `extrapolated` rather than discarded. They are
estimates, including any calculated values below 77 K. Raw voltages remain
available and the extrapolation does not establish physical LN2 equilibrium.

Use `--calibration-file PATH.json` for a revised profile. Use `--raw-temperatures`
to disable the derived named temperature columns. Keep existing profiles with
their runs; the metadata stores the full profile used at startup.

## Apply to older saved data

```powershell
uv run python sensor_calibration.py results/recooldown/merged_runs_2_to_6.csv --primary-channel 1 --output results/recooldown/both_sensors_calibrated_runs_2_to_6.csv
```

This export and its `.csv.calibration.json` sidecar are already provided. Choose
a different new output name to rerun it; outputs are never overwritten. For an
ordinary saved run, its adjacent metadata supplies the primary channel. If that
metadata is absent, explicitly pass the actual `--primary-channel`. Original
raw columns are preserved, including partial rows and out-of-range voltages.
For a live CSV that already contains named derived columns, the export recomputes
those columns in the NEW file using the selected profile. The source file stays
unchanged, and the sidecar lists the recomputed columns and source hash.
