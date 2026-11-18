"""Offline calibration helpers. Nothing is fitted or uploaded on import.

The old reference points remain available for comparison only. They are not
applied by acquisition. The new independent point is insufficient for a slope.
"""
import math

LEGACY_REFERENCE_POINTS = ((297.6, 435.9), (77.0, 992.0))  # K, mV
CURRENT_REFERENCE_POINT = (295.35, 435.4)  # User-reported pair, 2026-11-18: 22.2 °C, mV


def calibration2(temp, c1, c2):
    """Voltage in mV for temperature in K: V = c1 - c2*T."""
    return c1 - c2 * temp


def calibration3(temp, d1, d2):
    """Legacy log-corrected model, still fitted with TWO reference points."""
    import numpy as np
    if np.any(np.asarray(temp) <= 0):
        raise ValueError('Temperature must be positive in kelvin.')
    return d1 - d2 * temp - 0.405 * np.log(temp)


def calibration2_ln2(temp):
    """Legacy coefficients, NOT validated for the current experiment."""
    return calibration2(temp, 1186.10562, 2.5208)


def fit_two_points(point1, point2):
    """Return (c1, c2) from two measured (temperature_K, voltage_mV) pairs."""
    (t1, v1), (t2, v2) = point1, point2
    if not all(math.isfinite(x) for x in (t1, v1, t2, v2)) or min(t1, t2) <= 0:
        raise ValueError('Use finite voltages and positive Kelvin temperatures.')
    if t1 == t2 or v1 == v2:
        raise ValueError('Two distinct temperatures and voltages are required.')
    c2 = (v2 - v1) / (t1 - t2)
    return v1 + c2 * t1, c2


def temperature_from_mv(voltage_mv, c1, c2):
    if not all(math.isfinite(x) for x in (voltage_mv, c1, c2)) or c2 == 0:
        raise ValueError('Use finite values and a nonzero calibration slope.')
    return (c1 - voltage_mv) / c2


if __name__ == '__main__':
    print('Calibration deferred. No instrument settings have been changed.')
    print('Independent reference (K, mV):', CURRENT_REFERENCE_POINT)
    print('A second reference is needed before fitting a new calibration.')
