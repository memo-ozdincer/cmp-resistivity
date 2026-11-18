# Resistivity experiment acquisition

Run commands from this directory. Dependencies are managed by `uv` using
`pyproject.toml` and `uv.lock`; `uv run` prepares the environment automatically.
Original files are preserved in `backups/original/`.

## Connection check

```sh
uv run python daq_example.py --list-devices
```

The lab SIM900 has been identified at `/dev/cu.usbserial-BG02V860`, **9600 baud**.
The SIM922 is in **slot 7**, with the diode on **channel 1**. These are the defaults
except for the serial path, which is auto-selected only when unambiguous.

The 7270 now communicates successfully through its native USB-B socket,
identified as `0a2d:001b`. Use this connection for acquisition. A five-sample
combined live run passed with no overload/reference warnings and is saved at
`data/20261117T171932_299681Z.csv`, with metadata alongside it.

A separate Prolific serial cable had been connected to AUX and did not answer.
Its official driver is installed and active, but serial acquisition has not been
verified on the instrument. The front-panel serial settings are 19200 baud,
7 data bits, even parity, echo ON, prompt ON.

For native 7270 USB:

```sh
uv run python daq_example.py --port /dev/cu.usbserial-BG02V860 --check
```

For the serial connection, use the detected Prolific port (it can change when moved).
Read the 7270 **RS232 Settings** menu and match baud, data bits, parity, and echo.
The command below matches the photographed settings: 19200 baud, 7 data bits, even parity, echo enabled.
**Prompts must be enabled.** Add `--lockin-no-echo` if echo is off.

```sh
uv run python daq_example.py --port /dev/cu.usbserial-BG02V860 \
  --lockin-port /dev/cu.PL2303G-USBtoUART1140 \
  --lockin-baud 19200 --lockin-data-bits 7 --lockin-parity E --check
```

The code identifies both instruments and checks that the lock-in is using
single-reference voltage-input mode, with its input enabled. It does not set the
oscillator amplitude, frequency, input selection, phase, sensitivity, excitation,
or temperature calibration. Review those settings for the actual wiring. The
old A−B defaults are available only through an explicit `lockin.set_up()` call;
they are not applied by acquisition.

## Record data

For combined lock-in and temperature acquisition:

```sh
uv run python daq_example.py --port /dev/cu.usbserial-BG02V860 --duration 600 --period 1
```

Temperature-only acquisition is also available:

```sh
uv run python daq_example.py --temperature-only \
  --port /dev/cu.usbserial-BG02V860 --duration 600 --period 1
```

The five-sample live connection check is saved in
`data/20261117T170236_852605Z.csv` with metadata alongside it. It contains actual
diode readings of 431.651–431.654 mV; lock-in and derived columns are blank.

Replace `--check` in the applicable command above with `--duration 600 --period 1`
to request ten minutes of readings at roughly one-second intervals. Use Ctrl-C
to stop early. Run `--help` to see all options.

Each run creates a new timestamped CSV and JSON metadata file in `data/`.
Existing files are never overwritten, including when using `--output PATH.csv`.
Each CSV row is flushed and synced to disk immediately. A communication failure
stops acquisition and saves any values already read in the partial row, together
with the error. Metadata records identities, startup lock-in settings, arguments,
row count, and the completion/error/interruption status.

Readings include UTC and elapsed time, query duration, diode voltage in **mV**,
instrument-reported temperature in **K**, lock-in X/Y/magnitude in **V**, phase in
degrees, and status/overload flags. Queries are sequential, not simultaneous;
`read_duration_s` records their time span. Sampling can be slower than the requested
period if the instruments take longer to reply.

**Temperature calibration is deferred.** `temperature_reported_k` is the SIM922's
own unverified result, currently approximately 336 K near room temperature. It is
not a corrected temperature. The raw serial `VOLT?` response was verified live as
about 0.4317 **V**, matching approximately 431.7 **mV** on the front panel; this
corrects the original driver's misleading mV comment. Conversion to mV happens
once in the acquisition coordinator. No old calibration coefficients are applied.
The current user-reported reference (295.35 K / 22.2 °C, 435.4 mV), recorded on
2026-11-18, is preserved in
`temp_calibration.py`; a second reference is still needed.

## Resistance and resistivity

Without a measured current, derived columns stay blank. To enable them, supply
`--current-a` with the independently measured **sample RMS current in amperes**
and select `--voltage-component x` or `--voltage-component magnitude`.
Do not substitute the oscillator voltage for sample current.

`x` requires phase alignment to the sample current and preserves the measured
sign. `magnitude` gives impedance magnitude; interpreting it as resistance assumes
a negligible reactive component. The selected component is recorded in every row.
If an external amplifier is present, supply its voltage gain with `--voltage-gain`.

For a uniform sample, also supply `--area-m2` (cross-sectional area in m²) and
`--length-m` (voltage-contact spacing in m). The code uses `R = V/(gain*I)` and
`rho = R*A/L`. These geometry factors do not cover other arrangements such as
van der Pauw measurements. No current or dimensions are guessed. Derived values
are left blank when the lock-in reports overload or loss of reference lock.

## Simulation and verification

```sh
uv run python daq_example.py --simulate --duration 5 --period 1
uv run python -m unittest discover -s tests -v
```

Synthetic data are marked in every row, in metadata, and in default filenames.
They are not experimental measurements. Tests cover protocol framing, units,
resistivity calculations, overload handling, file protection, interruption, and
saving partial samples after a disconnect.

The oscilloscope is optional. `oscilloscope.py` provides `Oscilloscope`, and the
old misspelled `oscilliscope.py` remains a compatibility import. Its identity query
has been tested against the connected Keysight DSOX1204G. It is not used as a
substitute temperature sensor in the core acquisition path. The old threaded
curve acquisition has been retired from the active files and is archived with
the originals; the current path is designed for slow front-panel measurements.

## Fresh environment

```sh
uv sync
```

Native USB access also needs libusb; it is already installed on this Mac.
On another Mac: `brew install libusb`.

Protocol references: [7270 manual](https://www.ameteksi.jp/-/media/ameteksi/download_links/documentations/7270/197852-a-mnl-c.pdf),
[SIM900 manual](https://www.thinksrs.com/downloads/pdfs/manuals/SIM900m.pdf),
[SIM922 manual](https://www.thinksrs.com/downloads/pdfs/manuals/SIM922m.pdf).
