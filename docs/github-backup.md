# Automatic GitHub data backups on Windows

Backups use the existing private `memo-ozdincer/cmp-resistivity` repository, on
branch `main`. Each run has a separate UUID folder under `live/`.
The acquisition checkout stays on `main`: no local Git add, commit, pull,
stash or merge runs on the lab PC. A downloaded project ZIP also works.

## One-time Windows setup

No GitHub CLI installation is required. Create a [fine-grained personal access
token](https://github.com/settings/personal-access-tokens/new) on GitHub:

- Resource owner: memo-ozdincer
- Repository access: Only select repositories → cmp-resistivity
- Repository permissions: Contents → Read and write (Metadata read is automatic)
- Choose an expiry covering the lab session.

In PowerShell, paste the token into this hidden prompt:

```powershell
$env:GITHUB_TOKEN = [System.Net.NetworkCredential]::new('', (Read-Host "GitHub token" -AsSecureString)).Password
```

Keep this PowerShell window open for acquisition. The token is available to
Python in this session only; it is not written to files, command history or
uploaded metadata. Repeat the prompt when opening a new terminal. Clear it
after the session with `Remove-Item Env:GITHUB_TOKEN`. Never paste the token into
chat or repository files. Existing authenticated gh installations still work
when no environment token is set.

If using a Git checkout, stop acquisition before updating:

```powershell
git pull --ff-only
uv sync --locked --python 3.12
```

Test a short synthetic run first (automatically named and labelled SIMULATED):

```powershell
uv run python daq_example.py --simulate --duration 10 --github-backup
```

Check for `GitHub backup uploaded:` and follow the printed URL. Download the ZIP
from GitHub and confirm it contains the CSV and final metadata with `complete`
status. This command does not connect to instruments.

## Collect both diodes and upload automatically

Replace COM4 with the SIM900 port. Confirmed mapping: **channel 1 = base plate;
channel 2 = sample**. Keeping channel 1 primary preserves existing CSV names.

```powershell
uv run python daq_example.py --port COM4 --channel 1 --extra-channels 2 --sensor-name "base plate" --notes "SIM922 ch1 base plate; ch2 sample" --continuous --period 1 --timeout-ms 10000 --github-backup
```

Add `--github-backup` to an existing collection command to enable backups without
changing its other settings. Default cadence is 300 seconds; customize with
`--github-backup-seconds 600` (minimum 30 seconds). `--github-repo OWNER/REPO`
selects a different repository. Authentication/write access is checked before
connecting to hardware; missing credentials do not silently start an unbacked run.

Named temperatures are now computed using the [provisional sensor profile](sensor-calibration.md),
and its full contents are included in run metadata.

Local CSV rows are still flushed and fsynced first. The first saved sample starts
a background worker, which uploads an initial snapshot, periodic snapshots, and
a final snapshot after Ctrl-C, normal completion or acquisition error. Each ZIP
contains only that run's CSV, `.csv.json`, optional `.csv.events.jsonl`, and a
manifest with byte counts and SHA-256 hashes. In-progress incomplete CSV/event
records are deferred to the next snapshot. Sidecars are read sequentially, so a
live metadata row count can differ slightly from the captured CSV prefix.

The `live/` folder on main contains the latest uploaded ZIP. Backup commits advance
remote main without altering the local checkout. Stop acquisition, then use
`git pull --ff-only` before editing/pushing code from that checkout. Code CI ignores
commits that change only `live/` files. Previous snapshots remain in
Git history. This stores repeated snapshots, so it suits these small laboratory
runs rather than indefinitely running high-volume acquisition. There is a 40 MiB
uncompressed input limit per run snapshot; start new segments for larger runs.
Backups do not include unrelated files, other runs, or the entire project.

## Offline, interrupted or failed uploads

Network/API failures do not stop acquisition. The worker logs `backup pending`,
keeps recording locally, and retries the full current run at the next interval.
Once connectivity returns, that snapshot includes earlier locally saved readings.
The most recent local snapshot is `.csv.backup.zip`; `.csv.backup.json` records
`last_success_utc`, the uploaded snapshot's time, commit SHA, URL and retry state.
Check **last_success_utc**, not just the existence of a sidecar.

Stopping waits up to 30 seconds for final backup confirmation. If it cannot
confirm, preserve the local files and retry AFTER acquisition stops:

```powershell
uv run python github_backup.py data/runs/YOUR_RUN.csv
```

Keep `.csv.backup.json` to reuse the same remote run identity. Do not run manual
uploads for the same file concurrently with its active backup worker. The retry
command also uploads older completed runs that were collected without the flag.
A terminal crash, power loss or prolonged internet outage can leave readings
newer than the last successful backup only on the local disk. This does not
recover measurements lost before they were saved. Do not delete local originals.

## Optional lock-in recovery

The existing opt-in `--recover-lockin` applies only to native USB. It logs missing
electrical readings as `lockin_unavailable` while retaining diode readings,
waits 15 seconds by default, reconnects, and checks the original lock-in settings
before accepting new readings. It does not reset instrument settings. Changed
settings prevent resumption. Hardware recovery remains unverified on Windows;
the default still stops on communication failures. GitHub backup works in either
mode. Inspect missing-data quality flags when analyzing recovered runs.
