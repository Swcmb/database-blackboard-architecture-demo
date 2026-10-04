"""黑板风格服务 — 状态驱动的文本分析架构

核心逻辑：由黑板中心数据状态决定操作。
触发机制：系统不按用户输入顺序处理，而是根据黑板上变化的信息自由调度。

架构组成：
- 黑板 (Blackboard): 全局共享数据字典
- 知识源 (Knowledge Source): 独立的处理单元
- 控制器 (Controller): 后台轮询并调度知识源
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .blackboard import blackboard, controller


# --- Pydantic Schemas ---

class AnalyzeRequest(BaseModel):
    content: str


class TaskCreatedResponse(BaseModel):
    task_id: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    stage: str
    input: str
    keywords: list[str] | None = None
    sentiment: dict | None = None
    summary: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    await controller.start()
    yield
    await controller.stop()

app = FastAPI(
    title="Blackboard Service — 黑板风格",
    description="状态驱动：黑板状态变化 → 知识源激活 → 黑板更新",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API Endpoints ---

@app.post("/api/blackboard/analyze", response_model=TaskCreatedResponse)
async def create_analysis(req: AnalyzeRequest):
    """创建分析任务 → 写入黑板 → 控制器自动处理

    用户提交文本后，黑板 entry 被创建为 stage="init"，
    控制器检测到后自动触发知识源 A → B → C 的处理链。
    """
    task_id = await blackboard.create_entry(req.content)
    return TaskCreatedResponse(task_id=task_id, status="created")


@app.get("/api/blackboard/health")
async def health():
    return {"status": "ok", "service": "blackboard-service"}


@app.get("/api/blackboard/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态 — 前端通过轮询此接口获取处理进展

    返回黑板 entry 的当前状态，前端据此展示处理过程。
    """
    entry = await blackboard.get_entry(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**entry.to_dict())


@app.get("/api/blackboard/")
async def list_tasks():
    """列出所有任务"""
    entries = await blackboard.all_entries()
    return {
        "tasks": [entry.to_dict() for entry in entries],
        "count": len(entries),
    }
