# CMP resistivity lab

Measure lock-in voltage and temperature-diode voltage during cooling and warming
of a BSCCO sample. Python + **uv**. Raw voltages are saved first; temperature
calibration is applied afterward using the same run's reference intervals.

**Start here for the next lab session:** [collection runbook](docs/collection-runbook.md).
On the lab PC, first follow [Windows and USB setup](docs/windows-setup.md).
For automatic uploads, follow [GitHub data backups](docs/github-backup.md).
The logger now includes [named sensor temperatures](docs/sensor-calibration.md)
using the saved provisional sample and base plate calibration profile.
The [recooldown analysis](analysis/README.md) and
[graphs/data](results/recooldown/) include a provisional base plate calibration.

## Commands

Run from this project folder in PowerShell (Windows) or Terminal (Mac):

```sh
uv sync --locked --python 3.12
uv run python daq_example.py --list-devices
uv run python daq_example.py --simulate --duration 60 --period 1
```

Replace `COM4` below with the SIM900 port actually found on Windows:

```sh
uv run python daq_example.py --port COM4 --check
uv run python daq_example.py --port COM4 --channel 1 --extra-channels 2 --continuous --period 1 --sensor-name "base plate" --notes "ch1 base plate; ch2 sample" --github-backup
```

Ctrl-C stops and preserves written rows. The script prevents automatic idle sleep
on Windows while running; keep the PC powered and its lid open. A manual sleep,
shutdown, reboot or USB disconnect can still stop the run. On Mac the known SIM900
port was `/dev/cu.usbserial-BG02V860`; use that instead of COM4 if still present.

## Documentation

| File | Contents |
|---|---|
| [Collection runbook](docs/collection-runbook.md) | Before cooling, continuous logging, reference markers, heating, stopping |
| [Windows setup](docs/windows-setup.md) | uv installation, COM ports, native USB versus serial, driver troubleshooting |
| [GitHub backups](docs/github-backup.md) | Windows login, background snapshots, offline retry and downloads |
| [Experiment notes](docs/experiment-notes.md) | Theory, equipment roles, four-wire explanation, all reported observations and corrections |
| [Wiring worksheet](docs/wiring-worksheet.md) | Blank terminal and sensor map to verify with the apparatus/TA |
| [Data and calibration](docs/data-and-calibration.md) | Units, schemas, two-point models, derived output, limitations |
| [Code history](docs/code-history.md) | Supplied versus added code, original bugs, current design |
| [Verification](docs/verification.md) | Tests performed, hardware evidence, what remains unverified |
| [Original session notes](docs/archive/session-notes-2026-11-17.md) | Archived account of initial setup; current documents take precedence |
| [Lab handout](docs/handouts/cmp-lab-handout.pdf) | Course procedure, circuit, cryostat and calibration instructions |
| [Cryostat orientation](docs/handouts/cryostat-getting-started.pdf) | Dewar parts, vacuum spaces and handling |

## Folder layout

```text
*.py                    active acquisition, marking and analysis commands
pyproject.toml, uv.lock  reproducible uv environment (do not copy .venv to Windows)
docs/                   current documentation, handouts and archived notes
backups/original/       untouched supplied code, including its known faults
tests/                  hardware-free tests
data/preliminary/       actual five-sample connection checks from Nov 17
data/simulated/         old synthetic example; never use as experimental data
data/runs/              new raw runs, metadata, markers and derived outputs
```

Acquisition preserves instrument settings. Named temperatures use the provisional
sensor profile; original reported-temperature columns retain the unverified instrument curve. The latest reported 0.1-ohm resistor check gave approximately
0.114 ohm; driver distortion and grounding are **unresolved**, not a passed
validation for the superconducting sample. Confirm them with the TA before
relying on resistance results. Logging can still preserve the raw evidence.

## Program roles

- `daq_example.py`: instrument connections, CLI, metadata, continuous/timed mode.
- `event_handler.py`: sequential reads, timestamps, bounded-memory per-row saving.
- `lockin_7270.py`: native USB and optional RS232 front-panel queries.
- `sim922.py`: SIM900 serial pass-through to SIM922; raw voltage returned in V.
- `oscilloscope.py`: optional scope helper; NOT part of automatic current logging.
- `oscilliscope.py`: compatibility import for the old spelling.
- `run_support.py`: atomic metadata and temporary Windows idle-sleep prevention.
- `github_backup.py`: background GitHub run snapshots and manual upload/retry.
- `mark_run.py`: timestamp lab events from a second terminal on the same PC.
- `calibrate_run.py`: derive a NEW calibrated CSV from marked stable intervals.
- `sensor_calibration.py`: named live temperature estimates and export of older runs.
- `temp_calibration.py`: offline model helpers and clearly qualified historical points.

```sh
uv run python -m unittest discover -s tests -v
```
