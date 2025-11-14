"""AWS EC2 pricing fetcher (x86_64 Linux only)."""

import json
from typing import Dict

import requests


def fetch_aws_pricing(region: str = "us-east-1") -> Dict[str, Dict]:
    """
    Fetch AWS EC2 pricing from ec2instances.info.

    Filters for x86_64 Linux instances only.

    Args:
        region: AWS region (default: us-east-1)

    Returns:
        Dict of {instance_type: {cores, memory_gb, price, details}}
    """
    print(f"[AWS] Fetching EC2 pricing...")

    try:
        url = "https://ec2instances.info/instances.json"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        instances_list = response.json()
        pricing_data = {}
        count_x86 = 0
        count_no_pricing = 0

        for instance in instances_list:
            instance_type = instance.get("instance_type")

            # arch is now a list like ['x86_64'] or ['arm64']
            arch = instance.get("arch", [])
            if not isinstance(arch, list):
                arch = [arch] if arch else []

            # Filter: x86_64 only (skip ARM, etc)
            if "x86_64" not in arch:
                continue

            count_x86 += 1

            # Get pricing for the region
            pricing = instance.get("pricing", {})
            price_str = None

            # Try us-east-1 first
            if "us-east-1" in pricing and isinstance(pricing["us-east-1"], dict):
                region_data = pricing["us-east-1"]
                if "linux" in region_data:
                    price_str = region_data["linux"].get("ondemand")
                elif "ondemand" in region_data:
                    price_str = region_data.get("ondemand")
                elif "dedicated" in region_data:
                    price_str = region_data["dedicated"].get("ondemand")

            # Try any region if not found
            if not price_str:
                for region_key, region_data in pricing.items():
                    if isinstance(region_data, dict):
                        if "linux" in region_data:
                            price_str = region_data["linux"].get("ondemand")
                        elif "ondemand" in region_data:
                            price_str = region_data.get("ondemand")
                        elif "dedicated" in region_data:
                            price_str = region_data["dedicated"].get("ondemand")
                        if price_str:
                            break

            if not price_str:
                count_no_pricing += 1
                continue

            try:
                price_per_hour = float(price_str)
                price_per_month = price_per_hour * 730

                vcpu = instance.get("vCPU")
                memory = instance.get("memory")

                if vcpu is None or memory is None:
                    continue

                vcpu = int(vcpu) if vcpu else 0
                memory = float(memory) if memory else 0

                if vcpu > 0 and memory > 0:
                    # Extract details for Notes column
                    details = []

                    family = instance.get("family", "")
                    if family:
                        details.append(family)

                    processor = instance.get("physical_processor", "")
                    if processor:
                        processor = processor.replace("Intel Xeon ", "Xeon ")
                        processor = processor.replace("AMD EPYC ", "EPYC ")
                        details.append(processor)

                    network = instance.get("network_performance", "")
                    if network:
                        details.append(network)

                    base_perf = instance.get("base_performance")
                    if base_perf is not None and base_perf < 1:
                        burst_mins = instance.get("burst_minutes", 0)
                        if burst_mins:
                            details.append(f"Burstable ({burst_mins}min)")
                        else:
                            details.append("Burstable")

                    notes = ", ".join(details) if details else ""

                    # GPU information
                    gpu_count = instance.get("GPU", 0)
                    gpu_model = instance.get("GPU_model", "")
                    gpu_memory = instance.get("GPU_memory", 0)

                    pricing_data[instance_type] = {
                        "cores": vcpu,
                        "memory_gb": memory,
                        "price": round(price_per_month, 2),
                        "details": notes,
                        "gpu_count": gpu_count,
                        "gpu_model": gpu_model,
                        "gpu_memory": gpu_memory,
                    }
            except (ValueError, TypeError):
                continue

        print(f"      ✓ Fetched {len(pricing_data)} x86_64 Linux instances")
        return pricing_data

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}
