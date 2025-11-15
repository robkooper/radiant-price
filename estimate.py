#!/usr/bin/env python3
"""
OpenStack Environment Analyzer

Analyzes OpenStack environments to provide detailed VM, storage, and cost reports
with multi-cloud provider pricing comparisons.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import openstack
from tabulate import tabulate

# =============================================================================
# Global Singletons (Lazy-Initialized)
# =============================================================================
# These are initialized on first use, not at module load time
_openstack_connection: Optional[openstack.connection.Connection] = None
_openstack_cloud: Optional[str] = None
_flavor_cache: Optional[Dict[str, Dict]] = None
_flavor_cache_cloud: Optional[str] = None


# =============================================================================
# Pricing Configuration
# =============================================================================
def load_all_pricing_data():
    """
    Load all pricing configuration from unified pricing.csv file.

    Returns:
        Dict of {provider: {openstack_flavor: instance_data}}
        where instance_data includes: flavor, cores, memory_gb, gpu, price, boot_storage_gb, storage_price
    """
    config_file = "pricing.csv"

    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found!", file=sys.stderr)
        print(
            "Please ensure pricing.csv exists in the current directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Load CSV into list of dicts
        rows = []
        with open(config_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows or comments
                if not row.get("Cloud") or row["Cloud"].strip().startswith("#"):
                    continue
                rows.append(row)

        # For OpenStack rows, set Matched_OpenStack_Flavor = Flavor
        for row in rows:
            if row["Cloud"].strip() == "openstack":
                if not row.get("Matched_OpenStack_Flavor", "").strip():
                    row["Matched_OpenStack_Flavor"] = row["Flavor"].strip()

        # Build provider_pricing from rows
        provider_pricing = {}

        for row in rows:
            cloud = row["Cloud"].strip()
            flavor = row["Flavor"].strip()
            matched_flavor = row.get("Matched_OpenStack_Flavor", "").strip()

            # Skip rows without matched flavor
            if not matched_flavor:
                continue

            # Parse fields
            cores = int(row["Cores"].strip()) if row["Cores"].strip() else 0
            memory_gb = (
                float(row["Memory_GB"].strip()) if row["Memory_GB"].strip() else 0
            )
            boot_storage_gb = int(row.get("Boot_Storage_GB", "").strip() or 0)
            gpu = row.get("GPU", "").strip().lower()
            gpu = None if gpu in ("", "none") else gpu
            price = float(row["Compute_Price_Per_Month"].strip() or 0)
            storage_price = float(
                row.get("Storage_Price_Per_GB_Per_Month", "").strip() or 0
            )

            # Build provider_pricing
            if cloud not in provider_pricing:
                provider_pricing[cloud] = {}

            provider_pricing[cloud][matched_flavor] = {
                "flavor": flavor,
                "cores": cores,
                "memory_gb": memory_gb,
                "gpu": gpu,
                "price": price,
                "boot_storage_gb": boot_storage_gb,
                "storage_price": storage_price,
            }

        return provider_pricing

    except Exception as e:
        print(f"Error loading {config_file}: {e}", file=sys.stderr)
        sys.exit(1)


# Load pricing data at startup
PROVIDER_PRICING = load_all_pricing_data()


@dataclass
class VM:
    """Represents a virtual machine"""

    name: str
    flavor: str
    status: str
    cores: int
    ram_mb: int
    boot_storage_gb: int
    additional_storage_gb: int
    gpu_type: Optional[str] = None
    gpu_count: int = 0

    @property
    def storage_gb(self) -> int:
        """Total storage (boot + additional)"""
        return self.boot_storage_gb + self.additional_storage_gb

    @property
    def ram_gb(self) -> float:
        """RAM in gigabytes"""
        return self.ram_mb / 1024

    def get_billable_storage(self, provider: str) -> int:
        """
        Calculate billable storage (GB) for a provider.

        Returns storage beyond what the flavor includes.
        """
        if provider not in PROVIDER_PRICING:
            return 0

        if self.flavor not in PROVIDER_PRICING[provider]:
            return 0

        flavor_provided_storage = PROVIDER_PRICING[provider][self.flavor].get(
            "boot_storage_gb", 0
        )
        total_storage_gb = self.boot_storage_gb + self.additional_storage_gb
        return max(total_storage_gb - flavor_provided_storage, 0)

    def get_provider_flavor(self, provider: str) -> Optional[str]:
        """Get the provider's instance flavor name for this VM."""
        if provider not in PROVIDER_PRICING:
            return None

        if self.flavor not in PROVIDER_PRICING[provider]:
            return None

        return PROVIDER_PRICING[provider][self.flavor].get("flavor")

    def get_cost(self, provider: str) -> Optional[float]:
        """
        Calculate monthly cost for a VM on a given provider.

        Args:
            provider: The provider name (e.g., 'openstack', 'aws', 'gcp').

        Returns:
            The calculated monthly cost, or None if flavor not found for this provider.
        """
        # Check if provider exists
        if provider not in PROVIDER_PRICING:
            return None

        # Check if flavor exists for this provider
        if self.flavor not in PROVIDER_PRICING[provider]:
            return None

        # Get flavor pricing info
        flavor_pricing = PROVIDER_PRICING[provider][self.flavor]

        # Calculate cost: base price + storage cost (beyond what flavor provides)
        flavor_compute_price = flavor_pricing.get("price", 0)
        storage_price = flavor_pricing.get("storage_price", 0)
        billable_storage_gb = self.get_billable_storage(provider)
        storage_cost = billable_storage_gb * storage_price

        return flavor_compute_price + storage_cost


