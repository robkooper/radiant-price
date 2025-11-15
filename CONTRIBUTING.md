# Contributing to Radiant Price

This guide explains how to add support for new cloud providers to the Radiant Price cost comparison tool.

## Overview

Adding a new cloud provider involves three main steps:

1. **Create a pricing fetcher module** in `providers/`
2. **Register the provider** in `update.py`
3. **Test and update pricing data**

## Step 1: Create Pricing Fetcher Module

Create a new file `providers/yourprovider.py` that implements the pricing fetcher function.

### Template

```python
"""YourProvider Cloud pricing fetcher."""

import requests
from typing import Dict


def fetch_yourprovider_pricing() -> Dict[str, Dict]:
    """
    Fetch YourProvider Cloud pricing from their API.

    Returns:
        Dict of {instance_type: {cores, memory_gb, price, gpu_count, gpu_model}}
        
        Required fields:
        - cores: int (number of vCPUs)
        - memory_gb: float (RAM in GB)
        - price: float (monthly cost in USD)
        
        Optional fields:
        - gpu_count: int (number of GPUs, default 0)
        - gpu_model: str (GPU model name, e.g., "A100", "V100")
        - gpu_memory: int (total GPU memory in GB)
    """
    print(f"[YourProvider] Fetching pricing...")

    try:
        # Fetch pricing from provider API
        url = "https://api.yourprovider.com/pricing"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        pricing_data = {}

        # Parse response and build pricing dictionary
        for instance in data.get("instances", []):
            instance_type = instance.get("type")
            monthly_price = instance.get("price_monthly")
            vcpus = instance.get("vcpus")
            memory_mb = instance.get("memory_mb")
            
            if instance_type and monthly_price and vcpus and memory_mb:
                pricing_data[instance_type] = {
                    "cores": vcpus,
                    "memory_gb": memory_mb / 1024,  # Convert MB to GB
                    "price": round(monthly_price, 2),
                    "gpu_count": 0,  # Add GPU detection if applicable
                    "gpu_model": "",
                    "gpu_memory": 0,
                }

        print(f"      ✓ Fetched {len(pricing_data)} instances")
        return pricing_data

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}


def get_yourprovider_storage_price() -> float:
    """
    Get storage pricing for YourProvider.

    Returns:
        Storage price per GB per month (e.g., 0.10)
    """
    # Option 1: Fetch from API
    try:
        url = "https://api.yourprovider.com/storage-pricing"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        return float(data.get("price_per_gb_monthly", 0.10))
    except Exception:
        pass
    
    # Option 2: Return known/hardcoded value
    return 0.10  # $0.10 per GB per month
```

### Real-World Examples

#### Example 1: API with JSON Response (Linode)

```python
def fetch_linode_pricing() -> Dict[str, Dict]:
    """Fetch Linode Cloud pricing from their API."""
    print(f"[Linode] Fetching Cloud pricing...")

    try:
        url = "https://api.linode.com/v4/linode/types"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        data = response.json()
        pricing_data = {}

        for instance in data.get("data", []):
            type_id = instance.get("id")
            price = instance.get("price", {}).get("monthly", 0)
            vcpus = instance.get("vcpus", 0)
            memory = instance.get("memory", 0)
            gpus = instance.get("gpus", 0)

            if type_id and price > 0 and vcpus and memory:
                pricing_data[type_id] = {
                    "cores": vcpus,
                    "memory_gb": memory / 1024,
                    "price": round(price, 2),
                    "gpu_count": gpus,
                }

        print(f"      ✓ Fetched {len(pricing_data)} Linode instances")
        return pricing_data

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}
```

#### Example 2: Web Scraping (Hetzner)

```python
from bs4 import BeautifulSoup

def fetch_hetzner_pricing() -> Dict[str, Dict]:
    """Fetch Hetzner Cloud pricing by scraping their website."""
    print(f"[Hetzner] Fetching Cloud pricing...")

    try:
        url = "https://www.hetzner.com/cloud"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        pricing_data = {}

        # Parse HTML to extract pricing
        # (Implementation depends on website structure)

        return pricing_data

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}
```

### GPU Support

If the provider offers GPU instances, include GPU information:

```python
# Detect GPU model from instance type or label
gpu_model = ""
gpu_count = 0

if "a100" in instance_type.lower():
    gpu_model = "A100"
    gpu_count = 1
elif "v100" in instance_type.lower():
    gpu_model = "V100"
    gpu_count = 1

pricing_data[instance_type] = {
    "cores": vcpus,
    "memory_gb": memory_gb,
    "price": monthly_price,
    "gpu_count": gpu_count,
    "gpu_model": gpu_model,
    "gpu_memory": gpu_count * 80,  # e.g., 80GB per A100
}
```

## Step 2: Register the Provider

### 2.1 Update `providers/__init__.py`

Add your fetcher functions to the module exports:

```python
from .yourprovider import fetch_yourprovider_pricing, get_yourprovider_storage_price

__all__ = [
    # ... existing providers ...
    'fetch_yourprovider_pricing',
    'get_yourprovider_storage_price',
]
```

### 2.2 Update `update.py`

Register your provider in the `PROVIDERS` dictionary:

