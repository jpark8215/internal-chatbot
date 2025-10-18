# System Architecture

## 🏗️ High-Level Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web UI        │    │   FastAPI App    │    │   PostgreSQL    │
│   (Static HTML) │◄──►│   (RAG Service)  │◄──►│   + pgvector    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Ollama LLM     │
                       │   (Local Model)  │
                       └──────────────────┘
```

## 🔧 Core Components

### RAG Pipeline
- **Query Processing**: Intelligent strategy selection (semantic/keyword/hybrid)
- **Document Retrieval**: Vector similarity search with relevance filtering
- **Context Building**: Smart source prioritization and assembly
- **Response Generation**: Local LLM with structured prompting

### Performance Layer
- **Multi-Level Caching**: Response, embedding, and query result caches
- **Parallel Processing**: Concurrent retrieval and context building
- **Connection Pooling**: High-concurrency database connections
- **Metrics Collection**: Real-time performance monitoring

### File Management
- **Auto-Ingestion**: Startup and real-time file processing
- **Sync Monitoring**: Database-filesystem consistency checks
- **Change Detection**: Automatic cleanup of deleted files
- **Format Support**: PDF, DOCX, TXT, Markdown processing

## 📊 Data Flow

```
1. User Query → 2. Strategy Selection → 3. Document Retrieval
                                              ↓
6. Response ← 5. LLM Generation ← 4. Context Building
```

**Detailed Flow:**
1. **User Query** - Received via web UI or API
2. **Strategy Selection** - Auto-select optimal search approach
3. **Document Retrieval** - Vector/keyword search with caching
4. **Context Building** - Assemble relevant sources with scoring
5. **LLM Generation** - Generate response using local Ollama model
6. **Response** - Return with source citations and confidence scores

## 🚀 Performance Optimizations

### Caching Strategy
- **L1 Cache**: Response cache (complete RAG responses)
- **L2 Cache**: Embedding cache (text vectorizations)
- **L3 Cache**: Query result cache (database search results)

### Parallel Processing
- **Async Operations**: Non-blocking I/O for all external calls
- **Concurrent Retrieval**: Parallel document search and embedding
- **Batch Processing**: Efficient bulk operations for ingestion

### Database Optimization
- **Vector Indexing**: IVFFlat indexes for fast similarity search
- **Connection Pooling**: Reusable database connections
- **Query Optimization**: Minimized database round-trips

## 🔍 Key Modules

| Module | Purpose | Key Features |
|--------|---------|--------------|
| `rag_service.py` | Core RAG logic | Strategy selection, context building |
| `dao.py` | Database layer | Vector search, connection pooling |
| `performance_monitor.py` | System monitoring | Metrics, optimization recommendations |
| `file_watcher.py` | File management | Real-time monitoring, auto-ingestion |
| `app.py` | Web application | 50+ endpoints, admin dashboards |

## 📈 Scalability Features

- **Horizontal Scaling**: Stateless design supports load balancing
- **Resource Management**: Configurable pools and cache sizes
- **Monitoring**: Real-time metrics for capacity planning
- **Health Checks**: Automated system health monitoring