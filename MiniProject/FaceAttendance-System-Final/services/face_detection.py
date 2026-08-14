import os
import numpy as np
import cv2
from insightface.app import FaceAnalysis

# Initialize InsightFace Analysis Engine using CPU ONNX Execution Provider
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(640, 640))


def extract_face_encoding(image_path):
    """Reads image from path, detects face, and returns feature vector embedding."""
    if not os.path.exists(image_path):
        return None

    img = cv2.imread(image_path)  # pylint: disable=no-member
    if img is None:
        return None

    faces = face_app.get(img)
    if len(faces) == 0:
        return None

    return faces[0].embedding


def save_encoding(filepath, embedding):
    """Saves feature vector array to disk as a binary .npy file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    np.save(filepath, embedding)


def load_encoding(filepath):
    """Loads saved feature vector array from disk."""
    if os.path.exists(filepath):
        return np.load(filepath)
    return None


def compare_encodings(known_embedding, candidate_embedding, threshold=0.4):
    """Computes cosine similarity between two feature vectors."""
    if known_embedding is None or candidate_embedding is None:
        return False, 0.0

    dot_product = np.dot(known_embedding, candidate_embedding)
    norm_a = np.linalg.norm(known_embedding)
    norm_b = np.linalg.norm(candidate_embedding)

    if norm_a == 0 or norm_b == 0:
        return False, 0.0

    similarity = dot_product / (norm_a * norm_b)
    return similarity >= threshold, float(similarity)


def check_duplicate_face(candidate_embedding, encodings_folder, threshold=0.4):
    """
    Checks if candidate_embedding matches any existing .npy file in encodings_folder.
    Returns (is_duplicate, matched_filename).
    """
    if candidate_embedding is None or not os.path.exists(encodings_folder):
        return False, None

    for file_name in os.listdir(encodings_folder):
        if file_name.endswith('.npy'):
            file_path = os.path.join(encodings_folder, file_name)
            known_embedding = load_encoding(file_path)
            if known_embedding is not None:
                is_match, similarity = compare_encodings(
                    known_embedding, candidate_embedding, threshold)
                if is_match:
                    return True, file_name

    return False, None
