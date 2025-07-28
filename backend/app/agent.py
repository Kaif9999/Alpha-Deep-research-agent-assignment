import os
import json
import time
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from redis import Redis
from dotenv import load_dotenv
from .models import Person, Company, ContextSnippet, SearchLog

load_dotenv()

try:
    from serpapi import GoogleSearch
    HAS_SERPAPI = True
except ImportError:
    HAS_SERPAPI = False

class ResearchAgent:
    def __init__(self, db: Session, redis_conn: Redis = None):
        self.db = db
        
        load_dotenv(override=True)
        
        self.serpapi_key = (
            os.getenv("SERPAPI_KEY") or 
            os.environ.get("SERPAPI_KEY") or
            "c055a1a3babcd12cae9ea939d17bf1765ae5b50b1379daf3f433cc642318a8be"
        )
        
        self.redis_conn = redis_conn
        self.use_real_search = HAS_SERPAPI and bool(self.serpapi_key)
        
        if self.use_real_search:
            try:
                test_params = {
                    "engine": "google",
                    "q": "OpenAI company",
                    "api_key": self.serpapi_key,
                    "num": 3,
                    "hl": "en",
                    "gl": "us"
                }
                
                search = GoogleSearch(test_params)
                result = search.get_dict()
                
                if "error" in result:
                    self.use_real_search = False
                elif "organic_results" not in result or len(result["organic_results"]) == 0:
                    self.use_real_search = False
                
            except Exception as e:
                self.use_real_search = False

        self.research_mode = "REAL_SEARCH" if self.use_real_search else "LIMITED"

    def send_progress_update(self, percent: int, message: str, query: str = None, found_fields: List[str] = None):
        progress_data = {
            "percent": percent,
            "msg": message,
            "query": query,
            "found_fields": found_fields or [],
            "research_mode": self.research_mode
        }
        
        try:
            if self.redis_conn:
                self.redis_conn.publish("research_progress", json.dumps(progress_data))
        except Exception as e:
            pass

    def generate_search_queries(self, company_name: str, research_field: str) -> List[str]:
        field_display = research_field.replace("_", " ")
        
        fallback_queries = [
            f'"{company_name}" {field_display} 2024',
            f'{company_name} {field_display} official website',
            f'{company_name} {field_display} news information'
        ]
        return fallback_queries

    def search_web_real(self, query: str) -> Dict[str, Any]:
        if not self.use_real_search or not self.serpapi_key:
            return {
                "organic_results": [],
                "query": query,
                "search_metadata": {"status": "SerpAPI not available"}
            }
            
        try:
            search_params = {
                "engine": "google",
                "q": query,
                "api_key": self.serpapi_key,
                "num": 10,
                "hl": "en",
                "gl": "us",
                "safe": "active",
                "start": 0,
                "tbm": None
            }
            
            search = GoogleSearch(search_params)
            result = search.get_dict()
            
            if "error" in result:
                return {
                    "organic_results": [],
                    "query": query,
                    "search_metadata": {"status": f"SerpAPI Error: {result['error']}"}
                }
            
            organic_results = result.get("organic_results", [])
            
            if len(organic_results) == 0:
                other_results = []
                for key in ["knowledge_graph", "answer_box", "featured_snippet", "top_stories"]:
                    if key in result:
                        other_results.append(key)
                
                fallback_results = []
                
                if "knowledge_graph" in result:
                    kg = result["knowledge_graph"]
                    fallback_results.append({
                        "title": kg.get("title", "Knowledge Graph Result"),
                        "link": kg.get("website", "https://www.google.com"),
                        "snippet": kg.get("description", "Information from Google Knowledge Graph")
                    })
                
                if "answer_box" in result:
                    ab = result["answer_box"]
                    fallback_results.append({
                        "title": ab.get("title", "Answer Box Result"),
                        "link": ab.get("link", "https://www.google.com"),
                        "snippet": ab.get("answer", ab.get("snippet", "Information from Google Answer Box"))
                    })
                
                if fallback_results:
                    return {
                        "organic_results": fallback_results,
                        "query": query,
                        "search_metadata": {"status": "Fallback results used"}
                    }
                
                return {
                    "organic_results": [],
                    "query": query,
                    "search_metadata": {"status": "No results found"}
                }
            
            return result
            
        except Exception as e:
            return {
                "organic_results": [],
                "query": query,
                "search_metadata": {"status": f"Search failed: {str(e)}"}
            }

    def analyze_search_results(self, search_results: Dict[str, Any], field: str, company_name: str) -> str:
        organic_results = search_results.get("organic_results", [])
        
        if not organic_results:
            return f"No search results found for {field.replace('_', ' ')}"
        
        content_pieces = []
        for i, result in enumerate(organic_results[:5], 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            
            if snippet and len(snippet.strip()) > 15:
                content_pieces.append({
                    "title": title,
                    "snippet": snippet,
                    "url": link
                })
        
        if not content_pieces:
            return f"No meaningful content found for {field.replace('_', ' ')}"
        
        combined_snippets = []
        for piece in content_pieces[:3]:
            if piece["snippet"]:
                combined_snippets.append(f"From {piece['url']}: {piece['snippet']}")
        
        combined = " | ".join(combined_snippets)
        return combined[:800] + ("..." if len(combined) > 800 else "")

    def research_person(self, person_id: int) -> Dict[str, Any]:
        try:
            person = self.db.query(Person).filter(Person.id == person_id).first()
            if not person:
                raise ValueError(f"Person {person_id} not found")
                
            company = self.db.query(Company).filter(Company.id == person.company_id).first()
            if not company:
                raise ValueError(f"Company not found for person {person_id}")

            research_fields = [
                "company_overview",
                "products_services", 
                "business_model",
                "pricing_strategy",
                "key_competitors",
                "recent_news"
            ]
            
            insights = {}
            all_source_urls = []
            successful_fields = 0
            
            self.send_progress_update(5, f"Starting {self.research_mode} research for {company.name}")
            
            for i, field in enumerate(research_fields, 1):
                progress = 5 + int((i / len(research_fields)) * 85)
                
                try:
                    queries = self.generate_search_queries(company.name, field)
                    primary_query = queries[0]
                    
                    self.send_progress_update(
                        progress, 
                        f"{self.research_mode} search: {field.replace('_', ' ')}", 
                        primary_query,
                        list(insights.keys())
                    )
                    
                    search_results = self.search_web_real(primary_query)
                    analysis = self.analyze_search_results(search_results, field, company.name)
                    
                    if analysis and len(analysis.strip()) > 30:
                        insights[field] = analysis.strip()
                        successful_fields += 1
                        
                        for result in search_results.get("organic_results", [])[:5]:
                            link = result.get("link", "")
                            if link and link.startswith(("http://", "https://")):
                                all_source_urls.append(link)
                    else:
                        insights[field] = f"Limited web information found for {field.replace('_', ' ')}"
                    
                    try:
                        search_log = SearchLog(
                            context_snippet_id=None,
                            iteration=str(i),
                            query=primary_query,
                            top_results=search_results.get("organic_results", [])[:5]
                        )
                        self.db.add(search_log)
                        self.db.flush()
                    except Exception as log_error:
                        pass
                    
                    time.sleep(3)
                    
                except Exception as field_error:
                    insights[field] = f"Research error for {field.replace('_', ' ')}: {str(field_error)}"

            self.send_progress_update(95, f"Saving {self.research_mode} research results...")

            unique_urls = list(set(all_source_urls))
            
            content_parts = []
            content_parts.append(f"{self.research_mode} RESEARCH REPORT FOR {company.name.upper()}")
            content_parts.append("=" * 60)
            content_parts.append(f"Generated using live SerpAPI Google search")
            content_parts.append(f"Research completed: {successful_fields}/{len(research_fields)} fields")
            content_parts.append(f"Real web sources: {len(unique_urls)}")
            content_parts.append(f"Research mode: {self.research_mode}")
            content_parts.append("")
            
            for field, insight in insights.items():
                field_name = field.replace('_', ' ').title()
                content_parts.append(f"{field_name}:")
                content_parts.append(f"{insight}")
                content_parts.append("")
            
            if unique_urls:
                content_parts.append("REAL WEB SOURCES:")
                for i, url in enumerate(unique_urls[:10], 1):
                    content_parts.append(f"{i}. {url}")
            
            content_text = "\n".join(content_parts)
            
            snippet_type = f"{self.research_mode.lower()}_research"
            
            snippet = ContextSnippet(
                entity_type="company",
                entity_id=company.id,
                snippet_type=snippet_type,
                content=content_text,
                payload=insights,
                source_urls=unique_urls
            )
            
            self.db.add(snippet)
            self.db.commit()
            self.db.refresh(snippet)
            
            try:
                from datetime import datetime, timedelta
                recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
                
                recent_logs = self.db.query(SearchLog).filter(
                    SearchLog.context_snippet_id.is_(None),
                    SearchLog.created_at > recent_cutoff
                ).all()
                
                for log in recent_logs:
                    log.context_snippet_id = snippet.id
                
                self.db.commit()
                
            except Exception as e:
                pass
            
            self.send_progress_update(100, f"{self.research_mode} research completed! {successful_fields}/{len(research_fields)} fields with live web data")
            
            return {
                "success": True,
                "snippet_id": snippet.id,
                "company_id": company.id,
                "company_name": company.name,
                "insights": insights,
                "source_urls": unique_urls,
                "research_mode": self.research_mode,
                "successful_fields": successful_fields,
                "total_fields": len(research_fields),
                "real_sources": len(unique_urls)
            }
            
        except Exception as e:
            error_msg = f"{self.research_mode} research failed: {str(e)}"
            self.db.rollback()
            self.send_progress_update(0, error_msg)
            raise e

    def research_person_sync(self, person_id: int) -> Dict[str, Any]:
        return self.research_person(person_id)
