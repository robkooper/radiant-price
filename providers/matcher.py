"""
Match OpenStack flavors to cloud provider instances.

Finds the cheapest instance for each OpenStack flavor that meets or exceeds
its resource requirements (cores and memory).
"""

import csv
from typing import Dict, Tuple


def get_gpu_tier(gpu_name: str) -> int:
    """
    Get the tier/rank of a GPU for comparison.

    Higher numbers = better/newer GPUs.
    Returns 0 for no GPU or unknown GPU types.

    Args:
        gpu_name: GPU type string (e.g., "a100", "h100", "v100")

    Returns:
        Integer tier (0 = no GPU/unknown, higher = better)
    """
    gpu_lower = gpu_name.lower().strip()

    # GPU hierarchy (approximate performance/generation ordering)
    gpu_tiers = {
        # NVIDIA Data Center GPUs (newest to oldest)
        "h200": 1000,  # Hopper generation - H200
        "h100": 900,  # Hopper generation - H100
        "a100": 800,  # Ampere generation - A100 (80GB or 40GB)
        "a40": 700,  # Ampere generation - A40
        "a30": 650,  # Ampere generation - A30
        "a10": 600,  # Ampere generation - A10G
        "v100": 500,  # Volta generation - V100
        "p100": 400,  # Pascal generation - P100
        "t4": 300,  # Turing generation - T4 (inference focused)
        "k80": 200,  # Kepler generation - K80 (old)
        # AMD GPUs (generally lower tier for ML/AI workloads)
        "mi300": 850,  # AMD MI300 series (competitive with H100)
        "mi250": 750,  # AMD MI250 series (competitive with A100)
        "mi210": 700,  # AMD MI210
        "mi100": 650,  # AMD MI100
        "radeon": 100,  # Generic AMD Radeon (consumer/pro viz, not datacenter)
    }

    # Check for exact matches or substring matches
    for gpu_key, tier in gpu_tiers.items():
        if gpu_key in gpu_lower:
            return tier

    return 0  # Unknown or no GPU


def load_openstack_flavors(csv_file: str) -> Dict[str, Dict]:
    """
    Load OpenStack flavors from CSV.

    Args:
        csv_file: Path to pricing.csv

    Returns:
        Dict mapping flavor name to {cores, memory_gb, gpu, gpu_type}
    """
    flavors = {}

    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Cloud"].strip().lower() != "openstack":
                    continue

                flavor = row["Flavor"].strip()
                if not flavor or flavor == "flash":
                    continue

                try:
                    cores = int(row["Cores"].strip() or 0)
                    memory_gb = float(row["Memory_GB"].strip() or 0)
                    gpu = row.get("GPU", "").strip().lower()
                    # Normalize GPU field: "none" or empty = no GPU
                    has_gpu = gpu not in ("", "none")

                    if cores > 0 and memory_gb > 0:
                        flavors[flavor] = {
                            "cores": cores,
                            "memory_gb": memory_gb,
                            "gpu": has_gpu,
                            "gpu_type": gpu if has_gpu else "",
                        }
                except (ValueError, KeyError):
                    continue

        return flavors

    except FileNotFoundError:
        print(f"Error: {csv_file} not found")
        return {}


