"""事件录入接口 —— 手动命令解析 + 外部系统 Webhook

支持：
- 飞书 /event 命令手动录入
- 外部系统（Jenkins/Zabbix/Apollo 等）HTTP 推送
- 轻量本地实体提取（零 LLM 依赖）
"""

import logging
import re
import shlex
from typing import Any

from event_store import EventStore

log = logging.getLogger("event-ingest")

# 常见中文停用词（实体提取时过滤）
_STOP_WORDS = frozenset({
    "这是", "一个", "进行", "完成", "已经", "开始", "结束", "需要",
    "使用", "通过", "根据", "关于", "目前", "今天", "昨天", "最近",
})


def parse_manual_command(args_str: str) -> dict[str, Any]:
    """解析 /event 命令参数

    用法示例：
        /event 类型=系统变更 实体=test1,MySQL 标题=索引优化 描述=增加联合索引
        /event 类型=应用发版 实体=订单服务 标题=v2.3.1上线

    返回 dict，键：event_type, entities, title, description, severity, source
    """
    result: dict[str, Any] = {
        "event_type": "手动记录",
        "entities": [],
        "title": "",
        "description": "",
        "severity": "medium",
        "source": "manual",
    }

    if not args_str.strip():
        return result

    # 用 shlex 分词，支持引号包裹的值
    try:
        tokens = shlex.split(args_str)
    except ValueError:
        # 引号不匹配时退化为简单分割
        tokens = args_str.split()

    # 解析 key=value
    for token in tokens:
        if "=" in token:
            key, _, val = token.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key in ("类型", "type", "event_type"):
                result["event_type"] = val
            elif key in ("实体", "entities", "entity"):
                result["entities"] = [e.strip() for e in val.split(",") if e.strip()]
            elif key in ("标题", "title"):
                result["title"] = val
            elif key in ("描述", "desc", "description"):
                result["description"] = val
            elif key in ("级别", "severity"):
                result["severity"] = val
            elif key in ("来源", "source"):
                result["source"] = val

    # 如果标题为空，把整条命令当作标题（容错）
    if not result["title"]:
        result["title"] = args_str.strip()[:100]

    # 如果未提供实体，尝试从标题+描述中自动提取
    if not result["entities"]:
        combined = result["title"] + " " + result["description"]
        result["entities"] = extract_entities_from_text(combined)

    return result


def extract_entities_from_text(text: str) -> list[str]:
    """轻量实体提取：从文本中抽取候选资源名

    策略：
    1. 英文/数字/连字符标识符（如 test1, service-a, db_01, MySQL, EC2）
    2. 中文连续词（长度>=2），过滤停用词
    3. 去重并保持顺序
    """
    if not text:
        return []

    candidates: list[str] = []

    # 英文/数字/下划线/连字符（首字符必须是字母或数字）
    en = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", text)
    for w in en:
        if len(w) >= 2:
            candidates.append(w)

    # 中文连续词
    zh = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for w in zh:
        if w not in _STOP_WORDS:
            candidates.append(w)
        # 额外添加 2-gram / 3-gram 子串，提升子词召回
        if len(w) >= 3:
            for i in range(len(w) - 1):
                bigram = w[i : i + 2]
                if bigram not in _STOP_WORDS:
                    candidates.append(bigram)
            for i in range(len(w) - 2):
                trigram = w[i : i + 3]
                if trigram not in _STOP_WORDS:
                    candidates.append(trigram)

    # 去重并保持顺序
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        low = c.lower()
        if low not in seen:
            seen.add(low)
            result.append(c)
    return result


def webhook_handler(payload: dict[str, Any], default_user_id: str) -> dict[str, Any]:
    """处理外部系统推送的事件

    期望 payload 字段：
    - id: 业务系统唯一标识（必填，用于幂等）
    - event_type: 事件类型（必填）
    - title: 标题（必填）
    - description: 描述（可选）
    - entities: list[str]（可选，未提供时自动提取）
    - source: 来源标识（可选，默认 webhook）
    - severity: 级别（可选，默认 medium）
    - timestamp: ISO 格式时间（可选，默认当前时间）
    - user_id: 归属用户（可选，默认 default_user_id）

    返回：{"ok": True, "event_id": "..."} 或 {"ok": False, "error": "..."}
    """
    # 必填校验
    event_id = payload.get("id") or payload.get("event_id")
    if not event_id:
        return {"ok": False, "error": "缺少 id 字段"}

    event_type = payload.get("event_type")
    if not event_type:
        return {"ok": False, "error": "缺少 event_type 字段"}

    title = payload.get("title")
    if not title:
        return {"ok": False, "error": "缺少 title 字段"}

    # 实体提取（兜底）
    entities = payload.get("entities")
    if not entities:
        combined = title + " " + payload.get("description", "")
        entities = extract_entities_from_text(combined)

    return {
        "ok": True,
        "event_id": event_id,
        "user_id": payload.get("user_id") or default_user_id,
        "event_type": event_type,
        "title": title,
        "description": payload.get("description", ""),
        "entities": entities,
        "source": payload.get("source", "webhook"),
        "severity": payload.get("severity", "medium"),
        "timestamp": payload.get("timestamp"),
    }


def ingest_to_store(store: EventStore, record: dict[str, Any]) -> dict[str, Any]:
    """将校验后的记录写入 EventStore，返回操作结果"""
    try:
        eid = store.add_event(
            user_id=record["user_id"],
            title=record["title"],
            description=record.get("description", ""),
            event_type=record["event_type"],
            entities=record.get("entities"),
            ts=record.get("timestamp"),
            source=record.get("source", "webhook"),
            severity=record.get("severity", "medium"),
            event_id=record.get("event_id"),
        )
        return {"ok": True, "event_id": eid}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        log.exception("事件入库失败")
        return {"ok": False, "error": f"内部错误: {e}"}
