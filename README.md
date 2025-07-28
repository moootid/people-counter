# People Counter API

A high-performance FastAPI-based microservice for counting people in videos using YOLO11 deep learning models. This service processes videos from S3 URLs and provides real-time people counting with comprehensive monitoring and observability.

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-moootid%2Fpeople--counter%3Alatest-blue?logo=docker)](https://hub.docker.com/r/moootid/people-counter)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![YOLO](https://img.shields.io/badge/YOLO-v11-ff6b35?logo=yolo)](https://ultralytics.com/)

## Features

- 🎥 **Video Processing**: Process videos from S3 URLs or HTTPS links
- 👥 **People Detection**: YOLO11-based real-time people counting
- 🚀 **Async Processing**: Background task processing with job status tracking
- 📊 **Prometheus Metrics**: Comprehensive monitoring and observability
- 🐳 **Docker Ready**: Containerized with multi-stage builds
- 🔧 **GPU Support**: CUDA acceleration for faster inference
- 💾 **Database Integration**: PostgreSQL/CockroachDB for persistent storage
- 🔍 **Health Checks**: Built-in health monitoring endpoints
- 📝 **Structured Logging**: Detailed logging for debugging and monitoring

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client App    │───▶│  People Counter  │───▶│   Video Store   │
│                 │    │      API         │    │   (S3/HTTPS)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │    Database      │
                       │ (PostgreSQL/     │
                       │  CockroachDB)    │
                       └──────────────────┘
```

## Quick Start

### Using Docker (Recommended)

```bash
# Pull and run the latest image
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
  -e AWS_ACCESS_KEY_ID="your-access-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret-key" \
  -e AWS_DEFAULT_REGION="us-east-1" \
  moootid/people-counter:latest
```

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/moootid/people-counter.git
cd people-counter

# Start the service
docker-compose up -d
```

### Local Development

```bash
# Clone the repository
git clone https://github.com/moootid/people-counter.git
cd people-counter

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/peoplecount"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

### Endpoints

#### `POST /analyze-video`
Start video analysis job

**Request Body:**
```json
{
  "s3_url": "s3://bucket-name/path/to/video.mp4",
  "video_id": "optional-video-id",
  "user": "user-id-or-number"
}
```

**Response:**
```json
{
  "job_id": "uuid-generated-job-id",
  "status": "processing",
  "message": "Video analysis started"
}
```

#### `GET /status/{job_id}`
Get job status and results

**Response:**
```json
{
  "job_id": "job-uuid",
  "video_id": "video-uuid",
  "status": "completed",
  "people_count": 5,
  "created_at": "2025-07-28T10:00:00Z",
  "completed_at": "2025-07-28T10:02:30Z",
  "error_message": null
}
```

#### `GET /health`
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-07-28T10:00:00Z",
  "version": "1.0.0",
  "database": {
    "status": "healthy",
    "message": "Connection successful"
  },
  "video_processor": {
    "status": "healthy",
    "message": "Video processor initialized on cuda",
    "model_path": "yolo11n.pt"
  }
}
```

#### `GET /metrics`
Prometheus metrics endpoint for monitoring

### Interactive API Documentation

Once the service is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | - |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 | No* | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 | No* | - |
| `AWS_DEFAULT_REGION` | AWS region | No | `us-east-1` |
| `YOLO_MODEL_PATH` | Path to YOLO model file | No | `yolo11n.pt` |
| `ENABLE_METRICS` | Enable Prometheus metrics | No | `true` |

*Required for S3 URLs. HTTPS URLs work without AWS credentials.

### Database Setup

The service supports PostgreSQL and CockroachDB. Create the database and tables:

```sql
-- Example PostgreSQL setup
CREATE DATABASE peoplecount;
-- Tables are created automatically via SQLAlchemy
```

## Monitoring

### Prometheus Metrics

The service exposes comprehensive metrics at `/metrics`:

- **Request metrics**: Request duration, size, status codes
- **Business metrics**: Video processing duration, people count distribution
- **System metrics**: Active jobs, success/failure rates
- **Resource metrics**: Memory usage (when psutil is available)

### Custom Metrics

- `people_counter_video_analysis_requests_total`: Total analysis requests
- `people_counter_video_processing_duration_seconds`: Processing time histogram
- `people_counter_people_count_distribution`: People count distribution
- `people_counter_active_jobs`: Currently active processing jobs

### Logging

Structured logging with different levels:
- Request/response logging
- Error tracking with full stack traces
- Performance monitoring
- Kubernetes pod information

## Performance

### Hardware Requirements

**Minimum (CPU only):**
- 2 CPU cores
- 4GB RAM
- 10GB disk space

**Recommended (GPU):**
- 4 CPU cores
- 8GB RAM
- NVIDIA GPU with 4GB VRAM
- 20GB disk space

### Performance Characteristics

- **CPU Processing**: ~30-60 seconds per minute of video
- **GPU Processing**: ~10-30 seconds per minute of video
- **Concurrent Jobs**: 2 (configurable via ThreadPoolExecutor)
- **Model Size**: YOLO11n (~6MB) for optimal speed/accuracy balance

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: people-counter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: people-counter
  template:
    metadata:
      labels:
        app: people-counter
    spec:
      containers:
      - name: people-counter
        image: moootid/people-counter:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: database-url
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
            nvidia.com/gpu: 1
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
```

### Docker Compose with GPU

```yaml
version: '3.8'
services:
  people-counter:
    image: moootid/people-counter:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/peoplecount
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
```

## Development

### Project Structure

```
people-counter/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # Database configuration
│   └── video_processor.py   # YOLO video processing
├── requirements.txt         # Python dependencies
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Local development setup
├── yolo11n.pt             # YOLO model file
└── debug_production.py    # Debug utilities
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## Troubleshooting

### Common Issues

**1. CUDA not available**
```bash
# Check CUDA installation
nvidia-smi
# Or run CPU-only mode by setting device to 'cpu'
```

**2. Database connection failed**
```bash
# Test database connection
python test_db_connection.py
```

**3. S3 access denied**
```bash
# Check AWS credentials
aws s3 ls s3://your-bucket/
```

**4. Out of memory**
```bash
# Monitor memory usage
docker stats
# Reduce concurrent workers in video_processor.py
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run debug script
python debug_production.py
```

### Health Check Debugging

```bash
# Check service health
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 **Issues**: [GitHub Issues](https://github.com/moootid/people-counter/issues)
- 📖 **Documentation**: [API Docs](http://localhost:8000/docs)
- 🐳 **Docker Hub**: [moootid/people-counter](https://hub.docker.com/r/moootid/people-counter)

## Acknowledgments

- [Ultralytics YOLO](https://ultralytics.com/) for the excellent object detection framework
- [FastAPI](https://fastapi.tiangolo.com/) for the high-performance web framework
- [PyTorch](https://pytorch.org/) for the deep learning foundation
