"""
ai/face_recognition/detector.py
─────────────────────────────────
Face detection using DeepFace with RetinaFace backend.

"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from deepface import DeepFace


@dataclass
class DetectedFace:
    """Result of a single face detection."""
    bbox: list[int]               # [x, y, w, h] in pixels
    confidence: float             # detection score 0.0–1.0
    aligned_img: np.ndarray       # cropped + aligned face (112x112 BGR)
    original_img: np.ndarray      # original BGR frame (for fallback)
    facial_area: dict = field(default_factory=dict)


class FaceDetector:
    """
    Detects and aligns faces using DeepFace + RetinaFace.

    RetinaFace detects facial landmarks (eyes, nose, mouth) and uses
    them to geometrically align the face before embedding — this is
    critical for ArcFace accuracy.

    Alignment means:
      - Eyes are always at the same horizontal level
      - Face is centered and scaled to a fixed size
      - Result: same person at different head angles → similar vectors
    """

    DETECTOR = "retinaface"   # best accuracy; falls back to mtcnn if needed

    def __init__(self):
        # Warm up DeepFace on a blank image so the first real call is fast
        try:
            blank = np.zeros((112, 112, 3), dtype=np.uint8)
            DeepFace.represent(
                img_path=blank,
                model_name="ArcFace",
                detector_backend=self.DETECTOR,
                enforce_detection=False,
                align=True,
            )
        except Exception:
            pass   # warmup failure is non-fatal

    def detect(self, frame: np.ndarray,
               min_confidence: float = 0.85) -> list[DetectedFace]:
        """
        Detects all faces in a frame.

        Args:
            frame          : BGR numpy array from camera / uploaded image
            min_confidence : minimum detection confidence to keep a face

        Returns:
            List of DetectedFace objects (may be empty).
        """
        try:
            # DeepFace.extract_faces returns aligned face crops + metadata
            faces = DeepFace.extract_faces(
                img_path=frame,
                detector_backend=self.DETECTOR,
                enforce_detection=False,
                align=True,         # ← uses landmarks to align face
                grayscale=False,
            )
        except Exception:
            return []

        results = []
        for face_data in faces:
            conf = face_data.get("confidence", 1.0)
            if conf < min_confidence:
                continue

            area = face_data.get("facial_area", {})
            face_img = face_data.get("face", None)

            if face_img is None or face_img.size == 0:
                continue

            # Convert from RGB (DeepFace uses RGB) back to BGR (OpenCV)
            if face_img.dtype != np.uint8:
                face_img = (face_img * 255).astype(np.uint8)
            face_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)

            # Resize to standard 112x112 (ArcFace input size)
            face_bgr = cv2.resize(face_bgr, (112, 112))

            results.append(DetectedFace(
                bbox=[area.get("x", 0), area.get("y", 0),
                      area.get("w", 0), area.get("h", 0)],
                confidence=float(conf),
                aligned_img=face_bgr,
                original_img=frame,
                facial_area=area,
            ))

        return results

    def detect_largest(self, frame: np.ndarray,
                       min_confidence: float = 0.85) -> Optional[DetectedFace]:
        """
        Returns only the largest detected face (by bounding box area).
        Use this for single-person attendance scans.
        Returns None if no face found above confidence threshold.
        """
        faces = self.detect(frame, min_confidence)
        if not faces:
            return None
        return max(faces, key=lambda f: f.bbox[2] * f.bbox[3])

    def draw(self, frame: np.ndarray, faces: list[DetectedFace],
             label: str = "") -> np.ndarray:
        """Draws bounding boxes on a copy of the frame (for debug/preview)."""
        out = frame.copy()
        for f in faces:
            x, y, w, h = f.bbox
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 220, 100), 2)
            text = label or f"{f.confidence:.2f}"
            cv2.putText(out, text, (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 100), 1)
        return out
