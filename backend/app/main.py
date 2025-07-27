from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from rq import Queue
import uvicorn
import json
import logging

from .database import get_db, engine, get_redis_connection, get_redis_connection_websocket
from .models import Base, Campaign, Company, Person, ContextSnippet, SearchLog
from .schemas import PersonOut, CompanyOut, ContextSnippetOut
from .connection_manager import ConnectionManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Alpha Deep Research Agent API", 
    version="1.0.0",
    description="Advanced research agent implementing iterative search and quality validation"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global connections
conn_mgr = ConnectionManager()
redis_rq = get_redis_connection()
redis_websocket = get_redis_connection_websocket()
queue = Queue('default', connection=redis_rq)

@app.on_event("startup")
def seed_database():
    """Seed database with sample data as per PDF specification"""
    db = next(get_db())
    
    try:
        existing_campaigns = db.query(Campaign).count()
        if existing_campaigns == 0:
            # Create campaign
            campaign = Campaign(name="Alpha Research Campaign")
            db.add(campaign)
            db.flush()
            
            # Create company
            company = Company(
                name="Google",  # Changed from "Google LLC" to "Google"
                domain="google.com",
                campaign_id=campaign.id
            )
            db.add(company)
            db.flush()
            
            # Create sample people
            people_data = [
                {
                    "full_name": "Sundar Pichai",
                    "email": "sundar@google.com",
                    "title": "Chief Executive Officer",
                    "company_id": company.id
                },
                {
                    "full_name": "Jeff Dean",
                    "email": "jeff.dean@google.com",
                    "title": "Senior Fellow and SVP, Google Research and Google DeepMind",
                    "company_id": company.id
                }
            ]
            
            for person_data in people_data:
                person = Person(**person_data)
                db.add(person)
            
            db.commit()
            logger.info("✅ Database seeded successfully")
            logger.info(f"   - 1 Campaign: {campaign.name}")
            logger.info(f"   - 1 Company: {company.name}")
            logger.info(f"   - 2 People: {', '.join([p['full_name'] for p in people_data])}")
        else:
            logger.info(f"🔄 Database already contains {existing_campaigns} campaigns")
            
    except Exception as e:
        logger.error(f"❌ Database seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Alpha Deep Research Agent API", 
        "status": "running",
        "version": "1.0.0",
        "features": ["Iterative Research", "Quality Validation", "Real-time Progress", "Search Logging"]
    }

