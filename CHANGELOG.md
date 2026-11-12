# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Bounded retries with exponential backoff and full jitter for idempotent credentials lookup in `resilience.py` and `store.py`.
- Reliability test suite covering backoff, full jitter bounds, and fast fail HTTP 503 response (`test_reliability_retry.py`).

### Fixed

- Remove duplicate definitions and redundant initial engine in `db.py` (R-05).
- Run route handlers in the thread pool instead of the event loop: `async def` without `await` replaced with `def` (R-08).
- Store failed-login counters in the database (`login_failures` table) and record them atomically under `db_lock`, so the lockout survives restarts and parallel attempts (R-09).
- Add a 15 s request timeout (`AbortController`) to `App.api` in the web client; the error code is `TIMEOUT` (R-12).
- `App.getMe` returns `null` only without a session or on 401; server and network failures are logged and rethrown (R-13).
- Filter, order and paginate games in SQL (`store.query_games`, `find_busy_game`, `room_has_games`) instead of scanning all games in Python (R-14).
- Bound the proxy cache (LRU, 1024 entries) and rebuild cached values from the database row, which removes manual invalidation and stale reads (R-15).

### Tests

- Reliability tests for R-08, R-09, R-12, R-13, R-14 and R-15: `test_reliability_sync_handlers.py`, `test_reliability_login_lockout.py`, `test_reliability_frontend.py`, `test_reliability_game_queries.py`, `test_reliability_cache.py`.

## [0.1.1] - 2026-11-05

### Added

- Add a characterization test for the OpenAPI generator CLI entry point.

### Refactoring

- Replace global `isNaN` and `parseInt` with `Number.isNaN` and `Number.parseInt` in shared web-client helpers (Substitute Algorithm).
- Pin the GitHub Pages action to a full commit SHA and install CI dependencies from wheels only (CI supply-chain hardening, not a Fowler refactoring).
- Replace `[` with `[[` in the mutation-test script (Bash correctness fix, not a Fowler refactoring).
- Add a language attribute to the API documentation page and fallback text to the game-page title (accessibility/usability improvement, not a Fowler refactoring).

## [0.1.0] - 2026-11-04

### Baseline

- Mark the project state before the Lab 8 refactoring.

[0.1.1]: https://github.com/ukma-fin-ssdm-2026/vibecoders/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ukma-fin-ssdm-2026/vibecoders/tree/v0.1.0
