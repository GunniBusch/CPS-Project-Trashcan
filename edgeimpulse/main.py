import os
import sys
import signal
import time
from edge_impulse_linux.audio import AudioImpulseRunner
import numpy as np
from collections import deque
import sounddevice as sd
import queue
import serial
import threading
from collections import defaultdict
from dotenv import load_dotenv, find_dotenv

runner = None

# Protokoll-Kommandos nach Spezifikation
PROTOCOL_COMMANDS = {
    'start', 'mTray', 'mPosBottle', 'gPosBottle', 'gLimitTray', 'gState', 'gType', 'estop', 'ping',
    'gDiagTray', 'gDiagBottle', 'setTrayPos', 'setBottleSpeed'
}

# Abwärtskompatible Aliase
commands = {
    "GetBottleStatus": "gPosBottle",
    "MoveBottle": "mPosBottle",
    "MoveTray": "mTray",
    # Direkte Protokollnamen erlauben
    "start": "start",
    "mTray": "mTray",
    "mPosBottle": "mPosBottle",
    "gPosBottle": "gPosBottle",
    "gLimitTray": "gLimitTray",
    "gState": "gState",
    "gType": "gType",
    "estop": "estop",
    "ping": "ping",
    # Diagnose/Einstellungen
    "gDiagTray": "gDiagTray",
    "gDiagBottle": "gDiagBottle",
    "setTrayPos": "setTrayPos",
    "setBottleSpeed": "setBottleSpeed",
}

class Arduino:
    """Serielle Schnittstelle mit asynchronem Event-Reader und Ack-Wartelogik."""
    def __init__(self, port: str, baud: int = 9600, timeout: float = 1.0):
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        # Acks pro Kommando
        self._acks = defaultdict(queue.Queue)
        # Letzter bekannter State (aus Events)
        self.last_state = None
        self._running = True
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, name="arduino-reader", daemon=True)
        self._reader.start()

    def close(self):
        self._running = False
        try:
            self.ser.close()
        except Exception:
            pass

    def _read_loop(self):
        buffer = b''
        while self._running:
            try:
                line = self.ser.readline()
                if not line:
                    continue
                try:
                    s = line.decode('utf-8', errors='replace').strip()
                except Exception:
                    continue
                if not s:
                    continue
                # Event-Zeilen
                if s.startswith('event::state::'):
                    state = s.split('::', 2)[2]
                    self.last_state = state
                    print(f"[EVENT] state={state}")
                    continue
                # Ack-Zeilen: <cmd>::ack::<payload?>
                parts = s.split('::')
                if len(parts) >= 2 and parts[1] == 'ack':
                    cmd = parts[0]
                    payload = parts[2] if len(parts) > 2 else None
                    # Ack in passende Queue legen
                    self._acks[cmd].put(payload)
                    # Debug
                    # print(f"[ACK] {cmd} -> {payload}")
                    continue
                # Unbekannte Zeilen protokollieren
                print(f"[SERIAL] {s}")
            except Exception as e:
                # Nicht abstürzen bei sporadischen Fehlern
                print(f"[SERIAL-ERR] {e}")
                time.sleep(0.05)

    def send(self, command: str, value) -> str | None:
        if command not in commands:
            raise ValueError(f"Invalid command '{command}'")
        proto_cmd = commands[command]
        line = f"{proto_cmd}::{value}\n"
        with self._lock:
            self.ser.write(line.encode('utf-8'))
        try:
            # Auf Ack für dieses Kommando warten
            payload = self._acks[proto_cmd].get(timeout=2.0)
            return payload
        except queue.Empty:
            print(f"[WARN] Timeout auf Ack für {proto_cmd}")
            return None

    # Komfort-Methoden
    def ping(self) -> bool:
        p = self.send('ping', 'x')
        return p == 'pong'

    def get_state(self) -> str | None:
        p = self.send('gState', 'x')
        return p

    def start(self, type_value: int | str) -> bool:
        p = self.send('start', type_value)
        return p == 'OK'

    def move_tray(self, type_value: int | str) -> bool:
        p = self.send('mTray', type_value)
        return p == 'OK'

    def move_bottle(self, pos: int) -> str | None:
        return self.send('mPosBottle', pos)

    # Diagnose: Tray
    def diag_tray(self) -> dict | None:
        payload = self.send('gDiagTray', 'x')
        if not payload:
            return None
        # Erwartetes Format: pos=<cur>,target=<tgt>,dtg=<dist>,speed=<spd>,state=<trayState>
        out: dict = {}
        try:
            parts = [p.strip() for p in payload.split(',') if p.strip()]
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    if k in ('pos', 'target', 'dtg', 'speed'):
                        try:
                            out[k] = int(v)
                        except Exception:
                            out[k] = v
                    elif k == 'state':
                        out[k] = v
            return out
        except Exception:
            return { 'raw': payload }

    # Diagnose: Bottle
    def diag_bottle(self) -> int | None:
        payload = self.send('gDiagBottle', 'x')
        if not payload:
            return None
        try:
            # Format: state=<BottleStateNum>
            if payload.startswith('state='):
                return int(payload.split('=', 1)[1].strip())
            return int(payload)
        except Exception:
            return None

    # Einstellungen: Tray-Zielposition pro Typ setzen (dauerhaft im RAM laut Firmware)
    def set_tray_pos(self, type_value: int | str, steps: int) -> bool | None:
        value = f"{type_value}={int(steps)}"
        ack = self.send('setTrayPos', value)
        return True if ack == 'OK' else (False if ack else None)

    # Einstellungen: Bottle-Servo-Speed setzen (ms pro Schritt)
    def set_bottle_speed(self, ms: int) -> bool | None:
        ack = self.send('setBottleSpeed', int(ms))
        return True if ack == 'OK' else (False if ack else None)

