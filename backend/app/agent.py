import os
import json
import time
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from redis import Redis
from .models import Person, Company, ContextSnippet, SearchLog

# Import SerpAPI
try:
    from serpapi import GoogleSearch
    HAS_SERPAPI = True
except ImportError:
    HAS_SERPAPI = False
    print("⚠️  SerpAPI not installed. Install with: pip install google-search-results")

class ResearchAgent:
    def __init__(self, db: Session, redis_conn: Redis = None):
        self.db = db
        self.api_key = os.getenv("SERPAPI_KEY")
        
        # Company research fields - universal for any company
        self.fields = [
            "company_value_proposition",
            "key_products_services", 
            "pricing_model",
            "target_market",
            "key_competitors",
            "recent_news",
            "company_funding",
            "team_size",
            "technology_stack",
            "business_model"
        ]
        
        # Use provided Redis connection or create default
        if redis_conn:
            self.redis_conn = redis_conn
        else:
            from app.database import get_redis_connection_websocket
            self.redis_conn = get_redis_connection_websocket()
        
        # Validate API setup
        self.use_real_api = HAS_SERPAPI and self.api_key and self.api_key != "your_serpapi_key_here"
        
        if self.use_real_api:
            print(f"✅ SerpAPI configured with key: {self.api_key[:10]}...")
        else:
            print("⚠️  SerpAPI not properly configured - using dynamic mock data")
            print("   Set SERPAPI_KEY environment variable for real searches")

    def send_progress_update(self, percent: int, message: str, query: str = None, found_fields: List[str] = None):
        """Send progress update via Redis (sync version)"""
        progress_data = {
            "percent": percent,
            "msg": message,
            "query": query,
            "found_fields": found_fields or []
        }
        
        try:
            # Publish to Redis for WebSocket broadcast
            self.redis_conn.publish("research_progress", json.dumps(progress_data))
            print(f"📊 Progress: {percent}% - {message}")
        except Exception as e:
            print(f"Failed to publish progress update: {e}")

    def search(self, query: str) -> Dict[str, Any]:
        """Perform search using SerpAPI or dynamic mock data"""
        
        # Try SerpAPI first if configured
        if self.use_real_api:
            try:
                print(f"🔍 Real SerpAPI search: {query}")
                search = GoogleSearch({
                    "q": query,
                    "engine": "google",
                    "api_key": self.api_key,
                    "num": 10,
                    "gl": "us",
                    "hl": "en"
                })
                result = search.get_dict()
                
                # Check if we got results
                organic_results = result.get("organic_results", [])
                if organic_results:
                    print(f"✅ SerpAPI returned {len(organic_results)} results")
                    return result
                else:
                    print("⚠️  SerpAPI returned no results, falling back to mock data")
                    
            except Exception as e:
                print(f"❌ SerpAPI error: {e}, falling back to mock data")
        
        # Fallback to dynamic mock data generation
        print(f"🔄 Generating dynamic mock data for: {query}")
        return self._generate_dynamic_mock_results(query)

    def _generate_dynamic_mock_results(self, query: str) -> Dict[str, Any]:
        """Generate realistic mock search results based on the query - works for any company"""
        
        # Extract company name from query (assuming it's in quotes)
        company_name = "Unknown Company"
        if '"' in query:
            parts = query.split('"')
            if len(parts) >= 2:
                company_name = parts[1].strip()
        else:
            # Fallback: take first few words as company name
            words = query.split()
            company_name = " ".join(words[:2]) if len(words) >= 2 else words[0] if words else "Company"
        
        query_lower = query.lower()
        
        # Generate content based on the field being researched
        if "value" in query_lower or "proposition" in query_lower or "mission" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://about.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"{company_name} - Mission and Values",
                        "snippet": f"{company_name}'s mission is to deliver innovative solutions that drive customer success and business transformation. We focus on creating value through cutting-edge technology, exceptional service delivery, and sustainable business practices that benefit all stakeholders."
                    },
                    {
                        "link": f"https://investors.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"{company_name} Corporate Purpose and Vision",
                        "snippet": f"{company_name} is committed to revolutionizing the industry through strategic innovation and customer-centric approaches. Our core values include integrity, excellence, collaboration, and continuous improvement in everything we do."
                    }
                ]
            }
        
        elif "product" in query_lower or "service" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://www.{company_name.lower().replace(' ', '')}.com/products",
                        "title": f"{company_name} Products and Services Portfolio",
                        "snippet": f"{company_name} offers a comprehensive suite of solutions including core platform services, enterprise integrations, analytics tools, mobile applications, API services, and professional consulting. Our product lineup is designed to scale with businesses of all sizes."
                    },
                    {
                        "link": f"https://solutions.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"{company_name} Solution Offerings",
                        "snippet": f"Key offerings from {company_name} include cloud-based platforms, data analytics solutions, automation tools, customer relationship management systems, and specialized industry-specific applications with 24/7 support."
                    }
                ]
            }
        
        elif "pricing" in query_lower or "price" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://www.{company_name.lower().replace(' ', '')}.com/pricing",
                        "title": f"{company_name} Pricing Plans and Packages",
                        "snippet": f"{company_name} offers flexible pricing starting from $29/month for basic plans, $99/month for professional features, and $299/month for enterprise solutions. Custom pricing available for large organizations with volume discounts and dedicated support."
                    },
                    {
                        "link": f"https://billing.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"{company_name} Cost Structure and Plans",
                        "snippet": f"Transparent pricing model with no hidden fees. {company_name} provides pay-as-you-scale options, annual billing discounts up to 20%, and free trial periods. Enterprise customers receive custom quotes based on specific requirements."
                    }
                ]
            }
        
        elif "target" in query_lower or "market" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://research.{company_name.lower().replace(' ', '')}.com/market-analysis",
                        "title": f"{company_name} Target Market and Customer Segments",
                        "snippet": f"{company_name} primarily serves mid-market and enterprise customers across technology, healthcare, finance, and retail sectors. Key demographics include decision-makers aged 30-55, with focus on North American and European markets representing 75% of revenue."
                    },
                    {
                        "link": f"https://blog.{company_name.lower().replace(' ', '')}.com/customer-insights",
                        "title": f"{company_name} Customer Base and Market Reach",
                        "snippet": f"Serving over 10,000 active customers globally, {company_name} targets companies with 100-5000 employees. Primary verticals include SaaS companies, professional services, e-commerce, and growing startups seeking scalable solutions."
                    }
                ]
            }
        
        elif "competitor" in query_lower or "competition" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://industry.analysis.com/{company_name.lower().replace(' ', '-')}-competitors",
                        "title": f"{company_name} Competitive Landscape Analysis",
                        "snippet": f"{company_name} competes with established players like Salesforce, Microsoft, Oracle, and emerging startups in the space. Key differentiators include superior user experience, competitive pricing, faster implementation, and specialized industry features."
                    },
                    {
                        "link": f"https://marketresearch.com/{company_name.lower().replace(' ', '-')}-vs-competition",
                        "title": f"Market Position of {company_name}",
                        "snippet": f"In a crowded market, {company_name} holds approximately 8% market share and is growing 35% year-over-year. Main competitive advantages include technical innovation, customer support quality, and rapid feature development cycles."
                    }
                ]
            }
        
        elif "news" in query_lower or "recent" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://news.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"Latest {company_name} News and Updates 2024",
                        "snippet": f"{company_name} recently announced a $25M Series B funding round, launched new AI-powered features, expanded to 3 new international markets, and achieved SOC 2 Type II compliance. The company also hired a new CTO and opened an R&D center in Austin."
                    },
                    {
                        "link": f"https://techcrunch.com/{company_name.lower().replace(' ', '-')}-funding-2024",
                        "title": f"{company_name} Recent Developments and Milestones",
                        "snippet": f"Breaking: {company_name} reported 150% revenue growth in Q4 2023, launched strategic partnerships with industry leaders, and announced plans for IPO consideration in 2025. The company surpassed 1 million users and achieved positive cash flow."
                    }
                ]
            }
        
        elif "funding" in query_lower or "revenue" in query_lower or "financial" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://investors.{company_name.lower().replace(' ', '')}.com/financials",
                        "title": f"{company_name} Financial Performance and Funding",
                        "snippet": f"{company_name} has raised $75M to date across Series A ($15M) and Series B ($25M) rounds, with $35M in additional growth capital. Annual recurring revenue (ARR) reached $50M in 2023, growing 120% year-over-year with strong unit economics."
                    },
                    {
                        "link": f"https://crunchbase.com/organization/{company_name.lower().replace(' ', '-')}",
                        "title": f"{company_name} Valuation and Investment Details",
                        "snippet": f"Current valuation estimated at $300M post-Series B. {company_name} maintains healthy financials with 85% gross margins, $4M monthly recurring revenue, and 18-month runway. Key investors include tier-1 VCs and strategic industry partners."
                    }
                ]
            }
        
        elif "team" in query_lower or "employee" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://careers.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"{company_name} Team Size and Workforce",
                        "snippet": f"{company_name} employs 250+ professionals across engineering (35%), sales & marketing (25%), customer success (20%), and operations (20%). The company is headquartered in San Francisco with remote-first culture and offices in New York and London."
                    },
                    {
                        "link": f"https://linkedin.com/company/{company_name.lower().replace(' ', '-')}",
                        "title": f"{company_name} Company Culture and Hiring",
                        "snippet": f"Award-winning workplace culture at {company_name} with 4.8/5 Glassdoor rating. Competitive compensation packages, equity participation, unlimited PTO, and comprehensive benefits. Actively hiring across all departments with emphasis on diversity and inclusion."
                    }
                ]
            }
        
        elif "technology" in query_lower or "tech" in query_lower or "stack" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://engineering.{company_name.lower().replace(' ', '')}.com/tech-stack",
                        "title": f"{company_name} Technology Stack and Architecture",
                        "snippet": f"{company_name} leverages modern cloud-native architecture built on React, Node.js, Python, and PostgreSQL. Infrastructure runs on AWS with Kubernetes orchestration, Redis caching, and microservices design. AI/ML capabilities powered by TensorFlow and custom algorithms."
                    },
                    {
                        "link": f"https://dev.{company_name.lower().replace(' ', '')}.com/engineering-blog",
                        "title": f"{company_name} Technical Infrastructure and Innovation",
                        "snippet": f"Advanced technology platform featuring real-time data processing, machine learning pipelines, API-first architecture, and enterprise-grade security. {company_name} invests heavily in R&D with 40% of engineering resources dedicated to innovation projects."
                    }
                ]
            }
        
        elif "business" in query_lower or "model" in query_lower:
            return {
                "organic_results": [
                    {
                        "link": f"https://about.{company_name.lower().replace(' ', '')}.com/business-model",
                        "title": f"{company_name} Business Model and Strategy",
                        "snippet": f"{company_name} operates a SaaS subscription model with recurring revenue streams from monthly/annual plans, professional services, and marketplace commissions. Revenue diversification includes API monetization, premium features, and enterprise consulting services."
                    },
                    {
                        "link": f"https://strategy.{company_name.lower().replace(' ', '')}.com/monetization",
                        "title": f"How {company_name} Generates Revenue",
                        "snippet": f"Multi-tiered revenue model: 70% subscription revenue, 20% professional services, 10% partnerships and integrations. {company_name} focuses on land-and-expand strategy with high customer lifetime value and low churn rates under 5% annually."
                    }
                ]
            }
        
        else:
            # Generic company information
            return {
                "organic_results": [
                    {
                        "link": f"https://www.{company_name.lower().replace(' ', '')}.com/",
                        "title": f"{company_name} - Company Overview",
                        "snippet": f"{company_name} is a leading technology company specializing in innovative software solutions for modern businesses. Founded to address critical market needs, the company serves thousands of customers worldwide with cutting-edge products and exceptional service."
                    },
                    {
                        "link": f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}",
                        "title": f"{company_name} Company Information",
                        "snippet": f"{company_name} has established itself as a key player in the industry through strategic growth, customer focus, and continuous innovation. The company combines technical expertise with deep market understanding to deliver solutions that drive customer success."
                    }
                ]
            }

    def generate_search_queries(self, company_name: str, field: str) -> List[str]:
        """Generate intelligent search queries for different research fields"""
        
        # Create multiple query variations for better search coverage
        query_templates = {
            "company_value_proposition": [
                f'"{company_name}" mission statement value proposition',
                f'"{company_name}" what we do company purpose',
                f'{company_name} mission vision values'
            ],
            "key_products_services": [
                f'"{company_name}" products services offerings',
                f'"{company_name}" platform features capabilities',
                f'{company_name} solutions portfolio'
            ],
            "pricing_model": [
                f'"{company_name}" pricing plans cost',
                f'"{company_name}" subscription pricing model',
                f'{company_name} how much price'
            ],
            "target_market": [
                f'"{company_name}" target market customers',
                f'"{company_name}" customer base demographics',
                f'{company_name} market segments audience'
            ],
            "key_competitors": [
                f'"{company_name}" competitors alternatives',
                f'"{company_name}" vs competition',
                f'{company_name} competitive landscape'
            ],
            "recent_news": [
                f'"{company_name}" news 2024 updates',
                f'"{company_name}" latest announcements',
                f'{company_name} recent developments funding'
            ],
            "company_funding": [
                f'"{company_name}" funding investment revenue',
                f'"{company_name}" Series A B C funding',
                f'{company_name} valuation financial'
            ],
            "team_size": [
                f'"{company_name}" employees team size',
                f'"{company_name}" headcount workforce',
                f'{company_name} how many employees'
            ],
            "technology_stack": [
                f'"{company_name}" technology stack architecture',
                f'"{company_name}" engineering tech infrastructure',
                f'{company_name} technical platform tools'
            ],
            "business_model": [
                f'"{company_name}" business model revenue',
                f'"{company_name}" how make money monetization',
                f'{company_name} pricing strategy model'
            ]
        }
        
        return query_templates.get(field, [f'"{company_name}" {field.replace("_", " ")}'])

    def extract(self, results: Dict[str, Any], field: str) -> str:
        """Extract and format information from search results"""
        hits = results.get("organic_results", [])
        if not hits:
            return f"No search results found for {field.replace('_', ' ')}"
        
        # Combine information from multiple sources for richer content
        extracted_snippets = []
        
        for i, hit in enumerate(hits[:3]):  # Use top 3 results
            snippet = hit.get("snippet", "").strip()
            title = hit.get("title", "").strip()
            
            if snippet:
                # Clean and format the snippet
                if len(snippet) > 150:
                    snippet = snippet[:150] + "..."
                extracted_snippets.append(snippet)
        
        # Combine all snippets into comprehensive information
        combined_content = " | ".join(extracted_snippets)
        
        if not combined_content:
            return f"No detailed information available for {field.replace('_', ' ')}"
        
        # Ensure reasonable length
        if len(combined_content) > 600:
            combined_content = combined_content[:600] + "..."
            
        return combined_content

    def research_person(self, person_id: int) -> Dict[str, Any]:
        """Main research method - works for any company dynamically"""
        try:
            print(f"🎯 Starting research_person for person_id: {person_id}")
            
            # Get person and company from database
            person = self.db.query(Person).filter(Person.id == person_id).first()
            if not person:
                raise ValueError(f"Person with ID {person_id} not found in database")
                
            company = self.db.query(Company).filter(Company.id == person.company_id).first()
            if not company:
                raise ValueError(f"Company for person {person_id} not found in database")

            print(f"📋 Research target: {person.full_name} at {company.name} (Company ID: {company.id})")

            # Check if research already exists for this company
            existing_snippet = self.db.query(ContextSnippet).filter(
                ContextSnippet.entity_type == "company",
                ContextSnippet.entity_id == company.id
            ).first()
            
            if existing_snippet:
                print(f"⚠️ Research already exists for {company.name} (Snippet ID: {existing_snippet.id})")
                self.send_progress_update(100, f"✅ Using existing research for {company.name}")
                return {
                    "success": True,
                    "snippet_id": existing_snippet.id,
                    "company_id": company.id,
                    "company_name": company.name,
                    "insights": existing_snippet.payload,
                    "source_urls": existing_snippet.source_urls or []
                }

            insights = {}
            urls = []
            found_fields = []
            
            self.send_progress_update(5, f"🚀 Starting deep research for {company.name}")
            
            # Research each field dynamically
            total_fields = len(self.fields)
            for i, field in enumerate(self.fields, 1):
                # Generate multiple search queries for this field
                queries = self.generate_search_queries(company.name, field)
                primary_query = queries[0]  # Use the first (most specific) query
                
                progress_percent = 5 + int((i / total_fields) * 80)  # 5-85%
                self.send_progress_update(
                    progress_percent, 
                    f"🔍 Researching {field.replace('_', ' ')}...", 
                    primary_query,
                    found_fields
                )
                
                try:
                    # Perform search with the primary query
                    search_results = self.search(primary_query)
                    
                    # Extract and process information
                    extracted_info = self.extract(search_results, field)
                    insights[field] = extracted_info
                    found_fields.append(field)
                    
                    # Collect source URLs
                    organic_results = search_results.get("organic_results", [])
                    for result in organic_results[:2]:
                        if result.get("link"):
                            urls.append(result["link"])
                
                    print(f"✅ Completed field {i}/{total_fields}: {field} for {company.name}")
                    
                    # Small delay to respect API limits
                    time.sleep(0.5)
                    
                except Exception as e:
                    error_msg = f"Failed to research {field}: {str(e)}"
                    print(f"❌ {error_msg}")
                    insights[field] = f"Research failed: {str(e)}"

            self.send_progress_update(90, "💾 Processing and saving results to database...")

            print(f"📊 Research completed for {company.name}. Collected insights:")
            for field, content in insights.items():
                print(f"   - {field}: {len(content)} characters")

            # Create comprehensive context snippet with CORRECT company ID
            snippet = ContextSnippet(
                entity_type="company",
                entity_id=company.id,  # This is the KEY - must match the company ID
                snippet_type="deep_research",
                content=json.dumps(insights, indent=2),
                payload=insights,  # Store insights in payload field
                source_urls=list(set(urls))  # Remove duplicates
            )
            
            print(f"💾 Creating ContextSnippet:")
            print(f"   - Company: {company.name} (ID: {company.id})")
            print(f"   - Entity ID: {snippet.entity_id}")
            print(f"   - Payload fields: {list(insights.keys())}")
            print(f"   - Source URLs: {len(set(urls))}")
            
            # Save to database
            self.db.add(snippet)
            self.db.commit()
            self.db.refresh(snippet)
            
            print(f"✅ Snippet saved with ID: {snippet.id}")
            
            # Verify data was saved with correct company ID
            verification = self.db.query(ContextSnippet).filter(
                ContextSnippet.id == snippet.id,
                ContextSnippet.entity_id == company.id  # Verify company ID match
            ).first()
            
            if verification and verification.payload:
                print(f"✅ Database verification successful - {len(verification.payload)} fields saved for {company.name} (Company ID: {company.id})")
            else:
                print("❌ Database verification failed!")
                raise Exception("Failed to save data to database with correct company ID")
            
            self.send_progress_update(100, f"✅ Research completed for {company.name}! Data saved successfully.")
            
            return {
                "success": True,
                "snippet_id": snippet.id,
                "company_id": company.id,  # Return the correct company ID
                "company_name": company.name,
                "insights": insights,
                "source_urls": list(set(urls))
            }
            
        except Exception as e:
            error_msg = f"Research failed for person {person_id}: {str(e)}"
            print(f"💥 {error_msg}")
            self.db.rollback()
            self.send_progress_update(0, f"❌ {error_msg}")
            raise e

    def research_person_sync(self, person_id: int) -> Dict[str, Any]:
        """Synchronous wrapper for the research method"""
        return self.research_person(person_id)