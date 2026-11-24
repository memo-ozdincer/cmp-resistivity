# Wiring and sensor worksheet — fill in at the bench

Nothing in this table assigns actual numbered pairs without tracing. The handout
asks students to create this map. Different connector banks use overlapping numbers.

| Physical function | Internal contact/terminal | Breakout bank + numbers | Instrument connection | Verified by/date |
|---|---|---|---|---|
| Sample current + | | | Hartshorn rear TO LOAD + | |
| Sample current return | | | Hartshorn rear TO LOAD - | |
| Sample voltage + (inner contact) | | | Lock-in differential signal + | |
| Sample voltage - (inner contact) | | | Lock-in differential signal - | |
| Sample-stage diode | | | SIM922 channel ___ | |
| Baseplate diode | | | SIM922 channel ___ / controller | |
| Reservoir diode | | | SIM922 channel ___ | |
| Heater/controller harness | | | Per TeachSpin pinout; do not infer | |

Use the full bank name: BANANA JACKS, TERMINALS, BNC pair, D-SUB and feedthrough.
Do not guess that 3/4 means current or 5/6 means voltage. Handout Figure 1 letters
A/B/C/D label positions along the sample, not connector numbering.

## Electrical checks

- Current goes through outer sample contacts; voltage is sensed at inner contacts.
- On the practice resistor, sense contacts are on resistor leads close to its body;
  current contacts are farther out. Sensing at driver posts includes current-wire drops.
- The load must float. Neither terminal may be tied to earth/ground by a BNC shield
  or scope ground. Consult the TA/7270 manual for A-B differential inputs and grounding.
  Use the two input centre conductors appropriately; never remove protective earth.
- Prior A-only centre/shield sensing was a practice configuration, not an approved
  floating-load configuration for final collection.
- Input mode is VOLTAGE, not current. AC coupling was used for the 37 Hz sample signal.
  The scope's MON OUT channel was switched to DC input coupling to view distortion;
  its measurement can still be AC RMS. Input coupling and RMS statistic are separate.
- MON OUT connects to the ground-referenced current-monitor output, not directly
  across floating TO LOAD. OSC OUT splits to driver OSC IN and a scope reference channel.
- Confirm one connection per intended point and record photos before closing the cryostat.

## Room/cold references

| Item | Primary channel | Extra channel ___ | Extra channel ___ |
|---|---|---|---|
| Physical diode location | | | |
| Warm surface temperature, C +/- uncertainty | | | |
| Warm voltage mean/spread, mV | | | |
| Cold reference, K and pressure justification | | | |
| Cold voltage mean/spread, mV | | | |
| Stable interval marker times | | | |
| Equilibrium evidence / thermal lag | | | |

The diodes use 10 microampere excitation; the sample current near 40-100 mA must
never be applied to a thermodiode. Shared numbering is not proof of shared function.
