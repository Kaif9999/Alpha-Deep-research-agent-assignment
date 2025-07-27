from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Dict, Optional

class PersonOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    title: Optional[str] = None
    company_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class CompanyOut(BaseModel):
    id: int
    name: str
    domain: Optional[str] = None
    campaign_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ContextSnippetOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    snippet_type: str
    content: str
    payload: Dict[str, str]
    source_urls: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class CampaignOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Request schemas
class PersonCreate(BaseModel):
    full_name: str
    email: EmailStr
    title: Optional[str] = None
    company_id: int

class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    campaign_id: int

class CampaignCreate(BaseModel):
    name: str
