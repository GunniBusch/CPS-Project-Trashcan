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
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
import json

runner = None

# Protocol commands supported by the firmware
PROTOCOL_COMMANDS = {
    'start', 'mTray', 'mPosBottle', 'gPosBottle', 'gLimitTray', 'gState', 'gType', 'estop', 'ping',
    'gDiagTray', 'gDiagBottle', 'setTrayPos', 'setBottleSpeed',
    'gTrayEnabled', 'setTrayEnabled', 'recover', 'gLastError', 'gBottleAngle', 'mBottleAngle'
}

# Aliases and direct protocol names
commands = {
    "GetBottleStatus": "gPosBottle",
    "MoveBottle": "mPosBottle",
    "MoveTray": "mTray",
    # direct protocol names allowed
    "start": "start",
    "mTray": "mTray",
    "mPosBottle": "mPosBottle",
    "gPosBottle": "gPosBottle",
    "gLimitTray": "gLimitTray",
    "gState": "gState",
    "gType": "gType",
    "estop": "estop",
    "ping": "ping",
    # diagnostics/settings
    "gDiagTray": "gDiagTray",
    "gDiagBottle": "gDiagBottle",
    "setTrayPos": "setTrayPos",
    "setBottleSpeed": "setBottleSpeed",
    "gTrayEnabled": "gTrayEnabled",
    "setTrayEnabled": "setTrayEnabled",
    "recover": "recover",
    "gLastError": "gLastError",
    "gBottleAngle": "gBottleAngle",
    "mBottleAngle": "mBottleAngle",
}

class Arduino:
    """Serial interface with async event reader and per-command ack queues."""
    def __init__(self, port: str, baud: int = 9600, timeout: float = 1.0):
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._acks: Dict[str, queue.Queue] = defaultdict(queue.Queue)
        self.last_state: Optional[str] = None
        self.last_error: Optional[str] = None
        self._running = True
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, name="arduino-reader", daemon=True)
        self._reader.start()

    def close(self) -> None:
        self._running = False
        try:
            self.ser.close()
        except Exception:
            pass

    def _read_loop(self) -> None:
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
                # Async state events
                if s.startswith('event::state::'):
                    state = s.split('::', 2)[2]
                    self.last_state = state
                    print(f"[EVENT] state={state}")
                    # persist state for dashboard
                    try:
                        out_path = os.path.join(os.path.dirname(__file__), 'last_state.json')
                        with open(out_path, 'w') as f:
                            json.dump({'state': state, 'ts': time.time(), 'error': self.last_error}, f)
                    except Exception:
                        pass
                    continue
                # Async error events
                if s.startswith('event::error::'):
                    code = s.split('::', 2)[2]
                    self.last_error = code
                    print(f"[EVENT] error={code}")
                    # persist error for dashboard
                    try:
                        out_path = os.path.join(os.path.dirname(__file__), 'last_state.json')
                        with open(out_path, 'w') as f:
                            json.dump({'state': self.last_state, 'ts': time.time(), 'error': code}, f)
                    except Exception:
                        pass
                    continue
                # Acks: <cmd>::ack::<payload?>
                parts = s.split('::')
                if len(parts) >= 2 and parts[1] == 'ack':
                    cmd = parts[0]
                    payload = parts[2] if len(parts) > 2 else None
                    self._acks[cmd].put(payload)
                    continue
                # Unknown lines
                print(f"[SERIAL] {s}")
            except Exception as e:
                # do not crash on sporadic errors
                print(f"[SERIAL-ERR] {e}")
                time.sleep(0.05)

    def send(self, command: str, value) -> Optional[str]:
        if command not in commands:
            raise ValueError(f"Invalid command '{command}'")
        proto_cmd = commands[command]
        line = f"{proto_cmd}::{value}\n"
        with self._lock:
            self.ser.write(line.encode('utf-8'))
        try:
            payload = self._acks[proto_cmd].get(timeout=2.0)
            return payload
        except queue.Empty:
            print(f"[WARN] Ack timeout for {proto_cmd}")
            return None

    # Convenience methods
    def ping(self) -> bool:
        p = self.send('ping', 'x')
        return p == 'pong'

    def get_state(self) -> Optional[str]:
        return self.send('gState', 'x')

    def start(self, type_value: int | str) -> bool:
        return self.send('start', type_value) == 'OK'

    def move_tray(self, type_value: int | str) -> bool:
        return self.send('mTray', type_value) == 'OK'

    def move_bottle(self, pos: int) -> Optional[str]:
        return self.send('mPosBottle', pos)

    # Diagnostics: tray
    def diag_tray(self) -> Optional[Dict[str, Any]]:
        payload = self.send('gDiagTray', 'x')
        if not payload:
            return None
        out: Dict[str, Any] = {}
        try:
            parts = [p.strip() for p in payload.split(',') if p.strip()]
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    k = k.strip(); v = v.strip()
                    if k in ('pos', 'target', 'dtg', 'speed'):
                        try:
                            out[k] = int(v)
                        except Exception:
                            out[k] = v
                    elif k == 'state':
                        out[k] = v
            return out
        except Exception:
            return {'raw': payload}

    # Diagnostics: bottle
    def diag_bottle(self) -> Optional[int]:
        payload = self.send('gDiagBottle', 'x')
        if not payload:
            return None
        try:
            if payload.startswith('state='):
                return int(payload.split('=', 1)[1].strip())
            return int(payload)
        except Exception:
            return None

    # Settings
    def set_tray_pos(self, type_value: int | str, steps: int) -> Optional[bool]:
        ack = self.send('setTrayPos', f"{type_value}={int(steps)}")
        return True if ack == 'OK' else (False if ack else None)

    def set_bottle_speed(self, ms: int) -> Optional[bool]:
        ack = self.send('setBottleSpeed', int(ms))
        return True if ack == 'OK' else (False if ack else None)

    # Settings and queries added
    def get_tray_enabled(self) -> Optional[bool]:
        val = self.send('gTrayEnabled', 'x')
        if val is None:
            return None
        try:
            return bool(int(val))
        except Exception:
            return None

    def set_tray_enabled(self, enabled: bool) -> Optional[bool]:
        v = '1' if enabled else '0'
        ack = self.send('setTrayEnabled', v)
        return True if ack == 'OK' else (False if ack else None)

    def recover(self) -> Optional[bool]:
        ack = self.send('recover', 'x')
        return True if ack == 'OK' else (False if ack else None)

    def get_last_error(self) -> Optional[str]:
        return self.send('gLastError', 'x')

    def get_bottle_angle(self) -> Optional[int]:
        val = self.send('gBottleAngle', 'x')
        try:
            return int(val) if val is not None else None
        except Exception:
            return None

    def set_bottle_angle(self, deg: int) -> Optional[int]:
        val = self.send('mBottleAngle', int(deg))
        try:
            return int(val) if val is not None else None
        except Exception:
            return None

