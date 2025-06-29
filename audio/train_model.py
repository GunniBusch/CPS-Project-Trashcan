import os
import numpy as np
import librosa
import pickle
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.model_selection import cross_val_score
from tqdm import tqdm
from extract_features import extract_features
from preprocess_data import extract_post_hit

# --------- Configuration ---------
DATA_PATH = "audio/data/train"
MODEL_DIR = "audio/model"
SAMPLE_RATE = 44100
CLASSES = ["glass", "plastic"]
MAX_FRAMES = 50


# --------- Load Data and Extract Features ---------
X = []
y = []

print("Extracting features from training data...")
for label_idx, label in enumerate(CLASSES):
    folder = os.path.join(DATA_PATH, label)
    for fname in tqdm(sorted(os.listdir(folder))):
        if not fname.endswith(".wav"):
            continue
        filepath = os.path.join(folder, fname)
        y_audio, _ = librosa.load(filepath, sr=SAMPLE_RATE)
        y_audio = extract_post_hit(y_audio, SAMPLE_RATE)
        feat = extract_features(y_audio, SAMPLE_RATE)
        X.append(feat)
        y.append(label_idx)

X = np.array(X)
y = np.array(y)

# --------- Standardize ---------
print("Fitting StandardScaler...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# --------- Train SVM ---------
print("Training SVM...")
clf = SVC(kernel="rbf", C=10, gamma="scale", probability=False)
scores = cross_val_score(clf, X_scaled, y, cv=5)
print(f"Cross-validation accuracy: {scores.mean() * 100:.2f}%")

clf.fit(X_scaled, y)

# --------- Save model and scaler ---------
os.makedirs(MODEL_DIR, exist_ok=True)
with open(os.path.join(MODEL_DIR, "svm_model.pkl"), "wb") as f:
    pickle.dump(clf, f)
with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
    pickle.dump(scaler, f)

print("Model and scaler saved to 'audio/model/' directory.")
