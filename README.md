# CPS Project Trashcan – Audio Trigger, Classification and Serial Control

This service continuously listens to audio, captures a 1-second window (200 ms before, 800 ms after) when a sound threshold is exceeded, classifies it with an Edge Impulse model, and drives the mechanical trashcan over a simple serial protocol with state events.

## Highlights
- Event-triggered audio capture with a 1 s snapshot (200 ms pre + 800 ms post)
- Edge Impulse inference (model .eim) on captured audio (16 kHz, 1 s, int16)
- Serial API integration with state events and start cycle
- Diagnostics and runtime settings via new serial commands
- Config from .env, no CLI required
- Optional waveform/spectrogram/WAV export for debugging
- systemd unit provided for auto-start on boot

## Requirements
- Python 3.10+
- Linux/Raspberry Pi OS or macOS
- A working microphone input and PortAudio (sounddevice)
- Edge Impulse .eim model (placed under model/)

Install dependencies:
```bash
cd CPS-Project-Trashcan
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Note for macOS: Grant microphone access to Terminal/Python (System Settings → Privacy & Security → Microphone).

## Configure .env
A template .env is included. Adjust at least the serial port and model path.

Keys (defaults in parentheses):
- TRASHCAN_SERIAL_PORT=/dev/ttyACM0 (or /dev/ttyUSB0, /dev/cu.usbserial-XXXX)
- MODEL_EIM_PATH=model/modelmac.eim
- AUDIO_DEVICE_ID= (empty = auto)
- AUDIO_RMS_THRESHOLD=1200 (int16 RMS threshold)
- PRE_MS=200, POST_MS=800 (must sum to 1000 ms)
- TRIGGER_COOLDOWN_S=0.3
- VISUALIZE=0 (1 = save last_segment.png/.wav and spectrogram)
- DIAG_ENABLED=0, DIAG_INTERVAL_S=10 (periodic serial diagnostics)
- BOTTLE_SPEED_MS= (servo step duration in ms)
- TRAY_POS_0/1/2= (steps per type) or TRAY_POS_PLASTIC/GLAS/CAN=

Example:
```dotenv
TRASHCAN_SERIAL_PORT=/dev/ttyACM0
MODEL_EIM_PATH=model/modelmac.eim
AUDIO_RMS_THRESHOLD=1200
PRE_MS=200
POST_MS=800
TRIGGER_COOLDOWN_S=0.3
VISUALIZE=0
DIAG_ENABLED=1
DIAG_INTERVAL_S=10
```

## Run as a daemon (systemd)
A service unit is provided at deploy/trashcan.service. Edit the file to match your paths and user, then:
```bash
sudo cp deploy/trashcan.service /etc/systemd/system/trashcan.service
sudo systemctl daemon-reload
sudo systemctl enable --now trashcan.service
journalctl -u trashcan.service -f
```
Stop/Start:
```bash
sudo systemctl stop trashcan.service
sudo systemctl start trashcan.service
```

## Manual run (development)
```bash
source .venv/bin/activate
python edgeimpulse/main.py
```
- Reads .env automatically.
- Logs triggers, classification (top label/score), serial events.

## How it works
- Audio stream (sounddevice, mono int16, 16 kHz) feeds a 1 s ring buffer.
- When the RMS threshold is crossed, the service waits until 800 ms of future audio have been recorded.
- A 1 s segment is built from the ring buffer (contains ≥200 ms pre + 800 ms post) and sent to the Edge Impulse runner.
- If a confident label is found (score ≥ 0.7), the type is mapped to PLASTIC/GLAS/CAN and an automatic start::<type> cycle is initiated over serial.

Type mapping:
- 0=PLASTIC, 1=GLAS, 2=CAN
- Strings are recognized: plastic/plastik → 0, glas/glass → 1, can/dose → 2

Event/state flow (automatic):
- Wait until gState::ack::IDLE
- Send start::<type>
- Process asynchronous events:
  - event::state::CONTAINS_BOTTLE
  - event::state::WAITING_FOR_TRAY
  - event::state::TRAY_IN_POSITION
  - event::state::MOVING_BOTTLE_TO_TRAY
  - event::state::BOTTLE_IN_TRAY
  - event::state::MOVING_TO_IDLE
  - event::state::IDLE (cycle done)

## State diagram
The following Mermaid diagram summarizes the automatic state progression and the serial events involved.

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> CONTAINS_BOTTLE: start::<type>\n(event::state::CONTAINS_BOTTLE)
    CONTAINS_BOTTLE --> WAITING_FOR_TRAY: event::state::WAITING_FOR_TRAY
    WAITING_FOR_TRAY --> TRAY_IN_POSITION: event::state::TRAY_IN_POSITION
    TRAY_IN_POSITION --> MOVING_BOTTLE_TO_TRAY: event::state::MOVING_BOTTLE_TO_TRAY
    MOVING_BOTTLE_TO_TRAY --> BOTTLE_IN_TRAY: event::state::BOTTLE_IN_TRAY
    BOTTLE_IN_TRAY --> MOVING_TO_IDLE: event::state::MOVING_TO_IDLE
    MOVING_TO_IDLE --> IDLE: event::state::IDLE
```

