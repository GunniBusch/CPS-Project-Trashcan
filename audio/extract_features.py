import os
import numpy as np
import librosa
from tqdm import tqdm
import pickle

# Paths
PROCESSED_DATA_DIR = "audio/data/processed"
FEATURES_OUT_PATH = "audio/data/features.pkl"
CLASSES = ["glass", "plastic"]

# Feature extraction settings
SAMPLE_RATE = 44100
N_MFCC = 13  # Standard choice
MAX_FRAMES = 50  # Pad/truncate to fixed number of frames

def extract_features(file_path):
    y, sr = librosa.load(file_path, sr=SAMPLE_RATE)
    
    # MFCC and delta
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    delta = librosa.feature.delta(mfcc)
    
    # Stack: [13 MFCCs + 13 delta] x time
    features = np.vstack([mfcc, delta])

    # Pad or truncate to fixed number of frames (time steps)
    if features.shape[1] < MAX_FRAMES:
        pad_width = MAX_FRAMES - features.shape[1]
        features = np.pad(features, ((0, 0), (0, pad_width)), mode='constant')
    else:
        features = features[:, :MAX_FRAMES]

    return features.T  # Shape: (time_steps, feature_dim)

def build_feature_dataset():
    X = []
    y = []

    label_map = {cls: idx for idx, cls in enumerate(CLASSES)}

    for cls in CLASSES:
        class_dir = os.path.join(PROCESSED_DATA_DIR, cls)
        for fname in tqdm(os.listdir(class_dir), desc=f"Extracting {cls}"):
            if fname.endswith(".wav"):
                file_path = os.path.join(class_dir, fname)
                feat = extract_features(file_path)
                X.append(feat)
                y.append(label_map[cls])

    return np.array(X), np.array(y)

if __name__ == "__main__":
    X, y = build_feature_dataset()
    
    # Save features
    with open(FEATURES_OUT_PATH, "wb") as f:
        pickle.dump((X, y), f)

    print("Feature extraction complete.")
    print(f"Feature shape: {X.shape} | Labels shape: {y.shape}")
