# CPS Trashcan – Serielles Protokoll

Diese Datei beschreibt die serielle Schnittstelle zwischen Raspberry Pi und dem Arduino-Sketch in `arduino/platform-io`.

## Verbindung
- Baudrate: 9600
- Zeilentrenner: `\n` (LF)
- Befehlsschema: `name::wert`
- Antwortschema: `name::ack::rueckgabewert`
- Asynchrone Events:
  - `event::state::<STATE>` bei jedem Zustandswechsel
  - `event::error::<CODE>` bei Fehlern

## Typen und Mappings
- TrashType (Eingabe und Anzeige):
  - Zahlen: `0=PLASTIC`, `1=GLAS`, `2=CAN`
  - Strings: `plastic|plastik`, `glas|glass`, `can|dose`
- BottleState (Rückgabe als Zahl): `0=INIT_STATE`, `1=DROP_STATE`, `2=MOVING_STATE`, `3=UNKNOWN_STATE`
- Tray-Limit-Schalter (Pin 12, Pullup): `PRESSED` (LOW) / `RELEASED` (HIGH)

## Zustände (STATE)
- `LOADING`: Start/Kalibrierung des Tray
- `IDLE`: Bereit
- `CONTAINS_BOTTLE`: Vorbedingungen prüfen
- `WAITING_FOR_TRAY`: Tray fährt zur Zielposition
- `TRAY_IN_POSITION`: Ziel erreicht, Doppeltkontrolle
- `MOVING_BOTTLE_TO_TRAY`: Flasche/Schacht fährt über Loch
- `BOTTLE_IN_TRAY`: kurze Wartezeit zum Fallenlassen
- `MOVING_TO_IDLE`: Rückfahrt auf 90°
- `EMO_MOOD`: Fehlerzustand

## Fehlercodes (event::error::<CODE> und gLastError)
- `PRECONDITIONS_FAIL`: Vorbedingungen nicht erfüllt (Tray nicht READY, Bottle nicht INIT, Tray nicht geladen)
- `TRAY_TIMEOUT`: Tray hat das Ziel nicht rechtzeitig erreicht
- `TRAY_NOT_READY`: Tray meldet nach Ankunft nicht READY
- `BOTTLE_TIMEOUT`: Bewegung zum Loch zu lange
- `BOTTLE_HOME_TIMEOUT`: Rückfahrt auf Home (90°) zu lange
- `ESTOP`: Notstopp ausgelöst

## Winkel-Logik (Rohr/Bottle-Servo)
- `PLASTIC`/`CAN` -> Loch 1 bei `0°`
- `GLAS` -> Loch 2 bei `180°`
- Normalposition -> `90°`

## Kommandos

- ping::<any>
  - Antwort: `ping::ack::pong`
  - Zweck: Verbindungsprobe

- gState::<any>
  - Antwort: `gState::ack::<STATE>`
  - Liefert den aktuellen High‑Level‑State

- gType::<any>
  - Antwort: `gType::ack::<PLASTIC|GLAS|CAN>`
  - Aktueller Ziel‑TrashType

- gLimitTray::<any>
  - Antwort: `gLimitTray::ack::PRESSED|RELEASED`
  - Endschalterstatus Pin 12 (Pullup)

- gLastError::<any>
  - Antwort: `gLastError::ack::<CODE>`
  - Letzter Fehlergrund (siehe Fehlercodes)

- gDiagTray::<any>
  - Antwort: `gDiagTray::ack::pos=<cur>,target=<tgt>,dtg=<dist>,speed=<spd>,state=<TRAY_STATE>`
  - Diagnose des Trays (Stepper)

- gDiagBottle::<any>
  - Antwort: `gDiagBottle::ack::state=<BottleStateNum>`
  - Diagnose des Rohr‑Servos

- start::<type>
  - Antwort: `start::ack::OK` oder `ERR_BAD_TYPE` / `ERR_BUSY`
  - Startet den kompletten Zyklus: Tray fahren, Flasche über Loch bewegen, zurück zu IDLE
  - Events begleiten den Ablauf (state + evtl. error)

- mTray::<type>
  - Antwort: `mTray::ack::OK` oder `ERR_BAD_TYPE`
  - Setzt den Zieltyp und stößt den Ablauf an (wie `start`)

- gPosBottle::<any>
  - Antwort: `gPosBottle::ack::<BottleStateNum>`
  - Liefert den aktuellen BottleState

- mPosBottle::<1|2>
  - Antwort: `mPosBottle::ack::<BottleStateNum>`
  - 1: Move Drop (über Loch je nach Typ), 2: Move Init (zurück auf 90°)

- setTrayPos::<type>=<steps>
  - Antwort: `setTrayPos::ack::OK` oder `ERR_BAD_ARG` / `ERR_BAD_TYPE` / `ERR_FAIL`
  - Setzt Zielposition (Stepper‑Steps) für einen Typ

- setBottleSpeed::<ms>
  - Antwort: `setBottleSpeed::ack::OK`
  - Setzt die Verzögerung zwischen Servoschritten (größer = langsamer)

- recover::<any>
  - Antwort: `recover::ack::OK` oder `ERR_CAL`
  - Stoppt, kalibriert das Tray, fährt das Rohr auf 90° und setzt `IDLE`

- estop::<any>
  - Antwort: `estop::ack::OK`
  - Notstopp -> Fehlerzustand `EMO_MOOD`, `event::error::ESTOP`

## Typische Sequenz (Automatik)
1) `gState::x` abfragen, auf `IDLE` warten
2) `start::plastic` (oder `start::0`)
3) Events verfolgen: `event::state::...` bis wieder `IDLE`

## Hinweise
- Der Sketch liest serielle Befehle standardmäßig im Zustand `IDLE` (für Diagnose ggf. warten, bis `IDLE` erreicht ist). Events werden immer gesendet.
- Endschalter ist aktiv LOW (PRESSED). Nach Kalibrierung fährt der Tray leicht vom Schalter weg.