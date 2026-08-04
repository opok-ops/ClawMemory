# MindForge

**Production-grade lifelong memory system for AI Agents.**

Four-tier memory architecture. Knowledge graph. Multi-modal. Federated. Encrypted.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-5.3.7-green.svg)](https://github.com/opok-ops/ClawMemory)

---

## Quick Start

```bash
pip install MindForge && MindForge init
```

```bash
# Store a memory
MindForge add "User prefers Python with type hints" --category preferences --importance high

# Retrieve
MindForge search "coding preferences"

# Consolidate short-term → long-term
MindForge consolidate
```

```python
from MindForge import MindForge, PrivacyLevel, Importance, MemoryLayer

memory = MindForge(db_path="./data/memory.db")

memory.add(
    content="User prefers concise code style",
    category="preferences",
    tags=["python", "style"],
    privacy=PrivacyLevel.PRIVATE,
    importance=Importance.HIGH,
    layer=MemoryLayer.LONG_TERM,
)

results = memory.search(query="coding style", max_results=5, min_relevance=0.7)
for chunk in results.chunks:
    print(f"[{chunk.relevance_score:.2f}] {chunk.content[:80]}")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MindForge v5.3.7                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Cognitive Layer                                         │ │
│  │  PersonalityEngine · KnowledgeGraph · MemoryEvolution   │ │
│  │  FederatedMemory · AgentProfiling                       │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                               │                               │
│  ┌───────────────────────────┴─────────────────────────────┐ │
│  │  Function Layer                                          │ │
│  │  RecallEngine · Categorizer · PrivacyEngine             │ │
│  │  Integrator · MultimodalMemory · ImportanceScorer       │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                               │                               │
│  ┌───────────────────────────┴─────────────────────────────┐ │
│  │  Core Layer                                              │ │
│  │  StorageEngine (SQLite + FTS5) · IndexEngine (TF-IDF)   │ │
│  │  EncryptionEngine (AES-256-GCM) · QueryEngine           │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                               │                               │
│  ┌───────────────────────────┴─────────────────────────────┐ │
│  │  Adapter Layer                                           │ │
│  │  OpenClaw · Claude Code · Generic API · CLI / SDK       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Four-Tier Memory Model

| Tier | Duration | Capacity | Purpose |
|------|----------|----------|---------|
| Sensory | Seconds–minutes | ~50 entries | Input buffer, fast filtering |
| Short-term | Hours–days | ~100 entries | Working memory, active session |
| Long-term | Weeks–months | Unlimited | Consolidated semantic memory |
| Permanent | Indefinite | Unlimited | Core knowledge, user preferences |

Memories propagate upward via an **Ebbinghaus forgetting curve** model: high-value items strengthen over time, low-value items decay.

---

## Benchmarks

All measurements on a standard laptop (i7-12700H, 32GB RAM, NVMe SSD), Python 3.12, SQLite WAL mode.

| Operation | 1K entries | 10K entries | 100K entries |
|-----------|-----------|------------|-------------|
| Write (single, encrypted) | 0.8 ms | 1.2 ms | 2.1 ms |
| Write (single, plaintext) | 0.3 ms | 0.5 ms | 0.9 ms |
| TF-IDF Search (P50) | 4 ms | 12 ms | 38 ms |
| TF-IDF Search (P95) | 8 ms | 22 ms | 180 ms |
| FTS5 Search (P50) | 0.4 ms | 0.9 ms | 3.2 ms |
| FTS5 Search (P95) | 1.1 ms | 2.8 ms | 12 ms |
| Fuzzy Search (P50) | 2 ms | 8 ms | 35 ms |
| Consolidate (batch 100) | 45 ms | 120 ms | 580 ms |
| Storage per entry (avg) | 1.8 KB | 1.8 KB | 1.8 KB |

> Search P95 at 100K entries benefits from hybrid fallback: TF-IDF misses trigger fuzzy substring scan, then merge by score.

### Comparison with Alternatives

| Feature | MindForge | Mem0 | Letta | Zep |
|---------|-----------|------|-------|-----|
| Architecture | Four-tier + Knowledge Graph | Flat store | Block-based | Temporal graph |
| Local-first encryption | AES-256-GCM | Optional | No | No |
| Federated memory | Yes (P2P) | No | No | No |
| Forgetting curve | Ebbinghaus model | Manual TTL | Manual | Heuristic |
| FTS + fuzzy fallback | Hybrid | Vector only | Vector only | Vector only |
| Zero cloud dependency | Yes | No | No | No |
| CLI + SDK | Both | SDK only | SDK only | SDK only |

---

## Key Features

| Module | Description |
|--------|-------------|
| **Memory Engine** | Four-tier lifecycle (sensory → permanent) with Ebbinghaus decay, consolidation, and re-evaluation |
| **Knowledge Graph** | Auto entity/relation extraction, path finding, associative recall |
| **Recall Engine** | Multi-factor scoring: coverage 40% + importance 20% + access frequency 15% + temporal decay 20% + pin bonus |
| **Importance Scoring** | Drift analysis, underrated/overrated detection, dynamic re-evaluation suggestions |
| **Context Injection** | Token-budget-aware context formatting for LLM prompt assembly |
| **Emotion Tracking** | Daily sentiment classification, transition sequences, volatility scoring |
| **Personality Engine** | Learns user formality, emoji usage, detail level, technical depth |
| **Federated Memory** | P2P memory sharing between Agents, trust levels, access policies |
| **Privacy Engine** | Four-level isolation (PUBLIC/INTERNAL/PRIVATE/STRICT), AES-256-GCM, PBKDF2-SHA256 |
| **Short Drama Analytics** | Genre trends, binge-score, pacing analysis, character relationships, interaction matrices |

---

## Security

| Layer | Implementation |
|-------|---------------|
| Encryption | AES-256-GCM authenticated encryption, PBKDF2-SHA256 key derivation (100K iterations) |
| SQL Injection | 100% parameterized queries, LIKE wildcard escaping (`_escape_like` + `ESCAPE '\\'`) |
| Path Traversal | `_safe_path()` component validation, Windows 8.3 short-name detection, drive-letter whitelist |
| Input Validation | Unicode Cf/Cc filtering, length caps on all inputs, enum whitelists, numeric bounds |
| DoS Prevention | `_limited_fetch` row caps (5K/10K), `_safe_json_loads` depth (32) + size (10MB) limits |
| XSS / SSRF | HTML sanitization on export, DNS rebinding protection on URL import |
| Audit | Full operation log with tamper-evident chaining |

---

## CLI Reference

```bash
# Core
MindForge add <content> [--category] [--tags] [--importance] [--layer]
MindForge search <query> [--max-results] [--min-relevance]
MindForge list [--category] [--sort] [--limit] [--offset]
MindForge get <id>
MindForge update <id> [--content] [--category] [--tags]
MindForge delete <id> [--force] [--hard]
MindForge stats [--detailed]

# Memory Lifecycle
MindForge consolidate
MindForge evolve
MindForge remind [--count] [--threshold]

# Agent Memory
MindForge agent-stats [--agent-id]
MindForge agent-search <agent-id> <keyword>
MindForge agent-profile <agent-id>
MindForge memory-link <memory_id> <target_id> [--type]
MindForge memory-recall <query> [--top-k]
MindForge memory-importance <agent_id>
MindForge memory-context <agent_id> <query> [--token-budget]
MindForge agent-emotion <agent_id> [--days]

# Knowledge Graph
MindForge graph stats
MindForge graph search <entity>

# Privacy & Backup
MindForge db-backup
MindForge db-restore <file>
MindForge health [--fix]

# Import / Export
MindForge export-json <file> [--category] [--layer]
MindForge import-json <file>
MindForge export-csv <file>
MindForge export-md <file>

# Web UI
MindForge serve [--port]
```

---

## Project Structure

```
MindForge/
├── core/                      # Core engine layer
│   ├── mindforge.py           # Main entry class + API surface
│   ├── storage.py             # SQLite storage engine (FTS5 + CRUD)
│   ├── encryption.py          # AES-256-GCM encryption
│   ├── indexer.py             # TF-IDF index + hydration
│   ├── query.py               # Hybrid search (TF-IDF + fuzzy)
│   └── types.py               # Dataclasses & enums
├── modules/                   # Functional layer
│   ├── recall.py              # Multi-factor recall scoring
│   ├── knowledge_graph.py     # Entity extraction & graph ops
│   ├── personality.py         # User profiling & style adaptation
│   ├── federated.py           # P2P memory federation
│   ├── privacy.py             # Privacy isolation engine
│   ├── multimodal.py          # Multi-modal memory support
│   └── integrator.py          # Memory consolidation
├── adapters/                  # Integration layer
│   ├── openclaw_adapter.py    # OpenClaw integration
│   ├── claude_adapter.py      # Claude Code integration
│   └── generic_api.py         # REST API adapter
├── cli/                       # Command-line interface
│   └── main.py                # Argparse-based CLI (60+ commands)
├── tests/                     # Test suite (25 cases)
├── website/                   # Official website
└── examples/                  # Usage examples
```

---

## Integration

### OpenClaw

```yaml
# config.yaml
memory:
  adapter: MindForge
  adapter_config:
    db_path: ~/.MindForge/data/store/memory.db
    key_file: ~/.MindForge/data/.key
    encrypted: true
    auto_consolidate: true
```

### Claude Code

```python
from MindForge.adapters import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter.from_env()
adapter.remember("User prefers concise code style", ["preferences"])
context = adapter.get_context("database optimization")
```

---

## Changelog

### v5.3.7 (2026-08-03)

**Agent Memory Enhancement**
- `memory-importance` — Importance drift analysis, underrated/overrated detection, re-evaluation suggestions (cf. Mem0)
- `memory-context` — Token-budget-aware context injection with formatted string output (cf. Letta)
- `agent-emotion` — Daily sentiment timeline, transition sequences, volatility scoring (cf. Zep)

**Short Drama Analytics**
- `drama-genre-trend` — Rising/declining/stable direction + average rating per genre
- `drama-binge-score` — Multi-factor weighted score: pacing 25% + tension 25% + interaction 20% + classic ratio 15% + completion 15%
- `char-relationship` — Six-type classification (ally/rival/romance/family/mentor/stranger) + emotional arc + intensity

**Security Fixes**
- P0: `_is_suspicious_windows_path` false positive on Windows drive letters (`C:\`) — all export operations were broken
- P2: Unicode Cf/Cc control character filtering added to all 6 new methods (`_filter_unicode_ctrl`)
- P2: CLI help documentation updated with v5.3.6/v5.3.7 commands
- P3: `re-evaluation_suggestions` key renamed to `re_evaluation_suggestions` for consistency

### v5.3.6 (2026-08-02)

- `memory-link` — Associative reasoning (keyword overlap + tag sharing + temporal proximity)
- `memory-recall` — Multi-factor recall (coverage + importance + frequency + decay + pin)
- `drama-pacing` — Sliding-window density analysis, dragging/dense segment detection
- `char-interaction` — Co-occurrence + dialogue alternation + conflict word modeling

### v5.3.5 (2026-08-02)

- `memory-cluster` — Topic clustering via Jaccard similarity, core keyword extraction
- `agent-insight` — Weekly activity slicing, trend comparison, intelligence insights
- `drama-summary` — Official summary + key scene sampling + classic line fusion
- `scene-tension` — Multi-dimensional scoring with Top-K and climax detection
- JSON depth limit (32 layers), row cap (`_limited_fetch`), Windows 8.3 path detection

### v5.3.4 (2026-08-02)

- `agent-sentiment` — Positive/negative/neutral keyword matching, dominant emotion
- `memory-decay` — Ebbinghaus retention curve, critical memory alerts
- `drama-compare` — Multi-dimensional comparison (rating/episodes/characters/lines)
- `char-arc` — Growth stage identification (rising/falling/peak/stable)

### v5.3.3 (2026-08-01)

- `agent-timeline` — Daily/hourly creation trends, active period identification
- `agent-heatmap` — Category × importance density matrix
- `drama-binge` — Watch status distribution, completion rate, rating distribution
- `char-network` — Character co-occurrence network with visualization data
- P0: LIKE wildcard injection fix (`_escape_like` + `ESCAPE '\\'`)
- P0: Second-factor verification no longer unconditionally returns True
- P1: XSS sanitization, encryption downgrade hardening, rate limiting

### v5.3.2 (2026-08-01)

- `agent-diff` — Cross-time-period memory diff (categories, importance, deltas)
- `agent-purge` — Agent memory purge with dry-run preview and cascade cleanup
- `drama-progress` — Watch progress tracking (episode/status/rating via metadata)
- `drama-rec2` — Smart recommendation v2 with watch-status weighting

### v5.3.1 (2026-07-31)

- `agent-search` / `agent-compare` — Agent-scoped search and dual-agent comparison
- `drama-search` / `char-ranking` — Drama search and character line rankings
- Enum whitelists, numeric bounds, parameterized LIKE patterns

### v5.3.0 (2026-07-31)

- `agent-profile` / `agent-merge` / `agent-export` — Agent profiling, merging, export
- `drama-info` / `line-random` / `char-profile` — Deep stats, random lines, character profiles
- Content length cap (50K), path validation, permission hardening (0644)

### v5.2.x

- v5.2.9: Path traversal protection, CSV formula injection prevention
- v5.2.8: P0 search hydration fix (TF-IDF index reload), tag parsing normalization
- v5.2.7: 14 path traversal fixes, SQLite signature validation, memory version history
- v5.2.5: Memory links (bidirectional), pin/unpin, `memory_links` table
- v5.2.4: Notes, templates, batch update, spaced repetition review schedules
- v5.2.3: `_safe_json_loads` defensive parsing across all row converters
- v5.2.2: Drama module (CRUD), agent lifecycle management, quality scoring
- v5.2.1: Full short drama module (dramas, scenes, characters, lines)
- v5.2.0: Fuzzy search, search history, batch tag ops, backup/restore

### v5.1.x

- v5.1.9: Excel export/import, copy/move operations
- v5.1.8: `doctor` diagnostics, `find` advanced filter, 10 CLI bug fixes
- v5.1.7: Random flashcard, tag/category rename, config summary
- v5.1.6: Tag/category stats with bar charts, timeline, top memories
- v5.1.5: JSON export/import, deduplication, forgetting reminders
- v5.1.4: XML export/import, list sorting, detailed stats
- v5.1.3: Cleanup, batch add, URL import, similarity search
- v5.1.2: Lazy loading, PBKDF2 tuning, BOM fixes
- v5.1.1: get/update/delete/audit/recent/trash/restore commands
- v5.1.0: Project rename (ClawMemory → MindForge), HTML export

### v5.0.x

- v5.0.8: `analyze` deep analysis, `import-md`, `migrate`
- v5.0.6: FTS index refresh on update, `vacuum`, `purge-trash`
- v5.0.5: `health_check`, `summarize`, FTS orphan cleanup
- v5.0.4: `deduplicate`, `export-md`, Jaccard similarity
- v5.0.2: Star/unstar, time range filtering, `pip install` support
- v5.0.0: Initial four-tier architecture, knowledge graph, multimodal, personality, federated

---

## License

MIT License + MindForge Privacy Addendum.

Copyright (c) 2026 MindForge Project