```python
from providers import (
    # ... existing imports ...
    fetch_yourprovider_pricing,
    get_yourprovider_storage_price,
)

PROVIDERS = {
    # ... existing providers ...
    "yourprovider": {
        "fetch": fetch_yourprovider_pricing,
        "storage_price": get_yourprovider_storage_price,
    },
}
```

## Step 3: Test and Update Pricing

### 3.1 Test Fetching

Test that your fetcher works:

```bash
# Dry run - preview changes without modifying pricing.csv
python3 update.py yourprovider --dry-run
```

You should see output like:

```
Updating pricing for provider: yourprovider

[YourProvider] Fetching Cloud pricing...
      ✓ Fetched 25 instances

Matching OpenStack flavors to yourprovider instances...
      ✓ 15 flavors matched

Preview of changes (dry run - not writing to file):

gp.small:
  Match: small-2gb (2 cores, 2.0 GB)
  Price: $12.00/month
  Storage: $0.10/GB/month
```

### 3.2 Update Pricing Data

If the dry run looks good, apply the changes:

```bash
python3 update.py yourprovider
```

This will:
1. Fetch current pricing from the provider API
2. Match instances to OpenStack flavors
3. Update `pricing.csv` with new pricing data

### 3.3 Verify Changes

Check that `pricing.csv` was updated:

```bash
# Show your provider's entries
grep "^yourprovider," pricing.csv
```

### 3.4 Test Cost Comparison

Test the cost comparison feature:

```bash
# Compare with your provider
python3 estimate.py --cloud software --comparison yourprovider

# Include in "cheapest" comparison
python3 estimate.py --cloud software --comparison cheapest
```

## Advanced Topics

### Custom Matching Logic

The default matcher in `providers/matcher.py` finds the cheapest instance that meets or exceeds the OpenStack flavor requirements. To customize matching for your provider:

1. Modify `providers/matcher.py`
2. Add provider-specific logic in `find_matches()`
3. Consider factors like:
   - Regional pricing differences
   - Special instance types (burstable, spot, etc.)
   - Minimum instance sizes
   - GPU-specific matching

### Hourly to Monthly Conversion

If your API returns hourly prices, convert to monthly:

```python
hourly_price = instance.get("price_hourly")
monthly_price = hourly_price * 730  # 730 hours per month average
```

### Rate Limiting and Caching

If the API has rate limits:

```python
import time

def fetch_yourprovider_pricing() -> Dict[str, Dict]:
    """Fetch pricing with rate limiting."""
    pricing_data = {}
    
    for region in ["us-east", "us-west", "eu"]:
        # Fetch pricing per region
        response = requests.get(f"https://api.yourprovider.com/{region}/pricing")
        data = response.json()
        
        # Parse data...
        
        # Rate limit: wait between requests
        time.sleep(1)
    
    return pricing_data
```

### Error Handling

Implement robust error handling:

```python
def fetch_yourprovider_pricing() -> Dict[str, Dict]:
    """Fetch pricing with comprehensive error handling."""
    print(f"[YourProvider] Fetching pricing...")
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
    except requests.exceptions.Timeout:
        print(f"      ✗ Request timed out")
        return {}
        
    except requests.exceptions.HTTPError as e:
        print(f"      ✗ HTTP error: {e.response.status_code}")
        return {}
        
    except requests.exceptions.RequestException as e:
        print(f"      ✗ Request failed: {e}")
        return {}
        
    except json.JSONDecodeError:
        print(f"      ✗ Invalid JSON response")
        return {}
        
    except Exception as e:
        print(f"      ✗ Unexpected error: {e}")
        return {}
```

## Testing Checklist

Before submitting your provider implementation:

- [ ] Fetcher returns correct data structure
- [ ] All required fields present (cores, memory_gb, price)
- [ ] GPU information included (if applicable)
- [ ] Storage pricing function implemented
- [ ] Dry run completes without errors
- [ ] Pricing data successfully written to CSV
- [ ] Cost comparison works with `--comparison yourprovider`
- [ ] Provider included in `--comparison cheapest`
- [ ] Error handling works (test with network disconnect)
- [ ] Documentation updated (if needed)

## Common Issues

### Issue: No instances matched

**Cause**: OpenStack flavors might be larger than provider instances

**Solution**: 
- Check OpenStack flavor requirements in `pricing.csv`
- Ensure provider has instances large enough to match
- Consider adding smaller OpenStack flavors

### Issue: Prices seem wrong

**Cause**: Incorrect unit conversion or API response parsing

**Solution**:
- Verify hourly vs monthly pricing
- Check MB vs GB for memory
- Confirm currency (USD expected)
- Add debug prints to inspect raw API responses

### Issue: Import errors

**Cause**: Provider not properly registered

**Solution**:
- Verify `providers/__init__.py` includes your functions
- Check `update.py` imports
- Ensure no syntax errors in provider module

## Additional Resources

- **Existing Providers**: Reference `providers/linode.py`, `providers/aws.py` for examples
- **Matcher Logic**: See `providers/matcher.py` for flavor matching algorithm
- **Pricing Schema**: Check `pricing.csv` header for required columns
- **CLAUDE.md**: Comprehensive developer documentation

## Questions?

For additional help:
1. Review existing provider implementations in `providers/`
2. Check CLAUDE.md for architecture details
3. Test with `--dry-run` before making changes
4. Contact the development team

---

**Last Updated**: November 2025
