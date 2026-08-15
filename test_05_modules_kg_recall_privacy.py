"""
Test 5: Modules - KnowledgeGraph, RecallEngine, PrivacyEngine
"""
import sys
import os
import tempfile
import shutil
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.types import MemoryConfig, PrivacyLevel
RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_knowledge_graph_entity_extraction():
    """KnowledgeGraph: entity extraction quality"""
    try:
        from modules.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()

        text = "Python uses Django framework. React is a JavaScript library. Docker and Kubernetes are container tools."
        entities = kg.extract_entities(text)
        log("kg_extract_not_empty", len(entities) > 0, f"extracted={len(entities)}")

        # Check specific entities found
        entity_names = [e[0] for e in entities]
        found_python = "python" in entity_names
        found_docker = "docker" in entity_names
        log("kg_extract_python", found_python, f"entities={entity_names[:10]}")
        log("kg_extract_docker", found_docker, f"entities={entity_names[:10]}")

    except Exception as e:
        log("kg_entity_extraction", False, f"{e}\n{traceback.format_exc()}")


def test_knowledge_graph_relation_management():
    """KnowledgeGraph: add/get entities and relations"""
    try:
        from modules.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()

        # Add entities
        e1 = kg.add_entity("Python", "technology", "Programming language")
        e2 = kg.add_entity("Django", "technology", "Web framework")
        log("kg_add_entity", e1 is not None and e2 is not None, "entities added")

        # Add relation
        r = kg.add_relation("Python", "Django", "powers", weight=0.9)
        log("kg_add_relation", r is not None, "relation added")

        # Get related entities
        related = kg.get_related_entities("Python", depth=1, max_results=10)
        found_django = any("django" in str(rel).lower() for rel in related)
        log("kg_get_related", found_django, f"related={related}")

    except Exception as e:
        log("kg_relation_management", False, f"{e}\n{traceback.format_exc()}")


def test_recall_engine_scoring():
    """RecallEngine: scoring with various factor combinations"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from core.storage import StorageEngine
        from core.indexer import IndexEngine
        from modules.recall import RecallEngine, RecallConfig

        mf = MindForge(config=config)
        mf.add("Python programming tutorial", category="tech",
               importance=__import__('core.types', fromlist=['Importance']).Importance.HIGH)
        mf.add("Cooking recipe for pasta", category="food")
        mf.add("Python data science with pandas", category="tech",
               importance=__import__('core.types', fromlist=['Importance']).Importance.CRITICAL)

        re = RecallEngine(mf._storage, mf._index)
        rc = RecallConfig(max_results=5, min_relevance=0.1, use_knowledge_graph=False)
        result = re.recall("Python programming", config=rc)

        log("recall_returns_results", result.total_found > 0,
            f"found={result.total_found}")
        log("recall_has_strategy", result.strategy_used != "",
            f"strategy={result.strategy_used}")

    except Exception as e:
        log("recall_engine_scoring", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_privacy_engine_level_enforcement():
    """PrivacyEngine: level enforcement and sensitive detection"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from core.storage import StorageEngine
        from modules.privacy import PrivacyEngine

        mf = MindForge(config=config)
        pe = PrivacyEngine(mf._storage)

        # Scan sensitive content
        sensitive_text = "My phone number is 13812345678 and email is test@example.com"
        scan_result = pe.scan(sensitive_text)
        log("privacy_detect_sensitive", scan_result.is_sensitive,
            f"is_sensitive={scan_result.is_sensitive}, types={scan_result.detected_types}")

        # Scan non-sensitive content
        normal_text = "The weather is nice today"
        scan_result2 = pe.scan(normal_text)
        log("privacy_normal_content", not scan_result2.is_sensitive,
            f"is_sensitive={scan_result2.is_sensitive}")

    except Exception as e:
        log("privacy_engine", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 5: Modules - KnowledgeGraph, Recall, Privacy")
    print("=" * 60)

    test_knowledge_graph_entity_extraction()
    test_knowledge_graph_relation_management()
    test_recall_engine_scoring()
    test_privacy_engine_level_enforcement()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
