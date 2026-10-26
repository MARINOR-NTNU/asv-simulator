#!/usr/bin/env python3
"""Lager vannflaten til open_water som et OBJ-mesh: tett rutenett der båten kjører, glissere utover.

VRX sin coast_waves har punkter ca. 19 m fra hverandre rundt origo. Bølgene tegnes ved å flytte
punktene, så for en båt på 1,5 m blir den tegnede vannflaten helt feil (store flate trekanter), og
båten ser ut som den er under vann selv om fysikken er riktig. Her er det 1 m mellom punktene
innenfor ±FINE m, og avstanden vokser med GROWTH per punkt ut til ±SIZE m.

Teksturkoordinatene går fra 0 til 1 over hele flaten, som i coast_waves, så vannet ser likt ut.

Bruk: make_ocean_mesh.py <utfil.obj>
"""
import sys

FINE = 100.0    # m, halv bredde av det tette området rundt origo
STEP = 1.0      # m mellom punktene i det tette området
GROWTH = 1.15   # hvor mye avstanden øker per punkt utenfor det tette området
SIZE = 3000.0   # m, halv bredde av hele flaten (som coast_waves)


def axis():
    """Koordinatene langs én akse, symmetrisk om 0."""
    n = int(FINE / STEP)
    inner = [i * STEP for i in range(n + 1)]
    outer, x, dx = [], inner[-1], STEP
    while x < SIZE:
        dx *= GROWTH
        x = min(SIZE, x + dx)
        outer.append(x)
    half = inner + outer
    return [-v for v in reversed(half[1:])] + half


def main(path):
    a = axis()
    n = len(a)
    with open(path, 'w') as f:
        f.write(f'# Vannflate for open_water, {n} x {n} punkter (make_ocean_mesh.py)\n')
        f.write('vn 0 0 1\n')
        for y in a:
            for x in a:
                f.write(f'v {x:.3f} {y:.3f} 0\n')
        for y in a:
            for x in a:
                f.write(f'vt {(x + SIZE) / (2 * SIZE):.6f} {(y + SIZE) / (2 * SIZE):.6f}\n')
        for j in range(n - 1):
            for i in range(n - 1):
                # OBJ teller fra 1. To trekanter per rute, mot klokka sett ovenfra.
                p00 = j * n + i + 1
                p10, p01, p11 = p00 + 1, p00 + n, p00 + n + 1
                f.write(f'f {p00}/{p00}/1 {p10}/{p10}/1 {p11}/{p11}/1\n')
                f.write(f'f {p00}/{p00}/1 {p11}/{p11}/1 {p01}/{p01}/1\n')
    print(f'{path}: {n} x {n} = {n * n} punkter, {2 * (n - 1) ** 2} trekanter')


if __name__ == '__main__':
    main(sys.argv[1])
