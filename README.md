# Internal RAG Chatbot System

A comprehensive FastAPI-based RAG (Retrieval-Augmented Generation) chatbot system that combines local LLM capabilities via Ollama with advanced document retrieval using pgvector (PostgreSQL). Features intelligent search strategies, user feedback collection, automated monitoring, and performance optimization for enterprise deployment.

## 🚀 Key Features

### Core RAG Capabilities
- **Multi-Strategy Document Retrieval**: Semantic, keyword, hybrid, enhanced, and combined search strategies
- **Intelligent Source Boosting**: Dynamic source prioritization based on user feedback and query patterns  
- **Advanced Chunking**: Smart text chunking with overlap for better context preservation
- **Response Caching**: In-memory caching with TTL and LRU eviction for improved performance
- **Quality Indicators**: Real-time response quality assessment based on historical feedback

### User Experience & Feedback
- **Interactive Web UI**: Clean, responsive interface for chatting and document interaction
- **User Feedback System**: Rating, accuracy assessment, and detailed feedback collection
- **Query History**: Complete interaction tracking with search and analytics
- **Source Citations**: Transparent source attribution with confidence scores

### Monitoring & Analytics
- **Real-time Metrics**: Query performance, success rates, and system health monitoring
- **Automated Alerting**: Threshold-based alerts for quality degradation and anomalies
- **Feedback Analytics**: Trend analysis, pattern detection, and improvement recommendations
- **Performance Dashboards**: Multiple admin interfaces for system monitoring

### File Management
- **Auto-ingestion**: Automatic document processing on startup and file changes
- **File Watching**: Real-time monitoring of document directories with automatic updates
- **Multi-format Support**: PDF, DOCX, TXT, and Markdown file processing
- **Incremental Updates**: Smart re-ingestion of modified files only

### Enterprise Features
- **Scalable Architecture**: Connection pooling, batch processing, and concurrent request handling
- **Database Optimization**: Advanced indexing, query optimization, and performance tuning
- **Improvement Tracking**: Automated measurement of system improvements and their impact
- **Admin Tools**: Comprehensive management interfaces for system administration

## Prerequisites
- Python 3.11+ (Windows: use the Python Launcher `py`)
- Ollama (https://ollama.com) running locally
- Docker Desktop (for Postgres/pgvector without installing SQL locally)

## Quick Start
1) Create and activate a Python environment (optional but recommended).

2) Install dependencies:
```
py -m pip install -r api/requirements.txt
```

3) Configure environment variables:
- Copy `.env.example` to `.env` and adjust as needed.
```
Copy-Item .env.example .env
```
- Key settings in `.env`:
  - `DEFAULT_MODEL=mistral:7b` (LLM served by Ollama)
  - `OLLAMA_HOST=http://localhost:11434`
  - `EMBEDDING_MODEL=nomic-embed-text:latest`
  - `EMBEDDING_DIM=768`
  - `DATABASE_URL` (choose ONE):
    - `postgres://postgres:postgres@db:5432/internal_chatbot` if using Docker Compose service name `db`
    - or `postgres://postgres:postgres@localhost:5432/internal_chatbot` if exposing on localhost

4) Start the database (no local SQL install needed):
```
docker compose up -d db
```

5) Pull required Ollama models:
```
ollama pull mistral:7b
ollama pull nomic-embed-text:latest
```

6) Run the app:
```
py -m api.main
```
- Your browser should open to http://127.0.0.1:8000/
- **Auto-ingest**: If `AUTO_INGEST_ON_START=true` in `.env` and the `documents` table is empty, the app will automatically ingest files from `AUTO_INGEST_PATH` in the background on startup. Check console logs for `[auto-ingest]` messages.
- The UI posts to `POST /generate`. When documents are ingested, answers will be grounded in retrieved policy chunks and cite `[Source N]`.

## 🏗️ System Architecture

### Core Components

**FastAPI Application (`api/app.py`)**
- Main application server with REST API endpoints
- Serves static web UI and handles chat interactions
- Implements comprehensive health checks and debugging endpoints
- Manages startup/shutdown lifecycle with background services

