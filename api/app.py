from fastapi import FastAPI
import os
import asyncio
import asyncpg

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@db:5432/internal_chatbot")


@app.get("/health")
async def health():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/")
def root():
    return {"message": "Internal chatbot API placeholder"}