# Typ-Mapping
TYPE_NAME_BY_ID = {0: 'PLASTIC', 1: 'GLAS', 2: 'CAN'}
ID_BY_NAME = {
    'plastic': 0, 'plastik': 0,
    'glas': 1, 'glass': 1,
    'can': 2, 'dose': 2,
}

def normalize_type(value) -> int | None:
    # int oder string erlauben
    try:
        iv = int(value)
        if iv in (0, 1, 2):
            return iv
    except Exception:
        pass
    if isinstance(value, str):
        k = value.strip().lower()
        return ID_BY_NAME.get(k)
    return None

# Automatikablauf

def wait_for_idle(ard: Arduino, timeout_s: float = 5.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        # Bevorzugt letzten Event-State, sonst aktiv abfragen
        st = ard.last_state or ard.get_state()
        if st == 'IDLE':
            return True
        time.sleep(0.2)
    return False


def run_automatic_cycle(ard: Arduino, type_id: int, timeout_s: float = 30.0) -> bool:
    if not wait_for_idle(ard, timeout_s=5.0):
        print('[AUTO] Nicht IDLE, warte/abbruch')
        return False
    ok = ard.start(type_id)
    if not ok:
        print('[AUTO] start::<type> wurde nicht bestätigt')
        return False
    print(f"[AUTO] gestartet mit Typ {type_id}={TYPE_NAME_BY_ID.get(type_id)}")
    # Warte, bis wieder IDLE per Event oder Status
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if ard.last_state == 'IDLE':
            print('[AUTO] Zyklus abgeschlossen (Event)')
            return True
        st = ard.get_state()
        if st == 'IDLE':
            print('[AUTO] Zyklus abgeschlossen (Abfrage)')
            return True
        time.sleep(0.3)
    print('[AUTO] Timeout im Automatikablauf')
    return False




class Trashcan:
    def __int__(self):
        pass


    def recvDetection(self, type):
        print("Received detection", type)


    def sendHome(self):
        print("Sending home")

        # Todo arduino








def signal_handler(sig, frame):
    print('Interrupted')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def _help_old():
    print('python classify.py <path_to_model.eim> <audio_device_ID, optional>' )

def main(model, selected_device_id=None):

    # .env automatisch laden (robust, auch bei anderem CWD)
    load_dotenv(find_dotenv())

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    # Serielle Verbindung öffnen (9600 Baud). Port via ENV überschreibbar.
    serial_port = os.environ.get('TRASHCAN_SERIAL_PORT')
    if not serial_port:
        # Fallbacks (Mac/Linux gängige Devices)
        # Bitte via ENV setzen, falls abweichend
        for p in ('/dev/ttyACM0', '/dev/ttyUSB0', '/dev/cu.usbserial-21230'):
            if os.path.exists(p):
                serial_port = p
                break
    ard = None
    if serial_port:
        try:
            ard = Arduino(serial_port, baud=9600, timeout=1.0)
            print(f"[SERIAL] verbunden: {serial_port}")
            # Optional: Ping
            if not ard.ping():
                print('[SERIAL] Ping fehlgeschlagen (fahre trotzdem fort)')
            # Optional: Diagnose-Thread
            diag_enabled = os.environ.get('DIAG_ENABLED', '0') == '1'
            if diag_enabled:
                diag_interval = float(os.environ.get('DIAG_INTERVAL_S', '10'))
                def _diag_loop():
                    while True:
                        try:
                            t = ard.diag_tray()
                            b = ard.diag_bottle()
                            if t is not None:
                                print(f"[DIAG] Tray pos={t.get('pos')} tgt={t.get('target')} dtg={t.get('dtg')} spd={t.get('speed')} state={t.get('state')}")
                            if b is not None:
                                print(f"[DIAG] Bottle state={b}")
                        except Exception as e:
                            print(f"[DIAG] Fehler: {e}")
                        time.sleep(diag_interval)
                th = threading.Thread(target=_diag_loop, name='diag-thread', daemon=True)
                th.start()

            # Optional: Start-Konfiguration anwenden
            def _env_int(name):
                v = os.environ.get(name)
                if v is None or v == '':
                    return None
                try:
                    return int(v)
                except Exception:
                    return None
            # Bottle-Speed
            spd = _env_int('BOTTLE_SPEED_MS')
            if spd is not None:
                ok = ard.set_bottle_speed(spd)
                print(f"[CFG] setBottleSpeed={spd} -> {ok}")
            # Tray-Positionen (Unterstützt zwei Schemata)
            env_keys = [
                ('TRAY_POS_0', 0), ('TRAY_POS_1', 1), ('TRAY_POS_2', 2),
                ('TRAY_POS_PLASTIC', 0), ('TRAY_POS_GLAS', 1), ('TRAY_POS_CAN', 2)
            ]
            for key, tid in env_keys:
                steps = _env_int(key)
                if steps is not None:
                    ok = ard.set_tray_pos(tid, steps)
                    print(f"[CFG] setTrayPos type={tid} steps={steps} -> {ok}")
        except Exception as e:
            print(f"[SERIAL] Verbindung fehlgeschlagen: {e}")
            ard = None
    else:
        print('[SERIAL] Kein Port gefunden – setze TRASHCAN_SERIAL_PORT')

    with AudioImpulseRunner(str(modelfile)) as runner:
        model_info = runner.init()
        labels = model_info['model_parameters']['labels']
        print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')

        # Samplingrate aus Modell-Info
        sample_rate = model_info['model_parameters'].get('frequency', 16000)
        buffer_duration = 1.0 # Sekunden
        buffer_size = int(sample_rate * buffer_duration)
        audio_buffer = deque(maxlen=buffer_size)

        # Konfigurierbare Trigger-Parameter über ENV
        threshold = int(os.environ.get('AUDIO_RMS_THRESHOLD', '1200'))  # int16 RMS
        pre_ms = float(os.environ.get('PRE_MS', '200'))
        post_ms = float(os.environ.get('POST_MS', '800'))
        cooldown_s = float(os.environ.get('TRIGGER_COOLDOWN_S', '0.3'))
        visualize = os.environ.get('VISUALIZE', '0') == '1'

        triggered = False
        # Korrekt: 800 ms sammeln, 200 ms Vergangenheit (insgesamt 1 s)
        post_trigger_samples = int(sample_rate * (post_ms / 1000.0))
        pre_trigger_samples = int(sample_rate * (pre_ms / 1000.0))
        post_trigger_count = 0
        last_trigger_ts = 0.0

        # Audio-Queue und Callback für sounddevice
        q = queue.Queue(maxsize=50)
        def audio_callback(indata, frames, time_info, status):
            if status:
                print(str(status), file=sys.stderr)
            # int16-Mono sicherstellen
            if indata.ndim == 2:
                data = indata[:, 0].copy()
            else:
                data = indata.copy()
            q.put(data)

        # Blockgröße ~20ms
        blocksize = max(128, int(sample_rate * 0.02))

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=blocksize, callback=audio_callback, device=selected_device_id):
            while True:
                block = q.get()
                audio_np = np.asarray(block, dtype=np.int16)

                # In den Ringpuffer schreiben
                audio_buffer.extend(audio_np.tolist())

                # RMS berechnen (float32 vermeidet Overflow)
                if audio_np.size > 0:
                    rms = float(np.sqrt(np.mean(np.square(audio_np.astype(np.float32)))))
                else:
                    rms = 0.0

                now = time.time()
                if not triggered and (now - last_trigger_ts) >= cooldown_s and rms > threshold and len(audio_buffer) >= pre_trigger_samples:
                    triggered = True
                    post_trigger_count = 0
                    last_trigger_ts = now
                    print(f"Trigger! RMS={rms:.1f}")

                if triggered:

                    # AI PART – 800 ms sammeln
                    post_trigger_count += audio_np.size
                    if post_trigger_count >= post_trigger_samples:
                        # 1s Snapshot aus Ringpuffer (enthält >=200ms davor + 800ms danach)
                        segment = list(audio_buffer)
                        if len(segment) < buffer_size:
                            segment = ([0] * (buffer_size - len(segment))) + segment
                        elif len(segment) > buffer_size:
                            segment = segment[-buffer_size:]
                        segment = np.asarray(segment, dtype=np.int16)
                        print("Segment mit Länge", len(segment), "wird klassifiziert.")

                        # Klassifizierung einmalig
                        result = runner.classify(segment)
                        print("Klassifizierungsergebnis:", result)

                        # Besten Label ermitteln
                        scores = result.get('result', {}).get('classification', {})
                        top_label = max(scores, key=scores.get) if scores else None
                        top_score = scores.get(top_label, 0.0) if top_label else 0.0
                        print(f"Top: {top_label} ({top_score:.2f})")

                        # Optional: Visualisierung/Export
                        if visualize:
                            try:
                                import matplotlib.pyplot as plt
                                from scipy.io.wavfile import write as wavwrite
                                plt.figure(figsize=(10, 3))
                                plt.plot(segment, linewidth=0.8)
                                plt.title("Audio-Segment zur Klassifizierung")
                                plt.xlabel("Sample")
                                plt.ylabel("Amplitude")
                                plt.tight_layout()
                                plt.savefig("last_segment.png")
                                plt.close()
                                plt.figure(figsize=(10, 4))
                                plt.specgram(segment, Fs=sample_rate, NFFT=512, noverlap=256, cmap='magma')
                                plt.title("Spektrogramm des Audio-Segments")
                                plt.xlabel("Zeit [s]")
                                plt.ylabel("Frequenz [Hz]")
                                plt.colorbar(label='dB')
                                plt.tight_layout()
                                plt.savefig("last_segment_spectrogram.png")
                                plt.close()
                                wavwrite("last_segment.wav", sample_rate, segment)
                            except Exception as e:
                                print(f"[VIS] Fehler bei Visualisierung/Export: {e}")

                        # Typ-Mapping
                        type_id = None
                        if top_label and top_score >= 0.7:
                            type_id = normalize_type(top_label)
                        if type_id is None:
                            # Versuche Fallback anhand bekannter Labels
                            lbl = (top_label or '').lower()
                            if 'plast' in lbl:
                                type_id = 0
                            elif 'glas' in lbl or 'glass' in lbl:
                                type_id = 1
                            elif 'can' in lbl or 'dose' in lbl or 'metal' in lbl:
                                type_id = 2

                        if type_id is not None:
                            print(f"[CLASSIFY] erkannter Typ: {TYPE_NAME_BY_ID.get(type_id)}")
                            if ard is not None:
                                run_automatic_cycle(ard, type_id, timeout_s=45.0)
                            else:
                                print('[SERIAL] Keine Verbindung – Automatik wird übersprungen')
                        else:
                            print('[CLASSIFY] kein sicherer Typ erkannt, überspringe')

                        # Reset Trigger & Buffer
                        triggered = False
                        post_trigger_count = 0
                        audio_buffer.clear()

                        # Optional: Visualisierung/Export aktivieren
                        # plt.figure(figsize=(10, 3))
                        # plt.plot(segment, linewidth=0.8)
                        # plt.title("Audio-Segment zur Klassifizierung")
                        # plt.xlabel("Sample")
                        # plt.ylabel("Amplitude")
                        # plt.tight_layout()
                        # plt.savefig("last_segment.png")
                        # plt.close()
                        # plt.figure(figsize=(10, 4))
                        # plt.specgram(segment, Fs=sample_rate, NFFT=512, noverlap=256, cmap='magma')
                        # plt.title("Spektrogramm des Audio-Segments")
                        # plt.xlabel("Zeit [s]")
                        # plt.ylabel("Frequenz [Hz]")
                        # plt.colorbar(label='dB')
                        # plt.tight_layout()
                        # plt.savefig("last_segment_spectrogram.png")
                        # plt.close()
                        # wavwrite("last_segment.wav", sample_rate, segment)


def help():
    print('python edgeimpulse/main.py <path_to_model.eim> <audio_device_ID, optional>')

if __name__ == '__main__':
    # Daemon-Modus: keine CLI-Args nötig; lese aus .env
    load_dotenv(find_dotenv())
    model_path = os.environ.get('MODEL_EIM_PATH', '../model/modelmac.eim')
    dev_env = os.environ.get('AUDIO_DEVICE_ID')
    device_id = int(dev_env) if (dev_env and dev_env.isdigit()) else None
    main(model_path, device_id)
