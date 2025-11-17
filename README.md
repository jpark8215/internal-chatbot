# Internal RAG Chatbot System

A high-performance FastAPI-based RAG (Retrieval-Augmented Generation) chatbot system optimized for speed and accuracy. Combines local LLM capabilities via Ollama with advanced document retrieval using pgvector (PostgreSQL). Features intelligent search strategies, multi-level caching, automatic file synchronization, and comprehensive improvement tracking.

## 🚀 Key Features

- **Multi-Strategy Document Retrieval**: Semantic, keyword, hybrid, enhanced, and combined search with intelligent auto-selection
- **High-Performance Architecture**: Multi-level caching, parallel processing, and optimized database queries
- **Real-time File Management**: Automatic ingestion, deletion detection, and database-filesystem synchronization
- **Intelligent Source Scoring**: Intuitive percentage-based similarity scores with accurate normalization
- **Improvement Tracking**: Complete system for tracking improvements, measuring impact, and generating recommendations
- **Comprehensive Monitoring**: System health monitoring and optimization recommendations
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
OLLAMA_HOST=http://host.docker.internal:11434

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

**Metrics System (`api/metrics.py`)**
- System metrics collection and monitoring
- Multi-tier caching with intelligent eviction

**Improvement Tracking (`api/improvement_tracker.py`)**
- Records and categorizes system improvements
- Measures before/after impact on user satisfaction
- Generates automated improvement recommendations
- Tracks implementation dates and impact metrics

**Feedback System (`api/feedback_clean.py`)**
- Collects user ratings and detailed feedback
- Tracks accuracy and helpfulness metrics
- Provides analytics and trend data
- Links feedback to specific improvements
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


### Admin & Monitoring
- **Admin Panel** (`/admin`) - Administrative controls and settings
- **System Dashboard** (`/admin/system`) - Consolidated system health, database status, and diagnostics
- **Query History** (`/history`) - Query analytics and search
- **Debug Dashboard** (`/admin/debug`) - Comprehensive debugging tools including search testing

### Analytics & Feedback
- **Feedback Dashboard** (`/feedback-dashboard`) - User feedback analytics and trends
- **Improvement Tracking** - Built-in system for recording and measuring improvements

## 🔧 API Reference

### Core Functionality
- `POST /generate` - Main chat endpoint with RAG capabilities
- `GET /health` - Basic API health check
- `GET /api/system-health` - Comprehensive system health with diagnostics
- `GET /info` - API capabilities and configuration



### File Management
- `POST /api/admin/cleanup-orphaned` - Remove orphaned documents and invalidate caches
- `GET /api/admin/file-sync-status` - Database-filesystem synchronization status
- `POST /api/admin/sync-database` - Comprehensive database sync with filesystem

### Analytics & History
- `GET /api/history` - Query history with pagination
- `GET /api/analytics` - Usage analytics and top queries
- `POST /api/feedback` - Submit user feedback
- `GET /api/feedback/stats` - Feedback statistics
- `GET /api/feedback/trends` - Feedback trend data for charts
- `GET /api/feedback/recent` - Recent feedback entries

### Improvement Tracking
- `POST /api/admin/improvements` - Record new improvement actions
- `GET /api/admin/improvements/summary` - Get improvement summary and impact metrics
- `GET /api/admin/improvements/recommendations` - Get automated improvement recommendations
- `POST /api/admin/improvements/{id}/measure` - Measure impact of specific improvements
- `POST /api/admin/improvements/auto-measure` - Auto-measure recent improvements

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
OLLAMA_HOST=http://host.docker.internal:11434          # Ollama service URL

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

# Automatic cleanup
ENABLE_SCHEDULED_CLEANUP=true               # Enable automatic orphaned cleanup
CLEANUP_INTERVAL=600                        # Cleanup interval (seconds)
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

### Recent Optimizations
- **50-70% faster responses** through multi-level caching and parallel processing
- **Realistic similarity scores** with intuitive percentage display
- **Automatic file synchronization** with deletion detection and orphaned cleanup
- **Streamlined codebase** - Removed unused components and broken imports
- **Optimized cache keys** - 25% reduction in memory usage with MD5 hashing
- **Enhanced database efficiency** - Optimized queries and connection pooling

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
- **Automatic Cleanup**: Scheduled removal of orphaned documents (configurable interval)
- **Database Sync**: Real-time and scheduled cleanup of orphaned documents

### Improvement Tracking System

The system includes a comprehensive improvement tracking capability to help you systematically improve the RAG system based on user feedback.

#### Recording Improvements
```bash
POST /api/admin/improvements
{
  "feedback_id": 123,
  "action_type": "source_boost",
  "description": "Increased weight for HCBS manual based on user feedback",
  "implemented_at": "2024-01-15T10:30:00",
  "created_by": "admin"
}
```

#### Improvement Types
- **`source_boost`** - Increase weight for specific sources
- **`prompt_update`** - Modify system prompts
- **`document_update`** - Update or add documentation
- **`search_strategy`** - Change search algorithms
- **`threshold_adjustment`** - Modify relevance thresholds
- **`ui_enhancement`** - User interface improvements
- **`other`** - Custom improvements

