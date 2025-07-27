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
import time
from dotenv import load_dotenv, dotenv_values

from .database import get_db_session, VideoAnalysis
from .video_processor import VideoProcessor

# Load environment variables from .env file
load_dotenv()

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/people_counter.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 60)
logger.info("PEOPLE COUNTER API STARTING UP")
logger.info("=" * 60)

app = FastAPI(title="People Counter API", version="1.0.0")


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log incoming request
    logger.info(f"Incoming request: {request.method} {request.url}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    logger.debug(f"Client IP: {client_ip}")
    
    try:
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(f"Response: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.3f}s")
        
        # Add processing time to response headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request failed: {request.method} {request.url} - Error: {str(e)} - Time: {process_time:.3f}s")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise

# Initialize video processor
logger.debug("Initializing video processor...")
try:
    video_processor = VideoProcessor()
    logger.info("Video processor initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize video processor: {e}")
    logger.error(f"Error type: {type(e).__name__}")
    raise


# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.url}: {exc.errors()}")
    logger.error(f"Request body: {exc.body}")
    logger.error(f"Request headers: {dict(request.headers)}")
    logger.error(f"Request method: {request.method}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "body": exc.body
        }
    )


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for {request.url}: {str(exc)}")
    logger.error(f"Exception type: {type(exc).__name__}")
    logger.error(f"Request method: {request.method}")
    logger.error(f"Request headers: {dict(request.headers)}")
    
    # Import traceback to get full stack trace
    import traceback
    logger.error(f"Full traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


class VideoRequest(BaseModel):
    s3_url: str
    video_id: Optional[str] = None
    user: Optional[int | str] = None

    @validator('s3_url')
    def validate_s3_url(cls, v):
        logger.debug(f"Validating S3 URL: {v}")
        # Accept both s3:// URLs and https:// URLs
        s3_pattern = r'^s3://[a-zA-Z0-9.\-_]+/.*'
        https_pattern = r'^https?://.*'
        
        if not (re.match(s3_pattern, v) or re.match(https_pattern, v)):
            logger.error(f"Invalid S3 URL format: {v}")
            raise ValueError('s3_url must be a valid S3 URI (s3://bucket/key) or HTTPS URL')
        
        logger.debug(f"S3 URL validation passed: {v}")
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
    logger.debug("Checking environment configuration...")
    
    # Log AWS configuration status
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    if aws_access_key:
        logger.info(f"AWS credentials found for access key: {aws_access_key[:4]}****")
        logger.info(f"AWS region: {aws_region}")
    else:
        logger.warning("No AWS credentials found in environment variables")
        logger.warning("Will attempt to use default credential chain (IAM roles, etc.)")
    
    # Test database connection on startup
    logger.debug("Testing database connection on startup...")
    try:
        from .database import test_database_connection
        success, message = await test_database_connection()
        if success:
            logger.info(f"Database connection test successful: {message}")
        else:
            logger.error(f"Database connection test failed: {message}")
    except Exception as e:
        logger.error(f"Error testing database connection: {e}")
    
    # Initialize video processor
    logger.debug("Initializing video processor...")
    try:
        await video_processor.initialize()
        logger.info("Video processor initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize video processor: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Don't raise here to allow the app to start even if video processor fails
        logger.warning("Continuing startup despite video processor initialization failure")
    
    logger.info("People Counter API startup completed")


@app.post("/analyze-video", response_model=VideoResponse)
async def analyze_video(
    request: VideoRequest, background_tasks: BackgroundTasks
):
    """
    Endpoint to analyze video from S3 URL and count people
    """
    logger.debug(f"Received analyze-video request")
    logger.debug(f"Request data: s3_url={request.s3_url}, video_id={request.video_id}, user={request.user}")
    
    try:
        logger.info(f"Received video analysis request: s3_url={request.s3_url}, video_id={request.video_id}")
        print(f"Request data: {request}")
        
        # Generate IDs
        job_id = str(uuid.uuid4())
        video_id = request.video_id or str(uuid.uuid4())
        user_id = request.user if request.user else None
        
        logger.debug(f"Generated job_id: {job_id}, video_id: {video_id}")

        # Validate user_id
        if not user_id:
            logger.error("User ID is missing from request")
            raise HTTPException(
                status_code=400,
                detail="User ID is required for video analysis"
            )
        
        logger.debug(f"User ID validated: {user_id}")
        
        # Add background task to process video
        logger.debug("Adding background task for video processing...")
        background_tasks.add_task(
            process_video_task, 
            job_id, 
            video_id, 
            request.s3_url,
            user_id
        )
        logger.info(f"Background task added successfully for job: {job_id}")
        
        logger.info(f"Started video analysis job: {job_id} for video: {video_id}")
        
        response = VideoResponse(
            job_id=job_id,
            status="processing",
            message="Video analysis started"
        )
        logger.debug(f"Returning response: {response}")
        return response
    
    except HTTPException as he:
        logger.error(f"HTTP Exception in analyze_video: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting video analysis: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a video analysis job
    """
    logger.debug(f"Received status request for job_id: {job_id}")
    
    try:
        # Validate job_id format
        try:
            uuid.UUID(job_id)
            logger.debug(f"Job ID format validation passed: {job_id}")
        except ValueError:
            logger.error(f"Invalid job ID format: {job_id}")
            raise HTTPException(status_code=400, detail="Invalid job ID format")
        
        logger.debug("Opening database session to get job status...")
        async with get_db_session() as session:
            logger.debug(f"Querying database for job: {job_id}")
            result = await session.get(VideoAnalysis, job_id)
            
            if not result:
                logger.warning(f"Job not found in database: {job_id}")
                raise HTTPException(status_code=404, detail="Job not found")
            
            logger.debug(f"Job found: {job_id}, status: {result.status}")
            
            response_data = {
                "job_id": result.job_id,
                "video_id": result.video_id,
                "status": result.status,
                "people_count": result.people_count,
                "created_at": result.created_at,
                "completed_at": result.completed_at,
                "error_message": result.error_message
            }
            
            logger.debug(f"Returning job status: {response_data}")
            return response_data
    
    except HTTPException as he:
        logger.error(f"HTTP Exception in get_job_status: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting job status for {job_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def process_video_task(job_id: str, video_id: str, s3_url: str, user_id: str):
    """
    Background task to process video and count people
    """
    logger.info(f"Starting background video processing task for job: {job_id}")
    logger.debug(f"Task parameters: job_id={job_id}, video_id={video_id}, s3_url={s3_url}, user_id={user_id}")
    
    try:
        logger.debug("Opening database session to create initial record...")
        async with get_db_session() as session:
            # Create initial record
            logger.debug("Creating VideoAnalysis record...")
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
            logger.info(f"Initial database record created for job: {job_id}")
    
    except Exception as e:
        logger.error(f"Failed to create initial database record for job {job_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return  # Exit early if we can't even create the initial record
    
    try:
        logger.info(f"Starting video processing for job: {job_id}")
        logger.debug(f"Processing video from URL: {s3_url}")
        
        # Process video
        people_count = await video_processor.count_people_in_video(s3_url)
        logger.info(f"Video processing completed for job {job_id}. People count: {people_count}")
        
        # Update database with results
        logger.debug("Updating database with successful results...")
        async with get_db_session() as session:
            result = await session.get(VideoAnalysis, job_id)
            if not result:
                logger.error(f"Job record not found when updating results: {job_id}")
                return
                
            result.people_count = people_count
            result.status = "completed"
            result.completed_at = datetime.utcnow()
            await session.commit()
            logger.info(f"Database updated successfully for job: {job_id}")
            
        logger.info(f"Job {job_id} completed successfully. People count: {people_count}")
    
    except Exception as e:
        logger.error(f"Error processing video for job {job_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Update database with error
        try:
            logger.debug("Updating database with error status...")
            async with get_db_session() as session:
                result = await session.get(VideoAnalysis, job_id)
                if result:
                    result.status = "failed"
                    result.error_message = str(e)
                    result.completed_at = datetime.utcnow()
                    await session.commit()
                    logger.info(f"Database updated with error status for job: {job_id}")
                else:
                    logger.error(f"Job record not found when updating error status: {job_id}")
        except Exception as db_error:
            logger.error(f"Failed to update database with error status for job {job_id}: {db_error}")
            logger.error(f"Database error type: {type(db_error).__name__}")


@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint called")
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }
    
    # Test database connection
    try:
        from .database import test_database_connection
        db_success, db_message = await test_database_connection()
        health_status["database"] = {
            "status": "healthy" if db_success else "unhealthy",
            "message": db_message
        }
    except Exception as e:
        logger.error(f"Health check database test failed: {e}")
        health_status["database"] = {
            "status": "unhealthy",
            "message": str(e)
        }
    
    # Test video processor
    try:
        # Simple check to see if video processor is accessible
        if hasattr(video_processor, 'model_path'):
            health_status["video_processor"] = {
                "status": "healthy",
                "message": "Video processor initialized"
            }
        else:
            health_status["video_processor"] = {
                "status": "unknown",
                "message": "Video processor status unclear"
            }
    except Exception as e:
        logger.error(f"Health check video processor test failed: {e}")
        health_status["video_processor"] = {
            "status": "unhealthy",
            "message": str(e)
        }
    
    logger.debug(f"Health check result: {health_status}")
    return health_status