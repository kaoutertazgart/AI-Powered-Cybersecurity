"""
ai/face_recognition/embedder.py
─────────────────────────────────
Extracts 512-dimensional ArcFace face embeddings via DeepFace.

What is an embedding?
──────────────────────
A face embedding is a 512-float vector — a numerical "fingerprint" of an identity.
  Same person  →  vectors are CLOSE   (cosine similarity ≈ 0.7–1.0)
  Diff people  →  vectors are FAR     (cosine similarity ≈ 0.0–0.3)

Why ArcFace?
─────────────
ArcFace (Additive Angular Margin Loss) is specifically designed so that:
  • Embeddings of the same person cluster tightly in vector space
  • Embeddings of different people are pushed apart by an angular margin
  • This makes the cosine similarity threshold stable and meaningful

The model achieves >99.8% accuracy on LFW benchmark (standard face recognition test).

Why normalize?
───────────────
We always L2-normalize embeddings before storing and comparing.
This makes cosine_similarity(a,b) = dot(a,b), which is:
  • Numerically stable
  • Consistent across images of different sizes/lighting
  • Directly comparable to the threshold (0.68 in the backend)

Handling glasses:
──────────────────
ArcFace is trained on millions of faces including faces with/without glasses.
It learns to rely on other facial geometry (eye spacing, nose shape, jaw)
so glasses cause only a ~0.05 drop in similarity.

Best practice for enrollment:
  1. Enroll WITH glasses if the student usually wears them
  2. Enroll WITHOUT glasses as a second pass → 2 embeddings stored
  3. During recognition, both are checked → whichever matches wins
"""

import numpy as np
from typing import Optional

from deepface import DeepFace

from ai.face_recognition.detector import DetectedFace


class FaceEmbedder:
    """
    Extracts a 512-d ArcFace embedding from a detected face.
    Works directly with DetectedFace objects from FaceDetector.
    """

    MODEL = "ArcFace"

    def get_embedding(self, face: DetectedFace) -> Optional[np.ndarray]:
        """
        Extracts a normalized 512-d ArcFace embedding from a DetectedFace object.

        We use the pre-aligned face crop (face.aligned_img) which was already
        aligned by RetinaFace landmarks — this is the highest-accuracy path.

        Args:
            face : DetectedFace from FaceDetector.detect_largest()

        Returns:
            np.ndarray of shape (512,), L2-normalized float32.
            None if extraction fails.
        """
        try:
            reps = DeepFace.represent(
                img_path=face.aligned_img,
                model_name=self.MODEL,
                detector_backend="skip",   # ← skip re-detection, face is already aligned
                enforce_detection=False,
                align=False,               # ← already aligned by RetinaFace
                normalization="ArcFace",   # ← model-specific input normalization
            )
        except Exception as e:
            return None

        if not reps:
            return None

        raw = np.array(reps[0]["embedding"], dtype=np.float32)
        return self._normalize(raw)

    def get_embedding_from_bytes(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """
        Full pipeline in one call: decode image → detect → align → embed.
        This is what the routers call for uploaded images.

        Internally runs FaceDetector then get_embedding.

        Args:
            image_bytes : raw JPEG/PNG bytes from uploaded file

        Returns:
            512-d normalized np.ndarray or None if no face found.

        Raises:
            ValueError : if no face is detected
            RuntimeError : on model errors
        """
        import cv2
        arr   = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Could not decode image. Please send JPEG or PNG.")

        # Import here to avoid circular imports
        from ai.face_recognition.detector import FaceDetector
        detector = _get_detector()
        face     = detector.detect_largest(frame)

        if face is None:
            raise ValueError(
                "No face detected in the image. "
                "Please ensure: good lighting, face fully visible, "
                "looking directly at the camera."
            )

        emb = self.get_embedding(face)
        if emb is None:
            raise RuntimeError("Face detected but embedding extraction failed.")

        return emb

    # ── Multi-enrollment helper ──────────────────────────────────────────────

    def get_embeddings_from_multiple_images(
        self, images_bytes: list[bytes]
    ) -> list[np.ndarray]:
        """
        Extracts embeddings from multiple photos of the SAME student.
        Skips photos where no face is found (logs a warning instead of failing).

        Used during enrollment when multiple photos are uploaded for one student.
        More embeddings → more robust recognition (covers different angles,
        lighting, glasses vs no glasses).

        Args:
            images_bytes : list of raw JPEG/PNG byte strings

        Returns:
            List of 512-d normalized arrays. May be shorter than input
            if some images had no detectable face.
        """
        embeddings = []
        for i, img_bytes in enumerate(images_bytes):
            try:
                emb = self.get_embedding_from_bytes(img_bytes)
                if emb is not None:
                    embeddings.append(emb)
            except (ValueError, RuntimeError) as e:
                print(f"[Embedder] ⚠️  Photo {i+1} skipped: {e}")

        return embeddings

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        """L2-normalize so cosine_similarity = dot product."""
        n = np.linalg.norm(v)
        if n == 0:
            return v
        return v / n


# ── Module-level singletons (loaded once, reused every call) ─────────────────
# Loading DeepFace/ArcFace models takes ~3–5 seconds.
# By using module-level instances we pay that cost once at startup.

_embedder_instance: Optional[FaceEmbedder] = None

def get_embedder() -> FaceEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = FaceEmbedder()
    return _embedder_instance


# Detector singleton (used by get_embedding_from_bytes)
_detector_instance = None

def _get_detector():
    global _detector_instance
    from ai.face_recognition.detector import FaceDetector
    if _detector_instance is None:
        _detector_instance = FaceDetector()
    return _detector_instance