#### Impact Measurement
The system automatically measures improvement impact by comparing metrics before and after implementation:
- **Rating improvements** - Average user rating changes
- **Accuracy improvements** - Percentage of accurate responses
- **Helpfulness improvements** - Percentage of helpful responses
- **Feedback volume** - Changes in user engagement

#### Automated Recommendations
The system analyzes feedback patterns and generates specific recommendations:
- **Missing information** - Identifies commonly requested missing content
- **High-performing sources** - Suggests boosting sources with high ratings
- **Search strategy optimization** - Recommends strategy changes based on performance
- **Pattern analysis** - Detects recurring issues for systematic fixes

#### Usage Workflow
1. **Record improvements** as you make them to the system
2. **Wait 3+ days** for sufficient data to accumulate
3. **Measure impact** to quantify the effectiveness of changes
4. **Review recommendations** for new improvement opportunities
5. **Use auto-measure** to batch-analyze multiple improvements

### User Feedback System

The system collects comprehensive user feedback to drive continuous improvement:

#### Feedback Collection
- **Star ratings** (1-5) for overall response quality
- **Accuracy flags** - Boolean indicators for response accuracy
- **Helpfulness flags** - Boolean indicators for response usefulness
- **Detailed feedback** - Missing information, incorrect information, comments
- **Session tracking** - Links feedback to user sessions for pattern analysis
- **Source tracking** - Records which sources were used for each response

#### Feedback Analytics
- **Trend analysis** - Daily feedback patterns and improvements over time
- **Rating distribution** - Breakdown of user satisfaction levels
- **Accuracy metrics** - Percentage of responses marked as accurate
- **Source performance** - Which sources receive the highest ratings
- **Search strategy effectiveness** - Performance comparison across different search methods

#### Integration with Improvements
- **Automatic recommendations** - System analyzes feedback to suggest improvements
- **Impact measurement** - Before/after comparison of user satisfaction metrics
- **Pattern detection** - Identifies recurring issues for systematic fixes
- **Continuous optimization** - Feedback-driven system enhancement

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

**For 50+ Concurrent Users:**
- Increase `DATABASE_POOL_SIZE` to 100+
- Set `EMBEDDING_BATCH_SIZE` to 50+
- Increase `MAX_CONCURRENT_REQUESTS` to 20+
- Monitor system resources via system logs

**For Large Document Sets (1000+ files):**
- Enable incremental ingestion: `ENABLE_INCREMENTAL_INGESTION=true`
- Use batch ingestion for initial setup
- Monitor database performance and consider read replicas

## 🗄️ Database Schema

The system uses a streamlined PostgreSQL database with pgvector for efficient vector similarity search.

### Core Tables
1. **`documents`** - Vector storage for semantic search with embeddings
2. **`query_history`** - Complete query tracking and analytics
3. **`user_feedback`** - User ratings, accuracy flags, and detailed feedback
4. **`improvement_actions`** - System improvements with impact tracking

### Analytics Views
1. **`feedback_summary`** - Daily feedback statistics and trends
2. **`query_analytics`** - Query frequency and performance analysis
3. **`daily_usage_stats`** - Daily usage statistics and metrics

### Database Setup

#### Automatic (Docker - Recommended)
```bash
docker-compose up -d db
```
The database is automatically initialized with all required tables, indexes, and views.

#### Manual Setup
```bash
# Create database
createdb internal_chatbot

# Install extensions and create schema
psql -d internal_chatbot -f db/init_db.sql
```

#### Requirements
- **PostgreSQL 12+** with pgvector extension
- **pg_stat_statements** extension (optional, for query analytics)

#### Schema Management
The application automatically ensures all required tables exist on startup:
- No manual migrations needed
- Automatic schema creation and updates
- Self-healing database connections

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
- Check system logs for performance issues
- Monitor cache hit rates and database connection usage
- Check system configuration and resource usage

**Database Connection Errors:**
- Verify Docker database is running: `docker compose up -d db`
- Check DATABASE_URL configuration
- Monitor connection pool usage in system logs

**No Search Results:**
- Check document count: `GET /debug/database`
- Verify file ingestion: Check logs for `[auto-ingest]` messages
- Test search strategies: `GET /debug/search?query=test`



## 📈 Monitoring & Analytics

Access comprehensive monitoring through:

- **System Dashboard** (`/admin/system`) - System health monitoring and diagnostics
- **Query History** (`/history`) - User interaction analytics and query patterns
- **Feedback Analytics** (`/feedback-dashboard`) - User satisfaction trends and improvement opportunities
- **Improvement Tracking** - Built-in system for measuring and optimizing system performance

### System Health Monitoring
- **Database connectivity** and performance metrics
- **File monitoring** status and synchronization
- **Cache performance** and hit rates
- **System resources** (CPU, memory, disk usage)
- **Error tracking** and performance bottlenecks

### User Feedback Analytics
- **Rating trends** and satisfaction metrics
- **Accuracy tracking** for response quality
- **Source performance** analysis
- **Search strategy** effectiveness
- **Improvement impact** measurement



---

## 🏢 Enterprise Features

- **Scalable Architecture**: Horizontal scaling with load balancing support
- **Comprehensive Monitoring**: Real-time metrics, alerting, and performance optimization
- **Security Ready**: Authentication hooks and secure configuration management
- **High Availability**: Connection pooling, failover support, and health monitoring
- **Data Integrity**: Automatic backup recommendations and data consistency checks