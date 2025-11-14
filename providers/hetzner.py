"""Hetzner Cloud pricing fetcher."""

import re
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

# Hetzner instance specs and expected price ranges for validation
HETZNER_SPECS = {
    # CX series (Intel/AMD general purpose)
    "cx11": {"cores": 1, "memory": 1, "price_min": 0.5, "price_max": 2},
    "cx21": {"cores": 2, "memory": 4, "price_min": 3, "price_max": 6},
    "cx31": {"cores": 2, "memory": 8, "price_min": 6, "price_max": 10},
    "cx41": {"cores": 4, "memory": 16, "price_min": 12, "price_max": 18},
    "cx51": {"cores": 8, "memory": 32, "price_min": 24, "price_max": 35},
    # CX2x series (newer Intel)
    "cx23": {"cores": 2, "memory": 4, "price_min": 0.5, "price_max": 2},
    "cx33": {"cores": 4, "memory": 8, "price_min": 3, "price_max": 6},
    "cx43": {"cores": 8, "memory": 16, "price_min": 6, "price_max": 12},
    "cx53": {"cores": 16, "memory": 32, "price_min": 18, "price_max": 25},
    # CCX series (AMD Ryzen)
    "ccx11": {"cores": 2, "memory": 8, "price_min": 3, "price_max": 8},
    "ccx13": {"cores": 4, "memory": 16, "price_min": 12, "price_max": 18},
    "ccx23": {"cores": 8, "memory": 32, "price_min": 26, "price_max": 35},
    "ccx33": {"cores": 16, "memory": 64, "price_min": 50, "price_max": 70},
    "ccx43": {"cores": 32, "memory": 128, "price_min": 100, "price_max": 150},
    "ccx53": {"cores": 48, "memory": 192, "price_min": 200, "price_max": 250},
    "ccx63": {"cores": 64, "memory": 256, "price_min": 300, "price_max": 400},
    # CAX series (ARM - Ampere)
    "cax11": {"cores": 2, "memory": 4, "price_min": 3, "price_max": 8},
    "cax21": {"cores": 4, "memory": 8, "price_min": 6, "price_max": 12},
    "cax31": {"cores": 8, "memory": 16, "price_min": 12, "price_max": 20},
    "cax41": {"cores": 16, "memory": 32, "price_min": 25, "price_max": 35},
}


def fetch_hetzner_pricing() -> Dict[str, Dict]:
    """
    Fetch Hetzner Cloud pricing from their website.

    Scrapes https://www.hetzner.com/cloud to extract monthly pricing in USD.
    Uses heuristics to identify monthly prices based on value ranges.

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[Hetzner] Fetching Cloud pricing from website...")

    try:
        url = "https://www.hetzner.com/cloud"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        pricing_data = {}

        # Find the pricing table
        pricing_table = soup.find("div", class_=lambda x: x and "cloudservertable" in x)

        if not pricing_table:
            print(f"      ✗ Could not find pricing table")
            return {}

        # Extract all price containers and their values
        price_containers = pricing_table.find_all("price-container")
        prices = []

        for pc in price_containers:
            usd_span = pc.find("span", {"slot": "usd"})
            if usd_span:
                try:
                    price_text = usd_span.get_text(strip=True).lstrip("$")
                    price = float(price_text)
                    prices.append(price)
                except ValueError:
                    pass

        if not prices:
            print(f"      ✗ No prices found")
            return {}

        # Instance pattern
        instance_pattern = re.compile(r"(cx|ccx|cax)(\d{2})", re.IGNORECASE)

        # Find all instance names in the table text, in order
        table_text = pricing_table.get_text()
        instances_found = []
        for match in instance_pattern.finditer(table_text):
            instance_name = (match.group(1) + match.group(2)).lower()
            if instance_name not in [i[0] for i in instances_found]:
                instances_found.append((instance_name, match.start()))

        # Sort by position
        instances_found.sort(key=lambda x: x[1])
        instance_names = [i[0] for i in instances_found]

        # Match instances to prices
        # Each instance appears multiple times (monthly EU price, monthly US price, hourly, etc.)
        # The pattern seems to be: monthly price appears around every 4-8 prices
        # Find prices that match expected ranges for each instance
        for instance_name in instance_names:
            if instance_name not in HETZNER_SPECS:
                continue

            specs = HETZNER_SPECS[instance_name]
            price_min = specs["price_min"]
            price_max = specs["price_max"]

            # Find the first price in the range for this instance
            # We need to search through prices sequentially
            for price in prices:
                if (
                    price_min <= price <= price_max
                    and instance_name not in pricing_data
                ):
                    pricing_data[instance_name] = {
                        "cores": specs["cores"],
                        "memory_gb": specs["memory"],
                        "price": round(price, 2),
                        "gpu_count": 0,
                        "gpu_model": "",
                        "gpu_memory": 0,
                    }
                    break

        if pricing_data:
            print(f"      ✓ Fetched {len(pricing_data)} Hetzner Cloud instances")
            return pricing_data
        else:
            print(f"      ✗ No matching prices found for instances")
            return {}

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}
