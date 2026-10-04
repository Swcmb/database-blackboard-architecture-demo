"""传统数据库风格 — 数据流驱动的文本存储服务

核心逻辑：由输入事务决定操作。接收 HTTP 请求后执行纯 CRUD 操作。
触发机制：系统完全被输入流（HTTP 请求）驱动。
"""

import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db, init_db
from .models import Analysis


# --- Pydantic Schemas ---

class AnalyzeRequest(BaseModel):
    content: str


class AnalyzeResponse(BaseModel):
    id: int
    content: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="DB Service — 传统数据库风格",
    description="数据流驱动：HTTP 请求 → PostgreSQL CRUD → 响应",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API Endpoints ---

@app.post("/api/db/analyze", response_model=AnalyzeResponse)
async def create_analysis(req: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """接收文本 → 保存到 PostgreSQL → 返回记录。纯数据流驱动。"""
    record = Analysis(content=req.content)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@app.get("/api/db/history", response_model=list[AnalyzeResponse])
async def get_history(db: AsyncSession = Depends(get_db)):
    """查询所有历史分析记录。"""
    result = await db.execute(select(Analysis).order_by(Analysis.id.desc()))
    return result.scalars().all()


@app.get("/api/db/health")
async def health():
    return {"status": "ok", "service": "db-service"}


@app.get("/api/db/{record_id}", response_model=AnalyzeResponse)
async def get_analysis(record_id: int, db: AsyncSession = Depends(get_db)):
    """按 ID 查询单条分析记录。"""
    result = await db.execute(select(Analysis).where(Analysis.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
