"""黑板系统核心模块 — 状态驱动的文本分析架构

架构组成：
1. 黑板 (Blackboard): 全局共享数据字典，保存当前处理状态
2. 知识源 (Knowledge Source): 独立的处理单元，根据黑板状态激活
3. 控制器 (Controller): 后台轮询黑板，根据状态分派到对应知识源

触发机制：系统不按用户输入顺序处理，而是根据黑板上变化的信息自由调度。
"""

import asyncio
import uuid
import datetime
from typing import Any

from .processors import extract_keywords, analyze_sentiment, generate_summary


# --- 黑板数据结构 ---

class BlackboardEntry:
    """黑板上的一个任务条目"""

    def __init__(self, task_id: str, content: str):
        self.task_id = task_id
        self.input = content
        self.stage = "init"
        self.keywords = None
        self.sentiment = None
        self.summary = None
        self.error = None
        self.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.updated_at = self.created_at

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.updated_at = datetime.datetime.now(datetime.timezone.utc)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "stage": self.stage,
            "input": self.input,
            "keywords": self.keywords,
            "sentiment": self.sentiment,
            "summary": self.summary,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# --- 黑板管理器 ---

class Blackboard:
    """全局共享的黑板数据字典

    所有知识源和控制器通过此黑板进行通信。
    黑板的 stage 字段驱动整个系统的执行流程。
    """

    def __init__(self):
        self._entries: dict[str, BlackboardEntry] = {}
        self._lock = asyncio.Lock()

    async def create_entry(self, content: str) -> str:
        task_id = str(uuid.uuid4())
        async with self._lock:
            self._entries[task_id] = BlackboardEntry(task_id, content)
        return task_id

    async def get_entry(self, task_id: str) -> BlackboardEntry | None:
        return self._entries.get(task_id)

    async def update_entry(self, task_id: str, **kwargs):
        async with self._lock:
            entry = self._entries.get(task_id)
            if entry:
                entry.update(**kwargs)

    async def all_entries(self) -> list[BlackboardEntry]:
        return list(self._entries.values())


# --- 知识源 (Knowledge Sources) ---

class KeywordExtractor:
    """知识源A: 关键词提取

    激活条件：黑板 stage == "init"
    执行操作：提取关键词
    更新黑板：stage -> "keyword_done"
    """

    @staticmethod
    async def should_activate(entry: BlackboardEntry) -> bool:
        return entry.stage == "init"

    @staticmethod
    async def execute(blackboard: Blackboard, task_id: str):
        entry = await blackboard.get_entry(task_id)
        if not entry:
            return

        keywords = extract_keywords(entry.input)
        await blackboard.update_entry(
            task_id,
            keywords=keywords,
            stage="keyword_done",
        )
        print(f"[KS_A] 关键词提取完成: task={task_id}, keywords={keywords}")


class SentimentAnalyzer:
    """知识源B: 情感分析

    激活条件：黑板 stage == "keyword_done"
    执行操作：分析情感倾向
    更新黑板：stage -> "sentiment_done"
    """

    @staticmethod
    async def should_activate(entry: BlackboardEntry) -> bool:
        return entry.stage == "keyword_done"

    @staticmethod
    async def execute(blackboard: Blackboard, task_id: str):
        entry = await blackboard.get_entry(task_id)
        if not entry:
            return

        sentiment = analyze_sentiment(entry.input)
        await blackboard.update_entry(
            task_id,
            sentiment=sentiment,
            stage="sentiment_done",
        )
        print(f"[KS_B] 情感分析完成: task={task_id}, sentiment={sentiment['label']}")


class SummaryGenerator:
    """知识源C: 总结归纳

    激活条件：黑板 stage == "sentiment_done"
    执行操作：生成摘要
    更新黑板：stage -> "completed"
    """

    @staticmethod
    async def should_activate(entry: BlackboardEntry) -> bool:
        return entry.stage == "sentiment_done"

    @staticmethod
    async def execute(blackboard: Blackboard, task_id: str):
        entry = await blackboard.get_entry(task_id)
        if not entry:
            return

        summary = generate_summary(entry.input, entry.keywords, entry.sentiment)
        await blackboard.update_entry(
            task_id,
            summary=summary,
            stage="completed",
        )
        print(f"[KS_C] 总结归纳完成: task={task_id}")


# --- 控制器 (Controller) ---

class BlackboardController:
    """后台控制器 — 持续监控黑板状态并调度知识源

    这是黑板架构的核心：控制器不按固定顺序执行，
    而是根据黑板上的状态变化自由调度知识源。
    """

    def __init__(self, blackboard: Blackboard, poll_interval: float = 0.3):
        self.blackboard = blackboard
        self.poll_interval = poll_interval
        self.knowledge_sources = [
            KeywordExtractor(),
            SentimentAnalyzer(),
            SummaryGenerator(),
        ]
        self._running = False

    async def start(self):
        """启动控制器后台轮询任务"""
        self._running = True
        asyncio.create_task(self._poll_loop())
        print("[Controller] 黑板控制器已启动，开始轮询...")

    async def stop(self):
        self._running = False
        print("[Controller] 黑板控制器已停止")

    async def _poll_loop(self):
        """轮询循环：检查所有未完成的任务，尝试激活匹配的知识源"""
        while self._running:
            try:
                entries = await self.blackboard.all_entries()
                for entry in entries:
                    if entry.stage in ("completed", "error"):
                        continue
                    await self._try_activate(entry)
            except Exception as e:
                print(f"[Controller] 轮询异常: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _try_activate(self, entry: BlackboardEntry):
        """尝试激活匹配的知识源"""
        for ks in self.knowledge_sources:
            try:
                if await ks.should_activate(entry):
                    await ks.execute(self.blackboard, entry.task_id)
                    # 一个任务每轮只执行一个知识源，避免状态竞争
                    return
            except Exception as e:
                await self.blackboard.update_entry(
                    entry.task_id,
                    stage="error",
                    error=str(e),
                )
                print(f"[Controller] 知识源执行异常: task={entry.task_id}, error={e}")


# 全局单例
blackboard = Blackboard()
controller = BlackboardController(blackboard)
