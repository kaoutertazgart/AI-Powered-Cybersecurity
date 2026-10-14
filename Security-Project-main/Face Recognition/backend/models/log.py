from sqlalchemy import Column, Integer, String, Float, DateTime, func
from database import Base


class RecognitionLog(Base):
    __tablename__ = "recognition_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=True)
    action = Column(String, nullable=False)        # 'recognize' | 'enroll'
    result = Column(String, nullable=False)        # 'found' | 'not_found' | 'enrolled' | 'error'
    confidence = Column(Float, nullable=True)      #how  similar the incoming face is to the stored face 
    created_at = Column(DateTime, server_default=func.now())
