#!/usr/bin/env python3
"""Step 3 集成测试 —— 模拟 app.py 中 prompt 构建的完整链路"""

import os
import shutil
import tempfile

# 隔离测试环境
TEST_DIR = "./test_step3"
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
os.makedirs(TEST_DIR)

from event_store import EventStore
from semantic_store import SemanticStore
from memory import MemoryLayer
from prompt_builder import build_prompt, has_episodic_hint


def test_full_pipeline():
    print("=" * 60)
    print("测试: app.py 风格完整 prompt 构建链路")
    print("=" * 60)

    # 初始化（模拟 app.py 启动）
    memory = MemoryLayer(db_path=TEST_DIR)
    event_store = EventStore(db_path=os.path.join(TEST_DIR, "events.db"))

    user_id = "u_test"

    # 1. 预置语义记忆
    memory.add(user_id, "用户偏好中文交流")
    memory.add(user_id, "用户在北京工作")

    # 2. 预置事件记忆
    event_store.add_event(
        user_id=user_id,
        title="test1 数据库索引优化",
        description="orders 表增加联合索引",
        event_type="系统变更",
        entities=["test1", "MySQL"],
    )
    event_store.add_event(
        user_id=user_id,
        title="订单服务 v2.3.1 上线",
        event_type="应用发版",
        entities=["订单服务"],
    )
    event_store.add_event(
        user_id=user_id,
        title=" unrelated event",
        event_type="手动记录",
        entities=["other"],
    )

    # 3. 模拟用户消息（运维场景）
    user_text = "test1 数据库怎么了"
    assert has_episodic_hint(user_text) is True, "应触发事件检索"

    semantic_memories = memory.search(user_id, user_text)
    # 模拟 app.py 中的轻量实体提取
    raw_ents = __import__('re').findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", user_text)
    raw_ents += __import__('re').findall(r"[\u4e00-\u9fff]{2,}", user_text)
    entities = [e for e in raw_ents if len(e) >= 2]
    episodic_memories = event_store.search_events(
        user_id, query=user_text, entities=entities or None, days=14, top_k=5
    )

    prompt = build_prompt(user_text, semantic_memories, episodic_memories)

    print(f"\n生成的 prompt：\n{'-'*40}")
    print(prompt)
    print(f"{'-'*40}\n")

    # 验证结构
    assert "关于这个用户的已知信息：" in prompt, "Semantic 前缀必须存在"
    assert "用户偏好中文交流" in prompt, "语义记忆内容应包含"
    assert f"用户消息：{user_text}" in prompt, "用户消息主体应存在"
    assert "以下历史事件仅供参考，不影响你的判断" in prompt, "Episodic 围栏必须存在"
    assert "test1 数据库索引优化" in prompt, "相关事件应被召回"
    # 由于当前 FTS5 对中文支持有限，实体过滤是主要召回手段
    # test1 相关的查询应优先召回 test1 事件
    assert any("test1" in e["title"] for e in episodic_memories), "test1 相关事件应被召回"

    # 顺序验证
    semantic_pos = prompt.index("关于这个用户的已知信息")
    user_pos = prompt.index("用户消息：")
    episodic_pos = prompt.index("仅供参考")
    assert semantic_pos < user_pos < episodic_pos, "顺序必须 Semantic < User < Episodic"

    print("  ✅ 完整链路测试通过")
    print()

    # 4. 模拟闲聊消息（不应触发事件检索）
    user_text2 = "你好"
    assert has_episodic_hint(user_text2) is False, "闲聊不应触发事件检索"

    semantic_memories2 = memory.search(user_id, user_text2)
    episodic_memories2 = []
    if has_episodic_hint(user_text2):
        raw_ents2 = __import__('re').findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", user_text2)
        raw_ents2 += __import__('re').findall(r"[\u4e00-\u9fff]{2,}", user_text2)
        entities2 = [e for e in raw_ents2 if len(e) >= 2]
        episodic_memories2 = event_store.search_events(
            user_id, query=user_text2, entities=entities2 or None, days=14, top_k=5
        )

    prompt2 = build_prompt(user_text2, semantic_memories2, episodic_memories2)

    print(f"闲聊 prompt：\n{'-'*40}")
    print(prompt2)
    print(f"{'-'*40}\n")

    assert "仅供参考" not in prompt2, "闲聊不应包含事件围栏"
    assert "用户消息：你好" in prompt2
    print("  ✅ 闲聊场景测试通过")

    # 清理
    shutil.rmtree(TEST_DIR)


if __name__ == "__main__":
    test_full_pipeline()
    print("=" * 60)
    print("🎉 Step 3 集成测试通过！")
    print("=" * 60)
