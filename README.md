# Alpha Deep Research Agent

An AI-powered company research and data enrichment platform that provides real-time business intelligence using live web data.

## 🚀 Features

- **Real-time Research**: Live web scraping using SerpAPI Google Search
- **Company Intelligence**: Automated research on business models, competitors, pricing
- **WebSocket Updates**: Real-time progress tracking during research
- **Database Integration**: PostgreSQL with Redis for caching and job queues
- **Modern Stack**: FastAPI backend + Next.js frontend

## 🏗️ Architecture

```
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── main.py         # FastAPI application
│   │   ├── agent.py        # Research agent with SerpAPI
│   │   ├── models.py       # SQLAlchemy database models
│   │   ├── worker.py       # Background job processor
│   │   └── ...
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # Next.js React frontend
│   ├── components/
│   │   └── ResearchAgent.tsx
│   ├── app/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml      # Multi-service orchestration
└── README.md
```

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM
- **PostgreSQL** - Primary database (Neon)
- **Redis** - Caching and job queues
- **RQ** - Background job processing
- **SerpAPI** - Real-time Google search

### Frontend
- **Next.js 15** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **WebSocket** - Real-time updates

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/alpha-deep-research-agent.git
cd alpha-deep-research-agent
```

### 2. Environment Setup
The project uses these APIs (keys included for demo):
- **Database**: Neon PostgreSQL (configured)
- **SerpAPI**: Google search access (configured)

### 3. Start with Docker
```bash
# Start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

This will start:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Redis**: localhost:6379

### 4. Verify Setup
- Open http://localhost:3000
- Check backend health: http://localhost:8000/health
- API docs: http://localhost:8000/docs

## 📊 Usage

1. **Access the Application**: Navigate to http://localhost:3000
2. **View Research Targets**: See pre-loaded executives (Sundar Pichai, Ruth Porat)
3. **Start Research**: Click "Start Research" on any person
4. **Monitor Progress**: Watch real-time updates in the research console
5. **View Results**: Results automatically load when research completes

## 🗃️ Database Schema

The system uses a simple relational structure:
- **Campaigns** → **Companies** → **People** → **Context Snippets**

On startup, sample data is automatically created:
- 1 Campaign: "Alpha Research Campaign"
- 1 Company: "Google"
- 2 People: "Sundar Pichai (CEO)", "Ruth Porat (CFO)"

## 🔧 Development

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Database Management
The system automatically:
- Creates tables on startup
- Seeds sample data
- Handles migrations

## 📡 API Endpoints

- `GET /` - API status
- `GET /health` - System health check
- `GET /people` - List research targets
- `GET /companies` - List companies
- `POST /enrich/{person_id}` - Start research job
- `GET /snippets/{company_id}` - Get research results
- `WebSocket /ws` - Real-time updates

## 🔍 Research Process

1. **Target Selection**: Choose a person/company to research
2. **Query Generation**: Create targeted search queries
3. **Live Web Search**: Use SerpAPI to fetch real Google results
4. **Data Analysis**: Extract and structure business intelligence
5. **Storage**: Save insights with source URLs
6. **Real-time Updates**: WebSocket progress notifications

## 🚨 Production Notes

For production deployment:
1. Replace demo API keys with your own
2. Set up proper environment variables
3. Configure secure database credentials
4. Implement authentication/authorization
5. Set up monitoring and logging

## 📝 License

This project is for educational/demo purposes.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

**Built with ❤️ using FastAPI + Next.js**
