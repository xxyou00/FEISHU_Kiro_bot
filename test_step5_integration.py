#!/usr/bin/env python3
"""Step 5 集成测试 —— 端到端消息链路验证（不依赖飞书 SDK / kiro-cli）"""

import os
import shutil

TEST_DIR = "./test_step5"
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
os.makedirs(TEST_DIR)

from event_store import EventStore
from memory import MemoryLayer
from prompt_builder import build_prompt, has_episodic_hint


def test_memory_events_commands():
    print("=" * 60)
    print("测试: /memory events 命令逻辑")
    print("=" * 60)

    memory = MemoryLayer(db_path=TEST_DIR)
    event_store = EventStore(db_path=os.path.join(TEST_DIR, "events.db"))
    user_id = "u_step5"

    # 预置事件
    event_store.add_event(user_id, "test1 索引优化", event_type="系统变更", entities=["test1"])
    event_store.add_event(user_id, "订单服务发版", event_type="应用发版", entities=["订单服务"])
    event_store.add_event(user_id, " old event", event_type="手动记录", entities=["other"],
                          ts="2026-01-01T00:00:00")  # 30 天前，不应列出

    # 模拟 /memory events
    events = event_store.list_events(user_id, days=30, limit=20)
    assert len(events) == 2, f"应只列出最近 30 天的 2 条事件，实际 {len(events)}"
    assert events[0]["title"] == "订单服务发版"  # 时间倒序
    print(f"  ✅ list_events 返回 {len(events)} 条")

    # 模拟 /memory events clear
    event_store.clear(user_id)
    assert event_store.count(user_id) == 0
    print(f"  ✅ events clear 后为空")

    print()


def test_episodic_prompt_and_hint():
    print("=" * 60)
    print("测试: 事件检索 + Prompt 构建 + 关联提示")
    print("=" * 60)

    memory = MemoryLayer(db_path=TEST_DIR)
    event_store = EventStore(db_path=os.path.join(TEST_DIR, "events2.db"))
    user_id = "u_step5"

    memory.add(user_id, "用户偏好中文")
    event_store.add_event(user_id, "test1 数据库变更", event_type="系统变更", entities=["test1"])
    event_store.add_event(user_id, "test1 应用发版", event_type="应用发版", entities=["test1"])

    user_text = "test1 数据库怎么了"
    assert has_episodic_hint(user_text) is True

    semantic_memories = memory.search(user_id, user_text)

    # 模拟 app.py 中的实体提取
    import re
    raw_ents = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", user_text)
    raw_ents += re.findall(r"[\u4e00-\u9fff]{2,}", user_text)
    entities = [e for e in raw_ents if len(e) >= 2]
    episodic_memories = event_store.search_events(
        user_id, query=user_text, entities=entities or None, days=14, top_k=5
    )

    assert len(episodic_memories) == 2, f"应召回 2 条 test1 相关事件，实际 {len(episodic_memories)}"

    prompt = build_prompt(user_text, semantic_memories, episodic_memories)

    # 验证 prompt 结构
    assert "关于这个用户的已知信息：" in prompt
    assert "用户消息：test1 数据库怎么了" in prompt
    assert "以下历史事件仅供参考，不影响你的判断" in prompt
    assert "test1 数据库变更" in prompt
    assert "test1 应用发版" in prompt
    print(f"  ✅ Prompt 构建正确，包含 {len(episodic_memories)} 条事件")

    # 验证回复提示格式（模拟 _deliver_result 中的 suffix）
    episodic_count = len(episodic_memories)
    suffix = ""
    if episodic_count > 0:
        suffix = f"\n\n📎 本次分析关联了 {episodic_count} 条历史事件（/memory events 查看全部）"
    assert "📎 本次分析关联了 2 条历史事件" in suffix
    print(f"  ✅ 回复提示格式正确")

    # 验证闲聊不触发
    user_text2 = "你好"
    assert has_episodic_hint(user_text2) is False
    prompt2 = build_prompt(user_text2, memory.search(user_id, user_text2), [])
    assert "📎" not in prompt2
    assert "仅供参考" not in prompt2
    print(f"  ✅ 闲聊场景不触发事件检索")

    print()


def test_no_false_positive():
    print("=" * 60)
    print("测试: 无关消息不污染 prompt")
    print("=" * 60)

    memory = MemoryLayer(db_path=TEST_DIR)
    event_store = EventStore(db_path=os.path.join(TEST_DIR, "events3.db"))
    user_id = "u_step5"

    event_store.add_event(user_id, "test1 变更", event_type="系统变更", entities=["test1"])

    # 用户问完全不同的事
    user_text = "推荐一本好书"
    assert has_episodic_hint(user_text) is False
    episodic = []
    if has_episodic_hint(user_text):
        episodic = event_store.search_events(user_id, query=user_text, days=14, top_k=5)

    prompt = build_prompt(user_text, [], episodic)
    assert "仅供参考" not in prompt
    print(f"  ✅ 无关消息不附带事件记忆")

    print()


if __name__ == "__main__":
    test_memory_events_commands()
    test_episodic_prompt_and_hint()
    test_no_false_positive()

    shutil.rmtree(TEST_DIR)
    print("=" * 60)
    print("🎉 Step 5 集成测试通过！")
    print("=" * 60)
