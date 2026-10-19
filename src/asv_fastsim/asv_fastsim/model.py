"""2D-modell av båten (fram, sidelengs og dreiing) for raske simuleringer uten grafikk.

Tallene leses fra model.sdf i asv_gazebo, så modellen og Gazebo bruker de samme tallene.
Bølger, rull, stamp og hiv er ikke med. Ingen ROS-avhengigheter, så modellen kan testes uten ROS.

Koordinater: ENU i verden (x øst, y nord, yaw 0 = øst, positiv mot klokka) og FLU på båten.
Bevegelseslikningene er Fossen sin 3DOF-modell med origo i tyngdepunktet:
    M * nu_dot + C(nu) * nu + D(nu) * nu = tau
"""
import math
import xml.etree.ElementTree as ET


def _floats(text):
    return [float(v) for v in text.split()]


def _pose(element):
    pose = element.find('pose')
    return _floats(pose.text) if pose is not None else [0.0] * 6


class Thruster:

    def __init__(self, name, x, y, axis, min_thrust, max_thrust, steerable):
        self.name = name
        self.x, self.y = x, y              # i modellens ramme, før tyngdepunktet trekkes fra
        self.axis = axis                   # retningen thrusten virker i når vinkelen er 0
        self.min_thrust, self.max_thrust = min_thrust, max_thrust
        self.steerable = steerable
        self.angle_min, self.angle_max = 0.0, 0.0
        self.angle_rate = 0.0              # rad/s, største dreiehastighet (cmd_max)
        self.thrust = 0.0
        self.angle = 0.0
        self.angle_cmd = 0.0


