"""语义记忆层 —— 基于 SQLite 的轻量语义存储

设计原则：
- 零外部依赖，单文件可备份
- 数据量小（每用户通常 < 100 条），采用本地关键词重叠评分即可满足召回
- 不依赖向量模型，启动无延迟
"""

import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("semantic-store")

DB_NAME = "semantic_memory.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _extract_keywords(text: str) -> list[str]:
    """从查询/内容中提取关键词用于重叠评分

    策略：
    - 英文单词（>=2 字符）
    - 中文连续短语（>=2 字）
    - 中文 2-gram（提升单字命中）
    """
    text = text.lower()
    words: list[str] = []

    # 英文/数字单词
    en = re.findall(r"[a-z0-9]{2,}", text)
    words.extend(en)

    # 中文连续短语
    zh_phrases = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    words.extend(zh_phrases)

    # 中文 2-gram
    for phrase in zh_phrases:
        for i in range(len(phrase) - 1):
            words.append(phrase[i : i + 2])

    # 中文单字兜底（保证基本召回）
    zh_chars = re.findall(r"[\u4e00-\u9fff]", text)
    words.extend(zh_chars)

    # 去重并保持顺序
    seen = set()
    result = []
    for w in words:
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result


class SemanticStore:
    def __init__(self, db_path: str = DB_NAME):
        self.db_path = db_path
        self._ensure_schema()
        log.info(f"SemanticStore 初始化完成，路径: {self.db_path}")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_schema(self):
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sem_user ON semantic_memory(user_id);
                """
            )
            conn.commit()

    def add(self, user_id: str, text: str) -> str:
        """存入一条语义记忆，返回 id"""
        if not text or not text.strip():
            return ""
        doc_id = hashlib.md5(f"{user_id}:{text}".encode()).hexdigest()
        now = _now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO semantic_memory (id, user_id, content, ts, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_id, user_id, text.strip(), now, now),
            )
            conn.commit()
        return doc_id

    def search(self, user_id: str, query: str, top_k: int = 5) -> list[str]:
        """检索与 query 相关的语义记忆"""
        if not query or not query.strip():
            return []

        query = query.strip()
        tokens = _extract_keywords(query)

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM semantic_memory WHERE user_id = ?", (user_id,)
            ).fetchall()

        if not rows:
            return []

        # 评分排序
        scored: list[tuple[int, str]] = []
        for row in rows:
            content = row["content"]
            score = 0
            # 整句包含加分最高
            if query in content.lower():
                score += 10
            # 关键词重叠
            for t in tokens:
                if t in content.lower():
                    score += 1
            if score > 0:
                scored.append((score, content))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [content for _, content in scored[:top_k]]

        # 兜底：如果关键词完全无命中，返回最近添加的记忆（避免空结果导致调用方崩溃）
        if not results:
            with self._conn() as conn:
                fallback = conn.execute(
                    "SELECT content FROM semantic_memory WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
                    (user_id, top_k),
                ).fetchall()
                results = [r["content"] for r in fallback]

        return results

    def list_all(self, user_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content FROM semantic_memory WHERE user_id = ? ORDER BY ts DESC",
                (user_id,),
            ).fetchall()
            return [r["content"] for r in rows]

    def count(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM semantic_memory").fetchone()
            return row[0] if row else 0

    def clear(self, user_id: str | None = None):
        with self._conn() as conn:
            if user_id:
                conn.execute("DELETE FROM semantic_memory WHERE user_id = ?", (user_id,))
            else:
                conn.execute("DELETE FROM semantic_memory")
            conn.commit()
        log.info(f"语义记忆已清空 {'user=' + user_id if user_id else '全部'}")
