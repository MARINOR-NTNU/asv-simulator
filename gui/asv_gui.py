#!/usr/bin/env python3
"""Enkel GUI for å starte simulatoren og se ROS 2-topics live i Foxglove.

Kjører på verten (ikke i containeren) og trenger bare Python 3 med Tkinter og Docker.
Alt som har med ROS å gjøre, kjøres i simulator-containeren med docker exec:

  - Start/stopp: sim.launch.py i containeren, med valgene fra README («Starte alt med én kommando»).
  - Topics: henter `ros2 topic list -t` fra containeren.
  - Foxglove: starter foxglove_bridge i containeren med bare de valgte topicene
    (topic_whitelist), og åpner Foxglove mot ws://localhost:8765. Kjører containeren
    uten --net=host, videresender GUI-en porten fra localhost til containeren, siden
    nettleseren ikke tillater ws:// mot andre adresser enn localhost fra app.foxglove.dev.
  - Lager også en Foxglove-layout (foxglove_layout.json) med ett panel per valgt topic.

Bruk:
  python3 gui/asv_gui.py [--container asv_sim] [--image vrx-sim:humble-garden]
"""
import argparse
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYOUT_FILE = os.path.join(REPO_ROOT, 'gui', 'foxglove_layout.json')

ROS_SETUP = 'source /opt/ros/humble/setup.bash && source /root/vrx_ws/install/setup.bash'
SIM_LOG = '/tmp/gui_sim.log'
SIM_PID = '/tmp/gui_sim.pid'
BRIDGE_LOG = '/tmp/gui_foxglove.log'
BRIDGE_PID = '/tmp/gui_foxglove.pid'
BRIDGE_PARAMS = '/tmp/gui_foxglove.yaml'
BRIDGE_PORT = 8765

# Samme byggekommando som i CLAUDE.md: ett løp om gangen, maskinen har lite minne.
BUILD_CMD = ('cd /root/vrx_ws && MAKEFLAGS="-j1" colcon build --merge-install '
             '--executor sequential --parallel-workers 1 --packages-select asv_gazebo sim_interface')

SCALAR_TYPES = {'std_msgs/msg/Float64', 'std_msgs/msg/Float32', 'std_msgs/msg/Int32',
                'std_msgs/msg/Int64', 'std_msgs/msg/Bool'}
IMAGE_TYPES = {'sensor_msgs/msg/Image', 'sensor_msgs/msg/CompressedImage'}
SCENE_TYPES = {'sensor_msgs/msg/PointCloud2', 'sensor_msgs/msg/LaserScan',
               'visualization_msgs/msg/Marker', 'visualization_msgs/msg/MarkerArray',
               'geometry_msgs/msg/PoseStamped', 'nav_msgs/msg/Odometry'}


def docker(*args, input=None, timeout=60):
    """Kjører en docker-kommando og returnerer (returkode, stdout+stderr)."""
    try:
        result = subprocess.run(['docker', *args], input=input, capture_output=True,
                                text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, f'docker {args[0]} svarte ikke innen {timeout} s'
    return result.returncode, (result.stdout + result.stderr).strip()


def in_background(script, pid_file, log_file):
    """Skall-kode som starter script i egen prosessgruppe og lagrer PID-en, så den kan stoppes."""
    return (f'setsid bash -c {shell_quote(script)} > {log_file} 2>&1 < /dev/null & '
            f'echo $! > {pid_file}')


def stop_group(pid_file):
    """Skall-kode som stopper prosessgruppen i pid_file: først SIGINT (ros2 launch rydder opp), så KILL."""
    return (f'[ -f {pid_file} ] || exit 0; pid=$(cat {pid_file}); '
            f'kill -INT -- -$pid 2>/dev/null; '
            f'for i in $(seq 20); do kill -0 -- -$pid 2>/dev/null || break; sleep 0.5; done; '
            f'kill -KILL -- -$pid 2>/dev/null; rm -f {pid_file}')


def shell_quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


class PortForwarder:
    """Videresender localhost:port til containerens IP, for containere uten --net=host."""

    def __init__(self, port, target_host):
        self.port = port
        self.target_host = target_host
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('127.0.0.1', port))
        self.server.listen()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            try:
                upstream = socket.create_connection((self.target_host, self.port), timeout=5)
                upstream.settimeout(None)
            except OSError:
                client.close()
                continue
            for a, b in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pipe, args=(a, b), daemon=True).start()

    @staticmethod
    def _pipe(src, dst):
        try:
            while data := src.recv(65536):
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self):
        # shutdown vekker accept() i tråden. Bare close() lar porten stå åpen til neste
        # tilkobling, så en ny videresending på samme port feiler med «Address already in use».
        try:
            self.server.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.server.close()