@app.get("/health", tags=["Health"])
def health_check():
    try:
        redis_rq.ping()
        redis_websocket.ping()
        
        # Test database connection
        db = next(get_db())
        db.execute(text("SELECT 1")).fetchone()
        db.close()
        
        return {
            "status": "healthy", 
            "redis": "connected", 
            "database": "connected",
            "worker_queue": queue.count if queue else "unknown"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# Debug endpoints as per PDF specification
@app.get("/debug/db", tags=["Debug"])
def debug_database(db: Session = Depends(get_db)):
    """Comprehensive database debugging"""
    try:
        result = db.execute(text("SELECT 1")).fetchall()
        
        counts = {
            "campaigns": db.query(Campaign).count(),
            "companies": db.query(Company).count(),
            "people": db.query(Person).count(),
            "context_snippets": db.query(ContextSnippet).count(),
            "search_logs": db.query(SearchLog).count()
        }
        
        return {
            "status": "connected",
            "test_query": result[0] if result else None,
            "record_counts": counts,
            "database_url": "Connected",
            "tables_created": True
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/debug/snippets", tags=["Debug"])
def debug_snippets(db: Session = Depends(get_db)):
    """Debug all context snippets with detailed analysis"""
    try:
        snippets = db.query(ContextSnippet).all()
        
        debug_info = []
        for snippet in snippets:
            debug_info.append({
                "id": snippet.id,
                "entity_type": snippet.entity_type,
                "entity_id": snippet.entity_id,
                "snippet_type": snippet.snippet_type,
                "payload_keys": list(snippet.payload.keys()) if snippet.payload else [],
                "payload_field_count": len(snippet.payload) if snippet.payload else 0,
                "source_urls_count": len(snippet.source_urls) if snippet.source_urls else 0,
                "content_length": len(snippet.content) if snippet.content else 0,
                "created_at": snippet.created_at.isoformat(),
                "quality_score": len(snippet.content) if snippet.content else 0
            })
        
        return {
            "total_snippets": len(snippets),
            "snippets": debug_info,
            "summary": {
                "avg_quality_score": sum(s["quality_score"] for s in debug_info) / len(debug_info) if debug_info else 0,
                "avg_fields_per_snippet": sum(s["payload_field_count"] for s in debug_info) / len(debug_info) if debug_info else 0
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/debug/search-logs", tags=["Debug"])
def debug_search_logs(db: Session = Depends(get_db)):
    """Debug search logs to show research iterations"""
    try:
        logs = db.query(SearchLog).order_by(SearchLog.created_at.desc()).limit(50).all()
        
        log_info = []
        for log in logs:
            log_info.append({
                "id": log.id,
                "context_snippet_id": log.context_snippet_id,
                "iteration": log.iteration,
                "query": log.query,
                "results_count": len(log.top_results) if log.top_results else 0,
                "created_at": log.created_at.isoformat()
            })
        
        return {
            "total_logs": len(log_info),
            "recent_logs": log_info,
            "unique_queries": len(set(log["query"] for log in log_info)),
            "iterations_tracked": len(set(log["iteration"] for log in log_info))
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/people", response_model=list[PersonOut], tags=["People"])
def list_people(db: Session = Depends(get_db)):
    """Get all people in the system"""
    return db.query(Person).all()

@app.get("/companies", response_model=list[CompanyOut], tags=["Companies"])
def list_companies(db: Session = Depends(get_db)):
    """Get all companies in the system"""
    return db.query(Company).all()

@app.post("/enrich/{person_id}", tags=["Research"])
def trigger_research(person_id: int, db: Session = Depends(get_db)):
    """Start comprehensive research job for a person"""
    try:
        # Validate person exists
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail=f"Person with ID {person_id} not found")
        
        company = db.query(Company).filter(Company.id == person.company_id).first()
        company_name = company.name if company else "Unknown Company"
        company_id = company.id if company else None  # Fixed typo: was "Nones"
        
        logger.info(f"🎯 Research request for {person.full_name} at {company_name} (Company ID: {company_id})")
        
        # Test connections
        try:
            redis_rq.ping()
            redis_websocket.ping()
            logger.info("✅ Redis connections verified")
        except Exception as redis_error:
            logger.error(f"❌ Redis connection failed: {redis_error}")
            raise HTTPException(status_code=503, detail="Redis service unavailable")
        
        # Clear queue and enqueue job
        try:
            queue.empty()
            logger.info("🧹 Cleared existing jobs")
        except Exception:
            pass
        
        job = queue.enqueue(
            "app.worker.run_agent",
            person_id,
            job_timeout=1200,  # 20 minutes for comprehensive research
            result_ttl=60,
            failure_ttl=3600
        )
        
        logger.info(f"🚀 Research job {job.id} enqueued successfully")
        
        # Send initial progress with correct company ID
        try:
            initial_progress = {
                "percent": 0,
                "msg": f"🚀 Starting comprehensive research for {person.full_name} at {company_name}",
                "job_id": job.id,
                "person_id": person_id,
                "company_id": company_id,  # Include company ID in progress
                "iteration": 1
            }
            redis_websocket.publish("research_progress", json.dumps(initial_progress))
        except Exception as e:
            logger.warning(f"⚠️  Could not send initial progress: {e}")
        
        return {
            "success": True,
            "job_id": job.id, 
            "status": "enqueued", 
            "person_id": person_id,
            "person_name": person.full_name,
            "company_id": company_id,  # Return company ID
            "company_name": company_name,
            "message": f"Comprehensive research started for {person.full_name} at {company_name}",
            "estimated_duration": "5-10 minutes",
            "features": ["Multi-iteration search", "Quality validation", "Source logging"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to enqueue research job: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/snippets/{company_id}", response_model=list[ContextSnippetOut], tags=["Results"])
def get_research_results(company_id: int, db: Session = Depends(get_db)):
    """Get comprehensive research results for a company"""
    # Get company info for logging
    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.name if company else f"Company {company_id}"
    
    snippets = db.query(ContextSnippet).filter(
        ContextSnippet.entity_id == company_id,
        ContextSnippet.entity_type == "company"
    ).order_by(ContextSnippet.created_at.desc()).all()
    
    logger.info(f"📊 Found {len(snippets)} research snippets for {company_name} (ID: {company_id})")
    
    if snippets:
        for snippet in snippets:
            logger.info(f"   - Snippet {snippet.id}: {len(snippet.payload) if snippet.payload else 0} fields")
    
    return snippets

@app.get("/search-logs/{snippet_id}", tags=["Research"])
def get_search_logs(snippet_id: int, db: Session = Depends(get_db)):
    """Get search logs for a specific research session"""
    logs = db.query(SearchLog).filter(
        SearchLog.context_snippet_id == snippet_id
    ).order_by(SearchLog.created_at.asc()).all()
    
    return {
        "snippet_id": snippet_id,
        "total_searches": len(logs),
        "searches": [
            {
                "id": log.id,
                "iteration": log.iteration,
                "query": log.query,
                "results_count": len(log.top_results) if log.top_results else 0,
                "timestamp": log.created_at.isoformat()
            }
            for log in logs
        ]
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time research progress"""
    await conn_mgr.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        conn_mgr.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
