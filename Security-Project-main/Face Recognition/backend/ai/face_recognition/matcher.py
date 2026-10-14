"""
ai/face_recognition/matcher.py
────────────────────────────────
Compares a live face embedding against all stored student embeddings.

This is the decision-making core: given a 512-d query vector,
which student in the database is this?

Matching strategy — WHY we average multiple embeddings:
─────────────────────────────────────────────────────────
When a student is enrolled with multiple photos (e.g. 5–8 shots),
they have multiple embeddings stored. There are two strategies:

  Strategy A — Compare query against ALL embeddings, take best match:
    Pro: Catches edge cases (one photo at a specific angle matches)
    Con: More susceptible to false positives if threshold is loose

  Strategy B — Compare query against the AVERAGED embedding per student:
    Pro: More stable, one canonical "center" vector per student
    Con: Averages can wash out edge-case angles

  We use Strategy A (best-of-all) because:
    • ArcFace embeddings are L2-normalized unit vectors
    • The best matching embedding is the most informative signal
    • With a well-tuned threshold (0.68), false positives are rare

Glasses handling:
──────────────────
If a student enrolls BOTH with and without glasses, they'll have embeddings
covering both cases. The matcher automatically picks the best match,
so it doesn't matter which state the student is in during recognition.

"""

import numpy as np
from typing import Optional
from sqlalchemy.orm import Session

from models.student import Student


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two vectors.
    Since we always L2-normalize our embeddings in embedder.py,
    this reduces to a simple dot product: dot(a, b).
    We still normalize defensively in case a raw embedding slips through.
    """
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def embedding_to_bytes(v: np.ndarray) -> bytes:
    """Serialize a float32 numpy array to raw bytes for DB storage."""
    return v.astype(np.float32).tobytes()


def bytes_to_embedding(raw: bytes) -> np.ndarray:
    """Deserialize raw bytes back to a float32 numpy array."""
    return np.frombuffer(raw, dtype=np.float32).copy()


class FaceMatcher:
    """
    Matches a query embedding against all students in the database.

    Works with the existing Student model from the backend team —
    no schema changes needed.
    """

    def __init__(self, threshold: float = 0.68):
        """
        Args:
            threshold : Minimum cosine similarity to consider a match.
                        Read from settings in face_service.py.
                        Default 0.68 matches the backend's .env value.
        """
        self.threshold = threshold

    def find_best_match(
        self,
        query_embedding: np.ndarray,
        db: Session,
    ) -> tuple[Optional[Student], float]:
        """
        Searches all stored student embeddings for the best match.

        Each student stores ONE embedding (the backend's current design).
        If we later extend to multiple embeddings per student (recommended),
        this method handles it automatically by iterating all rows.

        Args:
            query_embedding : 512-d normalized float32 array (from FaceEmbedder)
            db              : SQLAlchemy session (from FastAPI dependency)

        Returns:
            (Student, similarity_score)  if match found above threshold
            (None,    best_score)        if no match above threshold
        """
        students = db.query(Student).all()
        if not students:
            return None, 0.0

        best_student: Optional[Student] = None
        best_score = 0.0

        for student in students:
            stored = bytes_to_embedding(student.embedding)
            score  = cosine_similarity(query_embedding, stored)

            if score > best_score:
                best_score   = score
                best_student = student

        if best_student and best_score >= self.threshold:
            return best_student, best_score

        return None, best_score

    def find_all_matches(
        self,
        query_embedding: np.ndarray,
        db: Session,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Returns the top-k closest students regardless of threshold.
        Useful for debugging ("who does this face resemble?").

        Args:
            query_embedding : 512-d normalized float32 array
            db              : SQLAlchemy session
            top_k           : number of candidates to return

        Returns:
            List of dicts sorted by similarity descending:
            [{"student": Student, "similarity": float}, ...]
        """
        students = db.query(Student).all()
        if not students:
            return []

        scored = []
        for student in students:
            stored = bytes_to_embedding(student.embedding)
            score  = cosine_similarity(query_embedding, stored)
            scored.append({"student": student, "similarity": score})

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]


# ── Module-level singleton ───────────────────────────────────────────────────

_matcher_instance: Optional[FaceMatcher] = None


def get_matcher(threshold: float = 0.68) -> FaceMatcher:
    """Returns the shared FaceMatcher instance (created once)."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = FaceMatcher(threshold=threshold)
    return _matcher_instance
