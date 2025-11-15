"""Vultr Cloud pricing fetcher."""

import re
from typing import Dict

import requests
from bs4 import BeautifulSoup


def fetch_vultr_pricing() -> Dict[str, Dict]:
    """
    Fetch Vultr Cloud Compute pricing from their website.

    Scrapes https://www.vultr.com/pricing/ to get current pricing.

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[Vultr] Fetching Cloud Compute pricing from website...")

    try:
        url = "https://www.vultr.com/pricing/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        pricing_data = {}
        seen_configs = set()  # Track unique vCPU/memory combinations

        # Find all pricing rows
        rows = soup.find_all("div", class_="pt__row")

        for row in rows:
            try:
                cells = row.find_all("div", class_="pt__cell")
                if len(cells) < 5:
                    continue

                # Extract vCPU count from first cell
                vcpu_text = cells[0].get_text(strip=True)
                vcpu_match = re.search(r"(\d+)\s*vCPU", vcpu_text)
                if not vcpu_match:
                    continue
                cores = int(vcpu_match.group(1))

                # Extract memory from second cell
                memory_text = cells[1].get_text(strip=True)
                memory_match = re.search(r"(\d+)\s*GB", memory_text)
                if not memory_match:
                    continue
                memory_gb = int(memory_match.group(1))

                # Extract price from price cell (last cell)
                price_text = cells[-1].get_text(strip=True)
                price_match = re.search(r"\$(\d+\.?\d*)\s*/hr", price_text)
                if not price_match:
                    continue
                hourly_price = float(price_match.group(1))
                monthly_price = hourly_price * 730  # Convert hourly to monthly

                # Create instance name from specs (avoid duplicates)
                config_key = (cores, memory_gb)
                if config_key in seen_configs:
                    continue
                seen_configs.add(config_key)

                instance_name = f"vultr-{cores}c-{memory_gb}gb"

                pricing_data[instance_name] = {
                    "cores": cores,
                    "memory_gb": memory_gb,
                    "price": round(monthly_price, 2),
                    "gpu_count": 0,
                    "gpu_model": "",
                    "gpu_memory": 0,
                }

            except (IndexError, AttributeError, ValueError):
                continue

        if pricing_data:
            print(f"      ✓ Fetched {len(pricing_data)} Vultr instances")
            return pricing_data
        else:
            print(f"      ⚠ No pricing data found, trying API fallback...")
            return _fetch_vultr_api()

    except Exception as e:
        print(f"      ✗ Error: {e}, trying API fallback...")
        return _fetch_vultr_api()


def _fetch_vultr_api() -> Dict[str, Dict]:
    """Fallback: Fetch from Vultr API if web scraping fails."""
    try:
        # Try the updated API endpoint
        url = "https://api.vultr.com/v2/products/compute"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        data = response.json()
        pricing_data = {}

        for compute in data.get("products", []):
            compute_id = compute.get("id")
            monthly_cost = compute.get("monthly_cost", 0)
            vcpu_count = compute.get("cpu_count", 0)
            ram_mb = compute.get("ram", 0)
            label = compute.get("label", "")

            # Extract GPU information from label
            gpu_count = 0
            gpu_model = ""
            gpu_memory = 0
            label_lower = label.lower()

            if "gpu" in label_lower:
                # Try to extract GPU info from label
                if "a100" in label_lower:
                    gpu_model = "NVIDIA A100"
                    gpu_count = 1
                    gpu_memory = 80
                elif "rtx" in label_lower:
                    gpu_model = "NVIDIA RTX"
                    gpu_count = 1
                    gpu_memory = 24

            if compute_id and monthly_cost > 0 and vcpu_count:
                pricing_data[compute_id] = {
                    "cores": vcpu_count,
                    "memory_gb": ram_mb / 1024 if ram_mb else 0,
                    "price": round(float(monthly_cost), 2),
                    "gpu_count": gpu_count,
                    "gpu_model": gpu_model,
                    "gpu_memory": gpu_memory,
                }

        if pricing_data:
            print(f"      ✓ Fetched {len(pricing_data)} Vultr instances from API")
        return pricing_data

    except Exception as e:
        print(f"      ✗ API fallback failed: {e}")
        return {}


def get_vultr_storage_price() -> float:
    """
    Fetch Vultr Block Storage pricing.

    Dynamically extracts the per-GB monthly cost for Block Storage volumes
    from the pricing page.

    Returns:
        Storage price per GB per month (e.g., 0.05), or 0.05 as fallback
    """
    try:
        import re

        import requests
        from bs4 import BeautifulSoup

        url = "https://www.vultr.com/pricing/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Look for block storage pricing like "$0.05 per GB"
        storage_pattern = (
            r"block\s+storage.*?\$(\d+\.\d+)(?:\s*per\s*|\s*\/\s*)(?:GB|gb)"
        )
        matches = re.findall(storage_pattern, page_text, re.IGNORECASE | re.DOTALL)

        if matches:
            price = float(matches[0])
            if 0.01 <= price <= 1.0:  # Sanity check
                return price

    except Exception:
        pass

    # Fallback to known pricing
    return 0.05
