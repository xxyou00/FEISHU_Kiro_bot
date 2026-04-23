#!/usr/bin/env python3
"""EventStore 功能与性能测试"""

import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

from event_store import EventStore

TEST_DB = "./test_events.db"


def setup() -> EventStore:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return EventStore(db_path=TEST_DB)


def teardown():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_basic_crud():
    print("=" * 60)
    print("测试 1: 基本 CRUD")
    print("=" * 60)

    store = setup()
    assert store.count() == 0, "初始应为空"
    print(f"  ✅ 初始事件数: {store.count()}")

    eid = store.add_event(
        user_id="user_001",
        title="test1 数据库索引优化",
        description="对 orders 表增加联合索引 (status, created_at)",
        event_type="系统变更",
        entities=["test1", "MySQL", "orders"],
        source="jenkins",
        severity="medium",
    )
    assert len(eid) == 32, "event_id 应为 32 位 hex"
    print(f"  ✅ 添加事件，id={eid[:8]}...")

    evt = store.get_event_by_id(eid)
    assert evt is not None
    assert evt["title"] == "test1 数据库索引优化"
    assert evt["entities"] == ["test1", "MySQL", "orders"]
    print(f"  ✅ 查询单条正确")

    # 再添加几条
    store.add_event("user_001", "订单服务 v2.3.1 上线", event_type="应用发版", entities=["订单服务"])
    store.add_event("user_002", "user_002 的独立事件", event_type="手动记录", entities=["user2-res"])
    assert store.count() == 3
    assert store.count("user_001") == 2
    assert store.count("user_002") == 1
    print(f"  ✅ 用户隔离正常")

    store.clear("user_002")
    assert store.count("user_002") == 0
    assert store.count() == 2
    print(f"  ✅ 清除单用户后总数: {store.count()}")

    store.clear()
    assert store.count() == 0
    print(f"  ✅ 全部清除后: {store.count()}")
    teardown()
    print()


def test_time_filter():
    print("=" * 60)
    print("测试 2: 时间范围过滤")
    print("=" * 60)

    store = setup()
    now = datetime.now(timezone.utc)

    # 插入不同时间的事件
    store.add_event("u1", "今天的事件", event_type="系统变更", ts=now)
    store.add_event("u1", "5天前的事件", event_type="系统变更", ts=now - timedelta(days=5))
    store.add_event("u1", "15天前的事件", event_type="系统变更", ts=now - timedelta(days=15))
    store.add_event("u1", "29天前的事件", event_type="系统变更", ts=now - timedelta(days=29))

    # 查最近 7 天
    results = store.search_events("u1", days=7)
    titles = [r["title"] for r in results]
    assert "今天的事件" in titles
    assert "5天前的事件" in titles
    assert "15天前的事件" not in titles
    print(f"  ✅ 7天过滤: 命中 {len(results)} 条，正确")

    # 查最近 20 天
    results = store.search_events("u1", days=20)
    titles = [r["title"] for r in results]
    assert "15天前的事件" in titles
    assert "29天前的事件" not in titles
    print(f"  ✅ 20天过滤: 命中 {len(results)} 条，正确")

    # list_events 30天（包含今天、5天前、15天前、29天前 = 4条）
    results = store.list_events("u1", days=30)
    assert len(results) == 4
    print(f"  ✅ list_events 30天: 命中 {len(results)} 条，正确")

    teardown()
    print()


def test_entity_and_type_filter():
    print("=" * 60)
    print("测试 3: 实体过滤 + 类型过滤")
    print("=" * 60)

    store = setup()
    store.add_event("u1", "test1 数据库变更", event_type="系统变更", entities=["test1", "MySQL"])
    store.add_event("u1", "test1 应用发版", event_type="应用发版", entities=["test1", "订单服务"])
    store.add_event("u1", "test2 数据库变更", event_type="系统变更", entities=["test2", "MySQL"])
    store.add_event("u1", "无关事件", event_type="手动记录", entities=["other"])

    # 按实体 test1
    results = store.search_events("u1", entities=["test1"])
    assert len(results) == 2
    assert all("test1" in r["title"] for r in results)
    print(f"  ✅ entities=[test1]: 命中 {len(results)} 条")

    # 按实体 MySQL
    results = store.search_events("u1", entities=["MySQL"])
    assert len(results) == 2
    print(f"  ✅ entities=[MySQL]: 命中 {len(results)} 条")

    # 按类型
    results = store.search_events("u1", event_types=["系统变更"])
    assert len(results) == 2
    assert all(r["event_type"] == "系统变更" for r in results)
    print(f"  ✅ event_types=[系统变更]: 命中 {len(results)} 条")

    # 组合：test1 + 系统变更
    results = store.search_events("u1", entities=["test1"], event_types=["系统变更"])
    assert len(results) == 1
    assert results[0]["title"] == "test1 数据库变更"
    print(f"  ✅ entities+types 组合过滤: 命中 {len(results)} 条")

    teardown()
    print()


