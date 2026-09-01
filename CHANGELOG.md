# Changelog

All notable changes to MindForge will be documented in this file.

## [5.5.8] - 2026-09-01

### Added
- **Memory Version Diff (记忆版本差异对比)**: `memory_diff(version_a, version_b)` — compare two historical versions of a memory, returning structured diff for content (unified diff), category, tags (added/removed), and importance changes
  - API: `mf.memory_diff(version_id_a, version_id_b)`
  - CLI: `MindForge memory-diff <version_a> <version_b> [--json]`
  - MCP: `memory_diff` tool with `version_a` / `version_b` parameters
- **MCP Parameter Validation**: All 32 MCP tool handlers now validate required parameters before execution, returning clear `{"ok": false, "error": "Missing required parameter(s): ..."}` instead of crashing with `KeyError`

### Fixed
- **P0: storage.py `__version__` NameError**: `export_agent_memories()` referenced undefined `__version__` variable, causing crash when exporting agent memories. Added `__version__` import with fallback.
- **P1: Falsy enum values silently overridden in `add()`**: `privacy or default` pattern caused valid falsy values like `PrivacyLevel.NONE` to be replaced by config defaults. Changed to explicit `is not None` checks for `privacy`, `importance`, `layer`, and `memory_type` parameters.
- **P1: CLI error message string concatenation**: Multi-line password error message was concatenated without spaces, producing mangled output. Fixed with proper string formatting.
- **P1: `cmd_list` showed global total instead of filtered count**: When using category/layer/starred/date filters, the displayed total was always the global database count instead of the filtered result count.
- **P2: REST API JSON body type validation**: `POST /api/memories`, `POST /api/import`, and `PUT /api/memories/{id}` now validate that the request body is a JSON object (dict), returning 400 error for arrays/strings/numbers instead of crashing with `AttributeError`.
- **P2: Encryption engine input validation**: `encrypt()`, `decrypt()`, and `hash()` now validate input types, raising `SecurityError` for non-string / non-EncryptedBlob inputs instead of bare `AttributeError`.
- **P2: MCP `_handle_tools_call` params type validation**: JSON-RPC `params` and `arguments` fields are now validated as dicts before accessing nested keys, preventing `AttributeError` on malformed requests.
- **P2: Stale docstrings**: Updated version strings in `core/storage.py`, `core/mindforge.py`, `core/encryption.py`, `cli/main.py`, `api/server.py` docstrings from stale versions to v5.5.8.

### Tests
- Added `tests/test_v558_features.py` with test cases covering:
  - `memory_diff` basic diff, identical versions, nonexistent version, content/category/tags/importance changes
  - MCP parameter validation: missing required params for memory_add, memory_search, memory_context
  - Falsy enum fix: `PrivacyLevel.NONE` preserved through `add()`
  - CLI `cmd_list` filtered total count
  - Version verification: `__version__` and `pyproject.toml` consistency

## [5.5.6] - 2026-08-26

### Added
- **Memory Pinning (置顶)**: Full pin/unpin lifecycle with priority sorting
  - `add(..., pinned=True)` — create memory already pinned
  - `pin(memory_id)` / `unpin(memory_id)` — toggle pin status with audit logging
  - `list(pinned=True/False)` — filter by pin status
  - `list_pinned(limit)` — list all pinned memories
  - Pinned memories always appear first in `list()` results (`ORDER BY pinned DESC`)
  - `update(memory_id, pinned=True/False)` — update pin status
- **Batch Get Memories**: `batch_get(memory_ids)` — fetch multiple memories in a single SQL query, preserving input order, with automatic dedup and expired-memory filtering
- **Memory Timeline View**: `timeline(category, layer, limit)` — group memories by time period (today / yesterday / this_week / this_month / earlier)
- **Search Suggestions**: `search_suggestions(prefix, limit, category)` — autocomplete suggestions based on existing tags and categories (case-insensitive prefix matching)
- **Duplicate Detection on Add**: `check_duplicates(content, threshold, category, limit)` — detect near-duplicate memories before adding, using Jaccard + SequenceMatcher hybrid similarity
- **Batch Tag Operations by ID**: `add_tags_to_memories(ids, tags)` and `remove_tags_from_memories(ids, tags)` — bulk add/remove tags for specific memory IDs
- **Stats Enhancement**: `stats()` now includes `pinned_count`

### Fixed
- **fuzzy_search crash on None/empty query**: Added defensive checks for `None`, non-string, and whitespace-only queries; returns `[]` instead of raising `AttributeError`
- **rename_tag case-insensitive matching**: Tags now match case-insensitively (`"MyTag"` renamed via `"mytag"` works); post-rename deduplication prevents duplicate tags
- **rename_tag empty/None input**: Returns `0` instead of crashing on empty or `None` tag names
- **batch_add missing fields**: Now supports `pinned`, `expires_at`, and `metadata` fields (previously silently ignored)
- **Facade `list()` missing `pinned` filter**: Now passes `pinned` parameter through to storage layer
- **Facade `update()` missing `pinned` parameter**: Now supports updating pin status via `update()`
- **P1: Conflict decay methods missing**: Added `adjust_importance()` and `append_tags()` to `StorageEngine`, which were called by the conflict resolution module but never implemented, causing silent failures in conflict decay functionality.
- **P1: Package naming conflict in pytest**: Removed root-level `__init__.py` that caused pytest to load the `MindForge` package from two different paths, resulting in enum classes with different identities and `isinstance()` returning `False`. Updated `setup.py` to read version from `MindForge.py` instead.
- **P2: Version hardcoded test failure**: Changed `test_version_is_555` in v5.5.5 tests to `test_version_at_least_555` to avoid breaking on minor version bumps.

### Performance
- `batch_get()` reduces N+1 query pattern to a single `IN` query for bulk memory retrieval
- Timeline view uses single sorted query instead of multiple date-range queries
- Search suggestions use in-memory set aggregation after one DB scan

### Tests
- Added `tests/test_v556_features.py` with 60+ test cases covering:
  - Pinning (10 tests): basic pin/unpin, add-with-pin, list filter, priority sorting, delete/restore persistence, update pin
  - Batch get (5 tests): basic, empty, nonexistent, order preservation, dedup
  - Timeline (4 tests): basic, empty, category filter, total count
  - Search suggestions (6 tests): tags, categories, empty/None prefix, no match, limit
  - Duplicate detection (6 tests): exact, high similarity, no match, empty, category filter, threshold
  - Batch tag ops (6 tests): add, no-duplicate, empty, nonexistent, remove, case-insensitive remove
  - adjust_importance (5 tests): lower, raise, zero delta, nonexistent, range clamping
  - append_tags (4 tests): basic, duplicate no-change, empty list, nonexistent
  - Package naming fix (3 tests): no root __init__.py, import consistency, isinstance cross-import
  - Bug fixes (12 tests): fuzzy_search None/empty/whitespace, rename_tag case/empty/dedup, batch_add pinned/expires/metadata, stats pinned_count
  - Version verification (3 tests): semver format, exact 5.5.6 match, pyproject.toml consistency
- Full suite: **260+ passed**

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