**RAG Service Layer (`api/rag_service.py`)**
- Centralized RAG logic with intelligent search strategy selection
- Dynamic source boosting based on user feedback patterns
- Quality indicator generation and response optimization
- Context building with smart document prioritization

**Database Layer (`api/dao.py`)**
- PostgreSQL with pgvector extension for vector similarity search
- Connection pooling for high-concurrency scenarios
- Multiple search strategies: semantic, keyword, hybrid, enhanced, combined
- Optimized indexing for performance at scale

**LLM Integration (`api/local_model.py`)**
- Asynchronous Ollama client with session management
- Model availability checking and error handling
- Configurable generation parameters and timeouts

**Document Processing (`api/ingest_files.py`)**
- Multi-format file parsing (PDF, DOCX, TXT, Markdown)
- Intelligent text chunking with boundary detection
- Batch embedding generation with concurrency control
- Incremental ingestion for modified files

### Advanced Features

**Feedback System (`api/feedback_clean.py`)**
- User rating and accuracy assessment collection
- Structured feedback storage with trend analysis
- Integration with improvement tracking system

**Monitoring & Alerting (`api/monitoring_service.py`, `api/alerting_system.py`)**
- Background monitoring service with configurable intervals
- Threshold-based alerting for quality metrics
- Pattern detection and anomaly identification
- Automated alert generation and management

**Performance Optimization**
- Response caching with LRU eviction (`api/response_cache.py`)
- Metrics collection and performance tracking (`api/metrics.py`)
- Query history and analytics (`api/query_history_dao.py`)
- File watching for real-time updates (`api/file_watcher.py`)

**Improvement Tracking (`api/improvement_tracker.py`)**
- Automated measurement of system improvements
- Impact analysis with before/after metrics
- Recommendation generation based on feedback patterns
- ROI tracking for optimization efforts

## ⚙️ Configuration Reference

See `.env.example` for all available settings. Key configuration categories:

### LLM & Embeddings
- `DEFAULT_MODEL` – LLM for generation (e.g., `mistral:7b`)
- `OLLAMA_HOST` – Ollama base URL (default `http://localhost:11434`)
- `EMBEDDING_MODEL` – embedding model (default `nomic-embed-text:latest`)
- `EMBEDDING_DIM` – must match pgvector dimension (`768` for nomic-embed-text)

### Database Configuration
- `DATABASE_URL` – Postgres connection string
- `DATABASE_POOL_SIZE` – Connection pool size (default: 10, recommended: 50+ for production)
- `DATABASE_MAX_OVERFLOW` – Max overflow connections (default: 20, recommended: 100+ for production)

### Performance Settings
- `EMBEDDING_BATCH_SIZE` – Batch size for embedding generation (default: 10, recommended: 50+ for production)
- `MAX_CONCURRENT_REQUESTS` – Max concurrent Ollama requests (default: 5, recommended: 20+ for production)
- `CACHE_MAX_SIZE` – Response cache size (default: 1000, recommended: 10000+ for production)
- `CACHE_TTL_SECONDS` – Cache TTL in seconds (default: 3600)

### Auto-ingestion
- `AUTO_INGEST_ON_START` – Enable auto-ingestion on startup (default: `true`)
- `AUTO_INGEST_PATH` – Path to documents folder (supports `.txt`, `.md`, `.pdf`, `.docx`)
- `AUTO_INGEST_WATCH_MODE` – Enable real-time file watching (default: `false`)
- `AUTO_INGEST_WATCH_INTERVAL` – File check interval in seconds (default: 600)

### Feature Flags
- `ENABLE_STREAMING` – Enable streaming responses (default: `false`)
- `ENABLE_CONVERSATION_MEMORY` – Enable conversation context (default: `false`)
- `ENABLE_HYBRID_SEARCH` – Enable hybrid search strategy (default: `false`)
- `ENABLE_RESPONSE_CACHE` – Enable response caching (default: `true`)
- `ENABLE_INCREMENTAL_INGESTION` – Enable incremental file updates (default: `true`)