def test_fts_search():
    print("=" * 60)
    print("测试 4: FTS5 全文检索")
    print("=" * 60)

    store = setup()
    store.add_event("u1", "orders 表增加索引", description="优化查询性能，减少慢 SQL", entities=["orders"])
    store.add_event("u1", "用户表迁移", description="将 user 表从 MyISAM 转为 InnoDB", entities=["user"])
    store.add_event("u1", "日志清理", description="删除 30 天前日志", entities=["log"])

    # 查 "索引"
    results = store.search_events("u1", query="索引")
    assert len(results) >= 1
    assert any("索引" in r["title"] for r in results)
    print(f"  ✅ query='索引': 命中 {len(results)} 条")

    # 查 "MyISAM"
    results = store.search_events("u1", query="MyISAM")
    assert len(results) >= 1
    assert any("MyISAM" in r["description"] for r in results)
    print(f"  ✅ query='MyISAM': 命中 {len(results)} 条（description 中匹配）")

    teardown()
    print()


def test_idempotency():
    print("=" * 60)
    print("测试 5: 幂等去重")
    print("=" * 60)

    store = setup()
    eid = "manual-id-001"
    store.add_event("u1", "首次写入", event_id=eid)
    store.add_event("u1", "重复写入", event_id=eid)
    assert store.count() == 1
    evt = store.get_event_by_id(eid)
    assert evt["title"] == "首次写入"  # 第二次应被跳过
    print(f"  ✅ 相同 event_id 重复写入被忽略，count={store.count()}")

    teardown()
    print()


def test_validation():
    print("=" * 60)
    print("测试 6: 参数校验")
    print("=" * 60)

    store = setup()

    try:
        store.add_event("u1", "标题", event_type="非法类型")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "非法 event_type" in str(e)
        print(f"  ✅ 非法 event_type 被拦截")

    try:
        store.add_event("u1", "", event_type="系统变更")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "title 不能为空" in str(e)
        print(f"  ✅ 空 title 被拦截")

    try:
        store.add_event("u1", "标题", event_type="系统变更", severity="unknown")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "非法 severity" in str(e)
        print(f"  ✅ 非法 severity 被拦截")

    teardown()
    print()


def test_empty_and_edge():
    print("=" * 60)
    print("测试 7: 空库与边界")
    print("=" * 60)

    store = setup()
    results = store.search_events("nobody", days=7)
    assert results == []
    print(f"  ✅ 空库 search 返回 []")

    results = store.list_events("nobody", days=7)
    assert results == []
    print(f"  ✅ 空库 list 返回 []")

    evt = store.get_event_by_id("not-exist")
    assert evt is None
    print(f"  ✅ 查询不存在返回 None")

    teardown()
    print()


def test_performance():
    print("=" * 60)
    print("测试 8: 性能基准")
    print("=" * 60)

    store = setup()
    now = datetime.now(timezone.utc)

    # 批量插入 1000 条（使用 batch 接口）
    batch = []
    for i in range(1000):
        ts = now - timedelta(days=i % 30, hours=i % 24)
        batch.append({
            "user_id": f"user_{i % 10}",
            "title": f"事件 {i}: {'test1' if i % 3 == 0 else 'test2'} 数据库操作",
            "description": f"这是第 {i} 条事件的详细描述内容",
            "event_type": "系统变更" if i % 2 == 0 else "应用发版",
            "entities": ["test1", "MySQL"] if i % 3 == 0 else ["test2", "Redis"],
            "ts": ts,
        })
    start = time.perf_counter()
    store.add_events_batch(batch)
    insert_elapsed = time.perf_counter() - start
    print(f"  ✅ 批量插入 1000 条耗时: {insert_elapsed:.3f}s (目标 < 3s)")
    assert insert_elapsed < 3.0, f"批量插入太慢: {insert_elapsed:.3f}s"

    # 查询性能
    start = time.perf_counter()
    for _ in range(100):
        store.search_events("user_0", entities=["test1"], days=14, top_k=10)
    query_elapsed = time.perf_counter() - start
    avg_ms = (query_elapsed / 100) * 1000
    print(f"  ✅ 100 次查询耗时: {query_elapsed:.3f}s，平均 {avg_ms:.2f}ms/次 (目标 < 50ms)")
    assert avg_ms < 50, f"查询太慢: {avg_ms:.2f}ms"

    # 验证数据量
    assert store.count() == 1000
    print(f"  ✅ 总事件数: {store.count()}")

    teardown()
    print()


if __name__ == "__main__":
    try:
        test_basic_crud()
        test_time_filter()
        test_entity_and_type_filter()
        test_fts_search()
        test_idempotency()
        test_validation()
        test_empty_and_edge()
        test_performance()

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
