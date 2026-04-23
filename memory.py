"""轻量记忆层 —— Semantic Memory 基于 SQLite，Episodic Memory 基于 event_store

改造后架构：
- Semantic Memory（用户偏好/事实）→ SQLite 本地关键词检索，零向量依赖
- Episodic Memory（系统事件）→ event_store.EventStore，见 event_store.py

回退方案：如需恢复旧版 ChromaDB 实现，执行
    cp memory_legacy.py memory.py
    # 并重新安装 chromadb + sentence-transformers
"""
import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime

from semantic_store import SemanticStore

log = logging.getLogger("memory")

KIRO_TIMEOUT = int(os.environ.get("KIRO_TIMEOUT", "120"))
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "memory_settings.json")


class MemoryLayer:
    """对外接口保持与改造前 100% 兼容"""

    def __init__(self, db_path: str = "./memory_db"):
        # db_path 保留接口兼容，实际作为 SQLite 存储目录
        semantic_db = os.path.join(db_path, "semantic_memory.db")
        os.makedirs(db_path, exist_ok=True)
        self._semantic = SemanticStore(db_path=semantic_db)
        self._settings = self._load_settings()
        log.info(f"记忆层初始化完成，语义记忆 {self._semantic.count()} 条")

    # ---- 用户设置持久化 ----
    def _load_settings(self) -> dict:
        try:
            with open(SETTINGS_PATH, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_settings(self):
        with open(SETTINGS_PATH, "w") as f:
            json.dump(self._settings, f, ensure_ascii=False, indent=2)

    def is_enabled(self, user_id: str) -> bool:
        return self._settings.get(user_id, {}).get("enabled", True)

    def set_enabled(self, user_id: str, enabled: bool):
        self._settings.setdefault(user_id, {})["enabled"] = enabled
        self._save_settings()

    # ---- Semantic Memory 接口 ----
    def add(self, user_id: str, text: str):
        """存入一条语义记忆（自动去重）"""
        self._semantic.add(user_id, text)

    def search(self, user_id: str, query: str, top_k: int = 5) -> list[str]:
        """检索与 query 相关的语义记忆"""
        return self._semantic.search(user_id, query, top_k)

    def list_all(self, user_id: str) -> list[str]:
        """列出某用户的所有语义记忆（调试用）"""
        return self._semantic.list_all(user_id)

    def count(self) -> int:
        return self._semantic.count()

    def clear(self, user_id: str = None):
        """清除记忆（调试用）"""
        self._semantic.clear(user_id)

    # ---- 记忆提取（保留原有 kiro-cli 提取逻辑）----
    def extract_and_store(self, user_id: str, conversation: str):
        """用 kiro-cli 从对话中提取值得记住的信息"""
        prompt = (
            "从以下对话中提取值得长期记住的关键信息（用户偏好、事实、决策等）。\n"
            "每条一行，只输出信息，不要编号不要解释。如果没有值得记住的，只输出'无'。\n\n"
            f"对话：\n{conversation}"
        )
        try:
            result = subprocess.run(
                ["kiro-cli", "chat", "--no-interactive", "-a", "--wrap", "never", prompt],
                capture_output=True, text=True, timeout=KIRO_TIMEOUT,
                env={**os.environ, "NO_COLOR": "1"},
            )
            output = result.stdout.strip()
            if not output or "无" == output.strip():
                return
            for line in output.splitlines():
                line = line.strip().lstrip("-•· ")
                if line and line != "无":
                    self.add(user_id, line)
                    log.info(f"新记忆 [{user_id}]: {line}")
        except Exception as e:
            log.warning(f"记忆提取失败: {e}")
