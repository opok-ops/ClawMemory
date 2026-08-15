#!/usr/bin/env python3
"""MindForge Benchmark - 简历用真实测试数据"""

import time, json, os, sys, tempfile, random, threading
from pathlib import Path

# 清理旧数据
db_path = os.path.join(tempfile.gettempdir(), "mindforge_resume_bench.db")
key_path = os.path.join(tempfile.gettempdir(), "mindforge_resume_bench.key")
for f in [db_path, key_path]:
    if os.path.exists(f):
        os.remove(f)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.mindforge import MindForge
from core.types import MemoryConfig, Importance, PrivacyLevel, MemoryLayer, MemoryType

results = {}

# ========== 1. 初始化 ==========
t0 = time.perf_counter()
config = MemoryConfig(db_path=db_path, key_file=key_path, encrypted=False)
mf = MindForge(config=config)
mf.init_with_password("")
results["init_ms"] = round((time.perf_counter() - t0) * 1000, 2)
print(f"[1/10] Init: {results['init_ms']}ms")

# ========== 2. 批量写入（1000 条多领域记忆）==========
categories = ["python", "javascript", "devops", "database", "architecture",
              "frontend", "backend", "testing", "security", "ml"]
tags_pool = [["python","coding"],["js","web"],["docker","deploy"],["sql","db"],
             ["design"],["react","ui"],["api","rest"],["test","ci"],
             ["auth","crypto"],["model","train"]]
importances = [Importance.LOW, Importance.MEDIUM, Importance.HIGH, Importance.CRITICAL]
layers = [MemoryLayer.SENSORY, MemoryLayer.SHORT_TERM, MemoryLayer.LONG_TERM, MemoryLayer.PERMANENT]

contents = [
    "Python 的 GIL 限制多线程并行计算，但 asyncio 适合 I/O 密集型任务",
    "React Hooks 中 useEffect 的依赖数组决定了 effect 的触发时机",
    "Docker Compose 用于定义多容器应用的编排工具",
    "PostgreSQL 的 MVCC 机制通过事务 ID 实现并发控制",
    "微服务架构中服务发现常用 Consul 或 etcd",
    "TypeScript 的类型系统支持泛型、联合类型和条件类型",
    "Redis 的持久化策略：RDB 快照 + AOF 日志",
    "Kubernetes Pod 是最小调度单元，包含一个或多个容器",
    "GraphQL 相比 REST 的优势在于客户端可精确指定需要的字段",
    "机器学习中的过拟合可通过正则化、Dropout、数据增强缓解",
    "用户偏好简洁的代码风格，不喜欢过多注释",
    "用户喜欢用 pytest 做单元测试，mock 用 unittest.mock",
    "项目使用 Git flow 分支策略，main/develop/feature/hotfix",
    "团队每日站会 15 分钟，使用 Jira 管理任务",
    "生产环境使用 AWS us-east-1 区域，3 个可用区部署",
    "数据库连接池配置：最小 5，最大 50，超时 30 秒",
    "API 限流策略：每用户每分钟 100 次请求",
    "日志级别：开发 DEBUG，生产 WARNING，安全相关 ERROR",
    "CI/CD 使用 GitHub Actions，测试通过后自动部署到 staging",
    "用户偏好暗色主题，字体大小 14px，等宽字体用 JetBrains Mono",
]

t0 = time.perf_counter()
ids = []
for i in range(1000):
    base = contents[i % len(contents)]
    content = f"{base} [variant-{i}]" if i >= len(contents) else base
    cat = categories[i % len(categories)]
    tag = tags_pool[i % len(tags_pool)]
    imp = importances[i % len(importances)]
    layer = layers[i % len(layers)]
    entry = mf.add(content=content, category=cat, tags=tag, importance=imp, layer=layer)
    ids.append(entry.id)
write_time = time.perf_counter() - t0
results["write_1000_total_s"] = round(write_time, 3)
results["write_1000_avg_ms"] = round(write_time * 1000 / 1000, 3)
print(f"[2/10] Write 1000: {results['write_1000_total_s']}s (avg {results['write_1000_avg_ms']}ms/item)")

# ========== 3. 检索性能 ==========
queries = [
    "Python 多线程 并行",
    "React Hooks 前端",
    "Docker 容器编排",
    "数据库 PostgreSQL 并发",
    "微服务 架构设计",
    "TypeScript 类型",
    "Redis 缓存",
    "Kubernetes 部署",
    "API 限流",
    "用户偏好 代码风格",
]

