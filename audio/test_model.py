import os
import librosa
import numpy as np
import pickle
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

# Config
VAL_DATA_DIR = "audio/data/val"
CLASSES = ["glass", "plastic"]
SAMPLE_RATE = 44100
POST_HIT_DURATION_SEC = 0.5
N_MFCC = 13
MAX_FRAMES = 50

# Load trained model and scaler
with open("audio/model/svm_model.pkl", "rb") as f:
    model = pickle.load(f)
with open("audio/model/scaler.pkl", "rb") as f:
    scaler = pickle.load(f)

def extract_post_hit(y, sr, duration_sec):
    energy = np.abs(y)
    peak_index = np.argmax(energy)
    end_index = min(len(y), peak_index + int(duration_sec * sr))
    return y[peak_index:end_index]

def extract_features(file_path):
    y, sr = librosa.load(file_path, sr=SAMPLE_RATE)
    y = extract_post_hit(y, sr, POST_HIT_DURATION_SEC)
    y = y / np.max(np.abs(y))  # Normalize

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    delta = librosa.feature.delta(mfcc)
    features = np.vstack([mfcc, delta])

    if features.shape[1] < MAX_FRAMES:
        pad_width = MAX_FRAMES - features.shape[1]
        features = np.pad(features, ((0, 0), (0, pad_width)), mode='constant')
    else:
        features = features[:, :MAX_FRAMES]

    return features.T.reshape(-1)  # Flatten to 1D

# Prepare validation data
X_val = []
y_val = []
label_map = {cls: i for i, cls in enumerate(CLASSES)}

for cls in CLASSES:
    folder = os.path.join(VAL_DATA_DIR, cls)
    for fname in os.listdir(folder):
        if not fname.endswith(".wav"):
            continue
        fpath = os.path.join(folder, fname)
        feats = extract_features(fpath)
        X_val.append(feats)
        y_val.append(label_map[cls])

X_val = np.array(X_val)
y_val = np.array(y_val)

# Scale and predict
X_val_scaled = scaler.transform(X_val)
y_pred = model.predict(X_val_scaled)

# Evaluate
acc = accuracy_score(y_val, y_pred)
print(f"Validation Accuracy: {acc*100:.2f}%")
print("Confusion Matrix:\n", confusion_matrix(y_val, y_pred))
print("Classification Report:\n", classification_report(y_val, y_pred, target_names=CLASSES))
