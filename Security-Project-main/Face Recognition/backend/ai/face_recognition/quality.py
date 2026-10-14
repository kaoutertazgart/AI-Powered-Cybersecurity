"""
ai/face_recognition/quality.py
────────────────────────────────
Image quality checks performed BEFORE extracting embeddings.

Why quality checks matter:
───────────────────────────
A blurry or dark photo produces an unreliable embedding — the same person
in a bad photo may have a very different vector from a good photo.
Rejecting bad inputs early means:
  • Only high-quality embeddings are stored during enrollment
  • Recognition attempts on poor frames are rejected with a helpful message
  • Overall system accuracy improves significantly

Checks performed:
  1. Blur detection     — rejects motion blur / out-of-focus frames
  2. Brightness check   — rejects images that are too dark or overexposed
  3. Face size check    — rejects faces that are too small (too far from camera)

These checks run in <1ms each (pure numpy/opencv), no model inference needed.
"""

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class QualityReport:
    """Result of all quality checks on an image/face."""
    passed: bool
    reason: str        # human-readable failure reason (empty if passed)
    blur_score: float  # Laplacian variance — higher = sharper
    brightness: float  # mean pixel value 0–255
    face_size_px: int  # face bounding box area in pixels


# ── Thresholds (tuned for typical webcam/phone footage) ─────────────────────
BLUR_THRESHOLD       = 60.0    # Laplacian variance. Below this = too blurry.
BRIGHTNESS_MIN       = 40.0    # Mean pixel value. Below = too dark.
BRIGHTNESS_MAX       = 230.0   # Above = overexposed.
MIN_FACE_SIZE_PX     = 40 * 40 # 40×40 pixels minimum face area.


def check_quality(face_crop: np.ndarray,
                  face_area_px: int | None = None) -> QualityReport:
    """
    Runs all quality checks on a face crop (aligned_img from DetectedFace).

    Args:
        face_crop     : BGR numpy array (the aligned face image)
        face_area_px  : face bounding box area in the original frame (optional)

    Returns:
        QualityReport with passed=True if all checks pass.
    """
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    # ── 1. Blur (Laplacian variance) ─────────────────────────────────────────
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # ── 2. Brightness ────────────────────────────────────────────────────────
    brightness = float(np.mean(gray))

    # ── 3. Face size ─────────────────────────────────────────────────────────
    face_size = face_area_px if face_area_px is not None else (
        face_crop.shape[0] * face_crop.shape[1]
    )

    # ── Evaluate ──────────────────────────────────────────────────────────────
    if blur_score < BLUR_THRESHOLD:
        return QualityReport(
            passed=False,
            reason=f"Image is too blurry (score={blur_score:.1f}). "
                   f"Please hold still and ensure the camera is in focus.",
            blur_score=blur_score,
            brightness=brightness,
            face_size_px=face_size,
        )

    if brightness < BRIGHTNESS_MIN:
        return QualityReport(
            passed=False,
            reason="Image is too dark. Please move to a better-lit area.",
            blur_score=blur_score,
            brightness=brightness,
            face_size_px=face_size,
        )

    if brightness > BRIGHTNESS_MAX:
        return QualityReport(
            passed=False,
            reason="Image is overexposed. Please avoid direct light behind you.",
            blur_score=blur_score,
            brightness=brightness,
            face_size_px=face_size,
        )

    if face_size < MIN_FACE_SIZE_PX:
        return QualityReport(
            passed=False,
            reason="Face is too small. Please move closer to the camera.",
            blur_score=blur_score,
            brightness=brightness,
            face_size_px=face_size,
        )

    return QualityReport(
        passed=True,
        reason="",
        blur_score=blur_score,
        brightness=brightness,
        face_size_px=face_size,
    )
