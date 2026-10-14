"""
ai/face_recognition/
─────────────────────
Public API for the face recognition module.

Import from here, not from the submodules directly:
    from ai.face_recognition import FaceDetector, FaceEmbedder, FaceMatcher
    from ai.face_recognition import get_embedder, get_matcher
"""
from ai.face_recognition.detector import FaceDetector, DetectedFace
from ai.face_recognition.embedder import FaceEmbedder, get_embedder
from ai.face_recognition.matcher  import FaceMatcher, get_matcher, cosine_similarity
from ai.face_recognition.quality  import check_quality, QualityReport

__all__ = [
    "FaceDetector", "DetectedFace",
    "FaceEmbedder", "get_embedder",
    "FaceMatcher",  "get_matcher", "cosine_similarity",
    "check_quality", "QualityReport",
]
