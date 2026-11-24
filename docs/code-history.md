# Code history and scope

## Supplied versus added

The lab supplied six files: `lockin_7270.py`, `sim922.py`, `event_handler.py`,
`daq_example.py`, `temp_calibration.py`, and misspelled `oscilliscope.py`. Their
original contents are preserved unchanged in `backups/original/`.

Active versions were substantially repaired or rewritten. Added files include the
correctly spelled `oscilloscope.py` (old spelling now imports it), automated tests,
uv configuration/lock, dependency list, Git ignore rules and documentation.
For continuous collection, `run_support.py`, `mark_run.py` and `calibrate_run.py`
were added. Third-party Python packages and hardware drivers were installed,
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

## Active design and remaining limits

- No instrument settings are applied automatically; no heater control or curve upload.
- Queries are bounded and sequential. Full USB response framing/status is consumed.
- Slow front-panel sampling replaces unverified high-speed threaded curve capture.
- Timestamped exclusive outputs; per-row flush/fsync; error/interruption partial rows.
- Requested cadence uses monotonic deadlines and skips missed slots; no catch-up bursts.
- Timed runs or explicit --continuous; metadata heartbeat and zero-based row indices.
- Optional additional SIM922 channels on the SAME connection; mapping must be supplied.
- Optional fixed-current calculations; no automatic scope current or clipping detection.
- Faults stop the run. Automatic reconnect is deliberately absent because a timeout can
  leave framing/settings uncertain; reconnect and start a new, documented file.
- Windows idle-sleep prevention is requested/restored, but not tested on Windows hardware.
- Old calibration points never automatically alter a live run. Derived calibration uses
  explicitly selected models/intervals and preserves raw readings.
