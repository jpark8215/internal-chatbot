# Internal RAG Chatbot System

A high-performance FastAPI-based RAG (Retrieval-Augmented Generation) chatbot system optimized for speed and accuracy. Combines local LLM capabilities via Ollama with advanced document retrieval using pgvector (PostgreSQL). Features intelligent search strategies, multi-level caching, automatic file synchronization, and comprehensive performance monitoring.

## 🚀 Key Features

- **Multi-Strategy Document Retrieval**: Semantic, keyword, hybrid, enhanced, and combined search with intelligent auto-selection
- **High-Performance Architecture**: Multi-level caching, parallel processing, and optimized database queries
- **Real-time File Management**: Automatic ingestion, deletion detection, and database-filesystem synchronization
- **Intelligent Source Scoring**: Intuitive percentage-based similarity scores with accurate normalization
- **Comprehensive Monitoring**: Performance dashboards, metrics collection, and optimization recommendations
- **Enterprise Ready**: Connection pooling, batch processing, and scalable architecture

## 📋 Prerequisites

- **Python 3.11+** (Windows: use `py` command)
- **Ollama** (https://ollama.com) running locally
- **Docker Desktop** (for PostgreSQL with pgvector)
- **4GB+ RAM** (8GB+ recommended for production)

## ⚡ Quick Start

### 1. Setup Environment
```bash
# Clone and navigate to project
git clone <repository-url>
cd internal-chatbot

# Create Python environment (optional but recommended)
py -m venv .venv
.venv\Scripts\activate

# Install dependencies
py -m pip install -r api/requirements.txt
```

### 2. Configure Settings
```bash
# Copy configuration template
Copy-Item .env.example .env

# Edit .env with your settings (key configurations below)
```

**Essential Configuration:**
```env
# Database (choose one approach)
DATABASE_URL=postgres://postgres:postgres@localhost:5432/internal_chatbot

# Ollama Models
DEFAULT_MODEL=mistral:7b
EMBEDDING_MODEL=nomic-embed-text:latest
OLLAMA_HOST=http://localhost:11434

# Document Processing
AUTO_INGEST_ON_START=true
AUTO_INGEST_PATH=C:\path\to\your\documents
AUTO_INGEST_WATCH_MODE=true
AUTO_INGEST_WATCH_INTERVAL=60

# Performance (Optimized Settings)
ENABLE_FAST_MODE=true
DATABASE_POOL_SIZE=100
EMBEDDING_BATCH_SIZE=50
MAX_CONCURRENT_REQUESTS=20
CACHE_MAX_SIZE=10000
```

### 3. Start Services
```bash
# Start database
docker compose up -d db

# Pull required Ollama models
ollama pull mistral:7b
ollama pull nomic-embed-text:latest

# Run the application
py -m api.main
```

### 4. Access the System
- **Main Chat Interface**: http://127.0.0.1:8000/
- **Performance Dashboard**: http://127.0.0.1:8000/performance-dashboard
- **API Documentation**: http://127.0.0.1:8000/docs

## 🏗️ System Architecture

### Core Components

**RAG Pipeline (`api/rag_service.py`)**
- Intelligent search strategy selection based on query characteristics
- Multi-level caching with automatic invalidation
- Parallel processing for retrieval and context building
- Accurate similarity scoring with intuitive percentages

**Database Layer (`api/dao.py`)**
- PostgreSQL with pgvector for vector similarity search
- Optimized queries with connection pooling
- Multiple search strategies: semantic, keyword, hybrid, enhanced

**File Management (`api/file_watcher.py`, `api/file_cleanup.py`)**
- Real-time file monitoring with automatic ingestion
- Database-filesystem synchronization
- Orphaned document cleanup and cache invalidation

**Performance System (`api/performance_monitor.py`, `api/metrics.py`)**
- Real-time performance monitoring and optimization
- Multi-tier caching with intelligent eviction
- Automatic performance tuning recommendations

### Performance Optimizations

**Multi-Level Caching:**
- **Response Cache**: Complete RAG responses (TTL: 2 hours)
- **Embedding Cache**: Text embeddings (LRU: 2000 entries)  
- **Query Result Cache**: Database search results (TTL: 5 minutes)

**Parallel Processing:**
- Concurrent document retrieval and context building
- Batch embedding generation with rate limiting
- Asynchronous file processing and monitoring

**Database Optimization:**
- Connection pooling (100+ concurrent connections)
- Optimized vector similarity queries
- Adaptive relevance filtering

## 📊 User Interfaces

### Main Application
- **Chat Interface** (`/`) - Interactive chat with source citations and confidence scores
- **Performance Dashboard** (`/performance-dashboard`) - Real-time system metrics and optimization

### Admin & Monitoring
- **Health Check** (`/health-check`) - System health and diagnostics
- **Query History** (`/history`) - Query analytics and search
- **Database Debug** (`/database-debug`) - Database diagnostics and file sync status
- **Search Debug** (`/search-debug`) - Search strategy testing and optimization

### Analytics & Feedback
- **Feedback Dashboard** (`/feedback-dashboard`) - User feedback analytics
- **System Stats** (`/system-stats`) - Comprehensive performance metrics
- **Monitoring Dashboard** (`/monitoring-dashboard`) - Real-time system monitoring

## 🔧 API Reference

### Core Functionality
- `POST /generate` - Main chat endpoint with RAG capabilities
- `GET /health` - System health check
- `GET /info` - API capabilities and configuration

### Performance Management
- `GET /api/performance/metrics` - Comprehensive system performance metrics
- `POST /api/performance/optimize` - Apply automatic performance optimizations
- `GET /api/performance/cache-stats` - Multi-level cache statistics
- `POST /api/performance/clear-all-caches` - Clear all system caches

### File Management
- `POST /api/admin/cleanup-orphaned` - Remove orphaned documents and invalidate caches
- `GET /api/admin/file-sync-status` - Database-filesystem synchronization status
- `POST /api/admin/sync-database` - Comprehensive database sync with filesystem

### Analytics & History
- `GET /api/history` - Query history with pagination
- `GET /api/analytics` - Usage analytics and top queries
- `POST /api/feedback` - Submit user feedback
- `GET /api/feedback/stats` - Feedback statistics

### Debug & Diagnostics
- `GET /debug/database` - Database connection and document stats
- `GET /debug/search` - Test search functionality
- `GET /debug/rag-flow` - Complete RAG pipeline debugging

## ⚙️ Configuration Reference

### Core Settings
```env
# LLM Configuration
DEFAULT_MODEL=mistral:7b                    # Primary language model
EMBEDDING_MODEL=nomic-embed-text:latest     # Embedding model
OLLAMA_HOST=http://localhost:11434          # Ollama service URL

# Database
DATABASE_URL=postgres://user:pass@host:port/db  # PostgreSQL connection
DATABASE_POOL_SIZE=100                      # Connection pool size
DATABASE_MAX_OVERFLOW=200                   # Max overflow connections
```

### Performance Tuning
```env
# Processing
EMBEDDING_BATCH_SIZE=50                     # Batch size for embeddings
MAX_CONCURRENT_REQUESTS=20                  # Max concurrent Ollama requests
ENABLE_FAST_MODE=true                       # Enable performance optimizations

# Caching
CACHE_MAX_SIZE=10000                        # Response cache size
EMBEDDING_CACHE_SIZE=2000                   # Embedding cache size
QUERY_RESULT_CACHE_TTL=300                  # Query cache TTL (seconds)
ENABLE_EMBEDDING_CACHE=true                 # Enable embedding caching
ENABLE_QUERY_RESULT_CACHE=true              # Enable query result caching
```

### File Management
```env
# Auto-ingestion
AUTO_INGEST_ON_START=true                   # Process files on startup
AUTO_INGEST_PATH=/path/to/documents         # Document directory path
AUTO_INGEST_WATCH_MODE=true                 # Enable file watching
AUTO_INGEST_WATCH_INTERVAL=60               # File check interval (seconds)
```

## 🚀 Performance Benchmarks

### Response Times (Typical)
- **Cached queries**: <100ms
- **New semantic queries**: 1-3 seconds  
- **Complex enhanced queries**: 3-5 seconds
- **Cache hit rate**: 60-80% for repeated queries

### System Capacity
- **Concurrent users**: 50+ (with optimized settings)
- **Document capacity**: 10,000+ documents
- **Memory usage**: 2-4GB (depending on cache sizes)
- **Database connections**: 100+ concurrent

### Recent Optimizations (v2.0)
- **50-70% faster responses** through multi-level caching
- **Parallel processing pipeline** for retrieval and context building
- **Realistic similarity scores** with intuitive percentage display
- **Automatic file synchronization** with deletion detection

## 🔧 Advanced Usage

### Search Strategy Selection
The system automatically selects optimal search strategies:

- **HCBS/HARP queries** → Enhanced search for complex healthcare queries
- **CCBHC queries** → Enhanced search for quality measures
- **Policy queries** → Combined search for comprehensive policy documents
- **Drug/substance queries** → Enhanced search for specific lists and procedures
- **Short queries** → Keyword search for exact terms
- **General queries** → Semantic search for conceptual understanding

### File Management Features
- **Supported Formats**: PDF, DOCX, TXT, Markdown with metadata extraction
- **Real-time Monitoring**: Automatic ingestion of new files and cleanup of deleted files
- **Smart Chunking**: Boundary-aware text segmentation with overlap
- **Incremental Updates**: Only processes modified files with change detection
- **Database Sync**: Automatic cleanup of orphaned documents when files are deleted

### Performance Tuning

**For Maximum Speed:**
```env
ENABLE_FAST_MODE=true
SKIP_QUALITY_INDICATORS=true
DATABASE_POOL_SIZE=100
EMBEDDING_BATCH_SIZE=50
MAX_CONCURRENT_REQUESTS=20
```

**For Maximum Accuracy:**
```env
ENABLE_FAST_MODE=false
SKIP_QUALITY_INDICATORS=false
# System will use enhanced/combined strategies for complex queries
```

## 📦 Deployment Options

### Development
```bash
py -m api.main
```

### Production (Docker Compose)
```bash
docker compose up -d
```

### Windows Executable
```bash
py -m pip install pyinstaller
pyinstaller --noconfirm --onedir --name InternalChatbot \
  --add-data "api/static;api/static" \
  --paths . \
  --hidden-import api.app \
  api/main.py
```

## 🔍 Troubleshooting

### Common Issues

**File Watching Not Working:**
- Real-time file watcher may fail on Windows due to watchdog library issues
- System automatically falls back to periodic checking (every 60 seconds)
- Use manual cleanup: `POST /api/admin/cleanup-orphaned`

**Performance Issues:**
- Check Performance Dashboard at `/performance-dashboard`
- Monitor cache hit rates and database connection usage
- Use auto-optimization: `POST /api/performance/optimize`

**Database Connection Errors:**
- Verify Docker database is running: `docker compose up -d db`
- Check DATABASE_URL configuration
- Monitor connection pool usage in performance dashboard

**No Search Results:**
- Check document count: `GET /debug/database`
- Verify file ingestion: Check logs for `[auto-ingest]` messages
- Test search strategies: `GET /debug/search?query=test`

### Performance Optimization

**For 50+ Concurrent Users:**
- Increase `DATABASE_POOL_SIZE` to 100+
- Set `EMBEDDING_BATCH_SIZE` to 50+
- Increase `MAX_CONCURRENT_REQUESTS` to 20+
- Monitor system resources via Performance Dashboard

**For Large Document Sets (1000+ files):**
- Enable incremental ingestion: `ENABLE_INCREMENTAL_INGESTION=true`
- Use batch ingestion for initial setup
- Monitor database performance and consider read replicas

## 📈 Monitoring & Analytics

Access comprehensive monitoring through:

- **Performance Dashboard** (`/performance-dashboard`) - Real-time system metrics, cache statistics, and optimization recommendations
- **System Stats** (`/system-stats`) - Detailed performance analytics and resource usage
- **Query History** (`/history`) - User interaction analytics and query patterns
- **Feedback Analytics** (`/feedback-dashboard`) - User satisfaction trends and improvement opportunities

The system provides automated performance monitoring with alerts and recommendations for optimal operation.

---

## 🏢 Enterprise Features

- **Scalable Architecture**: Horizontal scaling with load balancing support
- **Comprehensive Monitoring**: Real-time metrics, alerting, and performance optimization
- **Security Ready**: Authentication hooks and secure configuration management
- **High Availability**: Connection pooling, failover support, and health monitoring
- **Data Integrity**: Automatic backup recommendations and data consistency checks