### Logging & Monitoring
- `LOG_LEVEL` – Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `LOG_FORMAT` – Log format (`json` or `text`)
- `MONITORING_INTERVAL_MINUTES` – Background monitoring interval (default: 60)

## 📊 Available Interfaces

### Main Chat Interface
- **URL**: `http://localhost:8000/`
- **Features**: Interactive chat, source citations, feedback collection

### Admin & Monitoring Dashboards
- **Health Check**: `http://localhost:8000/health-check` - System health monitoring
- **Query History**: `http://localhost:8000/history` - Query analytics and search
- **Feedback Dashboard**: `http://localhost:8000/feedback-dashboard` - User feedback analytics
- **Feedback Management**: `http://localhost:8000/feedback-management` - Enhanced feedback tools
- **Analytics**: `http://localhost:8000/analytics-enhanced` - Advanced system analytics
- **Monitoring Dashboard**: `http://localhost:8000/monitoring-dashboard` - Real-time system monitoring
- **Alert Management**: `http://localhost:8000/alert-management` - Alert configuration and management
- **Database Debug**: `http://localhost:8000/database-debug` - Database diagnostics
- **Search Debug**: `http://localhost:8000/search-debug` - Search strategy testing
- **System Stats**: `http://localhost:8000/system-stats` - Performance metrics

### API Endpoints

#### Core Functionality
- `POST /generate` - Main chat endpoint with RAG capabilities
- `GET /health` - System health check
- `GET /info` - API capabilities and configuration

#### Analytics & History
- `GET /api/history` - Query history with pagination
- `GET /api/analytics` - Usage analytics and top queries
- `GET /api/search-history` - Search query history

#### Feedback System
- `POST /api/feedback` - Submit user feedback
- `GET /api/feedback/stats` - Feedback statistics
- `GET /api/feedback/recent` - Recent feedback entries
- `GET /api/feedback/trends` - Feedback trend data

#### Debug & Diagnostics
- `GET /debug/database` - Database connection and document stats
- `GET /debug/search` - Test search functionality
- `GET /debug/keyword-search` - Test keyword search
- `GET /stats` - Application statistics

## 🔧 Advanced Usage

### Search Strategy Selection
The system automatically selects optimal search strategies based on query characteristics:

- **Semantic Search**: Best for conceptual queries and general questions
- **Keyword Search**: Optimal for exact terms and specific phrases
- **Hybrid Search**: Combines semantic and full-text search (requires PostgreSQL full-text search)
- **Enhanced Search**: Advanced ranking with exact phrase matching and pattern detection
- **Combined Search**: Fallback strategy that tries multiple approaches

### User Feedback Integration
The system learns from user feedback to improve responses:

- **Rating System**: 1-5 star ratings for response quality
- **Accuracy Assessment**: Binary accurate/inaccurate feedback
- **Missing Information**: Users can specify what information was missing
- **Source Preferences**: Users can indicate preferred information sources
- **Automated Improvements**: System automatically adjusts based on feedback patterns

### File Management
- **Supported Formats**: PDF, DOCX, TXT, Markdown
- **Auto-ingestion**: Processes files on startup if database is empty
- **File Watching**: Real-time monitoring with automatic re-ingestion
- **Incremental Updates**: Only processes modified files
- **Batch Processing**: Efficient handling of large document sets

### Performance Optimization
- **Connection Pooling**: Configurable database connection management
- **Response Caching**: LRU cache with configurable TTL
- **Batch Embedding**: Concurrent embedding generation
- **Query Optimization**: Advanced database indexing and query patterns

## 📦 Deployment Options

### Development Mode
```bash
py -m api.main
```

### Docker Compose (Recommended for Production)
```bash
docker compose up -d
```

### Windows Executable (PyInstaller)
```bash
py -m pip install pyinstaller
pyinstaller --noconfirm --onedir --name InternalChatbot \
  --add-data "api/static;api/static" \
  --paths . \
  --hidden-import api.app \
  --hidden-import api.local_model \
  --hidden-import api.models \
  --hidden-import api.config \
  api/main.py
```
Run: `dist\\InternalChatbot\\InternalChatbot.exe`

