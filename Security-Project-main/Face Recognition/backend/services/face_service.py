from typing import List, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session

from ai.face_recognition.detector import FaceDetector
from ai.face_recognition.embedder import FaceEmbedder
from ai.face_recognition.matcher  import FaceMatcher, embedding_to_bytes, bytes_to_embedding
from ai.face_recognition.quality  import check_quality
from models.student import Student
from core.config import settings


# ── Singletons — loaded once at first call, reused forever ───────────────────
_detector: Optional[FaceDetector] = None
_embedder: Optional[FaceEmbedder] = None
_matcher:  Optional[FaceMatcher]  = None


def _get_detector() -> FaceDetector:
    global _detector
    if _detector is None:
        _detector = FaceDetector()
    return _detector


def _get_embedder() -> FaceEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = FaceEmbedder()
    return _embedder


def _get_matcher() -> FaceMatcher:
    global _matcher
    if _matcher is None:
        _matcher = FaceMatcher(threshold=settings.SIMILARITY_THRESHOLD)
    return _matcher


# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API  (same signatures as original face_service.py)
# ════════════════════════════════════════════════════════════════════════════

def extract_embedding(image_bytes: bytes) -> List[float]:
    """
    Decodes an image, detects + aligns the face, runs ArcFace, returns 512-d vector.

    This is the main function called by both /auth/recognize and /auth/enroll.

    Pipeline:
      image_bytes
        → cv2.imdecode  (decode JPEG/PNG)
        → FaceDetector  (RetinaFace: find + align face)
        → quality check (blur / brightness / size)
        → FaceEmbedder  (ArcFace: 512-d vector)
        → L2 normalize
        → list[float]   (returned to router)

    Args:
        image_bytes : raw bytes of a JPEG or PNG image

    Returns:
        List of 512 floats (L2-normalized ArcFace embedding)

    Raises:
        ValueError   : No face detected, or quality check failed — show to user
        RuntimeError : Model-level error — log and return 500
    """
    import cv2
    arr   = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Could not decode image. Please send a JPEG or PNG file.")

    # ── Step 1: Detect face ───────────────────────────────────────────────────
    detector = _get_detector()
    face     = detector.detect_largest(frame, min_confidence=0.85)

    if face is None:
        raise ValueError(
            "No face detected in the image. "
            "Please ensure: face is fully visible, good lighting, "
            "looking directly at the camera."
        )

    # ── Step 2: Quality check ─────────────────────────────────────────────────
    face_area_px = face.bbox[2] * face.bbox[3]
    quality      = check_quality(face.aligned_img, face_area_px)

    if not quality.passed:
        raise ValueError(quality.reason)

    # ── Step 3: Extract embedding ─────────────────────────────────────────────
    embedder  = _get_embedder()
    embedding = embedder.get_embedding(face)

    if embedding is None:
        raise RuntimeError(
            "Face detected but embedding extraction failed. "
            "This is a model error — try again."
        )

    return embedding.tolist()


def find_student(
    embedding: List[float],
    db: Session,
) -> Tuple[Optional[Student], float]:
    """
    Compares a 512-d embedding against all stored students.

    Args:
        embedding : list of 512 floats from extract_embedding()
        db        : SQLAlchemy session (from FastAPI dependency)

    Returns:
        (Student, similarity_score) if match found above threshold
        (None,    best_score)       if no match above threshold
    """
    query_vec = np.array(embedding, dtype=np.float32)
    matcher   = _get_matcher()
    return matcher.find_best_match(query_vec, db)


def store_embedding(
    full_name: str,
    embedding: List[float],
    db: Session,
) -> Student:
    """
    Creates a new Student record with the given embedding.

    Args:
        full_name : student's full name
        embedding : list of 512 floats from extract_embedding()
        db        : SQLAlchemy session

    Returns:
        The newly created Student ORM object.
    """
    vec     = np.array(embedding, dtype=np.float32)
    student = Student(
        full_name=full_name.strip(),
        embedding=embedding_to_bytes(vec),
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student
