"""Omregning fra ROS (ENU verden, FLU båt) til PX4/Seapath (NED verden, FRD båt).

Ingen ROS-avhengigheter, så funksjonene kan testes uten ROS.
"""
import math


def euler_from_quaternion(x, y, z, w):
    """Roll, pitch og yaw (ZYX) fra en kvaternion."""
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2.0 * (w * y - z * x))))
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return roll, pitch, yaw


def attitude_enu_to_ned(roll, pitch, yaw):
    """Vinkler i ENU/FLU -> roll, pitch og heading i NED/FRD.

    Roll er positiv med babord opp i begge. Pitch snur fortegn (positiv = baugen opp i FRD).
    Heading er kompasskurs: 0 = nord, positiv med klokka, 0 til 2*pi.
    """
    heading = (math.pi / 2.0 - yaw) % (2.0 * math.pi)
    return roll, -pitch, heading


def enu_to_flu(q, v):
    """Vektor i verden (ENU) -> båtens ramme (FLU). q = (x, y, z, w) er båtens orientering i ENU."""
    # Roterer med den konjugerte kvaternionen: v + 2w(u x v) + 2u x (u x v), med u = -(x, y, z).
    x, y, z, w = q
    ux, uy, uz = -x, -y, -z
    cx = uy * v[2] - uz * v[1]
    cy = uz * v[0] - ux * v[2]
    cz = ux * v[1] - uy * v[0]
    return (v[0] + 2.0 * (w * cx + uy * cz - uz * cy),
            v[1] + 2.0 * (w * cy + uz * cx - ux * cz),
            v[2] + 2.0 * (w * cz + ux * cy - uy * cx))


def rates_flu_to_frd(x, y, z):
    """Vinkelhastighet i båtens FLU -> FRD. Yaw rate blir positiv med klokka sett ovenfra."""
    return x, -y, -z
