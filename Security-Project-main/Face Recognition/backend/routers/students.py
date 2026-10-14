from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.student import Student
from schemas.student import StudentOut

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("/", response_model=List[StudentOut])
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).order_by(Student.id.desc()).all()


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    s = db.query(Student).filter(Student.id == student_id).first()
    if not s:
        raise HTTPException(404, "Student not found")
    return s


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    s = db.query(Student).filter(Student.id == student_id).first()
    if not s:
        raise HTTPException(404, "Student not found")
    db.delete(s)
    db.commit()
    return {"success": True, "message": f"Deleted student {student_id}"}
