import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from redis import Redis

# Load environment variables
load_dotenv()

# Access environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create database engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Redis connection with consistent encoding for RQ
def get_redis_connection():
    return Redis.from_url(
        REDIS_URL, 
        decode_responses=False,
        encoding='utf-8',
        socket_keepalive=True,
        socket_keepalive_options={},
        retry_on_timeout=True,
        health_check_interval=30
    )

# Separate Redis connection for WebSocket messages (needs decode_responses=True)
def get_redis_connection_websocket():
    return Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        encoding='utf-8',
        socket_keepalive=True,
        socket_keepalive_options={},
        retry_on_timeout=True,
        health_check_interval=30
    )

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