class BoatModel:

    def __init__(self, sdf_path, angle_gain=50.0):
        # angle_gain: dreiehastighet per radian vinkelfeil (1/s). Målt i Gazebo 2026-10-19:
        # thrusteren dreier med full fart (cmd_max) helt til vinkelen er nådd, så den er høy.
        self.angle_gain = angle_gain
        root = ET.parse(sdf_path).getroot()
        model = root.find('model')
        links = {link.get('name'): link for link in model.findall('link')}
        joints = {joint.get('name'): joint for joint in model.findall('joint')}

        # Masse, tyngdepunkt og treghetsmoment om z for hele båten, alle ledd regnet med.
        parts = []
        for link in links.values():
            inertial = link.find('inertial')
            if inertial is None:
                continue
            lx, ly = _pose(link)[:2]
            ix, iy = _pose(inertial)[:2]
            izz = float(inertial.find('inertia/izz').text)
            parts.append((float(inertial.find('mass').text), lx + ix, ly + iy, izz))
        self.mass = sum(p[0] for p in parts)
        self.xg = sum(p[0] * p[1] for p in parts) / self.mass
        self.yg = sum(p[0] * p[2] for p in parts) / self.mass
        self.iz = sum(p[3] + p[0] * ((p[1] - self.xg) ** 2 + (p[2] - self.yg) ** 2) for p in parts)

        plugins = model.findall('plugin')
        hydro = next(p for p in plugins if 'SimpleHydrodynamics' in p.get('name', ''))
        h = {child.tag: child.text for child in hydro}
        self.hx, self.hy = _pose(links[h['link_name']])[:2]
        self.damping = {k: float(h.get(k, 0.0)) for k in ('xU', 'xUU', 'yV', 'yVV', 'nR', 'nRR')}
        # Medsvingende vannmasse, som positive tall (0 i dag, som i Gazebo).
        self.added = {k: abs(float(h.get(k, 0.0))) for k in ('xDotU', 'yDotV', 'nDotR')}

        # Thrustere: propellen sitter på et ledd. Er foreldreleddet dreibart om z, kan den dreies.
        self.thrusters = {}
        for p in plugins:
            if 'thruster-system' not in p.get('filename', ''):
                continue
            joint = joints[p.find('joint_name').text]
            child = links[joint.find('child').text]
            name = p.find('topic').text.split('/')[-2]   # thrusters/<navn>/thrust
            parent = joint.find('parent').text
            pod = next((j for j in joints.values()
                        if j.find('child').text == parent and j.get('type') == 'revolute'), None)
            x, y = _pose(child)[:2]
            self.thrusters[name] = Thruster(
                name, x, y, _floats(joint.find('axis/xyz').text)[:2],
                float(p.find('min_thrust_cmd').text), float(p.find('max_thrust_cmd').text),
                steerable=pod is not None)
            if pod is not None:
                limit = pod.find('axis/limit')
                t = self.thrusters[name]
                t.angle_min = float(limit.find('lower').text)
                t.angle_max = float(limit.find('upper').text)
                t.pod_joint = pod.get('name')
        for p in plugins:
            if 'joint-position-controller' in p.get('filename', ''):
                name = p.find('topic').text.split('/')[-2]   # /asv/thrusters/<navn>/pos
                if name in self.thrusters:
                    self.thrusters[name].angle_rate = float(p.find('cmd_max').text)

        # Tilstand: posisjon og yaw i verden (tyngdepunktet), og fart i båtens ramme.
        self.x = self.y = self.yaw = 0.0
        self.u = self.v = self.r = 0.0
        self.u_dot = self.v_dot = 0.0

    def set_thrust(self, name, value):
        t = self.thrusters[name]
        t.thrust = max(t.min_thrust, min(t.max_thrust, value))

    def set_angle(self, name, value):
        t = self.thrusters[name]
        if t.steerable:
            t.angle_cmd = max(t.angle_min, min(t.angle_max, value))

    def forces(self, u, v, r):
        """Krefter og moment i tyngdepunktet (båtens ramme) for en gitt fart."""
        X = Y = N = 0.0
        for t in self.thrusters.values():
            c, s = math.cos(t.angle), math.sin(t.angle)
            fx = t.thrust * (c * t.axis[0] - s * t.axis[1])
            fy = t.thrust * (s * t.axis[0] + c * t.axis[1])
            dx, dy = t.x - self.xg, t.y - self.yg
            X += fx
            Y += fy
            N += dx * fy - dy * fx
        # Motstanden angriper i hydro_link, som ligger et stykke fra tyngdepunktet.
        d = self.damping
        dx, dy = self.hx - self.xg, self.hy - self.yg
        uh, vh = u - r * dy, v + r * dx
        xh = -(d['xU'] + d['xUU'] * abs(uh)) * uh
        yh = -(d['yV'] + d['yVV'] * abs(vh)) * vh
        X += xh
        Y += yh
        N += -(d['nR'] + d['nRR'] * abs(r)) * r + dx * yh - dy * xh
        return X, Y, N

    def derivatives(self, u, v, r):
        X, Y, N = self.forces(u, v, r)
        m, au, av, ar = self.mass, self.added['xDotU'], self.added['yDotV'], self.added['nDotR']
        u_dot = (X + (m + av) * v * r) / (m + au)
        v_dot = (Y - (m + au) * u * r) / (m + av)
        r_dot = (N - (av - au) * u * v) / (self.iz + ar)
        return u_dot, v_dot, r_dot

    def step(self, dt):
        # Thrustervinkelen følger kommandoen med begrenset dreiehastighet, som i Gazebo.
        for t in self.thrusters.values():
            if t.steerable:
                rate = self.angle_gain * (t.angle_cmd - t.angle)
                rate = max(-t.angle_rate, min(t.angle_rate, rate))
                t.angle += rate * dt

        # Runge-Kutta 4 for farten, med thrusterne holdt fast gjennom steget.
        def f(state):
            u, v, r, yaw = state
            du, dv, dr = self.derivatives(u, v, r)
            return du, dv, dr, r

        s0 = (self.u, self.v, self.r, self.yaw)
        k1 = f(s0)
        k2 = f(tuple(a + 0.5 * dt * b for a, b in zip(s0, k1)))
        k3 = f(tuple(a + 0.5 * dt * b for a, b in zip(s0, k2)))
        k4 = f(tuple(a + dt * b for a, b in zip(s0, k3)))
        new = tuple(a + dt / 6.0 * (b + 2 * c + 2 * d + e)
                    for a, b, c, d, e in zip(s0, k1, k2, k3, k4))

        # Posisjonen i verden integreres med snittet av yaw og farten gjennom steget.
        yaw_mid = 0.5 * (self.yaw + new[3])
        u_mid, v_mid = 0.5 * (self.u + new[0]), 0.5 * (self.v + new[1])
        self.x += (u_mid * math.cos(yaw_mid) - v_mid * math.sin(yaw_mid)) * dt
        self.y += (u_mid * math.sin(yaw_mid) + v_mid * math.cos(yaw_mid)) * dt
        self.u_dot, self.v_dot = (new[0] - self.u) / dt, (new[1] - self.v) / dt
        self.u, self.v, self.r = new[0], new[1], new[2]
        self.yaw = math.atan2(math.sin(new[3]), math.cos(new[3]))

    def origin_position(self):
        """Posisjonen til modellens origo (der GPS-en sitter i Gazebo), ikke tyngdepunktet."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return self.x - (c * self.xg - s * self.yg), self.y - (s * self.xg + c * self.yg)
