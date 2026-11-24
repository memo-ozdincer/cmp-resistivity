# Experiment notes and observations

Consolidated through 2026-11-23. This is a record of reported measurements and
interpretations, not a claim that every connection was independently verified.
The source procedures are in [the course handout](handouts/cmp-lab-handout.pdf)
and [cryostat orientation](handouts/cryostat-getting-started.pdf).

## Aim and theory

The aim is to measure electrical resistance versus temperature for BSCCO
(bismuth strontium calcium copper oxide), a high-temperature superconductor,
between approximately 77 and 300 K. The superconducting transition is observed as
resistance falls toward zero. Examine transition temperature and width, cooling
versus warming curves, sampling/time-constant effects and thermal equilibration.
Where appropriate, compare sample-chamber pressure conditions following the TA's
procedure. Resistance is the direct measurement; uniform-sample resistivity
requires cross-sectional area A and voltage-contact spacing L: rho = R*A/L.
Dimensions and current for the actual sample have not yet been supplied.

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
four-wire cartoon. Use [the worksheet](wiring-worksheet.md) and handout section 3.1.

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

## Temperature observations and calibration plan

SIM922 channel 1 initially showed ~336-338 K (one photo: 336.1 K) while the apparatus
was near room temperature; a later photo showed 334.7 K. Channels 2-4 displayed
HOT at that time; this does not identify their physical sensors. A disconnected
channel can return an extreme voltage (one photo showed ~2500 mV), not a useful
calibration value. Live channel 1 values ~0.4316 V confirmed serial voltage units,
matching the ~431.6 mV front panel. Standard curve selection was CURV 0.

The handout says the actual transdiodes do not follow the SIM922 standard curve;
it recommends logging voltage and converting in analysis. Each sensor location
has its own calibration. At 10 microampere forward excitation, diode voltage
increases as temperature decreases. Do not apply sample-drive currents to diodes.

The 26.2 C / 431.6 mV pair was explicitly rejected by the user. A later pair,
22.2 C (295.35 K) / 435.4 mV at ambient pressure with a settled apparatus, was
recorded as a candidate. Its matching physical surface/sensor still needs tracing.
It must not silently become tomorrow's reference. New warm and cold references
will be collected as part of the continuous run; see [calibration](data-and-calibration.md).

## Cryostat and thermal interpretation

The outer evacuated space insulates the LN2 reservoir. An inner can can provide
an independent sample environment. Room-temperature reference measurement without
vacuum is compatible with the handout's warm-point procedure, but does not remove
the requirement for outer-space vacuum before cryogenic operation. If the cold
sample chamber is kept near atmospheric pressure, the handout specifies dry
nitrogen rather than ambient air. Reservoir fill/vent tubes remain open to prevent
pressure buildup; pressure gauge for chamber vacuum is not reservoir boiling pressure.

Reservoir, baseplate and sample diodes can show different temperatures while cooling
because heat flow and thermal contact are finite. A stable reservoir is not proof
that the sample is at 77 K. Warm-up can take hours; record both directions and
consider thermal lag when interpreting transition width/hysteresis. The heater
controller is independent of logging; the logger does not operate or shut it down.

## USB and verified computer work

See [Windows setup](windows-setup.md) for current instructions. Mac testing found
SIM900 at 9600 baud through FTDI BG02V860; SIM922 slot 7, channel 1; native 7270
USB 0a2d:001b; Keysight DSOX1204G USB identity succeeded. A Prolific adapter
067b:23a3 initially went to AUX RS232. Installing the official Mac v2.2.11 driver
made a serial port available, but final successful acquisition used native 7270
USB instead. The shared Windows PC still requires its own connection test.

Actual five-row checks on Nov 17 are in data/preliminary. Synthetic examples are
in data/simulated. They are distinct from the later manually reported resistor
check and have not been retroactively calibrated. The earlier combined check's
X~-25.5 mV was NOT the later known-resistor result X~-4.5 mV.
