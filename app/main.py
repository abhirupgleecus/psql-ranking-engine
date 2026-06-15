from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routers.search import router as search_router
from app.routers.search_v2 import router as search_v2_router
from app.routers.search_v3 import router as search_v3_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    yield


app = FastAPI(
    title="psql-ranking-poc",
    lifespan=lifespan,
)

app.include_router(search_router)
app.include_router(search_v2_router)
app.include_router(search_v3_router)


@app.get("/health")
async def health():
    return {"status": "ok"}