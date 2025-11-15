# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.3.0] - 2025-11-15

### Added
- Global singleton pattern for OpenStack connection (lazy-initialized)
- Global singleton pattern for flavor cache (lazy-initialized)
- `get_flavor(cloud, flavor_name)` function for flavor lookups with caching
- Comprehensive documentation of singleton pattern in CLAUDE.md

### Changed
- **BREAKING:** Migrated from OpenStack CLI to Python openstacksdk library
- Removed connection parameter from `list_vms()` function signature
- OpenStack connection now created lazily on first use, not at startup
- Flavor cache now loaded on-demand only when needed
- All global singletons moved to top of file for clarity
- Updated CLAUDE.md with global singleton pattern guidelines

### Removed
- `run_openstack_command()` function (replaced by SDK calls)
- `python-openstackclient>=5.0.0` dependency
- Unnecessary connection passing between functions

### Fixed
- Volume attachments API: corrected to use `conn.compute.volume_attachments()` instead of `conn.block_storage.volume_attachments()`

### Performance
- **3.7x faster execution** with cached VMs (0.35s vs 1.3s)
- Lazy initialization eliminates overhead when not needed
- Singleton caching prevents redundant API calls

## [2.2.0] - 2025-11-15

### Added
- VM helper methods: `get_billable_storage()` and `get_provider_flavor()`
- Common utility functions: `format_price()` and `calculate_totals()`

### Changed
- Consolidated duplicate cost calculation code across all report functions
- Centralized price formatting logic
- Moved cost calculations to VM class methods

### Removed
- Unused `server_to_cache_format()` function
- Unused `list_vms_cached()` wrapper function
- Dead code paths storing `_details` in cache

## [2.1.0] - 2025-11-15

### Changed
- Streamlined documentation structure
- Consolidated multiple documentation files into core set

### Removed
- QUICKSTART.md
- CONFIG.md
- FEATURES.md
- INDEX.md

## [2.0.0] - 2025-11-14

### Added
- Comprehensive "Recent Major Simplifications" section in CLAUDE.md
- Table-first approach documentation
- On-demand calculation principles

### Changed
- Updated architecture documentation to reflect simplified codebase
- Updated CLI examples to show multiple VM pattern support
- Updated line number references in documentation

[Unreleased]: https://github.com/ncsa/rate-calc/compare/v2.3.0...HEAD
[2.3.0]: https://github.com/ncsa/rate-calc/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/ncsa/rate-calc/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/ncsa/rate-calc/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ncsa/rate-calc/releases/tag/v2.0.0