def foxglove_layout(topics):
    """Lager en Foxglove-layout med ett panel per topic, valgt ut fra meldingstypen."""
    panels = {}
    for i, (topic, msg_type) in enumerate(topics):
        if msg_type in SCALAR_TYPES:
            panels[f'Plot!p{i}'] = {
                'title': topic,
                'paths': [{'value': f'{topic}.data', 'enabled': True,
                           'timestampMethod': 'receiveTime'}],
                'showLegend': True, 'followingViewWidth': 30}
        elif msg_type in IMAGE_TYPES:
            panels[f'Image!p{i}'] = {'imageMode': {'imageTopic': topic}}
        elif msg_type in SCENE_TYPES:
            panels[f'3D!p{i}'] = {'topics': {topic: {'visible': True}}}
        elif msg_type == 'sensor_msgs/msg/NavSatFix':
            panels[f'map!p{i}'] = {}
        else:
            panels[f'RawMessages!p{i}'] = {'topicPath': topic}

    def tree(ids, depth=0):
        if len(ids) == 1:
            return ids[0]
        half = (len(ids) + 1) // 2
        return {'first': tree(ids[:half], depth + 1), 'second': tree(ids[half:], depth + 1),
                'direction': 'row' if depth % 2 == 0 else 'column',
                'splitPercentage': 100 * half / len(ids)}

    return {'configById': panels, 'globalVariables': {}, 'userNodes': {},
            'playbackConfig': {'speed': 1}, 'layout': tree(list(panels)) if panels else None}


