"""Microsoft Azure pricing fetcher."""

import json
from typing import Dict

import requests


def get_azure_flavor_prices(region: str = "us-east") -> Dict[str, Dict]:
    """
    Fetch Azure Virtual Machines pricing from Azure API.

    Args:
        region: Azure region (default: us-east)

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[Azure] Fetching Virtual Machines pricing...")

    try:
        url = f"https://azure.microsoft.com/api/v4/pricing/virtual-machines/calculator/{region}/"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        data = response.json()
        offers = data.get("offers", {})
        pricing_data = {}
        count_skipped = 0

        for offer_id, offer_data in offers.items():
            # Skip hidden offers
            if offer_data.get("isHidden", False):
                count_skipped += 1
                continue

            cores = offer_data.get("cores", 0)
            memory = offer_data.get("ram", 0)

            # Get hourly price
            prices = offer_data.get("prices", {})
            perhour = prices.get("perhour", {})
            hourly_price = perhour.get(region, {}).get("value", 0)

            if cores > 0 and hourly_price > 0:
                # Convert hourly to monthly
                monthly_price = hourly_price * 730

                # Extract GPU information from 'gpu' field (e.g., "1X H100", "4X A100")
                gpu_field = offer_data.get("gpu", "")
                gpu_count = 0
                gpu_model = ""
                gpu_memory = 0

                if gpu_field and isinstance(gpu_field, str):
                    gpu_field_lower = gpu_field.lower()
                    # Parse format like "1X H100" or "4X A100"
                    import re

                    match = re.match(r"(\d+)x?\s*(.+)", gpu_field_lower.strip())
                    if match:
                        gpu_count = int(match.group(1))
                        gpu_type = match.group(2).strip()

                        # Identify GPU model and memory per GPU
                        if "h100" in gpu_type:
                            gpu_model = "NVIDIA H100"
                            gpu_memory = 80 * gpu_count
                        elif "a100" in gpu_type:
                            gpu_model = "NVIDIA A100"
                            gpu_memory = 80 * gpu_count
                        elif "v100" in gpu_type:
                            gpu_model = "NVIDIA V100"
                            gpu_memory = 16 * gpu_count
                        elif "t4" in gpu_type:
                            gpu_model = "NVIDIA T4"
                            gpu_memory = 16 * gpu_count
                        else:
                            gpu_model = gpu_field  # Use original string

                # Fallback: check offer_id for GPU hints if gpu field is empty
                if not gpu_count:
                    if "h100" in offer_id.lower():
                        gpu_count = (
                            1  # Assume 1 if we can detect GPU type but not count
                        )
                        gpu_model = "NVIDIA H100"
                        gpu_memory = 80
                    elif "a100" in offer_id.lower():
                        gpu_count = 1
                        gpu_model = "NVIDIA A100"
                        gpu_memory = 80

                pricing_data[offer_id] = {
                    "cores": cores,
                    "memory_gb": memory if memory > 0 else 1,
                    "price": round(monthly_price, 2),
                    "gpu_count": gpu_count,
                    "gpu_model": gpu_model,
                    "gpu_memory": gpu_memory,
                }

        print(f"      ✓ Fetched {len(pricing_data)} Azure VM types")
        if count_skipped > 0:
            print(f"        (skipped {count_skipped} hidden offers)")

        return pricing_data

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}


def get_azure_storage_prices(region: str = "us-east") -> Dict[str, float]:
    """
    Get Azure Managed Disks storage pricing.

    Currently returns hardcoded pricing for Standard SSD (E-series).
    For dynamic pricing, would need to scrape Azure pricing calculator.

    Args:
        region: Azure region (default: us-east)

    Returns:
        Dict with storage prices per GB per month, e.g., {"flash": 0.05}
    """
    # Azure Managed Disks pricing (as of 2024):
    # Standard HDD: ~$0.04/GB/month
    # Standard SSD: ~$0.05/GB/month
    # Premium SSD: ~$0.13/GB/month
    # Using Standard SSD as baseline
    return {"flash": 0.05}
