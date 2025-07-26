from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from typing import Optional
import asyncio
import logging
from datetime import datetime
import uuid
import re
import os
from dotenv import load_dotenv, dotenv_values

from .database import get_db_session, VideoAnalysis
from .video_processor import VideoProcessor

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="People Counter API", version="1.0.0")

# Initialize video processor
video_processor = VideoProcessor()


# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.url}: {exc.errors()}")
    logger.error(f"Request body: {exc.body}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "body": exc.body
        }
    )


class VideoRequest(BaseModel):
    s3_url: str
    video_id: Optional[str] = None
    user: Optional[int | str] = None

    @validator('s3_url')
    def validate_s3_url(cls, v):
        # Accept both s3:// URLs and https:// URLs
        s3_pattern = r'^s3://[a-zA-Z0-9.\-_]+/.*'
        https_pattern = r'^https?://.*'
        
        if not (re.match(s3_pattern, v) or re.match(https_pattern, v)):
            raise ValueError('s3_url must be a valid S3 URI (s3://bucket/key) or HTTPS URL')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "s3_url": "s3://bucket-name/path/to/video.mp4",
                "video_id": "optional-video-id"
            }
        }


class VideoResponse(BaseModel):
    job_id: str
    status: str
    message: str


@app.on_event("startup")
async def startup_event():
    logger.info("Starting People Counter API")
    
    # Log AWS configuration status
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    if aws_access_key:
        logger.info(f"AWS credentials found for access key: {aws_access_key[:4]}****")
        logger.info(f"AWS region: {aws_region}")
    else:
        logger.warning("No AWS credentials found in environment variables")
        logger.warning("Will attempt to use default credential chain (IAM roles, etc.)")
    
    await video_processor.initialize()


@app.post("/analyze-video", response_model=VideoResponse)
async def analyze_video(
    request: VideoRequest, background_tasks: BackgroundTasks
):
    """
    Endpoint to analyze video from S3 URL and count people
    """
    try:
        logger.info(f"Received video analysis request: s3_url={request.s3_url}, video_id={request.video_id}")
        print(f"Request data: {request}")
        
        job_id = str(uuid.uuid4())
        video_id = request.video_id or str(uuid.uuid4())
        user_id = request.user if request.user else None

        if not user_id:
            return HTTPException(
                status_code=400,
                detail="User ID is required for video analysis"
            )
        
        # Add background task to process video
        background_tasks.add_task(
            process_video_task, 
            job_id, 
            video_id, 
            request.s3_url,  # No need to convert to string anymore
            user_id
        )
        
        logger.info(f"Started video analysis job: {job_id} for video: {video_id}")
        
        return VideoResponse(
            job_id=job_id,
            status="processing",
            message="Video analysis started"
        )
    
    except Exception as e:
        logger.error(f"Error starting video analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a video analysis job
    """
    try:
        async with get_db_session() as session:
            result = await session.get(VideoAnalysis, job_id)
            if not result:
                raise HTTPException(status_code=404, detail="Job not found")
            
            return {
                "job_id": result.job_id,
                "video_id": result.video_id,
                "status": result.status,
                "people_count": result.people_count,
                "created_at": result.created_at,
                "completed_at": result.completed_at,
                "error_message": result.error_message
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_video_task(job_id: str, video_id: str, s3_url: str, user_id: str):
    """
    Background task to process video and count people
    """
    async with get_db_session() as session:
        # Create initial record
        analysis = VideoAnalysis(
            job_id=job_id,
            video_id=video_id,
            s3_url=s3_url,
            status="processing",
            created_at=datetime.utcnow(),
            created_by=user_id
        )
        session.add(analysis)
        await session.commit()
    
    try:
        # Process video
        people_count = await video_processor.count_people_in_video(s3_url)
        
        # Update database with results
        async with get_db_session() as session:
            result = await session.get(VideoAnalysis, job_id)
            result.people_count = people_count
            result.status = "completed"
            result.completed_at = datetime.utcnow()
            await session.commit()
            
        logger.info(f"Job {job_id} completed. People count: {people_count}")
    
    except Exception as e:
        logger.error(f"Error processing video {job_id}: {str(e)}")
        
        # Update database with error
        async with get_db_session() as session:
            result = await session.get(VideoAnalysis, job_id)
            result.status = "failed"
            result.error_message = str(e)
            result.completed_at = datetime.utcnow()
            await session.commit()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}