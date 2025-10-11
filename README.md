# internal-chatbot

FastAPI-based local chatbot that uses a local LLM via Ollama and can optionally ground answers in your policy files using pgvector (Postgres) for Retrieval-Augmented Generation (RAG).

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

## How it works
- `api/app.py` exposes the FastAPI app, serves a static UI at `/`, and implements `/generate`.
- `api/local_model.py` calls the Ollama LLM (e.g., `mistral:7b`).
- `api/embeddings.py` requests embeddings from Ollama (`/api/embeddings`) and ensures the embedding model is pulled.
- `api/dao.py` handles Postgres connections and vector search with pgvector.
- `api/ingest_files.py` reads files, chunks them, embeds text, and inserts into `documents(content, embedding)`.
- `db/init_db.sql` creates the `vector` extension and a `documents` table of `vector(768)`.

## Configuration reference
See `.env.example` for all fields. Key settings:

**LLM & Embeddings**
- `DEFAULT_MODEL` – LLM for generation (e.g., `mistral:7b`)
- `OLLAMA_HOST` – Ollama base URL (default `http://localhost:11434`)
- `EMBEDDING_MODEL` – embedding model (default `nomic-embed-text:latest`)
- `EMBEDDING_DIM` – must match pgvector dimension (`768` for nomic-embed-text)

**Database**
- `DATABASE_URL` – Postgres connection string. Use `localhost` when running API on host, `db` only when API runs inside Docker Compose.

**Auto-ingest**
- `AUTO_INGEST_ON_START` – `true`/`false` (default `true`). When `true` and DB is configured, the server will ingest files from `AUTO_INGEST_PATH` in the background on first start if the `documents` table is empty.
- `AUTO_INGEST_PATH` – absolute path to a folder containing files to ingest (e.g., `C:\\Users\\jpark\\Desktop\\ChatbotFiles`). Supports `.txt`, `.md`, `.pdf`, `.docx`.

## Packaging (optional)
You can package a Windows app using PyInstaller.
```
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
- Run: `dist\\InternalChatbot\\InternalChatbot.exe`

## Troubleshooting
- **"python not found"**: Use the Python Launcher `py` and/or turn off Windows App Execution Aliases for `python.exe`.
- **Cannot reach Ollama**: Ensure the Ollama app is running and the model is pulled (`ollama list` to verify).
- **DB connection errors**: Verify `docker compose up -d db`, and `DATABASE_URL` uses `localhost` when running API on host (not `db`).
- **"No embedding returned from Ollama"**: Ensure `nomic-embed-text:latest` is pulled and Ollama is running. Check model name matches exactly.
- **Auto-ingest not running**: Verify `AUTO_INGEST_ON_START=true`, `AUTO_INGEST_PATH` exists, and DB is reachable. Check console logs for `[auto-ingest]` messages.
- **No retrieval results**: Ensure documents were ingested. Check document count: `docker exec -it internal-chatbot-db-1 psql -U postgres -d internal_chatbot -c "select count(*) from documents;"`
