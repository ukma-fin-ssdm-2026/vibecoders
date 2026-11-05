# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

### Added

- REST API and web interface for organizing tabletop role-playing games, player enrollment, and room bookings.
- User registration, profile management, user administration, notifications, and room calendar endpoints.
- Characterization and regression tests for OpenAPI generation and browser-side date, slot, and retry-delay helpers.

### Changed

- Make demo database seeding idempotent and resolve the SQLite database path consistently.
- Use explicit `Number.isNaN` and `Number.parseInt` methods in shared web-client helpers.
- Improve CI dependency installation and pin the documentation deployment action to a full commit SHA.

### Fixed

- Improve screen-reader support for the API documentation and game page.
- Use the Bash conditional syntax required by the mutation-test script.
