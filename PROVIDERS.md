# Cloud Providers Reference

This document describes how each cloud provider's pricing is fetched and used by the rate calculator.

## Quick Summary

| Provider | Flavors | Storage | Notes |
|----------|---------|---------|-------|
| [AWS](#aws) | Dynamic | Dynamic | x86_64 Linux only; fallback $0.10/GB |
| [Azure](#azure) | Dynamic | Hardcoded | Managed Disks Standard SSD; $0.05/GB |
| [GCP](#gcp) | Hardcoded | Hardcoded | Requires API auth; embedded pricing from 2024 |
| [Linode](#linode) | Dynamic | Dynamic | Public API; fallback $0.10/GB |
| [Hetzner](#hetzner) | Dynamic | Dynamic | US locations only; fallback $0.05/GB |
| [Vultr](#vultr) | Dynamic | Dynamic | Web scrape + API fallback; $0.05/GB fallback |
| [DigitalOcean](#digitalocean) | Dynamic | Dynamic | Extracts from pricing calculator; $0.10/GB fallback |

---

## Provider Architecture

Each provider module implements two functions:

- **`get_<provider>_flavor_prices()`** - Returns pricing for compute instances/flavors
- **`get_<provider>_storage_prices()`** - Returns pricing for block storage (returns dict with `"flash"` key)

Both functions return dicts that can be extended in the future with additional storage types.

---

## Provider Details

### AWS

**File:** `providers/aws.py`

**Flavor Pricing (get_aws_flavor_prices):**
- **Source:** Dynamic - fetches from `https://ec2instances.info/instances.json`
- **Filter:** x86_64 Linux instances only
- **Region:** us-east-1 (with fallback to any available region)
- **Details:** Extracts vCPU, memory, processor, network performance, burstable info
- **GPU Support:** Yes - detects GPU count and model from instance data

**Storage Pricing (get_aws_storage_prices):**
- **Source:** Dynamic - fetches from `https://aws.amazon.com/ebs/pricing/`
- **Type:** EBS gp3 (general purpose SSD)
- **Fallback:** `{"flash": 0.10}` if extraction fails
- **Returns:** `{"flash": <price_per_gb_per_month>}`

---

### Azure

**File:** `providers/azure.py`

**Flavor Pricing (get_azure_flavor_prices):**
- **Source:** Dynamic - fetches from Azure Pricing API
- **API Endpoint:** `https://azure.microsoft.com/api/v4/pricing/virtual-machines/calculator/{region}/`
- **Region:** us-east (default)
- **Details:** Extracts cores, RAM, hourly pricing (converts to monthly)
- **GPU Support:** Yes - parses GPU field from API (e.g., "1X H100", "4X A100")
- **Skips:** Hidden offers

**Storage Pricing (get_azure_storage_prices):**
- **Source:** Hardcoded
- **Type:** Managed Disks - Standard SSD (E-series)
- **Price:** `{"flash": 0.05}` per GB per month
- **Note:** Standard HDD ~$0.04, Premium SSD ~$0.13 (could be updated dynamically)

---

### GCP

**File:** `providers/gcp.py`

**Flavor Pricing (get_gcp_flavor_prices):**
- **Source:** Embedded/Hardcoded
- **Reason:** GCP Cloud Billing API requires authentication (API key + billing enabled)
- **Data:** Embedded in `GCP_PRICING` dict at module level
- **Machine Series:** N1, N2, E2, C2, and A2 (A100 GPUs)
- **Last Updated:** 2024
- **Region:** us-central1 (assumed)
- **GPU Support:** Yes - A2 instances with A100 GPUs

**Storage Pricing (get_gcp_storage_prices):**
- **Source:** Hardcoded
- **Type:** Persistent Disk - pd-standard (most cost-effective)
- **Price:** `{"flash": 0.04}` per GB per month
- **Available Types:** pd-standard ($0.04), pd-balanced ($0.10), pd-ssd ($0.17)

---

### Linode

**File:** `providers/linode.py`

**Flavor Pricing (get_linode_flavor_prices):**
- **Source:** Dynamic - fetches from Linode API
- **API Endpoint:** `https://api.linode.com/v4/linode/types`
- **Details:** Extracts vCPU, memory (MB → GB conversion), monthly price
- **GPU Support:** Yes - detects RTX6000, V100 from label
- **No Authentication:** Public API

**Storage Pricing (get_linode_storage_prices):**
- **Source:** Dynamic - scrapes from `https://www.linode.com/pricing/`
- **Type:** Block Storage volumes
- **Fallback:** `{"flash": 0.10}` if extraction fails
- **Returns:** `{"flash": <price_per_gb_per_month>}`

---

### Hetzner

**File:** `providers/hetzner.py`

**Flavor Pricing (get_hetzner_flavor_prices):**
- **Source:** Dynamic - scrapes from `https://www.hetzner.com/cloud`
- **Locations:** US only (Ashburn, Hillsboro)
- **Parsing:** Extracts vCPU, RAM, monthly price from HTML table
- **Complex Parsing:** Uses `extract_spec_from_container()` helper to parse HTML containers
- **GPU Support:** No GPU instances in current pricing

**Storage Pricing (get_hetzner_storage_prices):**
- **Source:** Dynamic - scrapes from `https://www.hetzner.com/cloud`
- **Type:** Block Storage Volumes
- **Format Extracted:** USD prices like "$0.0484 per GB"
- **Fallback:** `{"flash": 0.05}` if extraction fails
- **Returns:** `{"flash": <price_per_gb_per_month>}`

---

### Vultr

**File:** `providers/vultr.py`

**Flavor Pricing (get_vultr_flavor_prices):**
- **Source:** Dual approach
  1. Primary: Dynamic - scrapes `https://www.vultr.com/pricing/`
  2. Fallback: API from `https://api.vultr.com/v2/products/compute`
- **Parsing:** Extracts vCPU, memory, hourly price (converts to monthly)
- **De-duplication:** Avoids duplicate vCPU/memory configurations
- **GPU Support:** Yes - detects A100, H100 from instance label/slug
- **Instance Naming:** Creates synthetic names like `vultr-4c-16gb`

**Storage Pricing (get_vultr_storage_prices):**
- **Source:** Dynamic - scrapes from `https://www.vultr.com/pricing/`
- **Type:** Block Storage
- **Pattern:** Looks for "block storage ... $X.XX per GB"
- **Fallback:** `{"flash": 0.05}` if extraction fails
- **Returns:** `{"flash": <price_per_gb_per_month>}`

---

### DigitalOcean

**File:** `providers/digitalocean.py`

**Flavor Pricing (get_digitalocean_flavor_prices):**
- **Source:** Dynamic - fetches from `https://www.digitalocean.com/pricing/calculator`
- **Method:** Extracts `__NEXT_DATA__` JSON script from pricing calculator page
- **Advantages:** Independent of buildId/API endpoint changes
- **Data:** Regular droplets + GPU droplets
- **Parsing:** Navigates nested structure (categories → plan_type → instances)
- **GPU Support:** Yes - detects A100, H100 from slug

**Storage Pricing (get_digitalocean_storage_prices):**
- **Source:** Dynamic - scrapes from `https://www.digitalocean.com/pricing/calculator`
- **Type:** Block Storage volumes
- **Pattern:** Looks for "block storage ... $X.XX per GB per month"
- **Fallback:** `{"flash": 0.10}` if extraction fails
- **Returns:** `{"flash": <price_per_gb_per_month>}`

---

## Adding a New Provider

To add a new cloud provider:

1. **Create** `providers/newprovider.py` with two functions:
   ```python
   def get_newprovider_flavor_prices() -> Dict[str, Dict]:
       """Fetch instance pricing from NewProvider API."""
       return {
           'instance-type': {
               'cores': 4,
               'memory_gb': 16,
               'price': 100.0,  # Monthly price
               'gpu_count': 0,
               'gpu_model': '',
               'gpu_memory': 0,
           },
           ...
       }
   
   def get_newprovider_storage_prices() -> Dict[str, float]:
       """Fetch storage pricing from NewProvider API."""
       return {
           'flash': 0.10,  # Price per GB per month
       }
   ```

2. **Update** `providers/__init__.py`:
   ```python
   from .newprovider import get_newprovider_flavor_prices, get_newprovider_storage_prices
   
   __all__ = [
       ...,
       "get_newprovider_flavor_prices",
       "get_newprovider_storage_prices",
   ]
   ```

3. **Update** `update.py` PROVIDERS dict:
   ```python
   PROVIDERS = {
       ...,
       "newprovider": {
           "get_flavors": get_newprovider_flavor_prices,
           "get_storage": get_newprovider_storage_prices,
       },
   }
   ```

4. **Test:**
   ```bash
   python3 update.py newprovider --dry-run
   ```

5. **Update documentation:**
   - Add provider entry to `PROVIDERS.md` table and detailed section
   - Add provider instructions to `CONTRIBUTING.md`
   - See "Documentation Requirements" below

---

## Documentation Requirements

**Important:** When adding a new provider or modifying provider behavior, you MUST update:

1. **`PROVIDERS.md`** (this file)
   - Add row to Quick Summary table
   - Add detailed section with flavor and storage pricing info
   - Include fallback prices, data sources, and special notes

2. **`CONTRIBUTING.md`**
   - Update function names in examples
   - Update the step-by-step guide to match current interface
   - Include new provider in provider list

Failing to update documentation will make it harder for future developers to maintain and extend the codebase.

---

## Maintenance Notes

### When to Fetch Dynamically vs Hardcode

**Fetch Dynamically:**
- Cloud provider has public API (no auth required)
- Data changes frequently (pricing updates)
- Web scraping is stable and resilient

**Hardcode:**
- API requires authentication
- Data rarely changes (annual review sufficient)
- Web scraping is fragile or prohibited
- Serves as fallback when dynamic fetch fails

### Common Issues

**Web Scraping Failures:**
- HTML structure changes → parsing breaks
- Solution: Implement fallback prices + robust error handling
- Monitor: Test providers periodically to catch breakage

**API Rate Limiting:**
- Some APIs limit requests
- Solution: Cache results (pricing.csv acts as cache)
- Use `--dry-run` during testing

**GPU Detection:**
- Different providers use different GPU naming conventions
- Solution: `matcher.py` has flexible GPU matching with tier system
- See `get_gpu_tier()` for GPU hierarchy

---

## Future Improvements

- [ ] Add dynamic pricing updates for GCP (requires authentication setup)
- [ ] Implement caching for web scraping (reduce request load)
- [ ] Add timeout/retry logic for flaky API endpoints
- [ ] Support regional pricing variants (currently single region per provider)
- [ ] Add more GPU types to tier system as they emerge
- [ ] Implement spot/reserved instance pricing options

---

**Last Updated:** 2025-11-15
**Maintainers:** AI Assistants and Contributors