## 🔍 Troubleshooting

### Common Issues

**Python Environment**
- **"python not found"**: Use Python Launcher `py` and/or disable Windows App Execution Aliases for `python.exe`
- **Module import errors**: Ensure virtual environment is activated and dependencies installed

**Ollama Integration**
- **Cannot reach Ollama**: Verify Ollama is running and accessible at configured host
- **Model not found**: Pull required models: `ollama pull mistral:7b` and `ollama pull nomic-embed-text:latest`
- **"No embedding returned"**: Check model name matches exactly and Ollama is responsive

**Database Issues**
- **Connection errors**: Verify `docker compose up -d db` and correct `DATABASE_URL`
- **Schema errors**: Check database initialization and permissions
- **Performance issues**: Monitor connection pool usage and consider increasing pool size

**Document Ingestion**
- **Auto-ingest not running**: Verify `AUTO_INGEST_ON_START=true`, path exists, and database is reachable
- **No retrieval results**: Check document count and ingestion logs
- **File format errors**: Ensure supported formats and file accessibility

**Performance Issues**
- **Slow responses**: Check Ollama performance, database query times, and cache hit rates
- **High memory usage**: Monitor embedding cache and response cache sizes
- **Connection timeouts**: Increase database pool size and connection timeouts

### Diagnostic Commands

**Check document count**:
```bash
docker exec -it internal-chatbot-db-1 psql -U postgres -d internal_chatbot -c "SELECT COUNT(*) FROM documents;"
```

**View recent logs**:
```bash
docker logs internal-chatbot-db-1 --tail 50
```

**Test Ollama connectivity**:
```bash
curl http://localhost:11434/api/tags
```

**Check database performance**:
```bash
docker exec -it internal-chatbot-db-1 psql -U postgres -d internal_chatbot -c "SELECT schemaname,tablename,attname,n_distinct,correlation FROM pg_stats WHERE tablename='documents';"
```

### Performance Tuning

**For 50+ Concurrent Users**:
- Increase `DATABASE_POOL_SIZE` to 50+
- Set `EMBEDDING_BATCH_SIZE` to 50+
- Increase `MAX_CONCURRENT_REQUESTS` to 20+
- Set `CACHE_MAX_SIZE` to 10000+
- Consider Redis for distributed caching
- Use multiple Ollama instances with load balancing

**For 100+ Documents**:
- Enable `ENABLE_INCREMENTAL_INGESTION`
- Use batch ingestion for initial setup
- Monitor database index usage
- Consider document partitioning for very large datasets

## 🚀 Scaling for Production

### Database Optimization
- **Connection Pooling**: Use pgbouncer for connection management
- **Read Replicas**: Distribute query load across multiple database instances
- **Indexing**: Monitor and optimize database indexes for query patterns
- **Partitioning**: Consider table partitioning for very large document sets

### Application Scaling
- **Load Balancing**: Deploy multiple application instances behind a load balancer
- **Caching**: Implement Redis for distributed caching across instances
- **Queue Management**: Use background job queues for document processing
- **Monitoring**: Implement comprehensive monitoring and alerting

### Infrastructure Considerations
- **Resource Allocation**: Monitor CPU, memory, and disk usage patterns
- **Network Optimization**: Optimize network latency between components
- **Backup Strategy**: Implement regular database and configuration backups
- **Security**: Configure proper authentication, authorization, and network security

## 📈 Monitoring & Analytics

The system provides comprehensive monitoring capabilities:

- **Real-time Metrics**: Query performance, success rates, user engagement
- **Automated Alerting**: Quality degradation, performance issues, system anomalies
- **Feedback Analytics**: User satisfaction trends, improvement opportunities
- **Performance Dashboards**: System health, resource utilization, optimization insights
- **Improvement Tracking**: Measure impact of system enhancements and optimizations

Access monitoring dashboards through the admin interfaces listed above for detailed insights into system performance and user experience.
