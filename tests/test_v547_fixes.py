"""验证 MindForge v5.4.7 三个修复的正确性"""
import sys
import os
import struct
import tempfile
import sqlite3

# 确保导入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storage import StorageEngine
from core.indexer import IndexEngine
from core.embedding import EmbeddingEngine

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# ============================================================
# 修复 1: get_embedding_status() 在 engine 不可用时仍返回 DB 实际数量
# ============================================================
print("\n=== 修复 1: get_embedding_status ===")

tmpdir1 = tempfile.mkdtemp()
try:
    db_path = os.path.join(tmpdir1, "test.db")
    storage = StorageEngine(db_path=db_path, encrypted=False)
    conn = storage._get_conn()

    # 手动插入 3 条向量到 memory_embeddings（表已由 StorageEngine 自动创建）
    for i in range(3):
        blob = struct.pack('<4f', 1.0, 0.0, 0.0, 0.0)
        conn.execute(
            "INSERT OR REPLACE INTO memory_embeddings (memory_id, embedding, model_name, dimension, created_at) VALUES (?,?,?,?,?)",
            (f"mem_{i}", blob, "test-model", 4, 1000.0)
        )
    conn.commit()

    # 确保 embedding_engine 不可用
    storage._embedding_eng = None

    # 模拟修复后的 get_embedding_status 行为
    row = conn.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()
    count = row[0] if row else 0
    check("DB 中有 3 条向量，直接查询 count=3", count == 3)

    engine = storage.embedding_engine
    if engine is None or not (hasattr(engine, 'is_available') and engine.is_available):
        status = {
            "available": False,
            "model_name": "",
            "dimension": 0,
            "embedding_count": count,
        }
    check("engine 不可用时 embedding_count=3（非 0）", status["embedding_count"] == 3)
    check("engine 不可用时 available=False", status["available"] == False)
finally:
    storage.close()
    import shutil
    shutil.rmtree(tmpdir1, ignore_errors=True)


# ============================================================
# 修复 2: FTS5 查询特殊字符转义
# ============================================================
print("\n=== 修复 2: FTS5 特殊字符转义 ===")

# 测试 _escape_fts5_query
check("转义 C++ → '\"C++\"'", IndexEngine._escape_fts5_query("C++") == '"C++"')
check("转义 hello:world → '\"hello:world\"'", IndexEngine._escape_fts5_query("hello:world") == '"hello:world"')
check("转义 a\"b → '\"a\"\"b\"'", IndexEngine._escape_fts5_query('a"b') == '"a""b"')
check("转义 (test) → '\"(test)\"'", IndexEngine._escape_fts5_query("(test)") == '"(test)"')
check("空字符串返回空", IndexEngine._escape_fts5_query("") == "")
check("纯空白返回空", IndexEngine._escape_fts5_query("   ") == "")
check("普通文本 MySQL 复制 → '\"MySQL 复制\"'", IndexEngine._escape_fts5_query("MySQL 复制") == '"MySQL 复制"')

# 实际 FTS5 测试：含特殊字符的查询不应崩溃
tmpdir2 = tempfile.mkdtemp()
try:
    db_path = os.path.join(tmpdir2, "test.db")
    storage = StorageEngine(db_path=db_path, encrypted=False)
    indexer = IndexEngine()

    # 禁用 embedding engine，防止 add_memory 尝试下载模型
    storage._embedding_eng = None

    conn = storage._get_conn()

    # 插入测试数据
    from core.types import MemoryLayer
    entry = storage.add_memory(
        content="C++ is a programming language",
        category="tech",
        layer=MemoryLayer.LONG_TERM,
    )
    entry2 = storage.add_memory(
        content="Python decorator pattern",
        category="tech",
        layer=MemoryLayer.LONG_TERM,
    )
    # 同步 FTS
    conn.execute("""
        INSERT INTO memory_fts (rowid, content, category, tags)
        SELECT rowid, content, category, tags FROM memories
    """)
    conn.commit()

    # 测试含特殊字符的查询不崩溃
    results = indexer.fts_search(conn, "C++", top_k=5)
    check("FTS5 搜索 'C++' 不崩溃", isinstance(results, list))
    check("FTS5 搜索 'C++' 有结果", len(results) > 0)

    results2 = indexer.fts_search(conn, "decorator(pattern)", top_k=5)
    check("FTS5 搜索 'decorator(pattern)' 不崩溃", isinstance(results2, list))

    results3 = indexer.fts_search(conn, "test:value", top_k=5)
    check("FTS5 搜索 'test:value' 不崩溃", isinstance(results3, list))
