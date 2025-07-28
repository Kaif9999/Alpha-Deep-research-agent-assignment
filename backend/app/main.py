from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from rq import Queue
import json
import logging

from .database import get_db, get_redis_connection, get_redis_connection_websocket, init_database
from .models import Person, Company, ContextSnippet, SearchLog, Campaign
from .schemas import PersonOut, CompanyOut, ContextSnippetOut, CampaignOut, CampaignWithDetailsOut, CampaignCreate
from .worker import run_agent
from .connection_manager import ConnectionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alpha Deep Research Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

redis_conn = get_redis_connection()
redis_websocket = get_redis_connection_websocket()

queue = Queue('default', connection=redis_conn) if redis_conn else None

@app.on_event("startup")
async def startup_event():
    logger.info("Alpha Deep Research Agent starting up...")
    
    try:
        init_database()
        logger.info("Database initialized successfully")
        
        from .database import engine
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM campaigns"))
            campaign_count = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM companies"))
            company_count = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM people"))
            people_count = result.scalar()
            
            logger.info(f"Database ready: {campaign_count} campaigns, {company_count} companies, {people_count} people")
            
    except Exception as e:
        logger.error(f"Startup failed: {e}")

@app.get("/")
async def root():
    return {"message": "Alpha Deep Research Agent API", "status": "running"}

@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "redis": "connected" if redis_conn and redis_conn.ping() else "disconnected",
        "database": "connected",
        "worker_queue": queue.count if queue else 0
    }
    
    try:
        from .database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        health_status["database"] = "disconnected"
        health_status["status"] = "unhealthy"
    
    return health_status

@app.get("/debug/db")
async def debug_database(db: Session = Depends(get_db)):
    try:
        record_counts = {}
        
        campaigns_count = db.execute(text("SELECT COUNT(*) FROM campaigns")).scalar()
        record_counts["campaigns"] = campaigns_count
        
        companies_count = db.execute(text("SELECT COUNT(*) FROM companies")).scalar()
        record_counts["companies"] = companies_count
        
        people_count = db.execute(text("SELECT COUNT(*) FROM people")).scalar()
        record_counts["people"] = people_count
        
        snippets_count = db.execute(text("SELECT COUNT(*) FROM context_snippets")).scalar()
        record_counts["context_snippets"] = snippets_count
        
        search_logs_count = db.execute(text("SELECT COUNT(*) FROM search_logs")).scalar()
        record_counts["search_logs"] = search_logs_count
        
        sample_data = {}
        if campaigns_count > 0:
            campaign = db.query(Campaign).first()
            company = db.query(Company).filter(Company.campaign_id == campaign.id).first()
            people = db.query(Person).filter(Person.company_id == company.id).all() if company else []
            
            sample_data = {
                "campaign_name": campaign.name,
                "company_name": company.name if company else None,
                "people_names": [p.full_name for p in people]
            }
        
        return {
            "status": "connected",
            "record_counts": record_counts,
            "sample_data": sample_data,
            "timestamp": "2024-01-01T00:00:00Z"
        } # type: ignore
        
    except Exception as e:
        logger.error(f"Database debug error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "record_counts": {}
        } # type: ignore

@app.get("/campaigns", response_model=list[CampaignOut])
async def get_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    return campaigns

@app.get("/campaigns/{campaign_id}", response_model=CampaignWithDetailsOut)
async def get_campaign_details(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    company = db.query(Company).filter(Company.campaign_id == campaign_id).first()
    people = []
    
    if company:
        people = db.query(Person).filter(Person.company_id == company.id).all()
    
    return CampaignWithDetailsOut(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        created_at=campaign.created_at,
        company=company,
        people=people
    )

@app.post("/campaigns", response_model=CampaignWithDetailsOut)
async def create_campaign(campaign_data: CampaignCreate, db: Session = Depends(get_db)):
    try:
        campaign = Campaign(name=campaign_data.name)
        db.add(campaign)
        db.flush()
        
        company = Company(
            name=campaign_data.company.name,
            domain=campaign_data.company.domain,
            campaign_id=campaign.id
        )
        db.add(company)
        db.flush()
        
        people = []
        for person_data in campaign_data.people:
            person = Person(
                full_name=person_data.full_name,
                email=person_data.email,
                title=person_data.title,
                company_id=company.id
            )
            db.add(person)
            people.append(person)
        
        db.commit()
        db.refresh(campaign)
        db.refresh(company)
        for person in people:
            db.refresh(person)
        
        logger.info(f"Created campaign {campaign.id} with company {company.name} and {len(people)} people")
        
        return CampaignWithDetailsOut(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            created_at=campaign.created_at,
            company=company,
            people=people
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create campaign: {str(e)}")

@app.get("/people", response_model=list[PersonOut])
async def get_people(db: Session = Depends(get_db)):
    people = db.query(Person).all()
    return people

@app.get("/companies", response_model=list[CompanyOut])
async def get_companies(db: Session = Depends(get_db)):
    companies = db.query(Company).all()
    return companies

@app.get("/snippets/{company_id}", response_model=list[ContextSnippetOut])
async def get_context_snippets(company_id: int, db: Session = Depends(get_db)):
    snippets = db.query(ContextSnippet).filter(
        ContextSnippet.entity_type == "company",
        ContextSnippet.entity_id == company_id
    ).all()
    
    if not snippets:
        raise HTTPException(status_code=404, detail="No context snippets found for this company")
    
    return snippets

@app.post("/enrich/{person_id}")
async def enrich_person(person_id: int, db: Session = Depends(get_db)):
    if not queue:
        raise HTTPException(status_code=503, detail="Worker queue not available")
    
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    company = db.query(Company).filter(Company.id == person.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    try:
        job = queue.enqueue(
            run_agent, 
            person_id,
            job_timeout=1800
        )
        
        logger.info(f"Queued research job {job.id} for person {person_id} ({person.full_name})")
        
        return {
            "success": True,
            "job_id": job.id,
            "person_id": person_id,
            "person_name": person.full_name,
            "company_id": company.id,
            "company_name": company.name,
            "estimated_duration": "5-10 minutes",
            "message": f"Research started for {person.full_name} at {company.name}"
        }
        
    except Exception as e:
        logger.error(f"Failed to queue research job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start research: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"WebSocket received: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.get("/test")
async def test_endpoint():
    return {
        "message": "API is working",
        "timestamp": "2024-01-01T00:00:00Z",
        "components": {
            "database": "connected",
            "redis": "connected" if redis_conn else "disconnected",
            "queue": "available" if queue else "unavailable"
        }
    }
