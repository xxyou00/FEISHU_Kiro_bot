#!/usr/bin/env python3
"""Prompt 构建器测试 —— 验证 Semantic / Episodic 分离策略"""

from prompt_builder import build_prompt, has_episodic_hint


def test_only_semantic():
    print("=" * 60)
    print("测试 1: 仅 Semantic Memory")
    print("=" * 60)

    prompt = build_prompt(
        user_text="帮我看看 AWS 费用",
        semantic_memories=["用户偏好中文交流", "用户在北京工作"],
    )
    assert "关于这个用户的已知信息：" in prompt
    assert "用户偏好中文交流" in prompt
    assert "用户消息：帮我看看 AWS 费用" in prompt
    assert "仅供参考" not in prompt
    print(f"  ✅ Semantic 前缀正确，无 Episodic 围栏")
    print()


def test_only_episodic():
    print("=" * 60)
    print("测试 2: 仅 Episodic Memory")
    print("=" * 60)

    prompt = build_prompt(
        user_text="test1 数据库怎么了",
        episodic_memories=[
            {"title": "test1 索引优化", "event_type": "系统变更", "ts": "2026-04-20", "description": "增加联合索引"},
            {"title": "订单服务 v2.3.1 上线", "event_type": "应用发版", "ts": "2026-04-21"},
        ],
    )
    assert "关于这个用户的已知信息：" not in prompt
    assert "用户消息：test1 数据库怎么了" in prompt
    assert "以下历史事件仅供参考，不影响你的判断" in prompt
    assert "[系统变更] 2026-04-20 test1 索引优化 —— 增加联合索引" in prompt
    assert "[应用发版] 2026-04-21 订单服务 v2.3.1 上线" in prompt
    assert "-----------------------------------------------" in prompt
    # 确认 episodic 出现在 user_text 之后
    user_pos = prompt.index("用户消息：")
    episodic_pos = prompt.index("仅供参考")
    assert episodic_pos > user_pos, "Episodic 应出现在 user_text 之后"
    print(f"  ✅ Episodic 附录正确，有围栏标注，位置在 user_text 之后")
    print()


def test_both():
    print("=" * 60)
    print("测试 3: Semantic + Episodic 同时存在")
    print("=" * 60)

    prompt = build_prompt(
        user_text="test1 最近有什么变更",
        semantic_memories=["用户偏好中文交流"],
        episodic_memories=[
            {"title": "test1 配置调整", "event_type": "配置变更", "ts": "2026-04-22"},
        ],
    )
    # 顺序：semantic 前缀 -> user_text -> episodic 附录
    semantic_pos = prompt.index("关于这个用户的已知信息")
    user_pos = prompt.index("用户消息：")
    episodic_pos = prompt.index("仅供参考")
    assert semantic_pos < user_pos < episodic_pos
    print(f"  ✅ 顺序正确: Semantic({semantic_pos}) < User({user_pos}) < Episodic({episodic_pos})")
    print()


def test_none():
    print("=" * 60)
    print("测试 4: 无任何记忆")
    print("=" * 60)

    prompt = build_prompt(user_text="你好")
    assert prompt == "用户消息：你好"
    print(f"  ✅ 空记忆时 prompt 就是原始 user_text")
    print()


def test_episodic_empty_fields():
    print("=" * 60)
    print("测试 5: Episodic 字段缺省")
    print("=" * 60)

    prompt = build_prompt(
        user_text="查询",
        episodic_memories=[
            {"title": "无描述事件"},  # 缺少 event_type, ts, description
        ],
    )
    assert "无描述事件" in prompt
    assert "None" not in prompt  # 不应出现 Python None 字符串
    print(f"  ✅ 缺省字段处理正确")
    print()


def test_heuristic():
    print("=" * 60)
    print("测试 6: Episodic 触发启发式")
    print("=" * 60)

    assert has_episodic_hint("test1 数据库怎么了") is True
    assert has_episodic_hint("昨天有变更吗") is True
    assert has_episodic_hint("服务宕机了") is True
    assert has_episodic_hint("你好") is False
    assert has_episodic_hint("今天天气怎么样") is False
    print(f"  ✅ 启发式判断正确")
    print()


if __name__ == "__main__":
    test_only_semantic()
    test_only_episodic()
    test_both()
    test_none()
    test_episodic_empty_fields()
    test_heuristic()

    print("=" * 60)
    print("🎉 全部测试通过！")
    print("=" * 60)
