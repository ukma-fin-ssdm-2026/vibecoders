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
