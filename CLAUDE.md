# CLAUDE.md - AI Assistant Guide

This document provides comprehensive guidance for AI assistants (like Claude) working with the Radiant Price / OpenStack Analyzer codebase.

## Project Overview

**Radiant Price** (also known as OpenStack Analyzer) is a cloud cost comparison tool that:
- Analyzes OpenStack environments to inventory virtual machines and their resources
- Compares OpenStack costs against major cloud providers (AWS, GCP, Azure, Linode, etc.)
- Generates detailed cost reports in multiple formats (table, CSV, JSON)
- Helps organizations understand their cloud spending and potential migration costs

**Primary Use Cases:**
- Budget planning and cost tracking
- Cloud migration analysis (OpenStack ↔ Public Cloud)
- Resource optimization and rightsizing
- Multi-cloud cost comparisons

## Repository Structure

```
radiant-price/
├── estimate.py              # Main analysis tool (~1350 lines)
├── update.py                # Pricing updater for cloud providers (207 lines)
├── pricing.csv              # Central pricing database for all providers
├── requirements.txt         # Python dependencies
├── README.md                # User guide with quick start and examples
├── CLAUDE.md                # Comprehensive developer/AI guide (this file)
├── CONTRIBUTING.md          # Guide for adding new cloud providers
└── providers/               # Cloud provider pricing modules
    ├── __init__.py
    ├── matcher.py          # Flavor matching logic
    ├── aws.py              # AWS pricing fetcher
    ├── azure.py            # Azure pricing fetcher
    ├── gcp.py              # GCP pricing fetcher
    ├── linode.py           # Linode pricing fetcher
    ├── hetzner.py          # Hetzner pricing fetcher
    ├── vultr.py            # Vultr pricing fetcher
    └── digitalocean.py     # DigitalOcean pricing fetcher
```

## Core Architecture

### Data Flow

```
User Command
    ↓
estimate.py (CLI)
    ↓
1. Load pricing.csv → Single unified PROVIDER_PRICING dict
2. Query OpenStack CLI → List VMs with resources
3. Determine comparison provider → "cheapest" finds lowest cost (excl. OpenStack)
4. Calculate costs on-demand → vm.get_cost(provider)
5. Generate report → Table/CSV/JSON format
```

### Key Components

#### 1. estimate.py (Main Analysis Tool)

**Core Functions:**
- `load_all_pricing_data()` - Loads pricing.csv into single unified dict
- `list_vms(cloud, vm_filter)` - Queries OpenStack for VMs matching patterns
- `detect_gpu(vm_name)` - Detects GPU type/count from VM naming
- `find_cheapest_provider(vms, all_provider_pricing)` - Finds lowest-cost provider (excludes OpenStack)
- `generate_table_report()` / `generate_csv_report()` / `generate_json_report()` - Output formatting (calculate costs on-demand)

**CLI Arguments:**
```bash
python3 estimate.py [vm_patterns...] --cloud CLOUD --format FORMAT --output FILE --comparison PROVIDER
```

**Examples:**
```bash
# Single VM pattern (regex)
python3 estimate.py "cookiemonster" --comparison cheapest

# Multiple VM patterns (matches ANY pattern)
python3 estimate.py "cookie.*" "soma.*" --comparison aws

# All VMs
python3 estimate.py --comparison cheapest
```

**Important Data Structures:**
```python
@dataclass
class VM:
    name: str
    flavor: str              # OpenStack flavor name
    status: str
    cores: int
    ram_mb: int
    boot_storage_gb: int
    additional_storage_gb: int
    gpu_type: Optional[str]  # e.g., "A100", "V100"
    gpu_count: int

    def get_billable_storage(self, provider: str) -> int:
        """Calculate billable storage (GB) for a provider."""
    
    def get_provider_flavor(self, provider: str) -> Optional[str]:
        """Get the provider's instance flavor name for this VM."""

    def get_cost(self, provider: str) -> Optional[float]:
        """Calculate monthly cost for this VM on given provider.
        Includes base compute price + additional storage costs."""
```

**Global Pricing Structure:**
```python
# Loaded at startup from pricing.csv
PROVIDER_PRICING = {
    "openstack": {
        "gp.medium": {"flavor": "gp.medium", "cores": 2, "memory_gb": 8, ...}
    },
    "aws": {
        "gp.medium": {"flavor": "t3a.large", "cores": 2, "memory_gb": 8, ...}
    },
    ...
}
```

#### 2. update.py (Pricing Updater)

