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


def rates_flu_to_frd(x, y, z):
    """Vinkelhastighet i båtens FLU -> FRD. Yaw rate blir positiv med klokka sett ovenfra."""
    return x, -y, -z
