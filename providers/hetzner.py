"""Hetzner Cloud pricing fetcher."""

import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup


def extract_spec_from_container(
    container: BeautifulSoup, label_text: str
) -> Optional[float]:
    """
    Extract a numeric spec value from a container row.

    Args:
        container: The cputype-toggle container div
        label_text: The label to search for (e.g., "VCPU", "RAM")

    Returns:
        Float value or None if not found
    """
    # Find all label divs in the container
    labels = container.find_all("div", class_="cloud-table-label")

    for label_div in labels:
        # Check if this label matches
        if label_text.lower() in label_div.get_text(strip=True).lower():
            # Extract the value from the parent row
            row = label_div.parent
            value_span = row.find("span", class_="cloud-table-item")
            if value_span:
                text = value_span.get_text(strip=True)
                # Parse the value (e.g., "2", "4 GB", "40 GB")
                match = re.search(r"(\d+(?:\.\d+)?)", text)
                if match:
                    return float(match.group(1))

    return None


def get_hetzner_storage_price() -> float:
    """
    Fetch Hetzner Block Storage pricing from their website.

    Dynamically extracts the per-GB monthly cost for Block Storage Volumes
    in US locations.

    Returns:
        Storage price per GB per month (e.g., 0.0484), or 0.05 as fallback
    """
    try:
        url = "https://www.hetzner.com/cloud"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Search for text containing storage pricing
        page_text = soup.get_text()

        # Look for Block Storage pricing pattern: "$ X.XXXX GB"
        # Pattern for USD prices in format like "$ 0.0484"
        storage_pattern = r"\$\s*(0\.\d{4})\s*(?:GB|/)"

        matches = re.findall(storage_pattern, page_text)

        if matches:
            # Take the first match (should be the most relevant)
            price = float(matches[0])
            # Validate it's a reasonable storage price (between $0.01 and $0.10 per GB)
            if 0.01 <= price <= 0.10:
                return price

    except Exception:
        pass

    # Fallback to hardcoded value if extraction fails
    return 0.05


def fetch_hetzner_pricing() -> Dict[str, Dict]:
    """
    Fetch Hetzner Cloud pricing from their website.

    Scrapes https://www.hetzner.com/cloud to extract monthly pricing in USD
    for US locations only (Ashburn/Hillsboro).

    Dynamically extracts specs (cores, memory) from the HTML table to ensure
    compatibility with future pricing page updates.

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[Hetzner] Fetching Cloud pricing from website (US locations)...")

    try:
        url = "https://www.hetzner.com/cloud"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        pricing_data = {}

        # Find all server containers (cputype-toggle divs)
        # These containers have data-locations attribute indicating which regions they support
        containers = soup.find_all("div", class_="cputype-toggle")

        if not containers:
            print(f"      ✗ Could not find pricing containers")
            return {}

        # Process each container
        for container in containers:
            # Check if this container has US pricing (data-locations contains "us")
            locations = container.get("data-locations", "")
            if "us" not in locations:
                continue

            # Extract instance name
            instance_span = container.find("span", class_="cloud-table-name")
            if not instance_span:
                continue

            instance_name = instance_span.get_text(strip=True).lower()

            # Extract specs from the HTML (cores and memory)
            cores = extract_spec_from_container(container, "VCPU")
            memory_gb = extract_spec_from_container(container, "RAM")

            if cores is None or memory_gb is None:
                continue

            # Extract monthly price from price-containers
            # Hetzner organizes prices by location in <span data-location="US"> groups
            # There are multiple US groups (hourly vs monthly), we need the monthly one

            monthly_price = None

            # Find all US location price groups
            us_price_groups = container.find_all(
                lambda tag: tag.name == "span"
                and tag.get("data-location") == "US"
                and tag.find("price-container")
            )

            # Try each US group to find monthly pricing
            for us_price_group in us_price_groups:
                # Get price containers from the US group
                price_containers = us_price_group.find_all("price-container")

                # Find the first IPv4 price > 1.0 (monthly price, not hourly)
                for pc in price_containers:
                    classes = pc.get("class", [])
                    if isinstance(classes, str):
                        classes = classes.split()

                    # Only consider IPv4 prices (skip IPv6-only/hidden)
                    if "ipv4" not in classes or "hidden" in classes:
                        continue

                    usd_span = pc.find("span", {"slot": "usd"})
                    if usd_span:
                        try:
                            price_text = usd_span.get_text(strip=True)
                            price = float(price_text)

                            # Monthly prices are typically > 1.0, hourly < 0.2
                            if price > 1.0:
                                monthly_price = price
                                break
                        except ValueError:
                            pass

                # If we found a monthly price, stop looking at other groups
                if monthly_price is not None:
                    break

            if monthly_price is not None:
                pricing_data[instance_name] = {
                    "cores": int(cores),
                    "memory_gb": memory_gb,
                    "price": round(monthly_price, 2),
                    "gpu_count": 0,
                    "gpu_model": "",
                    "gpu_memory": 0,
                }

        if pricing_data:
            print(f"      ✓ Fetched {len(pricing_data)} Hetzner Cloud instances (US)")
            return pricing_data
        else:
            print(f"      ✗ No matching prices found for instances")
            return {}

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}
