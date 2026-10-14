"""
routers/auth.py
---------------
POST /auth/recognize  — identify face from camera frame
POST /auth/enroll     — register new student (full name + face)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.log import RecognitionLog
from schemas.student import RecognizeResponse, EnrollResponse
from services.face_service import extract_embedding, find_student, store_embedding

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _log(db: Session, *, student_id, action, result, confidence=None):
    db.add(RecognitionLog(
        student_id=student_id, action=action, result=result, confidence=confidence,
    ))
    db.commit()


@router.post("/recognize", response_model=RecognizeResponse)
async def recognize(
    image: UploadFile = File(..., description="Camera frame (JPEG/PNG)"),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()

    try:
        embedding = extract_embedding(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    student, confidence = find_student(embedding, db)

    if student:
        _log(db, student_id=student.id, action="recognize",
             result="found", confidence=confidence)
        return RecognizeResponse(
            found=True,
            message=f"Welcome, {student.full_name}!",
            student_id=student.id,
            full_name=student.full_name,
            confidence=round(confidence, 4),
        )

    _log(db, student_id=None, action="recognize",
         result="not_found", confidence=confidence)
    return RecognizeResponse(
        found=False,
        message="Does not exist",
        confidence=round(confidence, 4),
    )


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(
    full_name: str = Form(..., min_length=2),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()

    try:
        embedding = extract_embedding(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    student = store_embedding(full_name, embedding, db)
    _log(db, student_id=student.id, action="enroll", result="enrolled", confidence=None)

    return EnrollResponse(
        success=True,
        message=f"Student '{student.full_name}' enrolled successfully.",
        student_id=student.id,
        full_name=student.full_name,
    )
