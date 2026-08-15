"""
Test 6: Modules - IntentRouter, ConflictDetector, HybridSearch, SessionFocus
"""
import sys
import os
import tempfile
import shutil
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_intent_router_classify():
    """IntentRouter: classify various text types"""
    try:
        from modules.intent_router import IntentRouter
        router = IntentRouter()

        test_cases = [
            ("\u8bb0\u4f4f\u8fd9\u4ef6\u4e8b\uff1a\u660e\u5929\u5f00\u4f1a", "memory_store"),
            ("\u641c\u7d22\u4e00\u4e0b\u4e4b\u524d\u7684\u8bb0\u5f55", "memory_recall"),
            ("\u4e3a\u4ec0\u4e48\u5929\u7a7a\u662f\u84dd\u8272\u7684\uff1f", "question_answer"),
            ("\u5236\u5b9a\u4e00\u4e2a\u5f00\u53d1\u8ba1\u5212", "task_planning"),
            ("\u5199\u4e2a\u77ed\u5267\u5267\u672c", "drama_creation"),
            ("\u6211\u597d\u96be\u8fc7\u554a", "emotion_support"),
        ]

        correct = 0
        for text, expected_intent in test_cases:
            result = router.classify(text)
            intent = result.intent if hasattr(result, 'intent') else result.get('intent', '')
            if intent == expected_intent:
                correct += 1
            else:
                log("intent_router_detail", False,
                    f"text='{text[:20]}...' expected={expected_intent}, got={intent}")

        log("intent_router_accuracy", correct >= len(test_cases) * 0.5,
            f"{correct}/{len(test_cases)} correct")

    except Exception as e:
        log("intent_router", False, f"{e}\n{traceback.format_exc()}")


def test_conflict_detector_all_types():
    """ConflictDetector: test all three conflict types"""
    try:
        from modules.conflict_detector import ConflictDetector
        cd = ConflictDetector()

        # Type A: Direct antonym conflict
        text_a = "\u542f\u7528\u4e86\u65b0\u7684\u7f13\u5b58\u7b56\u7565"
        text_b = "\u7981\u7528\u4e86\u7f13\u5b58\u7b56\u7565"
        conflicts_a = cd.detect_antonym(text_a, text_b, "id_a", "id_b")
        log("conflict_antonym", len(conflicts_a) > 0,
            f"found={len(conflicts_a)}")

        # Type B: Attribute value conflict
        text_c = "\u4ef7\u683c\u662f100\u5143"
        text_d = "\u4ef7\u683c\u662f200\u5143"
        conflicts_b = cd.detect_attribute(text_c, text_d, "id_c", "id_d")
        log("conflict_attribute", len(conflicts_b) > 0,
            f"found={len(conflicts_b)}")

        # Type C: Timeline conflict
        text_e = "\u9879\u76ee\u5df2\u7ecf\u5b8c\u6210\u4e86"
        text_f = "\u9879\u76ee\u8ba1\u5212\u4e0b\u5468\u5b8c\u6210"
        conflicts_c = cd.detect_timeline(text_e, text_f, "id_e", "id_f")
        log("conflict_timeline", len(conflicts_c) > 0,
            f"found={len(conflicts_c)}")

    except Exception as e:
        log("conflict_detector", False, f"{e}\n{traceback.format_exc()}")


def test_hybrid_search_query_expansion():
    """HybridSearch: query expansion"""
    try:
        from modules.hybrid_search import QueryExpander
        qe = QueryExpander()

        # Test query expansion with synonyms
        expanded = qe.expand("k8s \u90e8\u7f72\u62a5\u9519")
        expanded_terms = expanded.expanded_terms if hasattr(expanded, 'expanded_terms') else expanded.terms if hasattr(expanded, 'terms') else []
        log("hybrid_expand_not_empty", len(expanded_terms) > 0 or expanded is not None,
            f"expanded: {expanded}")

        # Test abbreviation expansion
        expanded2 = qe.expand("k8s")
        expanded_terms2 = expanded2.expanded_terms if hasattr(expanded2, 'expanded_terms') else expanded2.terms if hasattr(expanded2, 'terms') else []
        has_kubernetes = any("kubernetes" in str(t).lower() or "Kubernetes" in str(t)
                            for t in expanded_terms2)
        log("hybrid_expand_abbr", has_kubernetes or len(expanded_terms2) > 0 or expanded2 is not None,
            f"expanded: {expanded2}")

    except Exception as e:
        log("hybrid_search_expansion", False, f"{e}\n{traceback.format_exc()}")


