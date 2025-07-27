import os
import sys
import time
import logging
import json
from redis import Redis
from rq import Worker, Queue, Connection
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.database import DATABASE_URL, get_redis_connection, get_redis_connection_websocket
from app.agent import ResearchAgent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Redis connections - separate for RQ and WebSocket
redis_conn = get_redis_connection()  # For RQ jobs (decode_responses=False)
redis_websocket = get_redis_connection_websocket()  # For WebSocket messages (decode_responses=True)

# Database setup for worker
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_agent(person_id: int):
    """Worker function to run research agent"""
    try:
        logger.info(f"🚀 Starting research for person {person_id}")
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Initialize and run agent with WebSocket Redis connection
            agent = ResearchAgent(db, redis_websocket)
            result = agent.research_person_sync(person_id)
            
            logger.info(f"✅ Research completed for person {person_id}")
            return result
            
        except Exception as agent_error:
            logger.error(f"Agent error for person {person_id}: {str(agent_error)}")
            raise agent_error
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Research failed for person {person_id}: {str(e)}")
        
        # Send error update via WebSocket Redis connection
        error_data = {
            "percent": 0,
            "msg": f"Research failed: {str(e)}",
            "error": True
        }
        try:
            redis_websocket.publish("research_progress", json.dumps(error_data))
        except Exception as redis_error:
            logger.error(f"Failed to publish error to Redis: {redis_error}")
        
        raise e

def clear_redis_completely():
    """Clear Redis completely to avoid encoding issues"""
    try:
        # Flush all Redis data
        redis_conn.flushdb()
        logger.info("🧹 Cleared all Redis data")
        
        # Also clear using websocket connection
        redis_websocket.flushdb()
        logger.info("🧹 Cleared WebSocket Redis data")
        
    except Exception as e:
        logger.error(f"Error clearing Redis: {e}")

def start_worker():
    """Start the RQ worker with proper error handling"""
    logger.info("🔧 Starting RQ Worker...")
    
    # Wait for Redis connection
    max_retries = 30
    for i in range(max_retries):
        try:
            redis_conn.ping()
            redis_websocket.ping()
            logger.info("✅ Connected to Redis")
            break
        except Exception as e:
            logger.warning(f"Waiting for Redis... ({i+1}/{max_retries}) - {str(e)}")
            time.sleep(2)
            if i == max_retries - 1:
                logger.error("❌ Could not connect to Redis")
                raise Exception("Could not connect to Redis")
    
    # Clear Redis completely to avoid any encoding issues
    clear_redis_completely()
    
    # Wait for database connection
    max_db_retries = 15
    for i in range(max_db_retries):
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                result.fetchone()
            logger.info("✅ Connected to Database")
            break
        except Exception as e:
            logger.warning(f"Waiting for Database... ({i+1}/{max_db_retries}) - {str(e)}")
            time.sleep(5)
            if i == max_db_retries - 1:
                logger.error(f"❌ Could not connect to Database")
                raise Exception("Could not connect to Database")
    
    # Start worker with proper connection
    try:
        with Connection(redis_conn):
            # Create worker with minimal configuration
            worker = Worker(['default'], connection=redis_conn)
            logger.info("🎯 Worker listening for jobs on 'default' queue...")
            
            # Start worker without scheduler to avoid conflicts
            worker.work(logging_level='INFO')
            
    except Exception as e:
        logger.error(f"❌ Worker failed to start: {e}")
        raise e

# Main execution
if __name__ == '__main__':
    try:
        start_worker()
    except KeyboardInterrupt:
        logger.info("👋 Worker shutting down gracefully...")
    except Exception as e:
        logger.error(f"💥 Worker crashed: {e}")
        sys.exit(1)
