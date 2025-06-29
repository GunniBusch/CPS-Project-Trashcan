import os
import numpy as np
import librosa
import pickle
from sklearn.metrics import classification_report, accuracy_score
from tqdm import tqdm
from extract_features import extract_features
from preprocess_data import extract_post_hit

# --------- Config ---------
VAL_PATH = "audio/data/val"
MODEL_PATH = "audio/model/svm_model.pkl"
SCALER_PATH = "audio/model/scaler.pkl"
CLASSES = ["glass", "plastic"]
SAMPLE_RATE = 44100
MAX_FRAMES = 50
POST_HIT_DURATION_SEC = 0.5

# --------- Load Model & Scaler ---------
with open(MODEL_PATH, "rb") as f:
    clf = pickle.load(f)
with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

# --------- Validate ---------
X_val = []
y_val = []

print("Extracting features from validation data...")
for label_idx, label in enumerate(CLASSES):
    folder = os.path.join(VAL_PATH, label)
    for fname in tqdm(sorted(os.listdir(folder))):
        if not fname.endswith(".wav"):
            continue
        filepath = os.path.join(folder, fname)
        y_audio, _ = librosa.load(filepath, sr=SAMPLE_RATE)
        y_audio = extract_post_hit(y_audio, SAMPLE_RATE)
        feat = extract_features(y_audio, SAMPLE_RATE)
        X_val.append(feat)
        y_val.append(label_idx)

X_val = np.array(X_val)
y_val = np.array(y_val)

# --------- Predict & Evaluate ---------
X_scaled = scaler.transform(X_val)
y_pred = clf.predict(X_scaled)

print("\nClassification Report:")
print(classification_report(y_val, y_pred, target_names=CLASSES))

acc = accuracy_score(y_val, y_pred)
print(f"Validation Accuracy: {acc * 100:.2f}%")
