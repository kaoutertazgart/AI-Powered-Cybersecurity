from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class StudentOut(BaseModel): 
    id: int
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecognizeResponse(BaseModel):
    found: bool
    message: str
    student_id: Optional[int] = None
    full_name: Optional[str] = None
    confidence: Optional[float] = None


class EnrollResponse(BaseModel):
    success: bool
    message: str
    student_id: Optional[int] = None
    full_name: Optional[str] = None