def extract_gpu_from_instance_name(instance_name: str) -> str:
    """
    Extract GPU type from instance name.

    Args:
        instance_name: Instance type name (e.g., "p4d.24xlarge", "Standard_NC96ads_A100_v4")

    Returns:
        GPU type string or empty string if no GPU detected
    """
    instance_lower = instance_name.lower()

    # Common GPU instance patterns
    # AWS: p4d/p4de (A100), p3 (V100), g5 (A10G), g4dn (T4), g4ad (AMD Radeon)
    # Azure: NC*_A100, NC*_V100, ND*_A100, ND*_H100, etc.
    # GCP: a2-* (A100), g2-* (L4), n1-*-gpu (various)

    # Check for explicit GPU mentions in name
    gpu_patterns = [
        "h200",
        "h100",  # Hopper
        "a100",
        "a40",
        "a30",
        "a10",  # Ampere
        "v100",  # Volta
        "p100",  # Pascal
        "t4",  # Turing
        "k80",  # Kepler
        "mi300",
        "mi250",
        "mi210",
        "mi100",  # AMD MI series
        "radeon",  # AMD Radeon
    ]

    for gpu in gpu_patterns:
        if gpu in instance_lower:
            return gpu

    # AWS instance family patterns (when GPU not in name)
    if instance_lower.startswith("p4d") or instance_lower.startswith("p4de"):
        return "a100"
    elif instance_lower.startswith("p3"):
        return "v100"
    elif instance_lower.startswith("g5"):
        return "a10"
    elif instance_lower.startswith("g4dn"):
        return "t4"
    elif instance_lower.startswith("g4ad"):
        return "radeon"  # AMD Radeon Pro V520
    elif instance_lower.startswith("p2"):
        return "k80"

    # GCP patterns
    elif instance_lower.startswith("a2-"):
        return "a100"
    elif instance_lower.startswith("g2-"):
        return "l4"  # L4 is similar tier to T4

    return ""


def find_matches(
    openstack_flavors: Dict[str, Dict],
    provider_pricing: Dict[str, Dict],
) -> Dict[str, Tuple[str, float, int, float]]:
    """
    Find cheapest instance matching each OpenStack flavor.

    Respects GPU requirements: GPU flavors only match GPU instances of equal or better tier.
    CPU flavors only match CPU instances.

    Args:
        openstack_flavors: Dict of {cores, memory_gb, gpu, gpu_type} by flavor name
        provider_pricing: Dict of pricing data by instance type

    Returns:
        Dict mapping OpenStack flavor to (instance_type, price, cores, memory) tuple
        or None if no match found
    """
    matches = {}

    for os_flavor, flavor_specs in openstack_flavors.items():
        req_cores = flavor_specs["cores"]
        req_memory = flavor_specs["memory_gb"]
        req_gpu = flavor_specs["gpu"]
        req_gpu_type = flavor_specs.get("gpu_type", "")

        candidates = []

        for instance_type, specs in provider_pricing.items():
            if instance_type == "flash":
                continue

            cores = specs.get("cores", 0)
            memory = specs.get("memory_gb", 0)
            price = specs.get("price", float("inf"))

            # Get GPU information from provider data or instance name
            gpu_count = specs.get("gpu_count", 0)
            gpu_model = specs.get("gpu_model", "")

            # Extract GPU type from model or instance name
            if gpu_model:
                instance_gpu = gpu_model.lower()
            else:
                instance_gpu = extract_gpu_from_instance_name(instance_type)

            has_gpu = bool(instance_gpu) or gpu_count > 0

            # GPU requirement matching:
            # - CPU flavors should only match CPU instances
            if not req_gpu and has_gpu:
                continue

            # - GPU flavors should only match GPU instances
            if req_gpu and not has_gpu:
                continue

            # - GPU flavors should only match equal or better GPU tier
            if req_gpu and has_gpu:
                req_tier = get_gpu_tier(req_gpu_type)
                instance_tier = get_gpu_tier(instance_gpu)

                # Instance GPU must be >= required GPU tier
                # (equal or better GPU)
                if instance_tier < req_tier:
                    continue

                # Adjust price if instance has multiple GPUs
                # Divide price by GPU count to get per-GPU pricing
                if gpu_count > 1:
                    price = price / gpu_count

            # Must meet or exceed requirements
            if cores >= req_cores and memory >= req_memory:
                candidates.append((instance_type, price, cores, memory))

        if candidates:
            # Choose cheapest
            cheapest = min(candidates, key=lambda x: x[1])
            matches[os_flavor] = cheapest

    return matches


def get_existing_matches(csv_file: str, provider: str) -> Dict[str, Dict[str, str]]:
    """
    Load existing matches for a provider from CSV.

    Args:
        csv_file: Path to pricing.csv
        provider: Cloud provider name (e.g., 'aws', 'gcp')

    Returns:
        Dict mapping OpenStack flavor to {flavor, price, cores, memory}
    """
    existing = {}

    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Cloud"].strip().lower() != provider.lower():
                    continue

                os_flavor = row.get("Matched_OpenStack_Flavor", "").strip()
                if not os_flavor:
                    continue

                existing[os_flavor] = {
                    "flavor": row["Flavor"].strip(),
                    "price": row.get("Compute_Price_Per_Month", "0"),
                    "cores": row.get("Cores", "0"),
                    "memory": row.get("Memory_GB", "0"),
                }
    except (FileNotFoundError, KeyError):
        pass

    return existing