class App:
    def __init__(self, root, container, image):
        self.root = root
        self.container = tk.StringVar(value=container)
        self.image = image
        self.events = queue.Queue()
        self.topics = []              # [(topic, type)] fra siste oppdatering
        self.forwarder = None
        self.log_tail = None          # docker exec tail -F på loggen til simulatoren
        self.forward_lock = threading.Lock()  # _watch og visualize kan sette opp videresending samtidig
        self.forward_error = None     # siste feil fra videresendingen, så den bare logges én gang

        root.title('ASV-simulator')
        root.geometry('900x700')
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        self._build_ui()
        self.root.after(100, self._poll_events)
        self._watch()

    # ---------- UI ----------
    def _build_ui(self):
        pad = {'padx': 6, 'pady': 4}
        top = ttk.Frame(self.root)
        top.pack(fill='x', **pad)
        ttk.Label(top, text='Container:').pack(side='left')
        ttk.Entry(top, textvariable=self.container, width=18).pack(side='left', padx=4)
        self.status = ttk.Label(top, text='…')
        self.status.pack(side='left', padx=10)
        ttk.Button(top, text='Lag container på nytt',
                   command=self.recreate_container).pack(side='right')

        # Simulator
        sim = ttk.LabelFrame(self.root, text='Simulator (sim.launch.py)')
        sim.pack(fill='x', **pad)
        self.opts = {}
        choices = [('sim', ['vrx_asv', 'vrx']), ('world', ['open_water', 'sydney_regatta']),
                   ('control', ['none', 'stub', 'px4']), ('autonomy', ['none', 'fake', 'path']),
                   ('path', ['path_demo', 'path_slalom'])]
        for col, (name, values) in enumerate(choices):
            ttk.Label(sim, text=name).grid(row=0, column=col, sticky='w', padx=4)
            var = tk.StringVar(value=values[0])
            ttk.Combobox(sim, textvariable=var, values=values, width=14,
                         state='readonly').grid(row=1, column=col, padx=4)
            self.opts[name] = var
        self.headless = tk.BooleanVar(value=False)
        self.build_first = tk.BooleanVar(value=True)
        ttk.Checkbutton(sim, text='headless', variable=self.headless).grid(
            row=2, column=0, sticky='w', padx=4)
        ttk.Checkbutton(sim, text='Bygg pakkene først', variable=self.build_first).grid(
            row=2, column=1, sticky='w', padx=4)
        ttk.Button(sim, text='▶ Start', command=lambda: self.run(self.start_sim)).grid(
            row=2, column=3, sticky='e', padx=4, pady=4)
        ttk.Button(sim, text='■ Stopp', command=lambda: self.run(self.stop_sim)).grid(
            row=2, column=4, sticky='e', padx=4, pady=4)

        # Topics og Foxglove
        mid = ttk.PanedWindow(self.root, orient='horizontal')
        mid.pack(fill='both', expand=True, **pad)

        topics = ttk.LabelFrame(mid, text='ROS 2-topics (velg dem som skal vises)')
        bar = ttk.Frame(topics)
        bar.pack(fill='x')
        ttk.Button(bar, text='Oppdater', command=lambda: self.run(self.refresh_topics)).pack(
            side='left', padx=2, pady=2)
        ttk.Button(bar, text='Velg alle',
                   command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side='left')
        ttk.Button(bar, text='Ingen',
                   command=lambda: self.tree.selection_set(())).pack(side='left', padx=2)
        self.filter = tk.StringVar()
        self.filter.trace_add('write', lambda *_: self._fill_tree())
        ttk.Entry(bar, textvariable=self.filter, width=20).pack(side='right', padx=2)
        ttk.Label(bar, text='Filter:').pack(side='right')
        self.tree = ttk.Treeview(topics, columns=('type',), selectmode='extended')
        self.tree.heading('#0', text='Topic')
        self.tree.heading('type', text='Type')
        self.tree.column('#0', width=330)
        self.tree.column('type', width=220)
        self.tree.pack(fill='both', expand=True)
        mid.add(topics, weight=3)

        fox = ttk.LabelFrame(mid, text='Foxglove')
        ttk.Button(fox, text='Vis valgte i Foxglove',
                   command=lambda: self.run(self.visualize)).pack(fill='x', padx=6, pady=4)
        ttk.Button(fox, text='Åpne Foxglove',
                   command=self.open_foxglove).pack(fill='x', padx=6, pady=4)
        ttk.Button(fox, text='Stopp bridge',
                   command=lambda: self.run(self.stop_bridge)).pack(fill='x', padx=6, pady=4)
        self.fox_status = ttk.Label(fox, text='Bridge: av', wraplength=220, justify='left')
        self.fox_status.pack(fill='x', padx=6, pady=8)
        ttk.Label(fox, wraplength=220, justify='left', foreground='gray',
                  text=f'Layout: gui/foxglove_layout.json\n(Foxglove: Layout → Import from file)'
                  ).pack(fill='x', padx=6)
        mid.add(fox, weight=1)

        # Logg
        log = ttk.LabelFrame(self.root, text='Logg')
        log.pack(fill='both', expand=True, **pad)
        self.log = tk.Text(log, height=12, wrap='none', state='disabled',
                           background='#1e1e1e', foreground='#d4d4d4')
        scroll = ttk.Scrollbar(log, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.log.pack(fill='both', expand=True)

    def _fill_tree(self):
        selected = {self.tree.item(i, 'text') for i in self.tree.selection()}
        self.tree.delete(*self.tree.get_children())
        pattern = self.filter.get().lower()
        for topic, msg_type in self.topics:
            if pattern in topic.lower() or pattern in msg_type.lower():
                item = self.tree.insert('', 'end', text=topic, values=(msg_type,))
                if topic in selected:
                    self.tree.selection_add(item)

    # ---------- tråder og hendelser ----------
    def run(self, func, *args):
        """Kjører func i en egen tråd, så docker-kallene ikke fryser vinduet."""
        threading.Thread(target=self._guarded, args=(func, *args), daemon=True).start()

    def _guarded(self, func, *args):
        try:
            func(*args)
        except Exception as error:  # vis feilen i loggen i stedet for å miste den i tråden
            self.say(f'Feil: {error}')

    def say(self, text):
        self.events.put(('log', text))

    def ui(self, func, *args):
        self.events.put(('call', (func, args)))

    def _poll_events(self):
        while not self.events.empty():
            kind, payload = self.events.get()
            if kind == 'log':
                self.log.configure(state='normal')
                self.log.insert('end', payload.rstrip('\n') + '\n')
                self.log.see('end')
                self.log.configure(state='disabled')
            else:
                func, args = payload
                func(*args)
        self.root.after(100, self._poll_events)

    # ---------- container ----------
    def exec(self, script, timeout=60, input=None):
        flags = ['-i'] if input is not None else []
        return docker('exec', *flags, self.container.get(), 'bash', '-c', script,
                      input=input, timeout=timeout)

    def container_info(self):
        """Returnerer (finnes, kjører, nettverksmodus, ip, har_x11)."""
        code, out = docker('inspect', self.container.get(), '--format',
                           '{{.State.Running}}|{{.HostConfig.NetworkMode}}|'
                           '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}|'
                           '{{range .Mounts}}{{.Destination}} {{end}}')
        if code != 0:
            return False, False, '', '', False
        running, network, ip, mounts = out.split('|')
        return True, running == 'true', network, ip, '/tmp/.X11-unix' in mounts

    def _refresh_status(self):
        exists, running, network, ip, _ = self.container_info()
        if not exists:
            text = 'finnes ikke (lages ved Start)'
        elif not running:
            text = 'stoppet'
        else:
            code, _ = self.exec(f'[ -f {SIM_PID} ] && kill -0 $(cat {SIM_PID})')
            text = f'kjører ({network}{", " + ip if network != "host" else ""})'
            text += ' – simulator kjører' if code == 0 else ' – simulator av'
            if code == 0 and not (self.log_tail and self.log_tail.poll() is None):
                self._follow_log()  # f.eks. når GUI-en er startet på nytt mens simulatoren går
        self.ui(self.status.configure, {'text': text})

    def _watch(self):
        """Sjekker hvert 3. sekund at bridgen kjører, og at porten er videresendt hvis den gjør det."""
        def work():
            try:
                self._refresh_status()
                exists, running, *_ = self.container_info()
                alive = running and self.exec(
                    f'[ -f {BRIDGE_PID} ] && kill -0 $(cat {BRIDGE_PID})')[0] == 0
                if alive:
                    self._setup_forwarder()
                    text = f'Bridge: på\nws://localhost:{BRIDGE_PORT}'
                    if self.forward_error:
                        text += f'\n{self.forward_error}'
                else:
                    text = 'Bridge: av\nTrykk «Vis valgte i Foxglove»'
                self.ui(self.fox_status.configure, {'text': text})
            finally:
                self.ui(self.root.after, 3000, self._watch)
        self.run(work)

    def ensure_container(self):
        exists, running, *_ = self.container_info()
        if not exists:
            self.create_container()
        elif not running:
            self.say(f'Starter containeren {self.container.get()}...')
            code, out = docker('start', self.container.get())
            if code != 0:
                raise RuntimeError(out)

    def create_container(self):
        """Lager containeren slik README beskriver: --net=host, X11 og GPU, src/ montert inn."""
        name = self.container.get()
        self.say(f'Lager containeren {name} fra {self.image}...')
        if shutil.which('xhost'):
            subprocess.run(['xhost', '+local:docker'], capture_output=True)
        args = ['run', '-d', '--name', name, '--net=host',
                '-e', f'DISPLAY={os.environ.get("DISPLAY", ":0")}',
                '-v', '/tmp/.X11-unix:/tmp/.X11-unix',
                '-v', f'{REPO_ROOT}/src:/root/vrx_ws/src/mysrc']
        if os.path.exists('/dev/dri'):
            args += ['--device', '/dev/dri']
        code, out = docker(*args, self.image, 'sleep', 'infinity')
        if code != 0:
            raise RuntimeError(out)

    def recreate_container(self):
        name = self.container.get()
        if messagebox.askyesno(
                'Lag container på nytt',
                f'Dette fjerner containeren «{name}» (alt som kjører i den stopper, og bygget i '
                f'den forsvinner) og lager den på nytt med --net=host, X11 og GPU.\n\nFortsette?'):
            self.run(self._recreate)

    def _recreate(self):
        name = self.container.get()
        self._stop_forwarder()
        self.say(f'Fjerner {name}...')
        docker('rm', '-f', name, timeout=30)
        self.create_container()
        self.say('Containeren er klar. Pakkene må bygges på nytt i den (gjøres ved Start).')
        self._refresh_status()

    def ask(self, title, text):
        """Ja/nei-spørsmål fra en arbeidstråd: dialogen må vises i hovedtråden."""
        answer = queue.Queue()
        self.ui(lambda: answer.put(messagebox.askyesno(title, text)))
        return answer.get()

    # ---------- simulator ----------
    def start_sim(self):
        self.ensure_container()
        _, _, _, _, has_x11 = self.container_info()
        headless = self.headless.get()
        build = self.build_first.get()
        if not headless and not has_x11:
            answer = self.ask(
                'Gazebo-vindu',
                f'Containeren «{self.container.get()}» er laget uten X11 (/tmp/.X11-unix), så '
                f'Gazebo-vinduet kan ikke vises fra den.\n\nLage den på nytt med X11, GPU og '
                f'--net=host? Alt som kjører i den stopper, og pakkene bygges på nytt.\n\n'
                f'Nei = start headless i stedet.')
            if answer:
                self._recreate()
                build = True
            else:
                self.say('Starter headless.')
                headless = True

        code, _ = self.exec(f'[ -f {SIM_PID} ] && kill -0 $(cat {SIM_PID})')
        if code == 0:
            self.say('Simulatoren kjører allerede. Stopp den først.')
            return

        launch_args = ' '.join(f'{k}:={v.get()}' for k, v in self.opts.items())
        launch_args += f' headless:={str(headless).lower()}'
        steps = ['source /opt/ros/humble/setup.bash']
        if build:
            steps.append(f'echo "== Bygger asv_gazebo og sim_interface ==" && {BUILD_CMD}')
        steps += ['source /root/vrx_ws/install/setup.bash',
                  f'echo "== ros2 launch sim_interface sim.launch.py {launch_args} =="',
                  f'exec ros2 launch sim_interface sim.launch.py {launch_args}']
        script = ' && '.join(steps)
        self.say(f'Starter: sim.launch.py {launch_args}')
        env = f'export DISPLAY={os.environ.get("DISPLAY", ":0")}; '
        code, out = self.exec(env + in_background(script, SIM_PID, SIM_LOG))
        if code != 0:
            raise RuntimeError(out)
        self._follow_log()
        self._refresh_status()

    def stop_sim(self):
        self.say('Stopper simulatoren...')
        self.exec(stop_group(SIM_PID), timeout=30)
        # gz sim kan bli hengende etter launch (se fast-skriptet), så rydd opp i den også.
        self.exec('pkill -INT -f "gz sim" ; sleep 1; pkill -KILL -f "gz sim"', timeout=15)
        self.say('Simulatoren er stoppet.')
        self._refresh_status()

    def _follow_log(self):
        """Strømmer simulatorloggen fra containeren inn i loggvinduet."""
        if self.log_tail and self.log_tail.poll() is None:
            self.log_tail.terminate()
        self.log_tail = subprocess.Popen(
            ['docker', 'exec', self.container.get(), 'tail', '-n', '+1', '-F', SIM_LOG],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        def pump(proc):
            for line in proc.stdout:
                self.say(line)
        threading.Thread(target=pump, args=(self.log_tail,), daemon=True).start()

    # ---------- topics og Foxglove ----------
    def refresh_topics(self):
        exists, running, *_ = self.container_info()
        if not running:
            self.say('Containeren kjører ikke. Start simulatoren først.')
            return
        self.say('Henter topics...')
        code, out = self.exec(f'{ROS_SETUP} && ros2 topic list -t', timeout=30)
        if code != 0:
            raise RuntimeError(out)
        topics = []
        for line in out.splitlines():
            match = re.match(r'^(/\S+)\s+\[(.+)\]$', line.strip())
            if match:
                topics.append((match.group(1), match.group(2)))
        self.topics = sorted(topics)
        self.ui(self._fill_tree)
        self.say(f'Fant {len(topics)} topics.')

    def selected_topics(self):
        types = dict(self.topics)
        return [(self.tree.item(i, 'text'), types.get(self.tree.item(i, 'text'), ''))
                for i in self.tree.selection()]

    def visualize(self):
        topics = self.selected_topics()
        if not topics:
            self.say('Velg minst én topic først (trykk «Oppdater» for å hente dem).')
            return
        # Starter bridgen på nytt med de valgte topicene i topic_whitelist (regex per topic).
        whitelist = ', '.join(json.dumps('^' + re.escape(t) + '$') for t, _ in topics)
        params = (f'/**:\n  ros__parameters:\n    port: {BRIDGE_PORT}\n'
                  f'    address: "0.0.0.0"\n    use_sim_time: true\n    topic_whitelist: [{whitelist}]\n')
        self.exec(f'cat > {BRIDGE_PARAMS}', input=params)
        self.exec(stop_group(BRIDGE_PID), timeout=30)
        code, out = self.exec(in_background(
            f'{ROS_SETUP} && exec ros2 run foxglove_bridge foxglove_bridge '
            f'--ros-args --params-file {BRIDGE_PARAMS}', BRIDGE_PID, BRIDGE_LOG))
        if code != 0:
            raise RuntimeError(out)
        self._setup_forwarder()

        with open(LAYOUT_FILE, 'w') as f:
            json.dump(foxglove_layout(topics), f, indent=2)
        self.say(f'foxglove_bridge strømmer {len(topics)} topics på ws://localhost:{BRIDGE_PORT}. '
                 f'Layout lagret i gui/foxglove_layout.json.')

    def _setup_forwarder(self):
        """Videresender porten hvis containeren ikke deler nettverk med verten."""
        with self.forward_lock:
            self._setup_forwarder_locked()

    def _setup_forwarder_locked(self):
        _, _, network, ip, _ = self.container_info()
        if self.forwarder and self.forwarder.target_host == ip and network != 'host':
            return  # samme container, behold videresendingen som allerede går
        self._stop_forwarder()
        if network == 'host' or not ip:
            return
        try:
            self.forwarder = PortForwarder(BRIDGE_PORT, ip)
            self.forward_error = None
            self.say(f'Videresender localhost:{BRIDGE_PORT} → {ip}:{BRIDGE_PORT} '
                     f'(containeren bruker ikke --net=host).')
        except OSError as error:
            message = f'Kunne ikke åpne localhost:{BRIDGE_PORT} ({error.strerror}).'
            if message != self.forward_error:
                self.say(f'{message} Er GUI-en åpen to ganger? Lukk den andre.')
            self.forward_error = message

    def _stop_forwarder(self):
        if self.forwarder:
            self.forwarder.close()
            self.forwarder = None

    def stop_bridge(self):
        self.exec(stop_group(BRIDGE_PID), timeout=30)
        self._stop_forwarder()
        self.ui(self.fox_status.configure, {'text': 'Bridge: av'})
        self.say('foxglove_bridge er stoppet.')

    def open_foxglove(self):
        """Åpner Foxglove-appen hvis den er installert, ellers app.foxglove.dev i nettleseren."""
        query = f'ds=foxglove-websocket&ds.url=ws://localhost:{BRIDGE_PORT}'
        if shutil.which('foxglove-studio') or shutil.which('foxglove'):
            subprocess.Popen(['xdg-open', f'foxglove://open?{query}'])
        else:
            webbrowser.open(f'https://app.foxglove.dev/?{query}')

    def on_close(self):
        if self.log_tail and self.log_tail.poll() is None:
            self.log_tail.terminate()
        self._stop_forwarder()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--container', default='asv_sim')
    parser.add_argument('--image', default='vrx-sim:humble-garden')
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args.container, args.image)
    root.mainloop()


if __name__ == '__main__':
    main()