# Cache management functions
def get_cache_path(cache_dir: str, cloud: str) -> str:
    """Get the path to the cache file for a given cloud"""
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{cloud}.json")


def load_cache(cache_file: str, cache_max_age_hours: float) -> Optional[List[Dict]]:
    """
    Load server list from cache if it exists and is still valid.

    Args:
        cache_file: Path to cache file
        cache_max_age_hours: Maximum age in hours (-1 = never expires, 0 = always refresh)

    Returns:
        Server data from cache, or None if cache invalid/missing
    """
    # cache_max_age_hours == 0 means always refresh
    if cache_max_age_hours == 0:
        return None

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r") as f:
            cache_data = json.load(f)

        # Check cache age (unless cache_max_age_hours < 0, which means never expire)
        if cache_max_age_hours > 0:
            cache_age_seconds = time.time() - cache_data.get("timestamp", 0)
            cache_age_hours = cache_age_seconds / 3600
            if cache_age_hours > cache_max_age_hours:
                return None  # Cache expired

        return cache_data.get("servers", [])
    except (json.JSONDecodeError, KeyError, ValueError):
        # Corrupted cache, treat as miss
        return None


def save_cache(cache_file: str, servers: List[Dict], cloud: str) -> None:
    """
    Save servers to cache file.

    Args:
        cache_file: Path to cache file
        servers: List of server dicts to cache
        cloud: Cloud name
    """
    try:
        cache_data = {
            "timestamp": time.time(),
            "cloud": cloud,
            "servers": servers,
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save cache: {e}", file=sys.stderr)


def get_openstack_connection(cloud: str) -> openstack.connection.Connection:
    """
    Get or create an OpenStack connection (singleton pattern).

    Connection is created only once on first call, then reused for all subsequent calls.
    This avoids expensive initialization overhead on every call.

    Args:
        cloud: Cloud name (maps to os-cloud in clouds.yaml)

    Returns:
        OpenStack SDK connection object

    Raises:
        SystemExit on connection failure
    """
    global _openstack_connection, _openstack_cloud

    # Return cached connection if already initialized for this cloud
    if _openstack_connection is not None and _openstack_cloud == cloud:
        return _openstack_connection

    # Create new connection
    try:
        _openstack_connection = openstack.connect(cloud=cloud)
        _openstack_cloud = cloud
        return _openstack_connection
    except openstack.exceptions.SDKException as e:
        print(f"Error connecting to OpenStack cloud '{cloud}': {e}", file=sys.stderr)
        print(f"Check that clouds.yaml has '{cloud}' configured", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error connecting to OpenStack: {e}", file=sys.stderr)
        sys.exit(1)


def get_flavor(cloud: str, flavor_name: str) -> Optional[Dict]:
    """
    Get flavor information by name (singleton-cached).

    Loads all flavors from OpenStack on first call, then caches them.
    Subsequent calls return cached values.

    Args:
        cloud: OpenStack cloud name
        flavor_name: Name of the flavor to look up

    Returns:
        Dict with {vcpus, ram, disk} or None if flavor not found
    """
    global _flavor_cache, _flavor_cache_cloud

    # Load flavor cache if needed (lazy initialization on first call)
    if _flavor_cache is None or _flavor_cache_cloud != cloud:
        print("Loading flavor cache from OpenStack", file=sys.stderr)
        conn = get_openstack_connection(cloud)

        _flavor_cache = {}
        try:
            for flavor in conn.compute.flavors():
                _flavor_cache[flavor.name] = {
                    "vcpus": flavor.vcpus,
                    "ram": flavor.ram,
                    "disk": flavor.disk,
                }
        except Exception as e:
            print(f"Warning: Could not load flavor cache: {e}", file=sys.stderr)
            _flavor_cache = {}

        _flavor_cache_cloud = cloud

    # Return the flavor or None if not found
    return _flavor_cache.get(flavor_name)


def detect_gpu(vm_name: str) -> Tuple[Optional[str], int]:
    """Detect GPU type and count from VM name"""
    gpu_patterns = {
        "a100": r"a100|a_100",
        "v100": r"v100|v_100",
    }

    # Check for specific GPU types first
    for gpu_type, pattern in gpu_patterns.items():
        matches = re.findall(rf"{pattern}\.x(\d+)", vm_name.lower())
        if matches and matches[0]:  # Ensure match is not empty
            try:
                count = int(matches[0])
                return gpu_type.upper(), count
            except (ValueError, IndexError):
                continue

    # If no specific GPU detected, return None
    return None, 0


def format_price(value: Optional[float]) -> str:
    """Format a price value for display."""
    if value is None or value == 0:
        return "-"
    return f"$ {value:.2f}"


def calculate_totals(vms: List[VM], provider: Optional[str] = None) -> Dict:
    """
    Calculate total resources and costs for a list of VMs.

    Returns dict with totals for cores, ram, storage, GPUs, and costs.
    """
    totals = {
        "vms": len(vms),
        "cores": sum(vm.cores for vm in vms),
        "ram_gb": int(sum(vm.ram_gb for vm in vms)),
        "boot_storage_gb": sum(vm.boot_storage_gb for vm in vms),
        "additional_storage_gb": sum(vm.additional_storage_gb for vm in vms),
        "total_storage_gb": sum(vm.storage_gb for vm in vms),
        "gpus": sum(vm.gpu_count for vm in vms),
        "has_gpu": any(vm.gpu_type for vm in vms),
        "os_cost": sum(vm.get_cost("openstack") or 0 for vm in vms),
        "comparison_cost": 0.0,
    }

    if provider:
        totals["comparison_cost"] = sum(vm.get_cost(provider) or 0 for vm in vms)

    return totals


def list_vms(
    cloud: str,
    vm_filter: Optional[List[str]] = None,
    cache_dir: str = ".vm_cache",
    cache_max_age_hours: float = 24,
) -> List[VM]:
    """
    List VMs from OpenStack, optionally filtered by regex pattern(s).

    Loads from cache if valid, otherwise fetches from OpenStack.
    Saves updated cache after processing.

    Uses the singleton OpenStack connection (lazily initialized on first call).

    Args:
        cloud: OpenStack cloud name (for cache file naming and display)
        vm_filter: Optional list of regex patterns to filter VMs
        cache_dir: Directory to store cache files (default: .vm_cache)
        cache_max_age_hours: Max cache age in hours (-1=never expire, 0=always refresh)

    Returns:
        List of VM objects (filtered)
    """
    # Get the singleton OpenStack connection
    conn = get_openstack_connection(cloud)
    # Get cache file path
    cache_file = get_cache_path(cache_dir, cloud)

    # Load server list (from cache or OpenStack)
    servers = load_cache(cache_file, cache_max_age_hours)
    if servers is not None:
        print(f"Using cached VMs from {cloud}", file=sys.stderr)
    else:
        # Cache miss - fetch from OpenStack using SDK
        try:
            servers_from_api = list(conn.compute.servers(details=True))
            # Convert SDK objects to dicts for cache compatibility
            servers = [
                {
                    "ID": s.id,
                    "Name": s.name,
                    "Status": s.status,
                    "flavor": s.flavor,
                }
                for s in servers_from_api
            ]
        except Exception as e:
            print(
                f"Error: Could not fetch server list from OpenStack: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    vms = []
    # Compile patterns from list of regex strings
    patterns = [re.compile(p) for p in vm_filter] if vm_filter else []

    for server in servers:
        name = server.get("Name", "")

        # Check if this VM matches the filter
        matches_filter = True
        if patterns:
            if not any(pattern.search(name) for pattern in patterns):
                matches_filter = False

        # Only process VMs that match the filter
        if not matches_filter:
            continue

        # Check if this VM is fully cached (has flavor_name data)
        is_cached = server.get("flavor_name") is not None

        if not is_cached:
            # Need to fetch details from OpenStack
            # Show progress
            print(f"\rProcessing VM: {name}\033[K", end="", file=sys.stderr, flush=True)

            # Get detailed server info using SDK
            try:
                server_obj = conn.compute.get_server(server.get("ID"))
                if server_obj is None:
                    continue
            except Exception as e:
                print(
                    f"Warning: Could not fetch details for {name}: {e}",
                    file=sys.stderr,
                )
                continue
        else:
            # Use cached data - no need to query OpenStack
            server_obj = None

        # Extract information
        status = server.get("Status", "UNKNOWN")

        # Check if we have cached flavor data
        if server.get("flavor_name") is not None:
            # Use cached flavor data
            flavor_name = server.get("flavor_name")
            cores = server.get("cores", 0)
            ram_mb = server.get("ram_mb", 0)
        else:
            # Extract flavor info from server object (freshly fetched)
            flavor_name = "unknown"
            cores = 0
            ram_mb = 0

            if server_obj and hasattr(server_obj, "flavor"):
                flavor_info = server_obj.flavor

                # flavor_info is a dict with flavor details
                if isinstance(flavor_info, dict):
                    flavor_name = flavor_info.get("original_name") or flavor_info.get(
                        "name", "unknown"
                    )
                    # Look up in pricing data first
                    if flavor_name in PROVIDER_PRICING.get("openstack", {}):
                        flavor_specs = PROVIDER_PRICING["openstack"][flavor_name]
                        cores = flavor_specs["cores"]
                        ram_mb = int(flavor_specs["memory_gb"] * 1024)
                    else:
                        # Fall back to OpenStack flavor info
                        flavor_info = get_flavor(cloud, flavor_name)
                        if flavor_info:
                            cores = flavor_info.get("vcpus", 0)
                            ram_mb = flavor_info.get("ram", 0)
                else:
                    # If flavor is a string, try to parse it
                    flavor_name = str(flavor_info).split("(")[0].strip()
                    if flavor_name in PROVIDER_PRICING.get("openstack", {}):
                        flavor_specs = PROVIDER_PRICING["openstack"][flavor_name]
                        cores = flavor_specs["cores"]
                        ram_mb = int(flavor_specs["memory_gb"] * 1024)
                    else:
                        # Fall back to OpenStack flavor info
                        flavor_info_data = get_flavor(cloud, flavor_name)
                        if flavor_info_data:
                            cores = flavor_info_data.get("vcpus", 0)
                            ram_mb = flavor_info_data.get("ram", 0)

        # Get storage info - only fetch if not already cached
        boot_storage_gb = server.get("boot_storage_gb")
        additional_storage_gb = server.get("additional_storage_gb")

        if boot_storage_gb is None or additional_storage_gb is None:
            # Need to fetch storage from OpenStack using SDK
            boot_storage_gb = 0
            additional_storage_gb = 0

            # Get flavor disk size from OpenStack flavor info
            flavor_info = get_flavor(cloud, flavor_name)
            if flavor_info:
                boot_storage_gb = flavor_info.get("disk", 0)

            # Get volumes attached to this server using SDK
            try:
                server_id = server.get("ID")
                if server_id:
                    # List volumes attached to this server
                    volume_attachments = list(
                        conn.compute.volume_attachments(server_id)
                    )

                    for attachment in volume_attachments:
                        device = attachment.get("device") or ""
                        vol_id = attachment.get("volume_id")

                        if vol_id:
                            try:
                                # Get the volume details to get its size
                                volume = conn.block_storage.get_volume(vol_id)
                                vol_size = volume.size if volume else 0

                                # Check if this is the boot disk (/dev/vda)
                                if device == "/dev/vda":
                                    boot_storage_gb = vol_size
                                else:
                                    # Count non-boot volumes as additional storage
                                    additional_storage_gb += vol_size
                            except Exception as e:
                                print(
                                    f"Warning: Could not fetch volume {vol_id}: {e}",
                                    file=sys.stderr,
                                )
            except Exception as e:
                print(
                    f"Warning: Could not fetch volumes for {name}: {e}",
                    file=sys.stderr,
                )

        # Detect GPU - check flavor specs first, then VM name
        gpu_type, gpu_count = None, 0
        if flavor_name in PROVIDER_PRICING.get("openstack", {}):
            flavor_gpu = PROVIDER_PRICING["openstack"][flavor_name].get("gpu")
            if flavor_gpu:
                gpu_type = flavor_gpu.upper()
                gpu_count = 1  # Default to 1 GPU per flavor if not specified in name
                # Try to detect count from VM name as override
                _, vm_gpu_count = detect_gpu(name)
                if vm_gpu_count > 0:
                    gpu_count = vm_gpu_count
        else:
            # Fall back to detecting from VM name if flavor not found
            gpu_type, gpu_count = detect_gpu(name)

        vm = VM(
            name=name,
            flavor=flavor_name,
            status=status,
            cores=cores,
            ram_mb=ram_mb,
            boot_storage_gb=boot_storage_gb,
            additional_storage_gb=additional_storage_gb,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
        )
        vms.append(vm)

        # Update the server in the servers list with fetched data
        cache_entry = {
            "ID": server.get("ID", ""),
            "Name": name,
            "Status": status,
            "flavor_name": flavor_name,
            "cores": cores,
            "ram_mb": ram_mb,
            "boot_storage_gb": boot_storage_gb,
            "additional_storage_gb": additional_storage_gb,
            "gpu_type": gpu_type,
            "gpu_count": gpu_count,
        }

        # Update in servers list
        for i, s in enumerate(servers):
            if s.get("Name") == name:
                servers[i] = cache_entry
                break

    # Clear progress line and show final count
    print(f"\rFound {len(vms)} VMs\033[K", file=sys.stderr)

    # Save updated cache
    if cache_file:
        save_cache(cache_file, servers, cloud)

    return sorted(vms, key=lambda x: x.name)


def find_cheapest_provider(vms: List[VM], all_provider_pricing: Dict) -> Optional[str]:
    """
    Find the provider with the lowest total cost for all VMs.
    Skips providers that don't support all required resources (e.g., GPUs).
    Does not consider 'openstack' as it is the baseline being compared against.

    Args:
        vms: List of VM objects
        all_provider_pricing: All provider pricing loaded from CSV

    Returns:
        Provider name with lowest total cost, or None if no provider can support all VMs
    """
    cheapest_provider = None
    cheapest_total = float("inf")

    for provider in all_provider_pricing:
        # Skip openstack - it's the baseline, not a comparison option
        if provider == "openstack":
            continue

        total = 0.0
        can_support_all = True

        for vm in vms:
            cost = vm.get_cost(provider)
            if cost is None:
                # Provider can't support this VM
                can_support_all = False
                break
            total += cost

        if can_support_all and total < cheapest_total:
            cheapest_total = total
            cheapest_provider = provider

    return cheapest_provider


def generate_table_report(
    vms: List[VM],
    provider: Optional[str],
    provider_display: str,
    provider_pricing: Dict,
) -> str:
    """Generate a formatted table report"""
    totals = calculate_totals(vms, provider)
    has_gpu = totals["has_gpu"]

    # Build headers
    headers = [
        "VM Name",
        "Flavor",
        "Cores",
        "RAM (GB)",
        "Storage (GB)",
    ]

    if has_gpu:
        headers.append("GPU")

    headers.append("OS Cost")

    if provider:
        headers.extend(
            [f"{provider_display} Flavor", f"{provider_display} Cost", "Savings"]
        )

    rows = []

    for vm in vms:
        os_cost = vm.get_cost("openstack")

        if vm.additional_storage_gb > 0:
            storage_display = f"{vm.boot_storage_gb} + {vm.additional_storage_gb}"
        else:
            storage_display = str(vm.boot_storage_gb)

        row = [
            vm.name,
            vm.flavor,
            vm.cores,
            int(vm.ram_gb),
            storage_display,
        ]

        if has_gpu:
            row.append(f"{vm.gpu_count}x {vm.gpu_type}" if vm.gpu_type else "-")

        row.append(f"${os_cost:>8.2f}" if os_cost is not None else "N/A")

        if provider:
            comparison_cost = vm.get_cost(provider)
            comparison_flavor = vm.get_provider_flavor(provider)

            row.extend(
                [
                    comparison_flavor or "N/A",
                    f"${comparison_cost:>8.2f}"
                    if comparison_cost is not None
                    else "N/A",
                    f"${comparison_cost - os_cost:>8.2f}"
                    if (comparison_cost is not None and os_cost is not None)
                    else "N/A",
                ]
            )

        rows.append(row)

    # Add summary row
    if totals["additional_storage_gb"] > 0:
        summary_storage_display = (
            f"{totals['boot_storage_gb']} + {totals['additional_storage_gb']}"
        )
    else:
        summary_storage_display = str(totals["boot_storage_gb"])

    summary_row = [
        "TOTAL",
        "",
        totals["cores"],
        totals["ram_gb"],
        summary_storage_display,
    ]

    if has_gpu:
        summary_row.append("")

    summary_row.append(f"${totals['os_cost']:>8.2f}")

    if provider:
        summary_row.extend(
            [
                "",
                f"${totals['comparison_cost']:>8.2f}"
                if totals["comparison_cost"] > 0
                else "N/A",
                f"${(totals['comparison_cost'] - totals['os_cost']):>8.2f}"
                if totals["comparison_cost"] > 0
                else "N/A",
            ]
        )

    rows.append(summary_row)

    # Format as table using tabulate
    return tabulate(rows, headers=headers, tablefmt="grid")


def generate_csv_report(
    vms: List[VM],
    provider: Optional[str],
    provider_display: str,
    provider_pricing: Dict,
) -> str:
    """Generate a CSV report"""
    totals = calculate_totals(vms, provider)
    has_gpu = totals["has_gpu"]

    output = []

    headers = [
        "VM Name",
        "Flavor",
        "Cores",
        "RAM (GB)",
        "Boot Storage (GB)",
        "Additional Storage (GB)",
    ]

    if has_gpu:
        headers.extend(["GPU Type", "GPU Count"])

    headers.append("OpenStack Cost")

    if provider:
        headers.extend(
            [f"{provider_display} Flavor", f"{provider_display} Cost", "Savings"]
        )

    output.append(headers)

    for vm in vms:
        os_cost = vm.get_cost("openstack")

        row_data = [
            vm.name,
            vm.flavor,
            vm.cores,
            int(vm.ram_gb),
            vm.boot_storage_gb,
            vm.additional_storage_gb,
        ]

        if has_gpu:
            row_data.extend([vm.gpu_type or "", vm.gpu_count])

        row_data.append(f"{os_cost:.2f}" if os_cost is not None else "")

        if provider:
            comparison_cost = vm.get_cost(provider)
            comparison_flavor = vm.get_provider_flavor(provider) or ""

            row_data.extend(
                [
                    comparison_flavor,
                    f"{comparison_cost:.2f}" if comparison_cost is not None else "",
                    f"{(comparison_cost - os_cost):.2f}"
                    if (comparison_cost is not None and os_cost is not None)
                    else "",
                ]
            )

        output.append(row_data)

    # Add summary
    summary = [
        "TOTAL",
        "",
        totals["cores"],
        totals["ram_gb"],
        totals["boot_storage_gb"],
        totals["additional_storage_gb"],
    ]

    if has_gpu:
        summary.extend(["", ""])

    summary.append(f"{totals['os_cost']:.2f}")

    if provider:
        summary.extend(
            [
                "",
                f"{totals['comparison_cost']:.2f}"
                if totals["comparison_cost"] > 0
                else "",
                f"{(totals['comparison_cost'] - totals['os_cost']):.2f}"
                if totals["comparison_cost"] > 0
                else "",
            ]
        )

    output.append(summary)

    csv_output = []
    for row in output:
        csv_output.append(",".join(str(v) for v in row))

    return "\n".join(csv_output)


def generate_json_report(
    vms: List[VM],
    provider: Optional[str],
    provider_pricing: Dict,
) -> str:
    """Generate a JSON report"""
    totals = calculate_totals(vms, provider)
    vms_data = []

    for vm in vms:
        os_cost = vm.get_cost("openstack")
        vm_data = {
            "name": vm.name,
            "flavor": vm.flavor,
            "cores": vm.cores,
            "ram_gb": int(vm.ram_gb),
            "storage": {
                "boot_gb": vm.boot_storage_gb,
                "additional_gb": vm.additional_storage_gb,
                "total_gb": vm.storage_gb,
            },
            "gpu": {"type": vm.gpu_type, "count": vm.gpu_count}
            if vm.gpu_type
            else None,
            "costs": {
                "openstack_monthly": round(os_cost, 2) if os_cost is not None else None
            },
        }

        if provider:
            comparison_cost = vm.get_cost(provider)
            comparison_flavor = vm.get_provider_flavor(provider)

            vm_data["costs"].update(
                {
                    "comparison_provider": provider,
                    "comparison_flavor": comparison_flavor,
                    "comparison_monthly": round(comparison_cost, 2)
                    if comparison_cost is not None
                    else None,
                    "savings_monthly": round(comparison_cost - os_cost, 2)
                    if (comparison_cost is not None and os_cost is not None)
                    else None,
                }
            )

        vms_data.append(vm_data)

    # Build summary
    summary = {
        "total_vms": totals["vms"],
        "total_cores": totals["cores"],
        "total_ram_gb": totals["ram_gb"],
        "total_storage": {
            "boot_gb": totals["boot_storage_gb"],
            "additional_gb": totals["additional_storage_gb"],
            "total_gb": totals["total_storage_gb"],
        },
        "total_gpus": totals["gpus"],
        "total_cost_openstack": round(totals["os_cost"], 2),
    }

    if provider:
        summary.update(
            {
                "comparison_provider": provider,
                "total_cost_comparison": round(totals["comparison_cost"], 2)
                if totals["comparison_cost"] > 0
                else None,
                "total_savings": round(totals["comparison_cost"] - totals["os_cost"], 2)
                if totals["comparison_cost"] > 0
                else None,
            }
        )

    report = {
        "timestamp": datetime.now().isoformat(),
        "vms": vms_data,
        "summary": summary,
    }

    return json.dumps(report, indent=2)


def generate_md_report(
    vms: List[VM],
    provider: Optional[str],
    provider_display: str,
    provider_pricing: Dict,
) -> str:
    """Generate a Markdown report"""
    totals = calculate_totals(vms, provider)
    has_gpu = totals["has_gpu"]

    # Build the markdown table
    md_lines = []

    # Headers
    headers = [
        "VM Name",
        "Flavor",
        "Cores",
        "RAM (GB)",
        "Storage (GB)",
    ]

    if has_gpu:
        headers.append("GPU")

    headers.append("OS Cost")

    if provider:
        headers.extend(
            [f"{provider_display} Flavor", f"{provider_display} Cost", "Savings"]
        )

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for vm in vms:
        os_cost = vm.get_cost("openstack")

        if vm.additional_storage_gb > 0:
            storage_display = f"{vm.boot_storage_gb} + {vm.additional_storage_gb}"
        else:
            storage_display = str(vm.boot_storage_gb)

        row = [
            vm.name,
            vm.flavor,
            str(vm.cores),
            str(int(vm.ram_gb)),
            storage_display,
        ]

        if has_gpu:
            row.append(f"{vm.gpu_count}x {vm.gpu_type}" if vm.gpu_type else "-")

        row.append(f"${os_cost:>8.2f}" if os_cost is not None else "N/A")

        if provider:
            comparison_cost = vm.get_cost(provider)
            comparison_flavor = vm.get_provider_flavor(provider)

            row.extend(
                [
                    comparison_flavor or "N/A",
                    f"${comparison_cost:>8.2f}"
                    if comparison_cost is not None
                    else "N/A",
                    f"${(comparison_cost - os_cost):>8.2f}"
                    if (comparison_cost is not None and os_cost is not None)
                    else "N/A",
                ]
            )

        md_lines.append("| " + " | ".join(row) + " |")

    # Add summary row
    if totals["additional_storage_gb"] > 0:
        summary_storage_display = (
            f"{totals['boot_storage_gb']} + {totals['additional_storage_gb']}"
        )
    else:
        summary_storage_display = str(totals["boot_storage_gb"])

    summary_row = [
        "**TOTAL**",
        "",
        str(totals["cores"]),
        str(totals["ram_gb"]),
        summary_storage_display,
    ]

    if has_gpu:
        summary_row.append("")

    summary_row.append(f"${totals['os_cost']:>8.2f}")

    if provider:
        summary_row.extend(
            [
                "",
                f"${totals['comparison_cost']:>8.2f}"
                if totals["comparison_cost"] > 0
                else "N/A",
                f"${(totals['comparison_cost'] - totals['os_cost']):>8.2f}"
                if totals["comparison_cost"] > 0
                else "N/A",
            ]
        )

    md_lines.append("| " + " | ".join(summary_row) + " |")

    return "\n".join(md_lines)


def generate_summary_report(
    vms: List[VM],
    provider: Optional[str],
    provider_display: str,
    provider_pricing: Dict,
) -> str:
    """Generate a summary report with resource counts and total costs"""
    headers = ["Unit", "Count", "OS Cost"]

    # Add comparison headers if provider specified
    if provider:
        headers.extend([f"{provider_display} Cost", "Difference"])

    rows = []

    # Helper function to get base compute price for a flavor
    def get_compute_price(vm, provider_name):
        if vm.flavor in provider_pricing.get(provider_name, {}):
            return float(provider_pricing[provider_name][vm.flavor].get("price", 0))
        return 0

    # Calculate total resources
    total_cores = sum(vm.cores for vm in vms)
    total_additional_storage = sum(vm.additional_storage_gb for vm in vms)
    total_gpus = sum(vm.gpu_count for vm in vms)

    # Calculate compute costs - separate CPU and GPU
    os_compute_cost = 0
    comparison_compute_cost = 0
    os_gpu_compute_cost = 0
    comparison_gpu_compute_cost = 0

    for vm in vms:
        if vm.gpu_type:
            # GPU VMs - add to GPU compute cost
            os_gpu_compute_cost += get_compute_price(vm, "openstack")
            if provider:
                comparison_gpu_compute_cost += get_compute_price(vm, provider)
        else:
            # CPU VMs - add to CPU compute cost
            os_compute_cost += get_compute_price(vm, "openstack")
            if provider:
                comparison_compute_cost += get_compute_price(vm, provider)

    # Cores row
    cores_row = [
        "Cores",
        str(total_cores),
        format_price(os_compute_cost)
        if os_compute_cost
        else "N/A",  # 11 chars for "   OS Cost"
    ]

    if provider:
        cores_row.append(
            format_price(comparison_compute_cost) if comparison_compute_cost else "-"
        )
        diff = (
            comparison_compute_cost - os_compute_cost
            if comparison_compute_cost and os_compute_cost
            else None
        )
        cores_row.append(format_price(diff) if diff is not None else "-")

    rows.append(cores_row)

    # RAM row
    total_ram = int(sum(vm.ram_gb for vm in vms))
    ram_row = [
        "RAM (GB)",
        str(total_ram),
        "-",  # OS Cost column width
    ]
    if provider:
        ram_row.extend(["-", "-"])
    rows.append(ram_row)

    # Storage row
    total_boot_storage = sum(vm.boot_storage_gb for vm in vms)
    total_storage = total_boot_storage + total_additional_storage

    if total_additional_storage > 0:
        storage_display = f"{total_boot_storage} + {total_additional_storage}"
    else:
        storage_display = str(total_boot_storage)

    # Calculate storage costs using VM helper method
    os_storage_cost = 0.0
    comparison_storage_cost = 0.0

    for vm in vms:
        # Get storage price per GB
        if vm.flavor in provider_pricing.get("openstack", {}):
            os_storage_price = provider_pricing["openstack"][vm.flavor].get(
                "storage_price", 0
            )
            os_storage_cost += vm.get_billable_storage("openstack") * os_storage_price

        if provider and vm.flavor in provider_pricing.get(provider, {}):
            comp_storage_price = provider_pricing[provider][vm.flavor].get(
                "storage_price", 0
            )
            comparison_storage_cost += (
                vm.get_billable_storage(provider) * comp_storage_price
            )

    storage_row = [
        "Storage (GB)",
        storage_display,
        format_price(os_storage_cost) if os_storage_cost > 0 else "-",
    ]

    if provider:
        storage_row.append(
            format_price(comparison_storage_cost)
            if comparison_storage_cost > 0
            else "-"
        )
        diff = (
            comparison_storage_cost - os_storage_cost
            if comparison_storage_cost > 0 or os_storage_cost > 0
            else None
        )
        storage_row.append(format_price(diff) if diff is not None else "-")

    rows.append(storage_row)

    # GPUs row (if any VMs have GPUs)
    if total_gpus > 0:
        gpu_row = [
            "GPUs",
            str(total_gpus),
            format_price(os_gpu_compute_cost) if os_gpu_compute_cost > 0 else "-",
        ]
        if provider:
            gpu_row.append(
                format_price(comparison_gpu_compute_cost)
                if comparison_gpu_compute_cost > 0
                else "-"
            )
            diff = (
                comparison_gpu_compute_cost - os_gpu_compute_cost
                if comparison_gpu_compute_cost > 0 or os_gpu_compute_cost > 0
                else None
            )
            gpu_row.append(format_price(diff) if diff is not None else "-")
        rows.append(gpu_row)

    # VMs count row
    vm_row = [
        "VMs",
        str(len(vms)),
        "-",  # OS Cost column width
    ]
    if provider:
        vm_row.extend(["-", "-"])
    rows.append(vm_row)

    # Total costs row (sum of all components: CPU compute + storage + GPU compute)
    total_os_cost = os_compute_cost + os_storage_cost + os_gpu_compute_cost
    total_comparison_cost = (
        comparison_compute_cost + comparison_storage_cost + comparison_gpu_compute_cost
        if provider
        else 0
    )

    total_row = [
        "Total Cost",
        "",
        format_price(total_os_cost) if total_os_cost else "N/A",
    ]

    if provider:
        total_row.append(
            format_price(total_comparison_cost) if total_comparison_cost else "-"
        )
        diff = (
            total_comparison_cost - total_os_cost
            if total_comparison_cost and total_os_cost
            else None
        )
        total_row.append(format_price(diff) if diff else "-")

    rows.append(total_row)

    # Use tabulate with proper column alignment
    # Columns: Unit, Count, OS Cost, [Provider Cost], [Difference]
    if provider:
        colalign = ("right", "right", "right", "right", "right")
    else:
        colalign = ("right", "right", "right")

    return tabulate(rows, headers=headers, tablefmt="grid", colalign=colalign)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze OpenStack environment and generate cost reports"
    )
    parser.add_argument(
        "vms",
        nargs="*",
        default=None,
        help='VM name patterns (regex). Can specify multiple patterns - VMs matching ANY pattern will be included (e.g., "web-.*" "gpu-.*")',
    )
    parser.add_argument(
        "--cloud",
        default="software",
        help="OpenStack cloud name (default: software)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json", "md", "summary", "all"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (if not specified, prints to stdout)",
    )
    parser.add_argument(
        "--comparison",
        default="none",
        help='Cloud provider to compare costs against (e.g., aws, gce, azure, linode; default: none, use "cheapest" to compare against lowest-cost provider)',
    )
    parser.add_argument(
        "--cache",
        type=float,
        default=24,
        help="Cache max age in hours (default: 24, use 0 to always refresh, use -1 to never expire)",
    )
    parser.add_argument(
        "--cache-dir",
        default=".vm_cache",
        help="Cache directory (default: .vm_cache)",
    )

    args = parser.parse_args()

    # Load provider pricing from pricing.csv
    print("Loading prices from pricing.csv", file=sys.stderr)
    provider_pricing = load_all_pricing_data()

    # List VMs (with caching)
    # Note: OpenStack connection will be created lazily on first call to list_vms()
    if args.vms:
        if len(args.vms) == 1:
            print(f"Listing VMs matching: {args.vms[0]}", file=sys.stderr)
        else:
            print(f"Listing VMs: {', '.join(args.vms)}", file=sys.stderr)
        vms = list_vms(
            args.cloud,
            vm_filter=args.vms,
            cache_dir=args.cache_dir,
            cache_max_age_hours=args.cache,
        )
    else:
        print("Listing VMs", file=sys.stderr)
        vms = list_vms(
            args.cloud,
            vm_filter=None,
            cache_dir=args.cache_dir,
            cache_max_age_hours=args.cache,
        )

    if not vms:
        print("No VMs found matching the criteria", file=sys.stderr)
        sys.exit(0)

    # Determine which provider to use for comparison
    comparison_provider = None
    provider_display = ""
    if args.comparison == "cheapest":
        comparison_provider = find_cheapest_provider(vms, provider_pricing)
        provider_display = comparison_provider.upper() if comparison_provider else ""
    elif args.comparison != "none":
        comparison_provider = args.comparison
        provider_display = args.comparison.upper()

    # Generate reports
    formats = (
        ["table", "csv", "json", "md", "summary"]
        if args.format == "all"
        else [args.format]
    )

    output_data = {}
    for fmt in formats:
        if fmt == "table":
            output_data["table"] = generate_table_report(
                vms, comparison_provider, provider_display, provider_pricing
            )
        elif fmt == "csv":
            output_data["csv"] = generate_csv_report(
                vms, comparison_provider, provider_display, provider_pricing
            )
        elif fmt == "json":
            output_data["json"] = generate_json_report(
                vms, comparison_provider, provider_pricing
            )
        elif fmt == "md":
            output_data["md"] = generate_md_report(
                vms, comparison_provider, provider_display, provider_pricing
            )
        elif fmt == "summary":
            output_data["summary"] = generate_summary_report(
                vms, comparison_provider, provider_display, provider_pricing
            )

    # Output results
    if args.output:
        if args.format == "all":
            for fmt, data in output_data.items():
                filename = f"{args.output}.{fmt}"
                with open(filename, "w") as f:
                    f.write(data)
                print(f"Report written to: {filename}", file=sys.stderr)
        else:
            with open(args.output, "w") as f:
                f.write(output_data[formats[0]])
            print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        if args.format == "all":
            for fmt in formats:
                print(f"\n{'=' * 80}")
                print(f"Report: {fmt.upper()}")
                print(f"{'=' * 80}\n")
                print(output_data[fmt])
        else:
            print(output_data[formats[0]])


if __name__ == "__main__":
    main()
