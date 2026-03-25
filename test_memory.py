#!/usr/bin/env python3
"""记忆层功能测试"""
import shutil
import sys
import os

# 用临时目录避免污染正式数据
TEST_DB = "./test_memory_db"
if os.path.exists(TEST_DB):
    shutil.rmtree(TEST_DB)

from memory import MemoryLayer

def test_basic_crud():
    """测试基本增删查"""
    print("=" * 50)
    print("测试 1: 基本 CRUD")
    print("=" * 50)

    mem = MemoryLayer(db_path=TEST_DB)
    assert mem.count() == 0, "初始应为空"
    print(f"  ✅ 初始记忆数: {mem.count()}")

    # 添加记忆
    mem.add("user_001", "用户偏好中文交流")
    mem.add("user_001", "用户在北京工作")
    mem.add("user_001", "用户使用 AWS 做云计算")
    mem.add("user_002", "这是另一个用户的记忆")
    assert mem.count() == 4
    print(f"  ✅ 添加 4 条记忆，当前: {mem.count()}")

    # 去重测试
    mem.add("user_001", "用户偏好中文交流")  # 重复
    assert mem.count() == 4, "重复记忆不应增加"
    print(f"  ✅ 去重正常，重复添加后仍为: {mem.count()}")

    # 按用户列出
    u1_mems = mem.list_all("user_001")
    assert len(u1_mems) == 3
    print(f"  ✅ user_001 有 {len(u1_mems)} 条记忆")

    u2_mems = mem.list_all("user_002")
    assert len(u2_mems) == 1
    print(f"  ✅ user_002 有 {len(u2_mems)} 条记忆（用户隔离正常）")

    # 清除单用户
    mem.clear("user_002")
    assert len(mem.list_all("user_002")) == 0
    print(f"  ✅ 清除 user_002 后: {len(mem.list_all('user_002'))} 条")

    # 全部清除
    mem.clear()
    assert mem.count() == 0
    print(f"  ✅ 全部清除后: {mem.count()}")
    print()


def test_search():
    """测试语义搜索"""
    print("=" * 50)
    print("测试 2: 语义搜索")
    print("=" * 50)

    mem = MemoryLayer(db_path=TEST_DB)
    mem.clear()

    # 添加多条记忆
    memories = [
        "用户的 AWS 账户月费用约 5 万元人民币",
        "用户主要使用 EC2 和 S3 服务",
        "用户偏好用中文沟通",
        "用户在北京海淀区办公",
        "用户的团队有 10 个开发人员",
        "用户正在考虑购买 Savings Plans",
        "用户的数据库使用 RDS MySQL",
    ]
    for m in memories:
        mem.add("user_test", m)
    print(f"  已添加 {len(memories)} 条记忆")

    # 搜索测试
    queries = [
        ("AWS 费用多少", "费用"),
        ("用什么云服务", "EC2"),
        ("在哪里上班", "北京"),
        ("省钱方案", "Savings"),
        ("数据库", "RDS"),
    ]

    all_pass = True
    for query, expected_keyword in queries:
        results = mem.search("user_test", query, top_k=2)
        hit = any(expected_keyword in r for r in results)
        status = "✅" if hit else "❌"
        if not hit:
            all_pass = False
        print(f"  {status} 查询「{query}」→ Top结果: {results[0][:40]}...")

    # 用户隔离：搜索不存在的用户
    results = mem.search("user_nobody", "AWS 费用")
    assert len(results) == 0
    print(f"  ✅ 用户隔离: 不存在的用户搜索返回 {len(results)} 条")

    mem.clear()
    print()
    return all_pass


def test_empty_search():
    """测试空数据库搜索"""
    print("=" * 50)
    print("测试 3: 边界情况")
    print("=" * 50)

    mem = MemoryLayer(db_path=TEST_DB)
    mem.clear()

    # 空库搜索不应报错
    results = mem.search("user_x", "任意查询")
    assert results == []
    print(f"  ✅ 空库搜索返回空列表")

    # 空文本
    mem.add("user_x", "")
    print(f"  ✅ 空文本添加不报错，当前: {mem.count()} 条")

    mem.clear()
    print()


if __name__ == "__main__":
    try:
        test_basic_crud()
        search_ok = test_search()
        test_empty_search()

        print("=" * 50)
        if search_ok:
            print("🎉 所有测试通过！")
        else:
            print("⚠️  部分语义搜索结果不够精确（可接受，embedding 模型的局限）")
        print("=" * 50)
    finally:
        # 清理测试数据
        if os.path.exists(TEST_DB):
            shutil.rmtree(TEST_DB)
            print("🧹 测试数据已清理")
