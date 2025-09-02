import os
import time
import serial
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

PORT = os.environ.get('TRASHCAN_SERIAL_PORT', '/dev/ttyACM0')
BAUD = 9600
TIMEOUT = 1.0

ser = serial.Serial(port=PORT, baudrate=BAUD, timeout=TIMEOUT)
print(f"Connected to {PORT} @ {BAUD} baud. Type commands like 'ping::x' or 'gState::x'. Ctrl+C to exit.")

def write_read(cmd: str):
    ser.write((cmd.strip() + "\n").encode('utf-8'))
    time.sleep(0.05)
    return ser.readline().decode('utf-8', errors='replace').strip()

try:
    while True:
        cmd = input(">> ")
        if not cmd:
            continue
        resp = write_read(cmd)
        print(resp)
except KeyboardInterrupt:
    print("Bye.")
finally:
    ser.close()
