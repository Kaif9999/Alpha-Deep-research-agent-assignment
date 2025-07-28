from sqlalchemy import Column, Integer, Text, DateTime, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    domain = Column(Text)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    title = Column(Text)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class ContextSnippet(Base):
    __tablename__ = "context_snippets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    snippet_type = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False)
    source_urls = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class SearchLog(Base):
    __tablename__ = "search_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    context_snippet_id = Column(Integer, ForeignKey("context_snippets.id"), nullable=True)
    iteration = Column(Text, nullable=False)
    query = Column(Text, nullable=False)
    top_results = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
