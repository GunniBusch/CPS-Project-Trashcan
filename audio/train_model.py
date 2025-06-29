import pickle
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

# Load extracted features
with open("audio/data/features.pkl", "rb") as f:
    X, y = pickle.load(f)  # X shape: (n_samples, time_steps, feature_dim)

# Flatten for classical ML: (samples, features)
X_flat = X.reshape(X.shape[0], -1)

# Normalize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_flat)

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, stratify=y, random_state=42
)

# Train SVM
model = SVC(kernel='rbf', C=10, gamma='scale')  # RBF kernel helps with nonlinear separation
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
print("Classification Report:\n", classification_report(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

# Save model and scaler
with open("audio/model/svm_model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("audio/model/scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)