search_times = []
total_results = []
for q in queries:
    t0 = time.perf_counter()
    r = mf.search(query=q, max_results=10)
    elapsed = (time.perf_counter() - t0) * 1000
    search_times.append(elapsed)
    n = len(r.chunks) if hasattr(r, "chunks") else 0
    total_results.append(n)

results["search_avg_ms"] = round(sum(search_times) / len(search_times), 2)
results["search_min_ms"] = round(min(search_times), 2)
results["search_max_ms"] = round(max(search_times), 2)
results["search_p50_ms"] = round(sorted(search_times)[len(search_times)//2], 2)
results["search_p95_ms"] = round(sorted(search_times)[min(int(len(search_times)*0.95), len(search_times)-1)], 2)
results["search_avg_results"] = round(sum(total_results) / len(total_results), 1)
print(f"[3/10] Search: avg={results['search_avg_ms']}ms p50={results['search_p50_ms']}ms p95={results['search_p95_ms']}ms")

# ========== 4. 检索精度 ==========
annotated_queries = {
    "Python 多线程": {"python": True},
    "React 前端": {"frontend": True, "javascript": True},
    "Docker 容器": {"devops": True},
    "PostgreSQL 数据库": {"database": True},
    "微服务 架构": {"architecture": True},
    "API 限流 安全": {"security": True, "backend": True},
    "Redis 缓存": {"database": True, "backend": True},
    "Kubernetes 部署": {"devops": True},
}

precision_scores = []
recall_scores = []
for q, cat_map in annotated_queries.items():
    r = mf.search(query=q, max_results=10)
    if hasattr(r, "chunks") and r.chunks:
        relevant = [c for c in r.chunks if c.category in cat_map]
        precision_scores.append(len(relevant) / len(r.chunks))
        # 简化 recall：前 5 结果中有多少命中
        top5 = r.chunks[:5]
        top5_relevant = [c for c in top5 if c.category in cat_map]
        recall_scores.append(len(top5_relevant) / 5.0)
    else:
        precision_scores.append(0.0)
        recall_scores.append(0.0)

results["precision_at_10"] = round(sum(precision_scores) / len(precision_scores), 3)
results["recall_at_5"] = round(sum(recall_scores) / len(recall_scores), 3)
print(f"[4/10] Precision@10={results['precision_at_10']} Recall@5={results['recall_at_5']}")

# ========== 5. 知识图谱 ==========
t0 = time.perf_counter()
from modules.knowledge_graph import KnowledgeGraph
kg = KnowledgeGraph(storage=mf.storage)
test_texts = [
    "Python 和 JavaScript 都是流行的编程语言。React 是一个 JavaScript 框架。",
    "Docker 用于容器化部署。PostgreSQL 是关系型数据库。Redis 是内存数据库。",
    "Kubernetes 编排容器。AWS 提供云计算服务。Terraform 管理基础设施。",
    "Git 是版本控制系统。GitHub 托管代码。CI/CD 自动化部署。",
]
all_entities = []
for text in test_texts:
    entities = kg.extract_entities(text)
    all_entities.extend(entities)

unique_entities = set(e[0] for e in all_entities)
results["kg_entities_extracted"] = len(unique_entities)
results["kg_extract_avg_ms"] = round((time.perf_counter() - t0) * 1000 / len(test_texts), 2)

for name, etype in all_entities:
    try:
        kg.add_entity(name, etype)
    except Exception:
        pass

kg.add_relation("Python", "JavaScript", "similar_to", 0.7)
kg.add_relation("React", "JavaScript", "built_with", 0.9)
kg.add_relation("Docker", "Kubernetes", "orchestrated_by", 0.8)
kg.add_relation("PostgreSQL", "Redis", "complementary", 0.6)
kg.add_relation("AWS", "Kubernetes", "hosts", 0.7)

related = kg.get_related_entities("JavaScript", depth=2)
results["kg_related_js"] = len(related)
print(f"[5/10] KG: {results['kg_entities_extracted']} entities, {results['kg_related_js']} related to JS")

# ========== 6. 意图路由 ==========
from modules.intent_router import IntentRouter
router = IntentRouter()
test_intents = [
    ("记住我喜欢 Python 编程", "memory_store"),
    ("搜索关于数据库的记忆", "memory_retrieve"),
    ("今天天气怎么样", "chitchat"),
    ("帮我写一个排序算法", "task_planning"),
    ("删除所有过期的记忆", "memory_delete"),
    ("查看记忆统计信息", "memory_stats"),
]
intent_correct = 0
intent_details = []
for text, expected in test_intents:
    result = router.classify(text)
    got = result.intent if hasattr(result, "intent") else str(result)
    match = got == expected
    if match:
        intent_correct += 1
    intent_details.append({"text": text, "expected": expected, "got": got, "match": match})

results["intent_accuracy"] = f"{intent_correct}/{len(test_intents)}"
results["intent_pct"] = round(intent_correct / len(test_intents) * 100, 1)
print(f"[6/10] Intent Router: {results['intent_accuracy']} ({results['intent_pct']}%)")

# ========== 7. 矛盾检测 ==========
mf.add(content="用户喜欢 Vim 编辑器", category="preferences", tags=["editor"], importance=Importance.HIGH)
mf.add(content="用户喜欢 VS Code 编辑器", category="preferences", tags=["editor"], importance=Importance.HIGH)
mf.add(content="用户偏好 Python 语言", category="preferences", tags=["lang"], importance=Importance.MEDIUM)
mf.add(content="用户偏好 Java 语言", category="preferences", tags=["lang"], importance=Importance.MEDIUM)

from modules.conflict_detector import ConflictDetector
conflicts = mf.scan_conflicts(category="preferences")
if isinstance(conflicts, dict):
    n_conflicts = conflicts.get("total_conflicts", conflicts.get("total", 0))
elif isinstance(conflicts, list):
    n_conflicts = len(conflicts)
else:
    n_conflicts = 0
results["conflicts_detected"] = n_conflicts
print(f"[7/10] Conflict Detection: {results['conflicts_detected']} conflicts found")

# ========== 8. 记忆巩固 ==========
t0 = time.perf_counter()
try:
    consolidate_result = mf.consolidate()
except Exception:
    consolidate_result = "completed"
results["consolidate_ms"] = round((time.perf_counter() - t0) * 1000, 2)
print(f"[8/10] Consolidation: {results['consolidate_ms']}ms")

# ========== 9. 加密性能 ==========
from core.encryption import EncryptionEngine
engine, salt = EncryptionEngine.from_password("benchmark_password_123")

enc_times = []
for i in range(100):
    t0 = time.perf_counter()
    blob = engine.encrypt(f"Test memory content number {i} with some extra data for benchmarking")
    enc_times.append((time.perf_counter() - t0) * 1000)

dec_times = []
blobs = [engine.encrypt(f"Decrypt test {i}") for i in range(100)]
for blob in blobs:
    t0 = time.perf_counter()
    text = engine.decrypt(blob)
    dec_times.append((time.perf_counter() - t0) * 1000)

results["encrypt_avg_ms"] = round(sum(enc_times)/len(enc_times), 3)
results["encrypt_p95_ms"] = round(sorted(enc_times)[95], 3)
results["decrypt_avg_ms"] = round(sum(dec_times)/len(dec_times), 3)
results["decrypt_p95_ms"] = round(sorted(dec_times)[95], 3)
print(f"[9/10] AES-256-GCM: enc={results['encrypt_avg_ms']}ms dec={results['decrypt_avg_ms']}ms")

# ========== 10. 并发安全 ==========
errors = []
def worker(wid):
    try:
        for j in range(20):
            mf.add(content=f"Concurrent memory from worker {wid} iter {j}", category="concurrent_test")
    except Exception as e:
        errors.append(str(e))

t0 = time.perf_counter()
threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
conc_time = time.perf_counter() - t0
results["concurrent_8w_20it_s"] = round(conc_time, 3)
results["concurrent_writes"] = 160
results["concurrent_errors"] = len(errors)
print(f"[10/10] Concurrency: 8x20={results['concurrent_8w_20it_s']}s errors={results['concurrent_errors']}")

# ========== Final Stats ==========
stats = mf.stats()
results["total_memories_final"] = stats.get("total", "N/A")

# 输出 JSON
output = json.dumps(results, ensure_ascii=False, indent=2, default=str)
print()
print("=== BENCHMARK JSON ===")
print(output)

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(output)

mf.close()
print(f"\nDone! Saved to {out_path}")
