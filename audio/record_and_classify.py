import os
import uuid
import sounddevice as sd
import pickle
from scipy.io.wavfile import write
from audio.extract_features import extract_features
from audio.preprocess_data import extract_post_hit
from material import Material

# Paths to model and scaler
MODEL_PATH = "audio/model/svm_model.pkl"
SCALER_PATH = "audio/model/scaler.pkl"

# Audio settings
DURATION = 5  # seconds
SAMPLE_RATE = 44100
CHANNELS = 1
N_MFCC = 13
MAX_FRAMES = 50
POST_HIT_DURATION_SEC = 0.5

# Output folders
SAVE_ROOT = "audio/data/test"
CLASSES = ["glass", "plastic"]  # must match model output indices

def record_and_classify() -> Material:
    # Load model and scaler
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    # 1. Record audio
    print("Start recording ...")
    recording = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32')
    sd.wait()
    print("Recording finished.")
    y = recording.flatten()

    # 2. Extract post-hit signal
    y_hit = extract_post_hit(y, SAMPLE_RATE)

    # 3. Feature extraction
    features = extract_features(y_hit, SAMPLE_RATE)
    features_scaled = scaler.transform([features])

    # 4. Classification
    prediction_index = model.predict(features_scaled)[0]
    predicted_label = CLASSES[prediction_index]
    print(f"\nPredicted class: **{predicted_label.upper()}**")

    # 5. Save to folder
    os.makedirs(os.path.join(SAVE_ROOT, predicted_label), exist_ok=True)
    filename = f"{uuid.uuid4().hex}.wav"
    save_path = os.path.join(SAVE_ROOT, predicted_label, filename)
    write(save_path, SAMPLE_RATE, (y_hit * 32767).astype("int16"))
    print(f"Audio saved to: {save_path}")

    return Material.GLASS if predicted_label.upper() == "GLASS" else Material.PLASTIC