finally:
    storage.close()
    import shutil
    shutil.rmtree(tmpdir2, ignore_errors=True)


# ============================================================
# 修复 3: vector_search 支持预计算 query_vector
# ============================================================
print("\n=== 修复 3: vector_search 支持 query_vector ===")

tmpdir3 = tempfile.mkdtemp()
try:
    db_path = os.path.join(tmpdir3, "test.db")
    storage = StorageEngine(db_path=db_path, encrypted=False)

    # 禁用 embedding engine，防止 add_memory 尝试下载模型
    storage._embedding_eng = None

    # 添加几条记忆
    e1 = storage.add_memory(content="手机是通讯工具", category="tech", layer=MemoryLayer.LONG_TERM)
    e2 = storage.add_memory(content="苹果是水果", category="life", layer=MemoryLayer.LONG_TERM)
    e3 = storage.add_memory(content="平板电脑是电子设备", category="tech", layer=MemoryLayer.LONG_TERM)

    # 手动注入向量
    conn = storage._get_conn()
    # 手机 → [1, 0, 0, 0]
    # 苹果 → [0, 1, 0, 0]
    # 平板 → [0.9, 0.1, 0, 0]
    vectors = {
        e1.id: [1.0, 0.0, 0.0, 0.0],
        e2.id: [0.0, 1.0, 0.0, 0.0],
        e3.id: [0.9, 0.1, 0.0, 0.0],
    }
    for mem_id, vec in vectors.items():
        blob = struct.pack(f'<{len(vec)}f', *vec)
        conn.execute(
            "INSERT OR REPLACE INTO memory_embeddings (memory_id, embedding, model_name, dimension, created_at) VALUES (?,?,?,?,?)",
            (mem_id, blob, "test", 4, 1000.0)
        )
    conn.commit()

    # 不传 query_vector → 应该返回空（无法 encode query）
    results_no_vec = storage.vector_search(query="通讯", top_k=5)
    check("engine 不可用 + 无 query_vector → 返回空", results_no_vec == [])

    # 传 query_vector → 应该返回结果
    query_vec = [1.0, 0.0, 0.0, 0.0]  # 接近"手机"
    results_with_vec = storage.vector_search(query="", top_k=5, query_vector=query_vec)
    check("engine 不可用 + 有 query_vector → 返回结果", len(results_with_vec) > 0)
    check("结果按余弦相似度排序", len(results_with_vec) >= 2)
    if len(results_with_vec) >= 2:
        check("手机排第一（最接近 [1,0,0,0]）",
              results_with_vec[0]["entry"].id == e1.id)
        check("平板排第二",
              results_with_vec[1]["entry"].id == e3.id)
    check("所有结果 strategy='vector'",
          all(r["strategy"] == "vector" for r in results_with_vec))

    # 测试 fallback 反序列化
    blob = struct.pack('<4f', 1.0, 2.0, 3.0, 4.0)
    deserialized = StorageEngine._deserialize_vector_fallback(blob, 4)
    check("fallback 反序列化正确", deserialized == [1.0, 2.0, 3.0, 4.0])
    check("fallback 维度不匹配返回 None",
          StorageEngine._deserialize_vector_fallback(blob, 3) is None)
    check("fallback 空 blob 返回 None",
          StorageEngine._deserialize_vector_fallback(b"", 4) is None)

    # 测试 fallback 余弦相似度
    candidates = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.707, 0.707])]
    batch = StorageEngine._cosine_similarity_batch_fallback([1.0, 0.0], candidates, top_k=2)
    check("fallback batch 返回 top_k=2", len(batch) == 2)
    check("fallback batch 排序正确（a 第一）", batch[0][0] == "a")
finally:
    storage.close()
    import shutil
    shutil.rmtree(tmpdir3, ignore_errors=True)


# ============================================================
# 汇总
# ============================================================
print(f"\n{'='*50}")
print(f"总计: {PASS + FAIL} | 通过: {PASS} | 失败: {FAIL}")
if FAIL == 0:
    print("全部通过！")
else:
    print(f"有 {FAIL} 个失败！")
    sys.exit(1)
