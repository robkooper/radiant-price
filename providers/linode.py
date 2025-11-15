"""Linode Cloud pricing fetcher."""

import json
from typing import Dict

import requests


def fetch_linode_pricing() -> Dict[str, Dict]:
    """
    Fetch Linode Cloud pricing from their API.

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[Linode] Fetching Cloud pricing...")

    try:
        url = "https://api.linode.com/v4/linode/types"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        data = response.json()
        pricing_data = {}

        for instance in data.get("data", []):
            type_id = instance.get("id")
            label = instance.get("label", "")
            price = instance.get("price", {}).get("monthly", 0)
            vcpus = instance.get("vcpus", 0)
            memory = instance.get("memory", 0)
            gpus = instance.get("gpus", 0)

            # Extract GPU model from label if present
            gpu_model = ""
            gpu_memory = 0
            label_lower = label.lower()

            if gpus > 0:
                if "rtx6000" in label_lower:
                    gpu_model = "NVIDIA Quadro RTX 6000"
                    gpu_memory = 24 * gpus
                elif "v100" in label_lower:
                    gpu_model = "NVIDIA V100"
                    gpu_memory = 32 * gpus
                else:
                    gpu_model = "GPU"

            if type_id and price > 0 and vcpus and memory:
                pricing_data[type_id] = {
                    "cores": vcpus,
                    "memory_gb": memory / 1024,  # Convert MB to GB
                    "price": round(price, 2),
                    "gpu_count": gpus,
                    "gpu_model": gpu_model,
                    "gpu_memory": gpu_memory,
                }

        print(f"      ✓ Fetched {len(pricing_data)} Linode instances")

        return pricing_data

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}


def get_linode_storage_price() -> float:
    """
    Fetch Linode Block Storage pricing.

    Dynamically extracts the per-GB monthly cost for Block Storage volumes
    from the pricing page.

    Returns:
        Storage price per GB per month (e.g., 0.10), or 0.10 as fallback
    """
    try:
        import re

        import requests
        from bs4 import BeautifulSoup

        url = "https://www.linode.com/pricing/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Look for block storage pricing like "$0.10 per GB per month"
        storage_pattern = r"block\s+storage.*?\$(\d+\.\d+)\s*(?:per|\/)\s*(?:GB|gb)"
        matches = re.findall(storage_pattern, page_text, re.IGNORECASE | re.DOTALL)

        if matches:
            price = float(matches[0])
            if 0.01 <= price <= 1.0:  # Sanity check
                return price

    except Exception:
        pass

    # Fallback to known pricing ($0.10 per GB per month)
    return 0.10
