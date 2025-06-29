import os
import uuid
import numpy as np
import sounddevice as sd
import librosa
import pickle
from scipy.io.wavfile import write
from sklearn.preprocessing import StandardScaler

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

# Load model and scaler
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

# Utility: Extract just the loudest region
def extract_post_hit(y, sr, duration_sec=POST_HIT_DURATION_SEC):
    energy = np.abs(y)
    peak_index = np.argmax(energy)
    end_index = min(len(y), peak_index + int(duration_sec * sr))
    return y[peak_index:end_index]

# Utility: Convert audio to feature vector
def extract_features(y, sr):
    y = y / np.max(np.abs(y))  # normalize
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    delta = librosa.feature.delta(mfcc)
    features = np.vstack([mfcc, delta])

    # Pad or truncate to consistent frame length
    if features.shape[1] < MAX_FRAMES:
        pad_width = MAX_FRAMES - features.shape[1]
        features = np.pad(features, ((0, 0), (0, pad_width)), mode='constant')
    else:
        features = features[:, :MAX_FRAMES]

    return features.T.reshape(-1)  # Flatten to 1D

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