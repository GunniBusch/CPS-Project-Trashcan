import numpy as np

POST_HIT_DURATION_SEC = 0.5  # How long after the hit to extract

def extract_post_hit(y, sr):
    """Extracts audio starting from the loudest point (hit) onward."""
    energy = np.abs(y)
    peak_index = np.argmax(energy)
    end_index = min(len(y), peak_index + int(POST_HIT_DURATION_SEC * sr))
    return y[peak_index:end_index]