**Purpose:** Fetches latest pricing from cloud provider APIs and updates pricing.csv

**Usage:**
```bash
python3 update.py aws              # Update AWS pricing
python3 update.py aws --dry-run    # Preview changes
python3 update.py all              # Update all providers
```

**Architecture:**
- Calls provider-specific fetchers (providers/*.py)
- Matches provider instances to OpenStack flavors using matcher.py
- Updates pricing.csv with new prices and instance types

#### 3. pricing.csv (Central Pricing Database)

**Schema:**
```csv
Cloud,Flavor,Matched_OpenStack_Flavor,Cores,Memory_GB,Boot_Storage_GB,GPU,Compute_Price_Per_Month,Storage_Price_Per_GB_Per_Month,Description,Notes
```

**Structure:**
- **OpenStack rows:** Define OpenStack flavors (Cloud="openstack")
  - Special flavors: "flash" (storage pricing), "floating_ip" (IP pricing)
- **Provider rows:** Define provider instances matched to OpenStack flavors
  - `Matched_OpenStack_Flavor` links provider instance to OpenStack flavor

**Example Rows:**
```csv
openstack,gp.medium,,2,8,0,none,10.06,0.14,gp.medium OpenStack flavor,Boot from disk
aws,t3a.large,gp.medium,2,8.0,,none,54.90,0.10,AWS t3a.large (matched to gp.medium),General purpose
```

#### 4. providers/ (Cloud Provider Modules)

Each provider module implements:
```python
def fetch_<provider>_pricing() -> Dict[str, Dict]:
    """
    Fetch pricing from provider API.

    Returns:
        Dict mapping instance type to {
            'cores': int,
            'memory_gb': float,
            'gpu': str or None,
            'price': float  # monthly cost
        }
    """
```

**matcher.py** implements:
- `load_openstack_flavors(csv_file)` - Parse OpenStack flavors from CSV
- `find_matches(flavors, provider_pricing)` - Match flavors to provider instances
- `update_csv_with_matches()` - Update CSV with new matches

## Development Workflows

### Adding a New Cloud Provider

1. Create `providers/newprovider.py`:
```python
def fetch_newprovider_pricing() -> Dict[str, Dict]:
    """Fetch pricing from NewProvider API."""
    # Implement API calls, return standardized dict
    return {
        'instance.type': {
            'cores': 4,
            'memory_gb': 16,
            'gpu': None,
            'price': 100.0
        }
    }
```

2. Update `providers/__init__.py`:
```python
from .newprovider import fetch_newprovider_pricing
__all__ = [..., 'fetch_newprovider_pricing']
```

3. Update `update.py` PROVIDERS dict:
```python
PROVIDERS = {
    'newprovider': {
        'fetch': fetch_newprovider_pricing,
        'storage_price': 0.10
    }
}
```

4. Test:
```bash
python3 update.py newprovider --dry-run
```

### Modifying estimate.py Logic

**When changing VM detection:**
- Modify `list_vms()` function (line 322+)
- Update OpenStack CLI queries as needed
- Test with: `python3 estimate.py --cloud software`

**When changing cost calculation:**
- Modify `VM.get_cost()` method - this is the single place for all cost calculations
- Helper methods: `VM.get_billable_storage()` and `VM.get_provider_flavor()`
- Cost formula: `base_compute_price + (billable_storage_gb * storage_price_per_gb)`
- Test: `python3 estimate.py cookiemonster --comparison aws`

**When adding new report formats:**
- Add new `generate_<format>_report()` function
- Use `calculate_totals(vms, provider)` helper to get aggregated stats
- Report functions loop over VMs and call `vm.get_cost(provider)` to calculate on-demand
- Update CLI choices in `main()`
- Update output handling in `main()`

### Updating Pricing Data

**Manual CSV Updates:**
1. Edit pricing.csv directly
2. Ensure proper schema compliance
3. Test: `python3 estimate.py --cloud software --format json`

**Automated Updates:**
```bash
# Update specific provider
python3 update.py aws

# Preview changes first
python3 update.py aws --dry-run

# Update all providers
python3 update.py all
```

### GPU Detection and Handling

**GPU Detection Rules:**
- GPUs detected from VM names using regex patterns in `detect_gpu()` (line 269)
- Patterns: `a100|a_100`, `v100|v_100`
- Count parsing: `gpu.a100.x2` → 2x A100 GPUs

**GPU Pricing:**
- GPU specs defined in pricing.csv (cores, type)
- GPU cores NOT counted toward CPU cores (avoid double-counting)
- Example: VM with flavor "gpu.a100.x1" has 24 cores (all GPU), 0 CPU cores

**Adding New GPU Types:**
1. Add GPU flavor to pricing.csv:
```csv
openstack,gpu.h100.x1,,40,230,0,h100,800.00,0.14,H100 GPU flavor,1x H100 GPU
```

2. Update `detect_gpu()` patterns:
```python
gpu_patterns = {
    'a100': r'a100|a_100',
    'v100': r'v100|v_100',
    'h100': r'h100|h_100',  # Add this
}
```

3. Update `providers/matcher.py` GPU tiers if needed:
```python
gpu_tiers = {
    'h100': 900,
    # ...
}
```

## Key Conventions and Standards

### Global Singleton Pattern

**Location:** All global singletons are declared at the top of estimate.py (right after imports), in a clearly marked section:

```python
# =============================================================================
# Global Singletons (Lazy-Initialized)
# =============================================================================
_openstack_connection: Optional[openstack.connection.Connection] = None
_openstack_cloud: Optional[str] = None
_flavor_cache: Optional[Dict[str, Dict]] = None
_flavor_cache_cloud: Optional[str] = None
```

**Pattern:**
- Initialized to `None` at module load time
- Created on first use (lazy initialization)
- Cached for reuse in subsequent calls
- Always kept at the top of the file for visibility

**Why this approach:**
- Avoids expensive initialization if not needed
- Single instance reused throughout execution
- Clear documentation of what's being cached
- Top placement makes it easy to review all global state

### Code Style

- **Python Version:** Python 3.7+
- **Formatting:** Follow PEP 8
- **Type Hints:** Use dataclasses and type annotations where appropriate
- **Error Handling:** Print errors to stderr, exit with status codes
- **Docstrings:** Use triple-quoted strings with Args/Returns sections
- **Globals:** Keep all global singletons at top of file, clearly marked

### Naming Conventions

- **Files:** lowercase_with_underscores.py
- **Functions:** lowercase_with_underscores()
- **Classes:** PascalCase (e.g., VM)
- **Constants:** UPPERCASE_WITH_UNDERSCORES
- **Variables:** lowercase_with_underscores

### OpenStack Integration

**Dependencies:**
- Requires `openstacksdk` Python library (not CLI)
- Requires `~/.config/openstack/clouds.yaml` configuration
- Uses Python SDK for direct API calls (faster, more reliable)

**Cloud Names:**
- Examples: "aifarms", "cori", "clowder", "software"
- Passed via `--cloud` argument
- Must match `os-cloud` alias in clouds.yaml configuration
- The `cloud` variable is used directly as the connection cloud name

**OpenStack SDK API Calls Used:**
```python
# Connection creation
conn = openstack.connect(cloud=cloud_name)

# Server operations
servers = conn.compute.servers(details=True)
server = conn.compute.get_server(server_id)

# Flavor operations
flavors = conn.compute.flavors()

# Volume operations (attachments are in compute, volumes in block_storage)
attachments = conn.compute.volume_attachments(server_id)
volume = conn.block_storage.get_volume(volume_id)
```

**Error Handling:**
- Catches `openstack.exceptions.SDKException` for OpenStack-specific errors
- Graceful degradation with warnings for individual VM/volume failures
- Early exit only on critical connection failures

### Pricing Conventions

**Monthly Costs:**
- All prices stored as monthly costs (not hourly)
- Convert hourly → monthly: `hourly * 730`

**Storage Pricing:**
- Boot storage (included in flavor) vs additional storage
- Additional storage = total_storage - boot_storage
- Additional storage cost = additional_storage * storage_price_per_gb

**Cost Calculation Formula:**
```python
total_cost = flavor_compute_price + (additional_storage_gb * storage_price)
```

### Output Formats

**Table Format:**
- ASCII table using tabulate library
- Human-readable, terminal-friendly
- Includes summary row with totals

**CSV Format:**
- Comma-separated values
- Excel/spreadsheet compatible
- Headers + data rows + summary row

**JSON Format:**
- Machine-readable structured data
- ISO timestamp
- Nested structure: `{vms: [...], summary: {...}}`

## Testing Guidelines

### Manual Testing Checklist

```bash
# 1. Test basic VM listing
python3 estimate.py --cloud software

# 2. Test regex filtering
python3 estimate.py "^test-.*" --cloud software

# 3. Test all output formats
python3 estimate.py --cloud software --format table
python3 estimate.py --cloud software --format csv
python3 estimate.py --cloud software --format json
python3 estimate.py --cloud software --format all --output test_report

# 4. Test provider comparisons
python3 estimate.py --cloud software --comparison aws
python3 estimate.py --cloud software --comparison cheapest
python3 estimate.py --cloud software --comparison none

# 5. Test pricing updates
python3 update.py aws --dry-run
python3 update.py aws

# 6. Validate pricing.csv integrity
# - Check CSV loads without errors
# - Verify OpenStack flavors present
# - Confirm provider matches exist
```

### Edge Cases to Test

1. **VMs with GPUs:** Ensure GPU detection works, cores not double-counted
2. **VMs without volumes:** Handle boot-from-flavor correctly
3. **Empty VM lists:** Graceful handling when no VMs match regex
4. **Missing flavors:** Handle unknown OpenStack flavors
5. **Provider unavailability:** Handle missing provider pricing gracefully

### Validation Scripts

```python
# Validate pricing.csv structure
import csv
with open('pricing.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        assert 'Cloud' in row
        assert 'Flavor' in row
        # ... validate required fields
```

## Common Tasks for AI Assistants

### Task: Debug Cost Calculation Issue

1. Check pricing.csv for correct flavor pricing
2. Verify OpenStack flavor name matches CSV exactly
3. Check storage calculation using `vm.get_billable_storage(provider)` helper
4. Review `VM.get_cost()` method logic - this is the single source of all cost calculations
5. Add debug prints: `print(f"VM {vm.name}: flavor={vm.flavor}, os_cost={vm.get_cost('openstack')}, billable_storage={vm.get_billable_storage('openstack')}", file=sys.stderr)`
6. Verify PROVIDER_PRICING global dict is loaded correctly
7. Missing costs will return `None` - check if VM flavor exists in PROVIDER_PRICING[provider]

### Task: Add Support for New Instance Type

1. Identify provider (AWS/GCP/Azure/etc.)
2. Add instance to provider's pricing file (providers/aws.py, etc.)
3. Update pricing.csv with new instance details
4. Match to appropriate OpenStack flavor in `Matched_OpenStack_Flavor` column
5. Test: `python3 estimate.py --cloud software --comparison PROVIDER`

### Task: Fix GPU Detection

1. Review VM naming patterns in OpenStack
2. Update regex patterns in `detect_gpu()` function
3. Test with actual VM names: `detect_gpu("gpu.a100.x2")`
4. Verify GPU specs in pricing.csv (cores, pricing)
5. Ensure GPU cores excluded from CPU count

### Task: Add or Modify a Cloud Provider

When adding a new cloud provider or changing how providers work:

1. **Implement two functions** in `providers/yourprovider.py`:
   - `get_<provider>_flavor_prices()` → Returns `Dict[str, Dict]` with compute instance pricing
   - `get_<provider>_storage_prices()` → Returns `Dict[str, float]` with `"flash"` key

2. **Update provider registration:**
   - Add exports to `providers/__init__.py`
   - Add entry to `PROVIDERS` dict in `update.py` (keep alphabetically sorted)

3. **Update both documentation files** (CRITICAL):
   - **`PROVIDERS.md`** - Add row to Quick Summary table + detailed section with:
     - Source (dynamic/hardcoded)
     - API endpoints
     - Fallback prices
     - GPU support details
   - **`CONTRIBUTING.md`** - Update if introducing new patterns or code examples

4. **Test:**
   - `python3 update.py yourprovider --dry-run`
   - `python3 update.py yourprovider`
   - `python3 estimate.py --cloud software --comparison yourprovider`

5. **See:** `PROVIDERS.md` and `CONTRIBUTING.md` for detailed instructions

**Note:** Failing to update `PROVIDERS.md` and `CONTRIBUTING.md` makes the codebase harder to maintain. Always update docs when provider behavior changes.

### Task: Improve Documentation

1. **User docs:** Update README.md
2. **Developer docs:** Update this CLAUDE.md file
3. **Contributor docs:** Update CONTRIBUTING.md
4. **Provider reference:** Update PROVIDERS.md when provider behavior changes
5. **Code comments:** Add inline documentation for complex logic

### Task: Optimize Performance

**Bottlenecks:**
- OpenStack CLI calls are slow (serial, subprocess overhead)
- `openstack server show` called for each uncached VM individually

**Current Optimizations:**
- VM data caching with configurable TTL (default 24 hours)
- Cache stores complete VM details to avoid re-querying OpenStack
- Lazy-loading of flavor cache (only fetched when needed)

**Future Optimization Strategies:**
1. Batch OpenStack queries where possible
2. Use OpenStack SDK directly instead of CLI (requires openstacksdk)
3. Parallelize VM detail fetching with threading/asyncio

## Error Handling Patterns

### Standard Error Messages

```python
# Configuration errors
print(f"Error: pricing.csv not found!", file=sys.stderr)
sys.exit(1)

# OpenStack errors
print(f"Error running OpenStack command: {e.stderr}", file=sys.stderr)
sys.exit(1)

# Data validation errors
print(f"Error: Could not parse OpenStack server list", file=sys.stderr)
sys.exit(1)

# User errors
print("No VMs found matching the criteria", file=sys.stderr)
sys.exit(0)  # Not an error, just empty result
```

### Exception Handling

```python
try:
    # Operation that may fail
    result = run_openstack_command(...)
except subprocess.CalledProcessError as e:
    print(f"Error: {e.stderr}", file=sys.stderr)
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: Could not parse JSON output", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)
```

## Important Gotchas and Pitfalls

### 1. GPU Core Double-Counting

**Problem:** GPUs have cores (e.g., A100 = 24 cores) that could be counted as CPU cores

**Solution:** GPU cores are stored separately in GPU_SPECS, not added to VM.cores

**Check:** Ensure `vm.cores` represents only CPU cores for GPU VMs

### 2. Boot vs. Attached Storage

**Problem:** OpenStack VMs can boot from flavor disk OR attached volumes

**Solution:**
- If VM has `/dev/vda` volume → use volume size
- Otherwise → use flavor boot_storage_gb
- See `list_vms()` logic around line 365

### 3. Pricing.csv Schema Changes

**Problem:** Adding columns breaks CSV parsing

**Solution:**
- Always use `csv.DictReader()` for forward compatibility
- Use `row.get('NewColumn', '')` for optional fields
- Update `load_all_pricing_data()` to handle new fields

### 4. Provider API Rate Limits

**Problem:** Cloud provider APIs may rate-limit pricing requests

**Solution:**
- Cache pricing data (pricing.csv serves as cache)
- Use `--dry-run` when testing update.py
- Implement exponential backoff if needed

### 5. OpenStack CLI Authentication

**Problem:** `openstack` commands fail if clouds.yaml not configured

**Solution:**
- Check `~/.config/openstack/clouds.yaml` exists
- Verify cloud name matches configuration
- Test manually: `openstack --os-cloud=software server list`

## Dependencies and Requirements

### Python Packages

```
requests==2.31.0           # HTTP library for API calls
tabulate==0.9.0            # ASCII table formatting
openstacksdk==1.5.0        # OpenStack SDK (optional)
python-openstackclient>=5.0.0  # OpenStack CLI
boto3>=1.26.0              # AWS SDK (for pricing API)
beautifulsoup4>=4.11.0     # HTML parsing (for web scraping)
```

### System Requirements

- **Python:** 3.7 or higher
- **OpenStack CLI:** Installed and configured
- **Internet Access:** Required for provider pricing updates
- **OS:** Linux/macOS (primary), Windows (untested but should work)

### External Tools

- `openstack` CLI command must be in PATH
- `~/.config/openstack/clouds.yaml` must be configured
- Git for version control

## Documentation Updates

**CRITICAL:** When making code changes, always update relevant documentation:

1. **CLAUDE.md** (this file) - Developer/AI guide
   - Update OpenStack Integration section if API calls change
   - Add entry to "Recent Major Simplifications" for significant refactors
   - Update line number references if functions move
   - Update version history at the end

2. **README.md** - User guide
   - Update examples if CLI arguments change
   - Update feature list if adding new functionality
   - Update usage instructions if workflow changes

3. **CONTRIBUTING.md** - Contributor guide
   - Update if adding new cloud providers
   - Update code patterns/examples if architecture changes
   - Update testing instructions if new test procedures needed

4. **requirements.txt** - Dependencies
   - Update whenever adding/removing Python packages
   - Keep versions synchronized with tested versions

5. **PROVIDERS.md** (if it exists) - Provider reference
   - Update when provider behavior changes
   - Document new provider integrations
   - Document API endpoints and fallback behavior

**Why this matters:**
- Out-of-date docs make the codebase harder to maintain
- Future developers (AI or human) rely on docs to understand intent
- Incomplete documentation leads to bugs and duplicated effort
- This is especially critical for API changes that affect integration points

**Checklist before committing:**
- [ ] Code changes complete and tested
- [ ] CLAUDE.md updated (if architecture/API changes)
- [ ] README.md updated (if user-facing changes)
- [ ] CONTRIBUTING.md updated (if contribution process changes)
- [ ] requirements.txt updated (if dependencies changed)
- [ ] Version history updated in CLAUDE.md
- [ ] All docs are accurate and reflect current state

---

## Git Workflow

### Branch Strategy

**Current Branch:** `main`

**Development:** Create feature branches off main

### Commit Guidelines

```bash
# Make changes
git add file1.py file2.py

# Commit with descriptive message
git commit -m "Add support for H100 GPUs in pricing and detection"

# Push to Claude branch
git push -u origin claude/claude-md-mhye6vfhxhycwk9i-01RqeH9ZJBeXrBQiL5ko3bi4
```

**Commit Message Style:**
- Imperative mood: "Add feature" not "Added feature"
- Clear, concise description
- Reference issues if applicable

### Creating Pull Requests

1. Ensure all tests pass
2. Update documentation if needed
3. Push to Claude branch
4. Create PR with description of changes
5. Include testing steps in PR description

## FAQ for AI Assistants

### Q: How do I test changes to estimate.py?

**A:** Run against a test OpenStack cloud:
```bash
python3 estimate.py --cloud software --format json
```

### Q: How do I add a new cloud provider?

**A:** See "Adding a New Cloud Provider" section above. Summary:
1. Create `providers/newprovider.py`
2. Implement `fetch_newprovider_pricing()`
3. Update `providers/__init__.py` and `update.py`
4. Test with `python3 update.py newprovider --dry-run`

### Q: How is pricing.csv structured?

**A:** Two types of rows:
- **OpenStack flavors:** `Cloud=openstack`, defines flavor specs and base pricing
- **Provider instances:** `Cloud=aws/gcp/etc`, matches to OpenStack flavors via `Matched_OpenStack_Flavor`

### Q: What if a provider doesn't have an exact match for an OpenStack flavor?

**A:** The matcher in `providers/matcher.py` finds the cheapest instance that meets or exceeds the flavor's requirements (cores, memory, GPU). It's fuzzy matching, not exact.

### Q: How do I handle authentication errors with OpenStack?

**A:**
1. Check clouds.yaml configuration: `cat ~/.config/openstack/clouds.yaml`
2. Test manually: `openstack --os-cloud=software server list`
3. Verify credentials are current

### Q: Why are some costs showing as "N/A"?

**A:** Likely causes:
- Provider doesn't have a matching instance for that OpenStack flavor
- Provider not included in pricing.csv
- `--comparison none` flag used

## Resources

### External Documentation

- **OpenStack CLI:** https://docs.openstack.org/python-openstackclient/
- **Boto3 (AWS SDK):** https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- **Tabulate:** https://github.com/astanin/python-tabulate

### Internal Documentation

- `README.md` - User guide with quick start, examples, and feature overview
- `CLAUDE.md` - This file - comprehensive developer and AI assistant guide
- `CONTRIBUTING.md` - Guide for adding new cloud providers

### Key Files to Reference

- `estimate.py` (lines 25-107) - Pricing data loading
- `estimate.py` (lines 110-185) - VM dataclass with helper methods
- `estimate.py` (lines 322-560) - VM discovery and enrichment with caching
- `estimate.py` (lines 564-600) - Provider comparison logic
- `estimate.py` (lines 603-1010) - Report generation functions
- `providers/matcher.py` - Flavor matching algorithm
- `update.py` - Pricing update orchestration

## Version History

For detailed information about changes, please see [CHANGELOG.md](CHANGELOG.md).

### Architecture Evolution

The codebase has evolved through several major simplifications:

1. **Unified Pricing Data Structure** - Single `PROVIDER_PRICING` global dict instead of multiple data structures
2. **Simplified Cost Calculation API** - Single `vm.get_cost(provider)` method instead of multiple helper functions
3. **On-Demand Calculation** - Costs calculated when needed instead of stored in VM state
4. **Streamlined Report Generation** - Report functions are pure formatters without business logic
5. **Lazy Initialization** - OpenStack connection and flavor cache created only when needed
6. **Singleton Pattern** - Global resources cached and reused for performance

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

**Document Version:** 2.3
**Last Updated:** 2025-11-15
**Maintained By:** AI Assistants (Claude)
**Status:** Production Ready

For version history and detailed changelog, see [CHANGELOG.md](CHANGELOG.md).

For questions or updates to this document, modify CLAUDE.md directly and commit changes.
