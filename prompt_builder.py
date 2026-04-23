"""Prompt 构建器 —— 分离 Semantic Memory 与 Episodic Memory 的注入策略

规则：
- Semantic Memory（用户偏好/事实）→ 作为前缀注入，影响 Agent 行为风格
- Episodic Memory（系统事件/变更/告警）→ 附加在 user_text 后，用围栏标注"仅供参考"，
  不直接注入 system prompt，避免干扰模型推理
"""

from typing import Any


def build_prompt(
    user_text: str,
    semantic_memories: list[str] | None = None,
    episodic_memories: list[dict[str, Any]] | None = None,
) -> str:
    """构建最终传给 kiro-cli 的 prompt 字符串

    Args:
        user_text: 用户原始消息
        semantic_memories: 语义记忆列表（用户偏好、事实）
        episodic_memories: 事件记忆列表（每条为 dict，至少含 title, event_type, ts）

    Returns:
        拼接后的 prompt 字符串
    """
    parts: list[str] = []

    # ---- Semantic Memory 前缀（影响行为）----
    if semantic_memories:
        parts.append("关于这个用户的已知信息：")
        for m in semantic_memories:
            parts.append(f"- {m}")
        parts.append("")  # 空行分隔

    # ---- 用户消息主体 ----
    parts.append(f"用户消息：{user_text}")

    # ---- Episodic Memory 附录（仅供参考）----
    if episodic_memories:
        parts.append("")
        parts.append("--- 以下历史事件仅供参考，不影响你的判断 ---")
        for idx, evt in enumerate(episodic_memories, 1):
            title = evt.get("title", "")
            etype = evt.get("event_type", "")
            ts = evt.get("ts", "")
            desc = evt.get("description", "")
            line = f"{idx}. [{etype}] {ts} {title}"
            if desc:
                line += f" —— {desc}"
            parts.append(line)
        parts.append("-----------------------------------------------")

    return "\n".join(parts)


def has_episodic_hint(text: str) -> bool:
    """简单启发式：判断用户消息是否可能涉及系统事件查询

    如果命中，可触发事件检索；否则跳过，减少无效查询。
    """
    # 强信号：直接涉及系统/运维/事件的关键词
    strong_hints = [
        "异常", "告警", "故障", "问题", "怎么了", "为什么", "报错",
        "变更", "发版", "上线", "部署", "升级", "重启",
        "数据库", "服务", "接口", "延迟", "超时", "宕机",
    ]
    # 弱信号：时间相关词，需配合至少一个强信号（但为简化，此处仅做初筛）
    # 实际上 SQLite 查询成本极低，宁可多查也不漏查
    hints = strong_hints
    low = text.lower()
    return any(h in low for h in hints)
