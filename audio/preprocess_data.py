import os
import librosa
import numpy as np
import soundfile as sf
from tqdm import tqdm

# Config
RAW_DATA_DIR = "audio/data/train"
PROCESSED_DATA_DIR = "audio/data/processed"
CLASSES = ["glass", "plastic"]
SAMPLE_RATE = 44100
POST_HIT_DURATION_SEC = 0.5  # How long after the hit to extract

def extract_post_hit(y, sr, duration_sec):
    """Extracts audio starting from the loudest point (hit) onward."""
    energy = np.abs(y)
    peak_index = np.argmax(energy)
    end_index = min(len(y), peak_index + int(duration_sec * sr))
    return y[peak_index:end_index]

def process_and_save_audio():
    for label in CLASSES:
        input_dir = os.path.join(RAW_DATA_DIR, label)
        output_dir = os.path.join(PROCESSED_DATA_DIR, label)
        os.makedirs(output_dir, exist_ok=True)

        for filename in tqdm(os.listdir(input_dir), desc=f"Processing {label}"):
            if not filename.endswith(".wav"):
                continue

            file_path = os.path.join(input_dir, filename)
            y, sr = librosa.load(file_path, sr=SAMPLE_RATE, mono=True)

            y_post_hit = extract_post_hit(y, sr, POST_HIT_DURATION_SEC)

            # Optional normalization
            y_post_hit = y_post_hit / np.max(np.abs(y_post_hit))

            out_path = os.path.join(output_dir, filename)
            sf.write(out_path, y_post_hit, sr)

if __name__ == "__main__":
    process_and_save_audio()
