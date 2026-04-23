#!/usr/bin/env python3
"""回退验证 —— 确认备份分支和旧代码可恢复"""

import os
import subprocess
import sys


def test_backup_branch_exists():
    print("=" * 60)
    print("验证 1: 备份分支存在")
    print("=" * 60)
    result = subprocess.run(
        ["git", "branch", "--list", "backup/before-memory-rewrite"],
        capture_output=True, text=True
    )
    assert "backup/before-memory-rewrite" in result.stdout
    print("  ✅ 备份分支存在")

    result = subprocess.run(
        ["git", "log", "backup/before-memory-rewrite", "--oneline", "-1"],
        capture_output=True, text=True
    )
    print(f"  备份提交: {result.stdout.strip()}")
    print()


def test_can_restore_memory_legacy():
    print("=" * 60)
    print("验证 2: 旧版 memory.py 可从备份恢复")
    print("=" * 60)
    # 从备份分支检出旧版 memory.py 到临时文件
    result = subprocess.run(
        ["git", "show", "backup/before-memory-rewrite:memory.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "chromadb" in result.stdout, "旧版应包含 chromadb 导入"
    assert "SentenceTransformerEmbeddingFunction" in result.stdout
    print("  ✅ 备份分支中的旧版 memory.py 完整可恢复")
    print()


def test_memory_legacy_file_intact():
    print("=" * 60)
    print("验证 3: 本地 memory_legacy.py 备份完好")
    print("=" * 60)
    assert os.path.exists("memory_legacy.py")
    with open("memory_legacy.py") as f:
        content = f.read()
    assert "chromadb" in content
    assert "SentenceTransformerEmbeddingFunction" in content
    print("  ✅ memory_legacy.py 备份完好，一键可回退")
    print()


def test_rollback_command_documented():
    print("=" * 60)
    print("验证 4: 回退命令文档化")
    print("=" * 60)
    with open("docs/plans/memory-rewrite-plan.md") as f:
        plan = f.read()
    assert "git reset --hard backup/before-memory-rewrite" in plan
    print("  ✅ 回退命令已在计划文档中记录")
    print()


if __name__ == "__main__":
    try:
        test_backup_branch_exists()
        test_can_restore_memory_legacy()
        test_memory_legacy_file_intact()
        test_rollback_command_documented()

        print("=" * 60)
        print("🎉 回退验证通过！如需回退，执行：")
        print("    git reset --hard backup/before-memory-rewrite")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 验证失败: {e}")
        sys.exit(1)
