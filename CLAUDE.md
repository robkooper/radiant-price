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
├── estimate.py              # Main analysis tool (1036 lines)
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
    storage_gb: int
    gpu_type: Optional[str]  # e.g., "A100", "V100"
    gpu_count: int
    floating_ip: bool

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
- Modify `list_vms()` function
- Update OpenStack CLI queries as needed
- Test with: `python3 estimate.py --cloud software`

**When changing cost calculation:**
- Modify `VM.get_cost()` method - this is the single place for all cost calculations
- Cost formula: `base_compute_price + (additional_storage_gb * storage_price_per_gb)`
- Test: `python3 estimate.py cookiemonster --comparison aws`

**When adding new report formats:**
- Add new `generate_<format>_report()` function
- Report functions simply loop over VMs and call `vm.get_cost(provider)` to calculate on-demand
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
- GPUs detected from VM names using regex patterns in `detect_gpu()` (line 268)
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

### Code Style

- **Python Version:** Python 3.7+
- **Formatting:** Follow PEP 8
- **Type Hints:** Use dataclasses and type annotations where appropriate
- **Error Handling:** Print errors to stderr, exit with status codes
- **Docstrings:** Use triple-quoted strings with Args/Returns sections

### Naming Conventions

- **Files:** lowercase_with_underscores.py
- **Functions:** lowercase_with_underscores()
- **Classes:** PascalCase (e.g., VM)
- **Constants:** UPPERCASE_WITH_UNDERSCORES
- **Variables:** lowercase_with_underscores

### OpenStack Integration

**Dependencies:**
- Requires OpenStack CLI (`openstack` command)
- Requires `~/.config/openstack/clouds.yaml` configuration
- Uses shell commands, not direct API calls

**Cloud Names:**
- Examples: "aifarms", "cori", "clowder", "software"
- Passed via `--cloud` argument
- Must match clouds.yaml configuration

**OpenStack Commands Used:**
```bash
openstack --os-cloud=CLOUD server list -f json
openstack --os-cloud=CLOUD server show VM_NAME -f json
openstack --os-cloud=CLOUD flavor show FLAVOR_NAME -f json
openstack --os-cloud=CLOUD server volume list VM_NAME -f json
openstack --os-cloud=CLOUD volume show VOLUME_ID -f json
```

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
3. Check storage calculation: `vm.storage_gb - boot_storage_gb`
4. Review `VM.get_cost()` method logic - this is the single source of all cost calculations
5. Add debug prints: `print(f"VM {vm.name}: flavor={vm.flavor}, os_cost={vm.get_cost('openstack')}", file=sys.stderr)`
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
- `openstack server show` called for each VM individually

**Optimization Strategies:**
1. Batch OpenStack queries where possible
2. Cache OpenStack responses for repeated queries
3. Use OpenStack SDK directly instead of CLI (requires openstacksdk)
4. Parallelize VM detail fetching with threading/asyncio

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

## Git Workflow

### Branch Strategy

**Current Branch:** `claude/claude-md-mhye6vfhxhycwk9i-01RqeH9ZJBeXrBQiL5ko3bi4`

**Main Branch:** (to be determined - likely `main` or `master`)

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

- `estimate.py` (lines 24-175) - Pricing data loading
- `estimate.py` (lines 289-421) - VM discovery and enrichment
- `estimate.py` (lines 424-507) - Cost calculation and provider matching
- `providers/matcher.py` - Flavor matching algorithm
- `update.py` - Pricing update orchestration

## Recent Major Simplifications (November 2025)

This section documents the major code simplifications made to the codebase, making it cleaner and more maintainable.

### 1. Unified Pricing Data Structure

**Before:** Multiple separate data structures (`openstack_pricing`, `gpu_specs`, `openstack_flavors`, `provider_pricing`)

**After:** Single unified `PROVIDER_PRICING` global dict
```python
PROVIDER_PRICING = {
    "openstack": {flavor: {...}},
    "aws": {flavor: {...}},
    "gcp": {flavor: {...}},
    ...
}
```

