"""DigitalOcean pricing fetcher."""

import json
from typing import Dict

import requests
from bs4 import BeautifulSoup


def fetch_digitalocean_pricing() -> Dict[str, Dict]:
    """
    Fetch DigitalOcean Droplet pricing from pricing calculator page.

    Extracts pricing data directly from the __NEXT_DATA__ script in the
    pricing calculator page, which contains all the pricing information.
    This approach is independent of any buildId or API endpoint changes.

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[DigitalOcean] Fetching Droplet pricing from calculator...")

    try:
        # Fetch the pricing calculator page
        pricing_page_url = "https://www.digitalocean.com/pricing/calculator"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(pricing_page_url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Extract pricing data from __NEXT_DATA__ script
        next_data_script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not next_data_script:
            print(f"      ✗ Could not find pricing data")
            return {}

        try:
            next_data = json.loads(next_data_script.string)
        except (json.JSONDecodeError, AttributeError):
            print(f"      ✗ Could not parse pricing data")
            return {}

        # Extract products data from the script
        products_data = (
            next_data.get("props", {}).get("pageProps", {}).get("productsData", {})
        )

        if not products_data:
            print(f"      ✗ No products data found")
            return {}

        pricing_data = {}

        # Process regular droplets (nested structure: categories -> regular -> instances)
        droplets = products_data.get("droplets", {})
        if isinstance(droplets, dict):
            for category_name, category_data in droplets.items():
                # Each category has "regular", "dedicated", etc.
                if isinstance(category_data, dict):
                    for plan_type, instances in category_data.items():
                        if not isinstance(instances, list):
                            continue

                        for instance in instances:
                            slug = instance.get("slug")
                            memory = instance.get("memory", 0)
                            cpus = instance.get("cpus", 0)
                            price_data = instance.get("price", {})
                            monthly_price = price_data.get("monthly", 0)

                            # Skip if no valid pricing or specs
                            if not slug or monthly_price <= 0 or cpus == 0:
                                continue

                            pricing_data[slug] = {
                                "cores": cpus,
                                "memory_gb": memory,
                                "price": round(monthly_price, 2),
                                "gpu_count": 0,
                                "gpu_model": "",
                                "gpu_memory": 0,
                            }

        # Process GPU droplets (similar structure)
        gpu_droplets = products_data.get("gpuDroplets", {})
        if isinstance(gpu_droplets, dict):
            for category_name, category_data in gpu_droplets.items():
                if isinstance(category_data, dict):
                    for plan_type, instances in category_data.items():
                        if not isinstance(instances, list):
                            continue

                        for instance in instances:
                            slug = instance.get("slug")
                            memory = instance.get("memory", 0)
                            cpus = instance.get("cpus", 0)
                            price_data = instance.get("price", {})
                            monthly_price = price_data.get("monthly", 0)

                            # Skip if no valid pricing or specs
                            if not slug or monthly_price <= 0 or cpus == 0:
                                continue

                            # Extract GPU information from slug
                            gpu_count = 0
                            gpu_model = ""
                            gpu_memory = 0
                            slug_lower = slug.lower()

                            if "gpu" in slug_lower or "g5" in slug_lower:
                                # Try to extract GPU info from slug/name
                                if "a100" in slug_lower:
                                    gpu_model = "NVIDIA A100"
                                    gpu_count = 1
                                    gpu_memory = 80
                                elif "h100" in slug_lower:
                                    gpu_model = "NVIDIA H100"
                                    gpu_count = 1
                                    gpu_memory = 80
                                else:
                                    gpu_model = "GPU"
                                    gpu_count = 1
                                    gpu_memory = 0

                            pricing_data[slug] = {
                                "cores": cpus,
                                "memory_gb": memory,
                                "price": round(monthly_price, 2),
                                "gpu_count": gpu_count,
                                "gpu_model": gpu_model,
                                "gpu_memory": gpu_memory,
                            }

        if pricing_data:
            print(f"      ✓ Fetched {len(pricing_data)} DigitalOcean Droplets")
            return pricing_data
        else:
            print(f"      ✗ No pricing data found in calculator")
            return {}

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}
