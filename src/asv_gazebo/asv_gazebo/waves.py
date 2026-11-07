"""Omregning mellom bølgehøyde og gain i VRX sin bølgemodell (Wavefield, Pierson-Moskowitz).

VRX lager bølgene av tre komponenter rundt perioden, og høyden skaleres med gain. Største utslag
er summen av de tre amplitudene. Samme formel som RecalculatePms i vrx_gz/src/Wavefield.cc.
"""
import math


def max_elevation(gain, period, scale=1.1):
    """Største utslag (m) over middelvannstand for en gain og periode."""
    w = 2.0 * math.pi / period
    spacing = [w * (1.0 - 1.0 / scale), w * (scale - 1.0 / scale) / 2.0, w * (scale - 1.0)]
    total = 0.0
    for i in range(3):
        omega = w * scale ** (i - 1)
        pm = 0.0081 * 9.81 ** 2 / omega ** 5 * math.exp(-1.25 * (w / omega) ** 4)
        total += gain * math.sqrt(2.0 * pm * spacing[i])
    return total


def gain_for_height(height, period):
    """Gain som gir det største utslaget height (m) med denne perioden."""
    return height / max_elevation(1.0, period)