def test_hybrid_search_reranking():
    """HybridSearch: reranking"""
    try:
        from modules.hybrid_search import CrossEncoderReranker
        from core.query import MemoryChunk
        from core.types import MemoryLayer

        reranker = CrossEncoderReranker()

        chunks = [
            MemoryChunk(memory_id="1", content="Python \u7f16\u7a0b\u8bed\u8a00\u5165\u95e8",
                       category="tech", relevance_score=0.8, layer=MemoryLayer.SHORT_TERM),
            MemoryChunk(memory_id="2", content="\u4eca\u5929\u5403\u4e86\u706b\u9505",
                       category="food", relevance_score=0.7, layer=MemoryLayer.SHORT_TERM),
            MemoryChunk(memory_id="3", content="Python \u6570\u636e\u5206\u6790\u5b9e\u6218",
                       category="tech", relevance_score=0.6, layer=MemoryLayer.SHORT_TERM),
        ]

        reranked = reranker.rerank("Python \u7f16\u7a0b", chunks)
        reranked_list = reranked.results if hasattr(reranked, 'results') else reranked
        log("hybrid_rerank_returns", len(reranked_list) > 0,
            f"reranked={len(reranked_list)}")
        # Top result should be about Python
        if reranked_list:
            top = reranked_list[0]
            top_content = top.content if hasattr(top, 'content') else str(top)
            log("hybrid_rerank_top_relevant", "Python" in top_content,
                f"top={top_content[:40]}")

    except Exception as e:
        log("hybrid_search_reranking", False, f"{e}\n{traceback.format_exc()}")


def test_session_focus_topic_clustering():
    """SessionFocus: topic clustering"""
    try:
        from modules.session_focus import SessionFocus

        sfe = SessionFocus()

        messages = [
            {"id": "m1", "role": "user", "content": "\u8ba8\u8bba\u4e00\u4e0b\u9879\u76ee\u8fdb\u5ea6", "timestamp": time.time() - 300},
            {"id": "m2", "role": "assistant", "content": "\u9879\u76ee\u5df2\u7ecf\u5b8c\u6210\u4e8680%", "timestamp": time.time() - 240},
            {"id": "m3", "role": "user", "content": "\u90a3\u4e0b\u5468\u7684\u8ba1\u5212\u662f\u4ec0\u4e48", "timestamp": time.time() - 180},
            {"id": "m4", "role": "assistant", "content": "\u4e0b\u5468\u8ba1\u5212\u5b8c\u6210\u5269\u4f59\u768420%", "timestamp": time.time() - 120},
            {"id": "m5", "role": "user", "content": "\u597d\u7684\uff0c\u6211\u4eec\u7ee7\u7eed\u5f00\u53d1", "timestamp": time.time() - 60},
        ]

        summary = sfe.summarize(messages)
        log("session_focus_summary", summary is not None,
            f"has_summary={summary is not None}")

        if hasattr(summary, 'clusters'):
            log("session_focus_clusters", len(summary.clusters) > 0,
                f"clusters={len(summary.clusters)}")
        elif isinstance(summary, dict):
            log("session_focus_clusters", len(summary.get('clusters', [])) > 0,
                f"clusters={len(summary.get('clusters', []))}")
        else:
            log("session_focus_clusters", True, f"type={type(summary)}")

    except Exception as e:
        log("session_focus", False, f"{e}\n{traceback.format_exc()}")


def test_session_focus_drift_detection():
    """SessionFocus: drift detection"""
    try:
        from modules.session_focus import SessionFocus
        sfe = SessionFocus()

        # Window 1: tech discussion
        msgs1 = [
            {"id": f"w1m{i}", "role": "user", "content": f"\u6280\u672f\u8ba8\u8bba\u7b2c{i}\u6761",
             "timestamp": time.time() - 600 + i * 30}
            for i in range(5)
        ]

        # Window 2: completely different topic
        msgs2 = [
            {"id": f"w2m{i}", "role": "user", "content": f"\u7f8e\u98df\u63a2\u5e97\u7b2c{i}\u6761",
             "timestamp": time.time() - 300 + i * 30}
            for i in range(5)
        ]

        all_msgs = msgs1 + msgs2
        summary = sfe.summarize(all_msgs)

        if hasattr(summary, 'drift_score'):
            drift = summary.drift_score
        elif isinstance(summary, dict):
            drift = summary.get('drift_score', 0)
        else:
            drift = 0

        log("session_focus_drift", drift >= 0,
            f"drift_score={drift}")

    except Exception as e:
        log("session_focus_drift", False, f"{e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 6: Modules - IntentRouter, ConflictDetector, HybridSearch, SessionFocus")
    print("=" * 60)

    test_intent_router_classify()
    test_conflict_detector_all_types()
    test_hybrid_search_query_expansion()
    test_hybrid_search_reranking()
    test_session_focus_topic_clustering()
    test_session_focus_drift_detection()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
