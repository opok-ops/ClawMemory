# Changelog

All notable changes to MindForge will be documented in this file.

## [5.5.2] - 2026-08-23

### Added
- **Memory TTL/Expiration System**: New `expires_at` field on memories with full lifecycle management
  - `add(..., expires_at=timestamp)` — create memory with expiration
  - `set_ttl(memory_id, ttl_seconds)` — set or cancel TTL on existing memory
  - `list_expired()` — list all expired memories pending cleanup
  - `purge_expired()` — batch-move expired memories to trash
  - Auto-expiry: `get()` automatically moves expired memories to trash and returns None
  - Database migration: `ALTER TABLE memories ADD COLUMN expires_at REAL DEFAULT 0` with index
- **Multi-keyword Search Highlighting**: Enhanced `highlight()` method
  - Space-separated multi-keyword support (e.g., "hello world" highlights both)
  - Chinese keyword support
  - Case-insensitive matching with original case preservation in output
  - Custom highlight tags (before_tag / after_tag)
  - Nested-replacement safe: long keywords processed first, placeholder-based replacement
- **Batch Delete by Category/Tag**: New bulk operations
  - `batch_delete_by_category(category, permanent=False)` — soft or permanent delete by category
  - `batch_delete_by_tag(tag, permanent=False)` — soft or permanent delete by tag (exact tag match, no false positives)
  - Full audit logging for all batch operations
  - Cascade deletion for permanent mode (versions, links, notes, embeddings, FTS index)

### Fixed
- **Critical: UTF-8 BOM in pyproject.toml**: Removed BOM from `pyproject.toml` that caused `tomllib.TOMLDecodeError: Invalid statement`, breaking `pytest` collection and `pip install`. Also removed BOM from 7 other source files (`api/server.py`, `cli/main.py`, `core/mindforge.py`, `core/storage.py`, `MindForge.py`, `__init__.py`).
- **FTS5 bm25 score overflow**: Added clamping (`max(-50, min(50, score))`) before `math.exp()` in `fts_search()` to prevent `OverflowError` on anomalous large positive bm25 scores. Also added `None` score handling.
- **Query engine double-fetch**: Added entry cache in `QueryEngine.search()` to avoid redundant `get_memory()` calls between the pre-filter phase and result-building phase, reducing DB queries by up to 2x for filtered searches.
- **Version consistency**: Updated README version badge from stale 5.5.0 to 5.5.2; updated version test to match current release.

### Performance
- Query engine filtered searches now use a single fetch per memory entry instead of two
- FTS5 search no longer risks exception on edge-case scores

### Tests
- Added `tests/test_v552_features.py` with 33 test cases covering:
  - TTL expiration (12 tests): add with expires_at, set_ttl, cancel TTL, auto-expire on get, list_expired, purge_expired, expired exclusion from search
  - Multi-keyword highlight (10 tests): single/multi keyword, Chinese, case-insensitive, empty inputs, custom tags, no nested replacement
  - Batch delete (7 tests): by category soft/permanent/empty, by tag soft/permanent/no-match/partial-match-no-false-positive
  - FTS5 score fix (2 tests)
  - Query engine cache (2 tests): category filter, layer filter
  - Version verification (2 tests): __version__ and pyproject.toml consistency
- Full suite: **189 passed** (155 existing + 33 new + 1 updated)

### Migration
- Existing databases are automatically migrated on first connection: `expires_at` column added with `DEFAULT 0` (never expires), with an index for efficient expired-item queries. No data loss.