def update_csv_with_matches(
    csv_file: str,
    provider: str,
    matches: Dict[str, Tuple[str, float, int, float]],
    provider_pricing: Dict[str, Dict],
    storage_price: float,
    dry_run: bool = False,
) -> Tuple[int, list]:
    """
    Update CSV with matched instances for a provider.

    Args:
        csv_file: Path to pricing.csv
        provider: Cloud provider name (e.g., 'aws', 'gcp')
        matches: Dict of matches from find_matches()
        provider_pricing: Original provider pricing dict
        storage_price: Storage price per GB per month
        dry_run: If True, don't write file

    Returns:
        Tuple of (number added/changed, list of changes)
    """

    rows = []
    fieldnames = []

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        rows = list(reader)

    # Ensure Matched_OpenStack_Flavor column exists
    if "Matched_OpenStack_Flavor" not in fieldnames:
        idx = fieldnames.index("Flavor") + 1
        fieldnames.insert(idx, "Matched_OpenStack_Flavor")

    # Get existing matches to detect changes
    existing = get_existing_matches(csv_file, provider)

    # Keep non-provider rows and provider's flash storage
    rows_to_keep = []
    for row in rows:
        cloud = row["Cloud"].strip().lower()
        flavor = row["Flavor"].strip()

        if cloud != provider.lower():
            # Keep other providers and OpenStack
            rows_to_keep.append(row)
        elif flavor == "flash":
            # Keep flash storage row
            rows_to_keep.append(row)

    # Add matched instances and detect changes
    added = 0
    changes = []
    for os_flavor in sorted(matches.keys()):
        instance_type, price, cores, memory = matches[os_flavor]

        new_row = {field: "" for field in fieldnames}
        new_row["Cloud"] = provider
        new_row["Flavor"] = instance_type
        new_row["Matched_OpenStack_Flavor"] = os_flavor
        new_row["Cores"] = str(int(cores))
        new_row["Memory_GB"] = str(float(memory))
        new_row["Compute_Price_Per_Month"] = f"{price:.2f}"
        new_row["GPU"] = "none"
        new_row["Storage_Price_Per_GB_Per_Month"] = f"{storage_price:.2f}"

        # Build description with GPU info if applicable
        description = f"{provider.upper()} {instance_type} (matched to {os_flavor})"
        new_row["Description"] = description

        # Add instance details to Notes if available
        notes_parts = []

        if instance_type in provider_pricing:
            specs = provider_pricing[instance_type]

            # Add existing details
            if "details" in specs and specs["details"]:
                notes_parts.append(specs["details"])

            # Add GPU information if present
            gpu_count = specs.get("gpu_count", 0)
            gpu_model = specs.get("gpu_model", "")

            if gpu_count > 1 and gpu_model:
                notes_parts.append(
                    f"{gpu_count}x {gpu_model} (price divided by {gpu_count} for single GPU)"
                )
            elif gpu_count == 1 and gpu_model:
                notes_parts.append(f"1x {gpu_model}")

        if notes_parts:
            new_row["Notes"] = ", ".join(notes_parts)

        rows_to_keep.append(new_row)

        # Check if this is a change
        if os_flavor in existing:
            old = existing[os_flavor]
            if old["flavor"] != instance_type or old["price"] != f"{price:.2f}":
                changes.append(
                    {
                        "flavor": os_flavor,
                        "old_instance": old["flavor"],
                        "new_instance": instance_type,
                        "old_price": float(old["price"]),
                        "new_price": price,
                    }
                )
        else:
            changes.append(
                {
                    "flavor": os_flavor,
                    "old_instance": None,
                    "new_instance": instance_type,
                    "old_price": None,
                    "new_price": price,
                }
            )

        added += 1

    if not dry_run:
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_to_keep)

    return added, changes
