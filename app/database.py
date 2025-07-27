import os
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import logging
from .models import Base, VideoAnalysis
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
logger.debug("Loading environment variables from .env file")
load_dotenv()  # Load from parent directory
logger.debug("Environment variables loaded")

# Database configuration
logger.debug("Reading database configuration from environment variables")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
db_port = os.getenv("DB_PORT", "5432")

# Debug environment variables (without exposing password)
logger.debug(f"DB_USER: {db_user}")
logger.debug(f"DB_HOST: {db_host}")
logger.debug(f"DB_NAME: {db_name}")
logger.debug(f"DB_PORT: {db_port}")
logger.debug(f"DB_PASSWORD: {'***HIDDEN***' if db_password else 'NOT SET'}")

# Check for missing required environment variables
missing_vars = []
if not db_user:
    missing_vars.append("DB_USER")
if not db_password:
    missing_vars.append("DB_PASSWORD")
if not db_host:
    missing_vars.append("DB_HOST")
if not db_name:
    missing_vars.append("DB_NAME")

if missing_vars:
    error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
    logger.error(error_msg)
    raise ValueError(error_msg)

logger.debug("All required environment variables are present")

try:
    url = URL.create(
        drivername="postgresql+asyncpg",
        username=db_user,
        password=db_password,
        host=db_host,
        database=db_name,
        port=db_port
    )
    logger.info(f"Database URL created: postgresql+asyncpg://{db_user}:***@{db_host}:{db_port}/{db_name}")
except Exception as e:
    logger.error(f"Failed to create database URL: {e}")
    raise
# Create async engine
logger.debug("Creating async database engine")
try:
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Create session factory
logger.debug("Creating session factory")
try:
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info("Session factory created successfully")
except Exception as e:
    logger.error(f"Failed to create session factory: {e}")
    raise


async def create_tables():
    """Create database tables"""
    logger.debug("Attempting to create database tables")
    try:
        async with engine.begin() as conn:
            logger.debug("Database connection established for table creation")
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise


@asynccontextmanager
async def get_db_session():
    """Get database session context manager"""
    logger.debug("Creating new database session")
    session = None
    try:
        session = AsyncSessionLocal()
        logger.debug("Database session created successfully")
        
        # Test the connection
        await session.execute("SELECT 1")
        logger.debug("Database connection test successful")
        
        yield session
        logger.debug("Database session completed successfully")
    except Exception as e:
        logger.error(f"Database session error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        if session:
            try:
                await session.rollback()
                logger.debug("Database session rolled back")
            except Exception as rollback_error:
                logger.error(f"Failed to rollback session: {rollback_error}")
        raise
    finally:
        if session:
            try:
                await session.close()
                logger.debug("Database session closed")
            except Exception as close_error:
                logger.error(f"Failed to close session: {close_error}")


async def test_database_connection():
    """Test database connection and return status"""
    logger.info("Testing database connection...")
    try:
        async with get_db_session() as session:
            result = await session.execute("SELECT version()")
            db_version = result.scalar()
            logger.info(f"Database connection successful! PostgreSQL version: {db_version}")
            return True, f"Connected to PostgreSQL: {db_version}"
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        return False, str(e)


# Make VideoAnalysis available at module level
__all__ = ["VideoAnalysis", "get_db_session", "create_tables", "test_database_connection"]