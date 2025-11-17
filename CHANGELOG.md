# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.4.0] - 2025-11-16

### Added
- GPU reservations feature: `load_gpu_reservations()` function to load GPU reservations from gpu.csv
- OpenStack quota fetching: `get_openstack_quotas()` function to fetch resource quotas from OpenStack
- Reservation calculations: `calculate_reservation_totals()` function to calculate reserved resources and costs
- Quota caching: Store and retrieve quotas alongside VMs in cache for performance
- `gpu.csv` file with GPU reservations per cloud (A100 and V100 counts)
- Reservation display in all report formats (table, CSV, JSON, summary)
- `vms_filtered` parameter to skip reservation display when VMs are filtered
- Comprehensive GPU reservations documentation and release process in CLAUDE.md

### Changed
- Updated `format_price()` to always display prices including $0.00 (no more hyphens for zero values)
- Modified `list_vms()` to return tuple of (vms, quota) instead of just vms
- Updated `load_cache()` and `save_cache()` to handle quota data
- All report functions now accept `cloud`, `gpu_reservations`, `quota`, and `vms_filtered` parameters
- Summary report now shows Reservation and Difference columns when no provider comparison is specified
- Table, CSV, and JSON reports now include RESERVATION row with reserved resources

### Fixed
- GPU cores and memory now properly subtracted from total to avoid double-counting
- Reservation calculations handle missing clouds in gpu.csv as having 0 GPUs
- Reservation data only shown when no provider comparison is specified (avoids confusion with filtered VMs)

### Performance
- Quotas cached with same TTL as VM cache (default 24 hours)
- GPU reservations loaded once and cached in global variable

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
