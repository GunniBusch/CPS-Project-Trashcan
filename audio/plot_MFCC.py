# %%

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

# Settings
SAMPLE_RATE = 44100
N_MFCC = 13
POST_HIT_DURATION_SEC = 0.5
MAX_FRAMES = 50

def extract_post_hit(y, sr, duration_sec):
    energy = np.abs(y)
    peak_index = np.argmax(energy)
    end_index = min(len(y), peak_index + int(duration_sec * sr))
    return y[peak_index:end_index]

def plot_mfcc(file_path, title=None):
    y, sr = librosa.load(file_path, sr=SAMPLE_RATE)
    y = extract_post_hit(y, sr, POST_HIT_DURATION_SEC)
    y = y / np.max(np.abs(y))  # Normalize

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    delta = librosa.feature.delta(mfcc)

    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    img1 = librosa.display.specshow(mfcc, x_axis='time', ax=ax[0], sr=sr)
    ax[0].set(title=f"MFCCs - {title if title else file_path}")
    fig.colorbar(img1, ax=ax[0])

    img2 = librosa.display.specshow(delta, x_axis='time', ax=ax[1], sr=sr)
    ax[1].set(title="Delta MFCCs")
    fig.colorbar(img2, ax=ax[1])

    plt.tight_layout()
    plt.show()

# Example usage
plot_mfcc("data/processed/plastic/1.wav")  # Change to any file you'd like to inspect

# %%