## Serial API reference
Commands are sent as a single line: `name::value\n`. Acks are returned as `<cmd>::ack::<payload?>`. Asynchronous state events can arrive at any time: `event::state::<STATE>`.

Core commands:
- start::<type>
  - type: 0|1|2 or plastic|glas|can
  - Ack: start::ack::OK or error (ERR_BAD_TYPE, ERR_BUSY)
- mTray::<type>
  - Manually set target tray and trigger CONTAINS_BOTTLE
  - Ack: mTray::ack::OK or ERR_BAD_TYPE
- mPosBottle::<1|2>
  - 1: moveDrop(), 2: moveInit()
  - Ack: mPosBottle::ack::<BottleStateNumber>
- gPosBottle::<any>
  - Ack: gPosBottle::ack::<stateNumber>
- gLimitTray::<any>
  - Ack: gLimitTray::ack::PRESSED|RELEASED
- gState::<any>
  - Ack: gState::ack::<STATE_NAME>
- gType::<any>
  - Ack: gType::ack::<PLASTIC|GLAS|CAN>
- estop::<any>
  - Sets error state (EMO_MOOD)
  - Ack: estop::ack::OK
- ping::<any>
  - Ack: ping::ack::pong

Diagnostics and settings:
- gDiagTray::<any>
  - Ack: gDiagTray::ack::pos=<cur>,target=<tgt>,dtg=<dist>,speed=<spd>,state=<trayState>
- gDiagBottle::<any>
  - Ack: gDiagBottle::ack::state=<BottleStateNum>
- setTrayPos::<type>=<steps>
  - Persist target steps per type in RAM
  - Ack: setTrayPos::ack::OK | ERR_BAD_ARG | ERR_BAD_TYPE | ERR_FAIL
- setBottleSpeed::<ms>
  - Set servo step duration (bigger = slower)
  - Ack: setBottleSpeed::ack::OK

The daemon exposes convenience methods and an optional background diagnostic loop controlled by `.env`:
- DIAG_ENABLED=1 enables periodic logs every DIAG_INTERVAL_S seconds.
- At startup, BOTTLE_SPEED_MS and TRAY_POS_* values are applied once if set.

## Tuning
- AUDIO_RMS_THRESHOLD: raise to avoid false triggers, lower to be more sensitive.
- AUDIO_DEVICE_ID: set to a specific input device if the default is wrong.
- PRE_MS/POST_MS: keep sum ≈ 1000 ms; change only if your model differs.
- TRIGGER_COOLDOWN_S: avoid repeated triggers from the same sound.
- Confidence threshold (currently 0.7): adjust if your model requires it.

## Troubleshooting
- Serial
  - Verify TRASHCAN_SERIAL_PORT and user permissions (dialout/uucp group on Linux, `ls -l /dev/tty*`).
  - The firmware must use the same baud rate as the daemon (default 9600).
- Audio
  - No triggers? Increase sensitivity (lower threshold) or verify microphone access.
  - On macOS, allow microphone usage for the terminal/Python process.
- Model
  - MODEL_EIM_PATH must point to a valid .eim, typically 16 kHz, 1 s input.
- Service
  - Adjust paths in deploy/trashcan.service (WorkingDirectory, EnvironmentFile, ExecStart). Check logs with `journalctl -u trashcan.service -f`.

## Project structure (excerpt)
- edgeimpulse/main.py – daemon: audio trigger, classification, serial control, diagnostics
- deploy/trashcan.service – systemd service unit
- .env – configuration
- model/ – Edge Impulse models (.eim)
- arduino/ – firmware/protocol (reference)

## License
Internal project. Please clarify license before public release.

<details>
  <summary>🪙 Easter egg</summary>

  When in doubt, just ping it.

  ```text
  $ echo "ping::<anything>" > /dev/serial
  ping::ack::pong
  ```

  Also, some ASCII trash… can!

  ```
      _______
     / _____ \
    / /     \ \
   | |  ___  | |
   | | (___) | |
    \ \_____/ /
     \_______/
       (♻)
  ```

  Reduce, Reuse, Recycle — and sometimes, Re-route to the right tray.
</details>

<!-- If you found this, the secret state is 42::LIFE_UNIVERSE_EVERYTHING -->
