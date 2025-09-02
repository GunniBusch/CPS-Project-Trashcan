import os
import sys
import signal
import time
from edge_impulse_linux.audio import AudioImpulseRunner
import numpy as np
from collections import deque
import matplotlib.pyplot as plt
import sounddevice as sd
import queue
from scipy.io.wavfile import write as wavwrite
import serial

runner = None




global commands


commands = {

    "GetBottleStatus": "gPosBottle",
    "MoveBottle": "mPosBottle",
    "MoveTray": "mTray",
}



class Arduino:
    # This will just be the interface to the arduino using serial basically it sends commands to the arduino in a format that is command::value, and the arduino will acknowledge the command by sending back command::ack::return_value
    def __init__(self, arduino: serial.Serial):
        self.arduino = arduino


    def send(self, command, value):
        if command not in commands:
            raise ValueError("Invalid command")
        cmd_str = commands[command] + "::" + str(value) + "\n"
        self.arduino.write(bytes(cmd_str, 'utf-8'))

        # the return value is that what the arudiono respons with form poll
        return self.poll()



    # we need to listen for responses from the arduino
    def poll(self):
        if self.arduino.in_waiting > 0:
            line = self.arduino.readline().decode('utf-8').rstrip()
            parts = line.split("::")
            if len(parts) < 2:
                print("Invalid response from arduino:", line)
                return None
            command = parts[0]
            if command not in commands.values():
                print("Unknown command from arduino:", command)
                return None
            if parts[1] != "ack":
                print("Invalid ack from arduino:", line)
                return None
            return command, parts[2] if len(parts) > 2 else None
        return None




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

def help():
    print('python classify.py <path_to_model.eim> <audio_device_ID, optional>' )

def main(model, selected_device_id=None):

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    ard = None #Arduino(serial.Serial(port='/dev/cu.usbserial-21230', baudrate=9600, timeout=.1))


    with AudioImpulseRunner(modelfile) as runner:
        model_info = runner.init()
        labels = model_info['model_parameters']['labels']
        print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')

        # Samplingrate aus Modell-Info
        sample_rate = model_info['model_parameters'].get('frequency', 16000)
        buffer_duration = 1.0 # Sekunden
        buffer_size = int(sample_rate * buffer_duration)
        audio_buffer = deque(maxlen=buffer_size)

        threshold = 1200  # RMS-Schwelle für int16, ggf. anpassen
        triggered = False
        post_trigger_samples = int(sample_rate * .800) # 55 ms
        pre_trigger_samples = int(sample_rate * 0.2)  # 5 ms
        post_trigger_count = 0
        cooldown_s = 0.3
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


                    ## AI PART

                    post_trigger_count += audio_np.size
                    if post_trigger_count >= post_trigger_samples:
                        # 1s Snapshot aus Ringpuffer (enthält ~5ms davor + 55ms danach)
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

                        # Visualisierung: Waveform
                        # plt.figure(figsize=(10, 3))
                        # plt.plot(segment, linewidth=0.8)
                        # plt.title("Audio-Segment zur Klassifizierung")
                        # plt.xlabel("Sample")
                        # plt.ylabel("Amplitude")
                        #
                        # ## the plots neet to be one above the other
                        # plt.tight_layout()
                        # # Visualisierung: Spektrogramm
                        #
                        # plt.specgram(segment, Fs=sample_rate, NFFT=512, noverlap=256, cmap='magma')
                        # plt.title("Spektrogramm des Audio-Segments")
                        # plt.xlabel("Zeit [s]")
                        # plt.ylabel("Frequenz [Hz]")
                        # plt.colorbar(label='dB')
                        #
                        # plt.savefig("last_segment_spectrogram.png")
                        #
                        # plt.show()
                        #
                        # # Export als WAV (16-bit PCM)
                        # wavwrite("last_segment.wav", sample_rate, segment)

                        # Reset
                        triggered = False
                        post_trigger_count = 0
                        audio_buffer.clear()

                        ## BOTTLE MOVE PART

                        detected_type = max(result['result']['classification'] , key=result['result']['classification'].get)

                        if result['result']['classification'][labels[0]] > 0.7 or result['result']['classification'][labels[2]] > 0.7 and not result['result']['classification'][labels[1]] > 0.7:
                            print("Detected type:", detected_type)

                            print(ard.send("MoveBottle", 1))

                            time.sleep(1)

                            print("move bottle to position 1")

                           # print(ard.send("MoveBottle", 2))



                        ## TRAY MOVE PART

if __name__ == '__main__':
    main("../model/modelmac.eim",2)