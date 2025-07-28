import os
import sys
import time
import logging
import json
from redis import Redis
from rq import Worker, Queue, Connection
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(override=True)

if os.path.exists('.env'):
    load_dotenv('.env', override=True)

serpapi_key = os.getenv("SERPAPI_KEY")

if not serpapi_key:
    os.environ["SERPAPI_KEY"] = "c055a1a3babcd12cae9ea939d17bf1765ae5b50b1379daf3f433cc642318a8be"

sys.path.insert(0, '/app')

from app.database import DATABASE_URL, get_redis_connection, get_redis_connection_websocket, init_database
from app.agent import ResearchAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_agent(person_id: int):
    logger.info(f"Worker starting research for person_id: {person_id}")
    
    try:
        if not isinstance(person_id, int):
            person_id = int(person_id)
        
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
            
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        redis_conn = get_redis_connection_websocket()
        
        logger.info(f"Database and Redis connections established")
        
        try:
            logger.info(f"Initializing research agent...")
            agent = ResearchAgent(db=db, redis_conn=redis_conn)
            
            logger.info(f"Starting research with live APIs...")
            
            result = agent.research_person_sync(person_id)
            
            logger.info(f"Research completed successfully!")
            logger.info(f"Snippet ID: {result.get('snippet_id')}")
            logger.info(f"Company: {result.get('company_name')}")
            logger.info(f"Research mode: {result.get('research_mode')}")
            logger.info(f"Successful fields: {result.get('successful_fields')}")
            logger.info(f"Real sources: {result.get('real_sources')}")
            
            return result
            
        except Exception as research_error:
            logger.error(f"Research failed for person {person_id}: {research_error}")
            
            try:
                error_data = {
                    "percent": 0,
                    "msg": f"Research failed: {str(research_error)}",
                    "error": True,
                    "person_id": person_id,
                    "research_mode": "REAL_SEARCH"
                }
                if redis_conn:
                    redis_conn.publish("research_progress", json.dumps(error_data))
            except Exception as redis_error:
                logger.error(f"Failed to publish error update: {redis_error}")
            
            raise research_error
            
        finally:
            db.close()
            logger.info(f"Database session closed for person {person_id}")
            
    except Exception as e:
        logger.error(f"Worker job failed for person {person_id}: {e}")
        raise e

if __name__ == "__main__":
    logger.info("Alpha Deep Research Agent Worker")
    
    try:
        logger.info("Initializing database on worker startup...")
        init_database()
        
        redis_conn = get_redis_connection()
        if not redis_conn:
            logger.error("Failed to connect to Redis - worker cannot start")
            sys.exit(1)
            
        logger.info("Starting RQ Worker...")
        logger.info("Connected to Redis")
        
        if DATABASE_URL:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Connected to Database")
        else:
            logger.error("DATABASE_URL not configured")
            sys.exit(1)
        
        with Connection(redis_conn):
            queue = Queue('default')
            worker = Worker([queue])
            
            logger.info("Worker listening for research jobs...")
            
            worker.work(with_scheduler=True)
            
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker startup failed: {e}")
        sys.exit(1)
