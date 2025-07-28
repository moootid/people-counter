import cv2
import torch
from ultralytics import YOLO
import tempfile
import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self):
        self.model = None
        self.device = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.s3_client = None
    
    async def initialize(self):
        """Initialize YOLO model and S3 client"""
        try:
            # Check if CUDA is available
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
            
            # Set CPU optimization if running on CPU
            if self.device == "cpu":
                # Use all available CPU cores for inference
                torch.set_num_threads(os.cpu_count() or 4)
                logger.info(f"CPU optimization: Using {torch.get_num_threads()} threads")
            
            # Load YOLO model
            model_path = os.getenv("YOLO_MODEL_PATH", "yolo11n.pt")
            self.model = YOLO(model_path)  # nano version for speed
            self.model.to(self.device)
            
            # Set model path for health checks
            self.model_path = model_path
            
            # Initialize S3 client
            self._initialize_s3_client()
            
            logger.info(f"YOLO model initialized successfully on {self.device}")
            if self.device == "cpu":
                logger.info("Running on CPU - expect slower inference times")
        
        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            raise
    
    def _initialize_s3_client(self):
        """Initialize S3 client with AWS credentials"""
        try:
            # Get AWS credentials from environment variables
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            
            if aws_access_key_id and aws_secret_access_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name=aws_region
                )
                logger.info("S3 client initialized with provided credentials")
            else:
                # Fallback to default credential chain (IAM roles, etc.)
                self.s3_client = boto3.client('s3')
                logger.info("S3 client initialized with default credential chain")
        
        except Exception as e:
            logger.warning(f"Could not initialize S3 client: {str(e)}")
            logger.warning("Will fall back to HTTP requests for S3 access")
    
    async def count_people_in_video(self, s3_url: str) -> int:
        """
        Download video from S3 and count people
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self._process_video_sync, s3_url
        )
    
    def _process_video_sync(self, s3_url: str) -> int:
        """
        Synchronous video processing
        """
        temp_video_path = None
        try:
            # Download video from S3
            temp_video_path = self._download_video(s3_url)
            
            # Process video and count people
            people_count = self._count_people_in_frames(temp_video_path)
            
            return people_count
        
        finally:
            # Clean up temporary file
            if temp_video_path and os.path.exists(temp_video_path):
                os.remove(temp_video_path)
    
    def _download_video(self, s3_url: str) -> str:
        """
        Download video from S3 URL to temporary file
        Supports both s3:// URIs and https:// URLs
        """
        try:
            parsed_url = urlparse(s3_url)
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp4"
            )
            temp_file.close()
            
            if parsed_url.scheme == 's3':
                # Handle S3 URI (s3://bucket/key)
                if not self.s3_client:
                    raise ValueError("S3 client not initialized. Cannot access S3 URIs.")
                
                bucket_name = parsed_url.netloc
                object_key = parsed_url.path.lstrip('/')
                
                logger.info(f"Downloading from S3: bucket={bucket_name}, key={object_key}")
                
                # Download file from S3
                self.s3_client.download_file(bucket_name, object_key, temp_file.name)
                
            else:
                # Handle HTTPS URL (fallback to original method)
                response = requests.get(s3_url, stream=True)
                response.raise_for_status()
                
                # Download video
                with open(temp_file.name, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            logger.info(f"Video downloaded to: {temp_file.name}")
            return temp_file.name
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket does not exist: {bucket_name}")
            elif error_code == 'NoSuchKey':
                logger.error(f"S3 object does not exist: {object_key}")
            elif error_code == 'AccessDenied':
                logger.error(f"Access denied to S3 object. Check your AWS credentials and permissions.")
            else:
                logger.error(f"S3 client error: {str(e)}")
            raise
        
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
            raise
        
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            raise
    
    def _count_people_in_frames(self, video_path: str) -> int:
        """
        Process video frames and count people
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError("Could not open video file")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Sample frames (every 2 seconds to reduce processing time)
            frame_interval = max(1, int(fps * 2))
            
            max_people_count = 0
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process every nth frame
                if frame_count % frame_interval == 0:
                    people_in_frame = self._detect_people_in_frame(frame)
                    max_people_count = max(max_people_count, people_in_frame)
                    
                    logger.debug(
                        f"Frame {frame_count}: {people_in_frame} people detected"
                    )
                
                frame_count += 1
            
            cap.release()
            
            logger.info(
                f"Processed {frame_count} frames, "
                f"max people count: {max_people_count}"
            )
            
            return max_people_count
        
        except Exception as e:
            logger.error(f"Error processing video frames: {str(e)}")
            raise
    
    def _detect_people_in_frame(self, frame) -> int:
        """
        Detect people in a single frame using YOLO
        """
        try:
            # Run YOLO inference
            results = self.model(frame, verbose=False)
            
            people_count = 0
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    # Count detections with class 0 (person) and confidence > 0.5
                    for box in boxes:
                        if (
                            box.cls.item() == 0 and  # person class
                            box.conf.item() > 0.5    # confidence threshold
                        ):
                            people_count += 1
            
            return people_count
        
        except Exception as e:
            logger.error(f"Error detecting people in frame: {str(e)}")
            return 0