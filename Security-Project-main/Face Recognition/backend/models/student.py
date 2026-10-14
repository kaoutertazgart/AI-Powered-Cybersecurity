from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, func
from database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False, index=True)
    embedding = Column(LargeBinary, nullable=False)  # raw float32 bytes
    created_at = Column(DateTime, server_default=func.now())
