from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class VideoAnalysis(Base):
    __tablename__ = "video_analyses"
    
    job_id = Column(
        String, 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    video_id = Column(String, nullable=False)
    s3_url = Column(Text, nullable=False)
    people_count = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=True)  # User ID of the creator