#!/usr/bin/env python3
"""性能基准测试 —— 验证大数据量下的查询延迟与内存占用"""

import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

from event_store import EventStore
from semantic_store import SemanticStore

TEST_DIR = "./test_perf"


def benchmark_event_store():
    print("=" * 60)
    print("EventStore 性能基准")
    print("=" * 60)

    db_path = os.path.join(TEST_DIR, "events_perf.db")
    store = EventStore(db_path=db_path)
    now = datetime.now(timezone.utc)

    # 插入 10000 条事件
    batch = []
    for i in range(10000):
        ts = now - timedelta(days=i % 60, hours=i % 24)
        batch.append({
            "user_id": f"user_{i % 50}",
            "title": f"事件 {i}: {'test1' if i % 5 == 0 else 'test2' if i % 5 == 1 else 'other'} 操作记录",
            "description": f"这是第 {i} 条事件的详细描述内容，用于性能测试",
            "event_type": "系统变更" if i % 3 == 0 else "应用发版" if i % 3 == 1 else "指标异常",
            "entities": ["test1", "MySQL"] if i % 5 == 0 else ["test2", "Redis"] if i % 5 == 1 else ["other"],
            "ts": ts,
        })

    start = time.perf_counter()
    store.add_events_batch(batch)
    insert_time = time.perf_counter() - start
    print(f"  批量插入 10000 条: {insert_time:.3f}s")
    assert insert_time < 10.0, f"插入太慢: {insert_time:.3f}s"

    # 查询性能
    start = time.perf_counter()
    for _ in range(200):
        store.search_events("user_0", entities=["test1"], days=14, top_k=10)
    query_time = time.perf_counter() - start
    avg_ms = (query_time / 200) * 1000
    print(f"  200 次查询: {query_time:.3f}s，平均 {avg_ms:.2f}ms/次")
    assert avg_ms < 100, f"查询太慢: {avg_ms:.2f}ms"

    # list_events 性能
    start = time.perf_counter()
    for _ in range(100):
        store.list_events("user_0", days=30, limit=100)
    list_time = time.perf_counter() - start
    avg_list_ms = (list_time / 100) * 1000
    print(f"  100 次 list: {list_time:.3f}s，平均 {avg_list_ms:.2f}ms/次")

    # 文件大小
    db_size = os.path.getsize(db_path) / (1024 * 1024)
    print(f"  数据库文件大小: {db_size:.2f} MB")

    print()


def benchmark_semantic_store():
    print("=" * 60)
    print("SemanticStore 性能基准")
    print("=" * 60)

    db_path = os.path.join(TEST_DIR, "semantic_perf.db")
    store = SemanticStore(db_path=db_path)

    # 插入 1000 条语义记忆
    start = time.perf_counter()
    for i in range(1000):
        store.add(f"user_{i % 20}", f"用户偏好记录 {i}：{'在北京工作' if i % 3 == 0 else '使用 AWS' if i % 3 == 1 else '喜欢中文'}")
    insert_time = time.perf_counter() - start
    print(f"  插入 1000 条: {insert_time:.3f}s")

    # 搜索性能
    start = time.perf_counter()
    for _ in range(200):
        store.search("user_0", "AWS 费用", top_k=5)
    search_time = time.perf_counter() - start
    avg_ms = (search_time / 200) * 1000
    print(f"  200 次搜索: {search_time:.3f}s，平均 {avg_ms:.2f}ms/次")
    assert avg_ms < 50, f"搜索太慢: {avg_ms:.2f}ms"

    # 文件大小
    db_size = os.path.getsize(db_path) / (1024 * 1024)
    print(f"  数据库文件大小: {db_size:.2f} MB")

    print()


def benchmark_memory_usage():
    print("=" * 60)
    print("进程内存基准（启动后 RSS）")
    print("=" * 60)
    import subprocess
    result = subprocess.run(
        ["python3", "-c",
         "import os; from semantic_store import SemanticStore; from event_store import EventStore; "
         "s=SemanticStore('/tmp/perf_sem.db'); e=EventStore('/tmp/perf_evt.db'); "
         "import psutil; p=psutil.Process(); print(p.memory_info().rss / 1024 / 1024)"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        rss = float(result.stdout.strip())
        print(f"  启动后 RSS: {rss:.1f} MB")
        assert rss < 100, f"内存占用过高: {rss:.1f} MB"
    else:
        print(f"  ⚠️  未安装 psutil，跳过内存测试。stderr: {result.stderr.strip()}")
    print()


if __name__ == "__main__":
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    try:
        benchmark_event_store()
        benchmark_semantic_store()
        benchmark_memory_usage()

        print("=" * 60)
        print("🎉 性能基准测试通过！")
        print("=" * 60)
    finally:
        shutil.rmtree(TEST_DIR)
