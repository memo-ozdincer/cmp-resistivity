# Windows setup and USB connections

For automatic uploads while recording, see [GitHub data backups](github-backup.md).
Install/authenticate GitHub CLI on this Windows PC; the Mac login does not carry over.

## uv and Python

Yes, uv runs on Windows. Use native **PowerShell**, not WSL, for this USB setup.
Install uv using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
winget install --id=astral-sh.uv -e
```

Or download the official standalone installer from that page if WinGet is absent.
Close and reopen PowerShell afterward. On a managed lab PC, follow its software
installation policy; an administrator/technologist may need to install drivers.

Copy/clone this repository into a local writable folder. If Git and access to the
private repository are available:

```powershell
git clone https://github.com/memo-ozdincer/cmp-resistivity.git
cd cmp-resistivity
uv --version
uv sync --locked --python 3.12
uv run python -m unittest discover -s tests -v
uv run python daq_example.py --simulate --duration 60 --period 1
```

A project ZIP works too: extract it, open PowerShell IN the extracted folder, then
run the commands starting with `uv --version`. No Git/GitHub credentials are needed
to use a locally copied project. Do not copy the Mac `.venv`; uv creates a Windows
one and downloads Python if needed. Initial setup needs internet; sync and test
before the run so packages are cached. Avoid updating dependencies during a run.

## There are three separate USB paths

| Device | Working Mac path | Windows requirement |
|---|---|---|
| SIM900 -> SIM922 | FTDI USB-to-RS232, 9600 baud, slot 7 | FTDI adapter exposed as a COM port |
| 7270 lock-in | Native USB-B, VID:PID `0a2d:001b` | PyUSB/libusb-compatible Windows device driver |
| Keysight DSOX1204G | USBTMC through PyVISA-py | Optional; no automatic scope acquisition in the main logger |

`uv sync` installs Python libraries and, on Windows, the `libusb-package` DLL.
It DOES NOT install or replace the Windows kernel driver assigned to a device.
[PyUSB](https://github.com/pyusb/pyusb) and
[libusb-package](https://github.com/pyocd/libusb-package) describe that distinction.

### SIM900 serial port

1. Connect the adapter to the SIM900 rear **COMPUTER** RS232 connector, not AUX A,
   AUX B, EAVESDROP, REMOTE SIM or a sensor DB9.
2. In Device Manager, inspect **Ports (COM & LPT)**, then run:

```powershell
uv run python -m serial.tools.list_ports -v
uv run python daq_example.py --list-devices
```

3. Use the actual `COMn`, e.g. `--port COM4`. COM4 in examples is a placeholder,
   not an assigned lab-PC port. The observed FTDI adapter has serial `BG02V860`.
4. If no COM port appears, check Windows Update / the lab's approved FTDI driver
   installation. Manufacturer source: https://ftdichip.com/drivers/vcp-drivers/ .
5. Known mainframe baud: **9600**, SIM922 **slot 7**. User-confirmed mapping:
   **channel 1 = base plate; channel 2 = sample**. The program identifies both mainframe and module.

### Native 7270 USB: test the existing driver first

Connect to the 7270's rear **USB-B** socket using a USB data cable. Native USB is
not the Prolific serial adapter. Run:

```powershell
uv run python daq_example.py --port COM4 --check
```

If Windows sees the 7270 but PyUSB cannot open it, inspect the assigned driver in
Device Manager. Existing Signal Recovery / NI-VISA software may use a driver this
PyUSB path cannot use. Have the lab technologist select a suitable driver or an
approved alternative. libusb documents support for **WinUSB** and related drivers:
https://github.com/libusb/libusb/wiki/Windows .

Zadig (https://zadig.akeo.ie/) can bind WinUSB, but installing it changes that
specific device's driver and may break existing lab software. Do not replace
FTDI, Prolific, the scope, a USB hub, or unrelated devices. Record the original
7270 driver and obtain the lab's authorization before changing a shared PC.
The Python scripts do not perform any such driver changes.

The DLL and interpreter must have matching architecture; uv-managed Python 3.12
plus the conditional `libusb-package` dependency is the intended configuration.
If a wheel/DLL is unavailable on the actual Windows architecture, use the approved
libusb distribution or serial alternative below. Windows hardware access has NOT
been verified on this Mac.

`--usb-terminator status` is the default, matching the 7270's null + status + overload
reply. Use `--usb-terminator null` only if the instrument's USB menu explicitly
selects null-only responses. No oscillator or input settings are reset by connecting.

### Optional RS232 fallback for the 7270

A Prolific adapter was identified as `067b:23a3`. A Mac-specific Prolific **v2.2.11**
package was installed on the Mac; that does not install a Windows driver. The
Windows adapter needs its appropriate signed Prolific driver if not already present.
Use the vendor's official source: https://www.prolific.com.tw/portfolio-item/pl2303gc/ .

IMPORTANT: connect the adapter to the rear **RS232** socket, NOT **AUX RS232**.
This mistake occurred during setup. Use a suitable cable/null-modem arrangement
per the 7270 manual. This route is implemented but not hardware-validated here.

Photographed settings were **19200 baud, 7 data bits, even parity, echo ON,
prompt ON, address 0**. Example if SIM900 is COM4 and lock-in adapter is COM5:

```powershell
uv run python daq_example.py --port COM4 --lockin-port COM5 --lockin-baud 19200 --lockin-data-bits 7 --lockin-parity E --check
```

Both ports must be different. Use `--lockin-no-echo` only when echo is off in the
instrument menu; prompts must be enabled. Serial input and configuration have to
match exactly. On the lock-in: MENU -> Configuration -> Communications -> RS232
Settings. The communications monitor can show whether commands reach the instrument.

## Multi-hour operation

The program requests Windows system-awake state while running and restores the
previous state when it exits normally. This prevents automatic idle sleep, not
manual sleep, lid-close policies, restart, power loss or USB power-management faults.
See [Microsoft's API documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate).
Use AC power, leave the lid open, and keep the acquisition terminal open. If a lab
policy forbids the request, configure the lab PC appropriately and use `--allow-sleep`
explicitly. On Mac use the system's normal no-sleep setup (e.g. `caffeinate -i uv run
python ...`); this program's built-in idle-sleep request is Windows only.

Before collecting: perform a real 5-10 minute baseline, then the continuous run.
Test a Ctrl-C stop and confirm all sidecars are present. Do this before adding LN2.

## What errors usually mean

| Symptom | Check |
|---|---|
| No COM port | Adapter driver, USB cable, Device Manager |
| No reply to SIM900 identity | Correct COM, COMPUTER socket, 9600 baud, no other owner; old pass-through is recovered only for the known escape string |
| No 7270 USB device | Rear native USB cable, device ID, hub/accessory permission |
| Access denied / unsupported USB | Windows device-driver binding, another program claiming it |
| Incomplete USB trailer | USB terminator menu and `--usb-terminator`; reconnect after failed framing |
| Serial 7270 no reply | RS232 vs AUX, baud/parity/echo, null-modem wiring |
| HOT / 2500 mV / implausible sensor | Physical channel mapping, diode wiring, excitation, disconnected input |
| CSV permission error | Writable local path; close Excel; choose a new filename |

### A query such as MAG. times out after earlier queries succeeded

A timeout means that query did not complete; it does not prove the cable or
terminator is wrong. The program saves the partial row and stops. Return the
7270 to Main Display (leave Communications Monitor), close other instrument
software, and reconnect its USB cable with acquisition stopped. Preserve any
existing CSV. Try a check with a longer timeout (10 seconds instead of two):

```powershell
git pull --ff-only
uv run python daq_example.py --port COM4 --timeout-ms 10000 --check
```

Use the actual SIM900 COM port. If the check succeeds, start a new run filename
and include `--timeout-ms 10000`. This is a diagnostic allowance, not proof that
the fault is fixed. If it repeatedly fails on MAG., retain the exact message
(including whether any response bytes arrived), the command line, and the USB
terminator-menu setting. Do not switch status/null by trial and error after
successful replies. Do not power-cycle a shared mainframe during cryogenic
operation just to recover a computer link.

If cooling is already in progress and lock-in acquisition is unavailable,
`--temperature-only` can preserve diode data in a separate new file. It cannot
recover missing sample voltages. Record the interruption and reference times;
references across separate files require explicit analysis rather than the
single-file calibration shortcut.
