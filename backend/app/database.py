import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from redis import Redis

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

required_vars = {
    "DATABASE_URL": DATABASE_URL,
    "SERPAPI_KEY": SERPAPI_KEY
}

missing_vars = [var for var, value in required_vars.items() if not value or len(str(value).strip()) == 0]

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    engine = None
    SessionLocal = None

def get_redis_connection():
    try:
        redis_conn = Redis.from_url(
            REDIS_URL, 
            decode_responses=False,
            encoding='utf-8',
            socket_keepalive=True,
            socket_keepalive_options={},
            retry_on_timeout=True,
            health_check_interval=30
        )
        redis_conn.ping()
        return redis_conn
    except Exception as e:
        return None

def get_redis_connection_websocket():
    try:
        redis_conn = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            encoding='utf-8',
            socket_keepalive=True,
            socket_keepalive_options={},
            retry_on_timeout=True,
            health_check_interval=30
        )
        redis_conn.ping()
        return redis_conn
    except Exception as e:
        return None

def get_db():
    if not SessionLocal:
        raise Exception("Database session not available - check DATABASE_URL")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database tables and seed with sample data"""
    from .models import Base, Campaign, Company, Person
    
    if not engine:
        print("No database engine available")
        return
    
    try:
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully")
        
        print("Seeding database with sample data...")
        seed_sample_data()
        print("Database seeded successfully")
        
    except Exception as e:
        print(f"Database initialization failed: {e}")

def seed_sample_data():
    """Seed database with 1 campaign, 1 company, and 2 people"""
    from .models import Campaign, Company, Person
    
    if not SessionLocal:
        return
    
    db = SessionLocal()
    try:
        existing_campaigns = db.query(Campaign).count()
        if existing_campaigns > 0:
            print(f"Database already contains {existing_campaigns} campaigns - skipping seed")
            return
        
        print("Creating sample campaign...")
        campaign = Campaign(name="Alpha Research Campaign")
        db.add(campaign)
        db.flush()
        print(f"Created campaign: {campaign.name} (ID: {campaign.id})")
        
        print("Creating sample company...")
        company = Company(
            name="Google",
            domain="google.com",
            campaign_id=campaign.id
        )
        db.add(company)
        db.flush()
        print(f"Created company: {company.name} (ID: {company.id})")
        
        print("Creating sample people...")
        people_data = [
            {
                "full_name": "Sundar Pichai",
                "email": "sundar@google.com",
                "title": "CEO"
            },
            {
                "full_name": "Ruth Porat",
                "email": "ruth@google.com", 
                "title": "CFO"
            }
        ]
        
        created_people = []
        for person_data in people_data:
            person = Person(
                full_name=person_data["full_name"],
                email=person_data["email"],
                title=person_data["title"],
                company_id=company.id
            )
            db.add(person)
            created_people.append(person)
            print(f"Created person: {person_data['full_name']} ({person_data['title']})")
        
        db.commit()
        
        for person in created_people:
            db.refresh(person)
        
        print("Sample data seeded successfully:")
        print(f"- Campaign: {campaign.name} (ID: {campaign.id})")
        print(f"- Company: {company.name} (ID: {company.id})")
        print(f"- People: {len(created_people)} executives")
        
        return {
            "campaign": campaign,
            "company": company,
            "people": created_people
        }
        
    except Exception as e:
        db.rollback()
        print(f"Failed to seed sample data: {e}")
        raise e
    finally:
        db.close()
