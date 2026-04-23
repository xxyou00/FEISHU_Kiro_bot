#!/usr/bin/env python3
"""事件录入接口测试"""

import os
import shutil
import sys

from event_ingest import (
    parse_manual_command,
    extract_entities_from_text,
    webhook_handler,
    ingest_to_store,
)
from event_store import EventStore

TEST_DB = "./test_events_ingest.db"


def setup() -> EventStore:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return EventStore(db_path=TEST_DB)


def teardown():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_parse_manual_command():
    print("=" * 60)
    print("测试 1: /event 命令解析")
    print("=" * 60)

    args = "类型=系统变更 实体=test1,MySQL 标题=索引优化 描述=增加联合索引"
    r = parse_manual_command(args)
    assert r["event_type"] == "系统变更"
    assert r["entities"] == ["test1", "MySQL"]
    assert r["title"] == "索引优化"
    assert r["description"] == "增加联合索引"
    assert r["severity"] == "medium"
    print(f"  ✅ 标准解析正确")

    # 缺省实体（自动提取），值含空格需用引号
    args2 = '标题="test1 数据库迁移到 PostgreSQL"'
    r2 = parse_manual_command(args2)
    assert r2["title"] == "test1 数据库迁移到 PostgreSQL"
    assert "test1" in r2["entities"]
    assert "数据库" in r2["entities"]
    print(f"  ✅ 缺省实体自动提取: {r2['entities']}")

    # 空参数
    r3 = parse_manual_command("")
    assert r3["title"] == ""
    print(f"  ✅ 空参数容错")

    print()


def test_extract_entities():
    print("=" * 60)
    print("测试 2: 轻量实体提取")
    print("=" * 60)

    text = "test1 数据库发生异常，订单服务接口超时，涉及 Redis 集群"
    ents = extract_entities_from_text(text)
    assert "test1" in ents
    assert any("数据库" in e for e in ents)
    assert any("订单服务" in e for e in ents)
    assert any("接口" in e for e in ents)
    assert "Redis" in ents
    assert "集群" in ents
    # 停用词应被过滤
    assert "这是" not in ents
    print(f"  ✅ 提取结果: {ents}")

    # 纯英文
    ents2 = extract_entities_from_text("AWS EC2 instance i-12345 failed")
    assert "AWS" in ents2
    assert "EC2" in ents2
    assert "instance" in ents2
    assert "i-12345" in ents2
    assert "failed" in ents2
    print(f"  ✅ 英文提取: {ents2}")

    print()


def test_webhook_handler():
    print("=" * 60)
    print("测试 3: Webhook 处理")
    print("=" * 60)

    payload = {
        "id": "jenkins-12345",
        "event_type": "应用发版",
        "title": "订单服务 v2.3.1 上线",
        "description": "修复支付回调超时问题",
        "entities": ["订单服务"],
        "source": "jenkins",
        "severity": "low",
        "timestamp": "2026-04-23T10:00:00",
        "user_id": "u_001",
    }
    r = webhook_handler(payload, default_user_id="u_fallback")
    assert r["ok"] is True
    assert r["event_id"] == "jenkins-12345"
    assert r["user_id"] == "u_001"
    assert r["source"] == "jenkins"
    print(f"  ✅ 完整 payload 处理正确")

    # 缺省字段
    payload2 = {
        "id": "zbx-999",
        "event_type": "指标异常",
        "title": "test1 CPU 使用率超过 90%",
    }
    r2 = webhook_handler(payload2, default_user_id="u_fallback")
    assert r2["ok"] is True
    assert r2["user_id"] == "u_fallback"  # 使用默认值
    assert r2["source"] == "webhook"
    assert "test1" in r2["entities"]  # 自动提取
    assert "CPU" in r2["entities"]
    print(f"  ✅ 缺省字段自动填充: entities={r2['entities']}")

    # 校验失败
    r3 = webhook_handler({}, "u_fallback")
    assert r3["ok"] is False
    assert "id" in r3["error"]
    print(f"  ✅ 空 payload 被拦截")

    print()


def test_ingest_and_idempotency():
    print("=" * 60)
    print("测试 4: 入库 + 幂等")
    print("=" * 60)

    store = setup()

    record = {
        "event_id": "test-001",
        "user_id": "u1",
        "title": "test event",
        "event_type": "系统变更",
        "entities": ["test1"],
    }
    r1 = ingest_to_store(store, record)
    assert r1["ok"] is True
    assert store.count() == 1
    print(f"  ✅ 首次入库成功")

    # 重复写入
    r2 = ingest_to_store(store, record)
    assert r2["ok"] is True
    assert store.count() == 1, "幂等去重失败"
    print(f"  ✅ 重复写入被忽略，count={store.count()}")

    # 非法类型
    record_bad = {
        "event_id": "test-002",
        "user_id": "u1",
        "title": "bad",
        "event_type": "不存在的类型",
    }
    r3 = ingest_to_store(store, record_bad)
    assert r3["ok"] is False
    print(f"  ✅ 非法类型被拦截: {r3['error']}")

    teardown()
    print()


if __name__ == "__main__":
    try:
        test_parse_manual_command()
        test_extract_entities()
        test_webhook_handler()
        test_ingest_and_idempotency()

        print("=" * 60)
        print("🎉 全部测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
