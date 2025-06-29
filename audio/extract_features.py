import numpy as np
import librosa

def extract_features(y, sr, n_mfcc=8):
    """
    Extracts relevant features to distinguish between glass and plastic:
    - MFCCs (reduced to n_mfcc)
    - Spectral Centroid
    - Spectral Bandwidth
    - Zero-Crossing Rate
    - RMS Energy
    - Decay Rate
    """  

    # Normalize audio
    y = y / np.max(np.abs(y))

    # Frame-level features (mean and std for each)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)
    rms = librosa.feature.rms(y=y)

    # Decay rate: slope of energy envelope
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    decay_rate = 0.0
    if len(onset_env) > 1:
        decay_rate = np.polyfit(np.arange(len(onset_env)), onset_env, 1)[0]

    # Aggregate features (mean/std)
    features = np.concatenate([
        mfcc_mean,
        mfcc_std,
        [np.mean(centroid), np.std(centroid)],
        [np.mean(bandwidth), np.std(bandwidth)],
        [np.mean(zcr), np.std(zcr)],
        [np.mean(rms), np.std(rms)],
        [decay_rate]
    ])

    return features