# Type mapping helpers
TYPE_NAME_BY_ID = {0: 'PLASTIC', 1: 'GLAS', 2: 'CAN'}
ID_BY_NAME = {
    'plastic': 0, 'plastik': 0,
    'glas': 1, 'glass': 1,
    'can': 2, 'dose': 2,
}

def normalize_type(value) -> Optional[int]:
    try:
        iv = int(value)
        if iv in (0, 1, 2):
            return iv
    except Exception:
        pass
    if isinstance(value, str):
        return ID_BY_NAME.get(value.strip().lower())
    return None

# Automatic cycle helpers

def wait_for_idle(arduino: Arduino, timeout_s: float = 5.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = arduino.last_state or arduino.get_state()
        if st == 'IDLE':
            return True
        time.sleep(0.2)
    return False


def run_automatic_cycle(arduino: Arduino, type_id: int, timeout_s: float = 30.0) -> bool:
    if not wait_for_idle(arduino, timeout_s=5.0):
        print('[AUTO] Not IDLE, aborting start')
        return False
    if not arduino.start(type_id):
        print('[AUTO] start::<type> was not acknowledged')
        return False
    print(f"[AUTO] started, type {type_id}={TYPE_NAME_BY_ID.get(type_id)}")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if arduino.last_state == 'IDLE':
            print('[AUTO] cycle completed (event)')
            return True
        st = arduino.get_state()
        if st == 'IDLE':
            print('[AUTO] cycle completed (poll)')
            return True
        time.sleep(0.3)
    print('[AUTO] timeout while waiting for IDLE')
    return False


class Trashcan:
    def __int__(self):
        pass

    def recvDetection(self, material_type):
        print("Received detection", material_type)

    def sendHome(self):
        print("Sending home")
        # TODO: implement Arduino interaction here if needed


def signal_handler(sig, frame):
    print('Interrupted')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


# --- HTTP API for dashboard ---

def start_api_server(arduino_inst: Optional[Arduino]):
    app = FastAPI(title="Trashcan Daemon API")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/state")
    def api_state():
        path = os.path.join(os.path.dirname(__file__), 'last_state.json')
        if os.path.exists(path):
            with open(path, 'r') as f:
                return JSONResponse(content=json.load(f))
        return JSONResponse(content={"state": None, "error": None, "ts": None})

    @app.get("/api/result")
    def api_result():
        path = os.path.join(os.path.dirname(__file__), 'last_result.json')
        if os.path.exists(path):
            with open(path, 'r') as f:
                return JSONResponse(content=json.load(f))
        return JSONResponse(content={})

    @app.get("/api/segment/wave")
    def api_wave():
        fp = os.path.join(os.path.dirname(__file__), 'last_segment.png')
        if not os.path.exists(fp):
            raise HTTPException(status_code=404, detail="wave not found")
        return FileResponse(fp, media_type='image/png')

    @app.get("/api/segment/spec")
    def api_spec():
        fp = os.path.join(os.path.dirname(__file__), 'last_segment_spectrogram.png')
        if not os.path.exists(fp):
            raise HTTPException(status_code=404, detail="spec not found")
        return FileResponse(fp, media_type='image/png')

    @app.get("/api/segment/audio")
    def api_audio():
        fp = os.path.join(os.path.dirname(__file__), 'last_segment.wav')
        if not os.path.exists(fp):
            raise HTTPException(status_code=404, detail="audio not found")
        return FileResponse(fp, media_type='audio/wav')

    # Control endpoints (non-blocking)
    @app.post("/api/control/start")
    def api_start(payload: dict):
        if not arduino_inst:
            raise HTTPException(status_code=503, detail="serial not connected")
        t = payload.get('type')
        if t is None:
            raise HTTPException(status_code=400, detail="missing type")
        ok = arduino_inst.start(t)
        return {"ack": ok}

    @app.post("/api/control/mtray")
    def api_mtray(payload: dict):
        if not arduino_inst:
            raise HTTPException(status_code=503, detail="serial not connected")
        t = payload.get('type')
        if t is None:
            raise HTTPException(status_code=400, detail="missing type")
        ok = arduino_inst.move_tray(t)
        return {"ack": ok}

    @app.post("/api/control/mbottle")
    def api_mbottle(payload: dict):
        if not arduino_inst:
            raise HTTPException(status_code=503, detail="serial not connected")
        mode = payload.get('mode')
        if mode is None:
            raise HTTPException(status_code=400, detail="missing mode")
        val = arduino_inst.move_bottle(int(mode))
        return {"ack": True if val is not None else False, "state": val}

    @app.post("/api/control/estop")
    def api_estop():
        if not arduino_inst:
            raise HTTPException(status_code=503, detail="serial not connected")
        ok = (arduino_inst.send('estop', 'x') == 'OK')
        return {"ack": ok}

    @app.post("/api/control/recover")
    def api_recover():
        if not arduino_inst:
            raise HTTPException(status_code=503, detail="serial not connected")
        ok = arduino_inst.recover()
        return {"ack": ok}

    host = os.environ.get('DASH_HOST', '127.0.0.1')
    port = int(os.environ.get('DASH_PORT', '8008'))

    def _run():
        uvicorn.run(app, host=host, port=port, log_level="warning")

    threading.Thread(target=_run, name='api-server', daemon=True).start()


def main(model: str, selected_device_id: Optional[int] = None):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    # Open serial (9600 baud). Port via .env
    serial_port = os.environ.get('TRASHCAN_SERIAL_PORT')
    if not serial_port:
        for p in ('/dev/ttyACM0', '/dev/ttyUSB0', '/dev/cu.usbserial-21230'):
            if os.path.exists(p):
                serial_port = p
                break
    arduino: Optional[Arduino] = None
    if serial_port:
        try:
            arduino = Arduino(serial_port, baud=9600, timeout=1.0)
            print(f"[SERIAL] connected: {serial_port}")
            if not arduino.ping():
                print('[SERIAL] ping failed (continuing)')
            # start HTTP API server for dashboard
            start_api_server(arduino)
            # Apply tray enabled setting if provided
            tray_enabled_env = os.environ.get('TRAY_ENABLED')
            if tray_enabled_env is not None and tray_enabled_env != '':
                te = tray_enabled_env.strip().lower() in ('1', 'true', 'on', 'yes')
                ok = arduino.set_tray_enabled(te)
                print(f"[CFG] setTrayEnabled={te} -> {ok}")
            # Optional diagnostic thread
            diag_enabled = os.environ.get('DIAG_ENABLED', '0') == '1'
            if diag_enabled:
                diag_interval = float(os.environ.get('DIAG_INTERVAL_S', '10'))
                def _diag_loop():
                    while True:
                        try:
                            t = arduino.diag_tray()
                            b = arduino.diag_bottle()
                            if t is not None:
                                print(f"[DIAG] Tray pos={t.get('pos')} tgt={t.get('target')} dtg={t.get('dtg')} spd={t.get('speed')} state={t.get('state')}")
                            if b is not None:
                                print(f"[DIAG] Bottle state={b}")
                        except Exception as e:
                            print(f"[DIAG] error: {e}")
                        time.sleep(diag_interval)
                threading.Thread(target=_diag_loop, name='diag-thread', daemon=True).start()

            # Optional startup configuration from .env
            def _env_int(name: str) -> Optional[int]:
                v = os.environ.get(name)
                if not v:
                    return None
                try:
                    return int(v)
                except Exception:
                    return None
            spd = _env_int('BOTTLE_SPEED_MS')
            if spd is not None:
                ok = arduino.set_bottle_speed(spd)
                print(f"[CFG] setBottleSpeed={spd} -> {ok}")
            for key, tid in ((
                ('TRAY_POS_0', 0), ('TRAY_POS_1', 1), ('TRAY_POS_2', 2),
                ('TRAY_POS_PLASTIC', 0), ('TRAY_POS_GLAS', 1), ('TRAY_POS_CAN', 2)
            )):
                steps = _env_int(key)
                if steps is not None:
                    ok = arduino.set_tray_pos(tid, steps)
                    print(f"[CFG] setTrayPos type={tid} steps={steps} -> {ok}")
        except Exception as e:
            print(f"[SERIAL] connection failed: {e}")
            arduino = None
    else:
        print('[SERIAL] no port found – set TRASHCAN_SERIAL_PORT in .env')

    with AudioImpulseRunner(str(modelfile)) as runner:
        model_info = runner.init()
        labels = model_info['model_parameters']['labels']
        print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')

        # Pull frequency from the model
        sample_rate = model_info['model_parameters'].get('frequency', 16000)
        buffer_duration = 1.0  # seconds
        buffer_size = int(sample_rate * buffer_duration)
        audio_buffer = deque(maxlen=buffer_size)

        # Configurable trigger params
        threshold = int(os.environ.get('AUDIO_RMS_THRESHOLD', '1200'))  # int16 RMS
        pre_ms = float(os.environ.get('PRE_MS', '200'))
        post_ms = float(os.environ.get('POST_MS', '800'))
        cooldown_s = float(os.environ.get('TRIGGER_COOLDOWN_S', '0.3'))
        visualize = os.environ.get('VISUALIZE', '1') == '1'

        triggered = False
        post_trigger_samples = int(sample_rate * (post_ms / 1000.0))
        pre_trigger_samples = int(sample_rate * (pre_ms / 1000.0))
        post_trigger_count = 0
        last_trigger_ts = 0.0

        # Audio callback and queue
        q = queue.Queue(maxsize=50)
        def audio_callback(indata, frames, time_info, status):
            if status:
                print(str(status), file=sys.stderr)
            data = indata[:, 0].copy() if indata.ndim == 2 else indata.copy()
            q.put(data)

        blocksize = max(128, int(sample_rate * 0.02))  # ~20 ms

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=blocksize, callback=audio_callback, device=selected_device_id):
            while True:
                block = q.get()
                audio_np = np.asarray(block, dtype=np.int16)

                # Fill ring buffer
                audio_buffer.extend(audio_np.tolist())

                # Compute RMS in float32 to avoid overflow
                rms = float(np.sqrt(np.mean(np.square(audio_np.astype(np.float32))))) if audio_np.size > 0 else 0.0

                now = time.time()
                if not triggered and (now - last_trigger_ts) >= cooldown_s and rms > threshold and len(audio_buffer) >= pre_trigger_samples:
                    triggered = True
                    post_trigger_count = 0
                    last_trigger_ts = now
                    print(f"[AUDIO] trigger RMS={rms:.1f}")

                if triggered:
                    # collect post window (800 ms default)
                    post_trigger_count += audio_np.size
                    if post_trigger_count >= post_trigger_samples:
                        # Build 1s snapshot from ring buffer (>=200 ms pre + 800 ms post)
                        segment = list(audio_buffer)
                        if len(segment) < buffer_size:
                            segment = ([0] * (buffer_size - len(segment))) + segment
                        elif len(segment) > buffer_size:
                            segment = segment[-buffer_size:]
                        segment = np.asarray(segment, dtype=np.int16)
                        print("[AUDIO] classifying segment len=", len(segment))

                        # Classify once
                        result = runner.classify(segment)
                        print("[CLASSIFY] result:", result)

                        # shit best label
                        scores = result.get('result', {}).get('classification', {})
                        top_label = max(scores, key=scores.get) if scores else None
                        top_score = scores.get(top_label, 0.0) if top_label else 0.0
                        print(f"[CLASSIFY] top={top_label} score={top_score:.2f}")

                        # Map to type
                        type_id = None
                        if top_label and top_score >= 0.7:
                            type_id = normalize_type(top_label)
                        if type_id is None and top_label:
                            lbl = top_label.lower()
                            if 'plast' in lbl:
                                type_id = 0
                            elif 'glas' in lbl or 'glass' in lbl:
                                type_id = 1
                            elif 'can' in lbl or 'dose' in lbl or 'metal' in lbl:
                                type_id = 2

                        if type_id is not None:
                            print(f"[CLASSIFY] mapped type: {TYPE_NAME_BY_ID.get(type_id)}")
                            if arduino is not None:
                                run_automatic_cycle(arduino, type_id, timeout_s=45.0)
                            else:
                                print('[SERIAL] no connection – skipping automatic cycle')
                        else:
                            print('[CLASSIFY] no confident type detected; skipping')

                        # Reset trigger and buffer
                        triggered = False
                        post_trigger_count = 0
                        audio_buffer.clear()

                        # Persist classification summary for dashboard
                        try:
                            out_path = os.path.join(os.path.dirname(__file__), 'last_result.json')
                            payload = {
                                'scores': scores,
                                'top_label': top_label,
                                'top_score': top_score,
                                'type_id': type_id,
                                'type_name': TYPE_NAME_BY_ID.get(type_id) if type_id is not None else None,
                                'ts': time.time()
                            }
                            with open(out_path, 'w') as f:
                                json.dump(payload, f)
                        except Exception:
                            pass

                        # Optional visualization/export
                        if visualize:
                            try:
                                import matplotlib.pyplot as plt
                                from scipy.io.wavfile import write as wavwrite
                                base = os.path.dirname(__file__)
                                plt.figure(figsize=(10, 3))
                                plt.plot(segment, linewidth=0.8)
                                plt.title("Audio segment for classification")
                                plt.xlabel("Sample")
                                plt.ylabel("Amplitude")
                                plt.tight_layout(); plt.savefig(os.path.join(base, "last_segment.png")); plt.close()
                                plt.figure(figsize=(10, 4))
                                plt.specgram(segment, Fs=sample_rate, NFFT=512, noverlap=256, cmap='magma')
                                plt.title("Spectrogram of audio segment")
                                plt.xlabel("Time [s]"); plt.ylabel("Freq [Hz]")
                                plt.colorbar(label='dB')
                                plt.tight_layout(); plt.savefig(os.path.join(base, "last_segment_spectrogram.png")); plt.close()
                                wavwrite(os.path.join(base, "last_segment.wav"), sample_rate, segment)
                            except Exception as e:
                                print(f"[VIS] error: {e}")

if __name__ == '__main__':
    # Daemon mode: no CLI args, read config from .env
    load_dotenv(find_dotenv())
    model_path = os.environ.get('MODEL_EIM_PATH', 'model/modelmac.eim')
    dev_env = os.environ.get('AUDIO_DEVICE_ID')
    device_id = int(dev_env) if (dev_env and dev_env.isdigit()) else None
    main(model_path, device_id)