**Benefits:**
- Single source of truth for all pricing data
- Simpler to query and maintain
- Reduced memory footprint

### 2. Simplified Cost Calculation API

**Before:** Multiple helper functions (`calculate_vm_cost()`, `estimate_cost_by_provider()`)

**After:** Single method on VM class
```python
vm.get_cost("aws")  # Returns Optional[float]
```

**Benefits:**
- Clean, simple API
- Calculates base price + additional storage in one place
- Easy to understand and debug

### 3. Removed Redundant VM State

**Before:** VMs stored `comparison_flavor` and `comparison_price` fields

**After:** Calculate costs on-demand when needed

**Benefits:**
- No stale state
- Always accurate (recalculates with current pricing)
- Simpler VM dataclass

### 4. Streamlined Report Generation

**Before:** Report functions determined provider, called helper functions, managed state

**After:** Report functions just loop and calculate
```python
for vm in vms:
    os_cost = vm.get_cost("openstack")
    comparison_cost = vm.get_cost(provider)
    # Display the costs
```

**Benefits:**
- Report functions are pure formatters
- No business logic in presentation layer
- Easier to add new report formats

### 5. Provider Determination in main()

**Before:** Each report function determined which provider to use

**After:** Determined once in `main()`, passed to all reports

**Benefits:**
- Single point where cheapest provider is calculated
- No duplicate `find_cheapest_provider()` calls
- Consistent across all report formats

### 6. list_vms() Accepts Multiple Patterns

**Before:** Single regex string parameter

**After:** Optional list of regex patterns
```python
list_vms(cloud, vm_filter=["cookie.*", "soma.*"])  # Matches ANY pattern
list_vms(cloud, vm_filter=["cookiemonster"])       # Single pattern
list_vms(cloud, vm_filter=None)                    # All VMs
```

**Benefits:**
- Can filter for multiple VMs in one command
- Simpler type signature (no Union[str, List[str]])
- Consistent interface (always a list or None)

### 7. OpenStack Excluded from find_cheapest_provider()

**Before:** OpenStack was considered in the comparison

**After:** OpenStack explicitly skipped (it's the baseline)

**Benefits:**
- `--comparison cheapest` now only considers alternative providers
- Matches user expectations
- Clearer intent in code

### 8. Graceful Handling of Missing Pricing

**Before:** Crashed with TypeError when flavor not in pricing.csv

**After:** Returns None, displays "N/A" in reports

**Benefits:**
- Tool continues working even with incomplete pricing data
- Easy to identify which VMs need pricing added
- Better user experience

### Key Architectural Principles

1. **Table-First Approach**: Load CSV into single table, build one dict from it
2. **On-Demand Calculation**: Calculate costs when needed, don't store
3. **Single Source of Truth**: PROVIDER_PRICING is the only pricing data structure
4. **Simple APIs**: `vm.get_cost(provider)` is the only cost calculation entry point
5. **Separation of Concerns**: main() determines provider, reports just format data

## Changelog Template

When making significant changes, update this section:

```markdown
### [Version] - YYYY-MM-DD

#### Added
- New feature X

#### Changed
- Modified behavior of Y

#### Fixed
- Bug in Z calculation

#### Removed
- Deprecated feature A
```

---

**Document Version:** 2.1
**Last Updated:** 2025-11-15
**Maintained By:** AI Assistants (Claude)
**Status:** Production Ready

**Version History:**
- **v2.1 (2025-11-15)**: Streamlined documentation structure - removed redundant files (QUICKSTART.md, CONFIG.md, FEATURES.md, INDEX.md), consolidated into README.md, CLAUDE.md, and CONTRIBUTING.md
- **v2.0 (2025-11-14)**: Updated architecture documentation to reflect simplified codebase, added "Recent Major Simplifications" section, removed references to deprecated functions, updated CLI examples to show multiple VM pattern support, documented table-first approach and on-demand calculation principles

For questions or updates to this document, modify CLAUDE.md directly and commit changes.
