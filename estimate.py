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
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from tabulate import tabulate


# Pricing configuration - loads from pricing.csv
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

            # Skip flash storage rows
            if flavor == "flash":
                continue

            # Skip rows without matched flavor
            if not matched_flavor:
                continue

            # Parse fields
            cores = int(row["Cores"].strip()) if row["Cores"].strip() else 0
            memory_gb = float(row["Memory_GB"].strip()) if row["Memory_GB"].strip() else 0
            boot_storage_gb = int(row.get("Boot_Storage_GB", "").strip() or 0)
            gpu = row.get("GPU", "").strip().lower()
            gpu = None if gpu in ("", "none") else gpu
            price = float(row["Compute_Price_Per_Month"].strip() or 0)
            storage_price = float(row.get("Storage_Price_Per_GB_Per_Month", "").strip() or 0)

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
    storage_gb: int
    gpu_type: Optional[str] = None
    gpu_count: int = 0
    floating_ip: bool = False
    comparison_flavor: Optional[str] = None
    comparison_price: Optional[float] = None

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

        # Calculate cost: base price + additional storage beyond boot storage
        flavor_compute_price = flavor_pricing.get("price", 0)
        boot_storage_gb = flavor_pricing.get("boot_storage_gb", 0)
        storage_price = flavor_pricing.get("storage_price", 0)

        additional_storage_gb = max(0, self.storage_gb - boot_storage_gb)
        additional_storage_cost = additional_storage_gb * storage_price

        return flavor_compute_price + additional_storage_cost

    def set_comparison_cost(
        self, flavor: Optional[str], price: Optional[float]
    ) -> None:
        """Set the comparison provider flavor and price for this VM"""
        self.comparison_flavor = flavor
        self.comparison_price = price

    def get_comparison_cost(self) -> Optional[float]:
        """Get the comparison provider cost for this VM"""
        return self.comparison_price


def run_openstack_command(cmd: str, cloud: str) -> str:
    """Run an OpenStack command with the specified cloud"""
    full_cmd = f"openstack --os-cloud={cloud} {cmd}"
    try:
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running OpenStack command: {e.stderr}", file=sys.stderr)
        sys.exit(1)


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


def list_vms(cloud: str, vm_regex: Optional[str] = None) -> List[VM]:
    """List VMs from OpenStack, optionally filtered by regex"""
    try:
        output = run_openstack_command("server list -f json", cloud)
        servers = json.loads(output)
    except json.JSONDecodeError:
        print("Error: Could not parse OpenStack server list", file=sys.stderr)
        sys.exit(1)

    vms = []
    pattern = re.compile(vm_regex) if vm_regex else None

    for server in servers:
        name = server.get("Name", "")

        # Filter by regex if provided
        if pattern and not pattern.search(name):
            continue

        # Show progress
        print(f"\rProcessing VM: {name}\033[K", end="", file=sys.stderr, flush=True)

        # Get detailed server info
        try:
            detail_output = run_openstack_command(f"server show {name} -f json", cloud)
            details = json.loads(detail_output)
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            continue

        # Extract information
        status = server.get("Status", "UNKNOWN")

        # Get flavor (size) info - query flavor details for accurate disk size
        flavor_info = details.get("flavor", {})
        flavor_name = "unknown"
        boot_storage_gb = 0
        if isinstance(flavor_info, str):
            # If flavor is a string like "gp.medium (gp.medium)", extract the name
            flavor_name = flavor_info.split("(")[0].strip()
            if flavor_name in PROVIDER_PRICING.get("openstack", {}):
                flavor_specs = PROVIDER_PRICING["openstack"][flavor_name]
                cores = flavor_specs["cores"]
                ram_mb = int(flavor_specs["memory_gb"] * 1024)
            else:
                cores = 0
                ram_mb = 0
        else:
            # If flavor is a dict with details
            flavor_name = flavor_info.get(
                "original_name", flavor_info.get("name", "unknown")
            )
            cores = flavor_info.get("vcpus", 0) or 0
            ram_mb = flavor_info.get("ram", 0) or 0

        # Get flavor disk size from OpenStack flavor object
        try:
            flavor_detail_output = run_openstack_command(
                f"flavor show {flavor_name} -f json", cloud
            )
            flavor_detail = json.loads(flavor_detail_output)
            boot_storage_gb = flavor_detail.get("disk", 0)
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            boot_storage_gb = 0

        # Get storage info - query volumes attached to this server
        volume_size = 0
        has_boot_disk = False
        try:
            # Get server's volume attachments
            vol_attach_output = run_openstack_command(
                f"server volume list {name} -f json", cloud
            )
            vol_attachments = json.loads(vol_attach_output)

            # Sum up the sizes of attached volumes
            for attachment in vol_attachments:
                device = attachment.get("Device", "")
                vol_id = attachment.get("Volume ID")

                # Check if this is the boot disk (/dev/vda)
                if device == "/dev/vda":
                    has_boot_disk = True

                if vol_id:
                    # Get the volume details to get its size
                    vol_detail_output = run_openstack_command(
                        f"volume show {vol_id} -f json", cloud
                    )
                    vol_detail = json.loads(vol_detail_output)
                    volume_size += vol_detail.get("size", 0)
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            pass

        # If no boot disk attached (/dev/vda), add the flavor's boot storage
        # This handles cases where the server boots from the flavor's disk, not an attached volume
        if not has_boot_disk:
            volume_size += boot_storage_gb

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

        # Check for floating IP
        has_floating_ip = False
        if "networks" in details and details["networks"]:
            networks = details["networks"]
            if isinstance(networks, dict):
                for net_name, net_ips in networks.items():
                    if any("floating" in str(ip).lower() for ip in net_ips):
                        has_floating_ip = True

        vm = VM(
            name=name,
            flavor=flavor_name,
            status=status,
            cores=cores,
            ram_mb=ram_mb,
            storage_gb=volume_size,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            floating_ip=has_floating_ip,
        )
        vms.append(vm)

    # Clear progress line and show final count
    print(f"\rFound {len(vms)} VMs\033[K", file=sys.stderr)

    return sorted(vms, key=lambda x: x.name)


def estimate_cost_by_provider(
    vm: VM, provider_pricing: Dict
) -> Tuple[Optional[float], Optional[str]]:
    """
    Estimate cost for equivalent resources using provider pricing from CSV.

    Uses Matched_OpenStack_Flavor to match OpenStack VMs to provider instances.

    Args:
        vm: VM object with resource specifications
        provider_pricing: Provider pricing loaded from CSV, indexed by OpenStack flavor name
                         Structure: {openstack_flavor: {flavor, cores, memory_gb, gpu, price}}

    Returns:
        Tuple of (monthly cost estimate, matched provider instance type) or (None, None) if no match
    """
    # Look up the provider pricing for this VM's OpenStack flavor
    if vm.flavor in provider_pricing:
        provider_instance = provider_pricing[vm.flavor]
        cost = calculate_vm_cost(vm, provider_instance)
        return cost, provider_instance["flavor"]

    # No match found
    return None, None


def find_cheapest_provider(
    vms: List[VM], all_provider_pricing: Dict
) -> Tuple[
    Optional[str], Optional[float], Dict[str, Tuple[Optional[float], Optional[str]]]
]:
    """
    Find the provider with the lowest total cost for all VMs.
    Skips providers that don't support all required resources (e.g., GPUs).

    Args:
        vms: List of VM objects
        all_provider_pricing: All provider pricing loaded from CSV
                             Structure: {provider: {openstack_flavor: {flavor, cores, memory_gb, gpu, price}}}

    Returns:
        Tuple of (best_provider_name, total_cost, vm_costs_dict)
        Where vm_costs_dict = {vm_name: (cost, flavor)}
        Returns (None, None, {}) if no provider can support all VMs
    """
    provider_costs = {}
    provider_vm_details = {}

    for provider, provider_flavors in all_provider_pricing.items():
        total_cost = 0.0
        vm_details = {}
        can_support_all = True

        for vm in vms:
            if vm.flavor not in provider_flavors:
                can_support_all = False
                break

            provider_instance = provider_flavors[vm.flavor]
            cost = calculate_vm_cost(vm, provider_instance)

            # GPU check: If the OpenStack flavor has a GPU (e.g., gpu.a100.x1),
            # the matched provider flavor must support it. We assume if the provider
            # has a matching flavor, it supports the required GPUs (since it's in the
            # Matched_OpenStack_Flavor column, which explicitly maps GPU flavors).
            # The GPU field in provider_instance is only set if it has its own GPU specs.

            total_cost += cost
            vm_details[vm.name] = (cost, provider_instance["flavor"])

        # Only consider this provider if it can support all VMs
        if can_support_all:
            provider_costs[provider] = total_cost
            provider_vm_details[provider] = vm_details

    if not provider_costs:
        return None, None, {}

    # Find the provider with the lowest total cost
    best_provider = min(provider_costs, key=provider_costs.get)
    best_cost = provider_costs[best_provider]

    return best_provider, best_cost, provider_vm_details[best_provider]


def find_best_provider(vms: List[VM], all_provider_pricing: Dict) -> Optional[str]:
    """
    Find the provider with the lowest total cost for all VMs.
    Skips providers that don't support all required resources.

    Args:
        vms: List of VMs
        all_provider_pricing: All providers' pricing data
                             Structure: {provider: {openstack_flavor: {flavor, cores, memory_gb, gpu, price}}}

    Returns:
        Provider name with lowest total cost, or None if no provider supports all VMs
    """
    provider_costs = {}

    for provider, provider_flavors in all_provider_pricing.items():
        total_cost = 0.0
        can_support_all = True

        for vm in vms:
            if vm.flavor not in provider_flavors:
                can_support_all = False
                break
            total_cost += provider_flavors[vm.flavor]["price"]

        if can_support_all:
            provider_costs[provider] = total_cost

    if not provider_costs:
        return None

    return min(provider_costs, key=provider_costs.get)


def populate_vm_comparison_costs(
    vms: List[VM], provider_pricing: Dict, comparison_provider: str
) -> None:
    """
    Populate comparison_flavor and comparison_price for each VM.

    Args:
        vms: List of VMs to populate
        provider_pricing: Provider pricing dict
        comparison_provider: Provider to use ('cheapest' or specific provider name)
    """
    if comparison_provider == "none":
        return

    # Determine which provider to use
    if comparison_provider == "cheapest":
        provider = find_best_provider(vms, provider_pricing)
        if provider is None:
            return
    else:
        provider = comparison_provider

    # Populate each VM with comparison costs
    if provider in provider_pricing:
        provider_flavors = provider_pricing[provider]
        for vm in vms:
            if vm.flavor in provider_flavors:
                flavor_data = provider_flavors[vm.flavor]
                vm.set_comparison_cost(flavor_data["flavor"], flavor_data["price"])


def build_comparison_data(
    vms: List[VM], provider_pricing: Dict, comparison_provider: str
) -> Dict:
    """
    Build a standardized comparison data structure for all report formats.

    Args:
        vms: List of VMs to compare
        provider_pricing: Provider pricing dict from load_pricing_config()
        comparison_provider: Provider to compare against or 'cheapest'

    Returns:
        Dict with structure:
        {
            'provider': str (provider name),
            'total_cost': float (total cost for all VMs),
            'vm_costs': {vm_name: (cost, flavor), ...}
        }
        Returns empty dict if no comparison or provider not available
    """
    if comparison_provider == "none":
        return {}

    if comparison_provider == "cheapest":
        best_provider, total_cost, vm_details = find_cheapest_provider(
            vms, provider_pricing
        )
        if best_provider is None:
            return {}
        return {
            "provider": best_provider,
            "total_cost": total_cost,
            "vm_costs": vm_details,
        }
    else:
        # Single provider comparison
        total_cost = 0.0
        vm_details = {}
        for vm in vms:
            cost, flavor = estimate_cost_by_provider(vm, provider_pricing)
            if cost is not None:
                total_cost += cost
                vm_details[vm.name] = (cost, flavor)

        return {
            "provider": comparison_provider,
            "total_cost": total_cost if vm_details else None,
            "vm_costs": vm_details,
        }


def generate_table_report(
    vms: List[VM],
    comparison_provider: str,
    provider_pricing: Dict,
) -> str:
    """Generate a formatted table report"""
    # Build headers based on comparison provider
    headers = [
        "VM Name",
        "Flavor",
        "Cores",
        "RAM (MB)",
        "Storage (GB)",
        "GPU",
        "OS Cost",
    ]

    # Add comparison columns only if not 'none'
    if comparison_provider != "none":
        provider_display = comparison_provider.upper()
        headers.extend(
            [f"{provider_display} Flavor", f"{provider_display} Cost", "Savings"]
        )

    rows = []
    total_os_cost = 0.0
    total_comparison_cost = 0.0

    for vm in vms:
        os_cost = vm.get_cost("openstack")

        row = [
            vm.name,
            vm.flavor,
            vm.cores,
            vm.ram_mb,
            vm.storage_gb,
            f"{vm.gpu_count}x {vm.gpu_type}" if vm.gpu_type else "-",
            f"${os_cost:.2f}",
        ]

        if comparison_provider != "none":
            row.extend(
                [
                    vm.comparison_flavor or "N/A",
                    f"${vm.comparison_price:.2f}" if vm.comparison_price else "N/A",
                    f"${vm.comparison_price - os_cost:.2f}"
                    if vm.comparison_price
                    else "N/A",
                ]
            )
            if vm.comparison_price:
                total_comparison_cost += vm.comparison_price

        total_os_cost += os_cost
        rows.append(row)

    # Add summary row
    summary_row = [
        "TOTAL",
        "",
        sum(vm.cores for vm in vms),
        sum(vm.ram_mb for vm in vms),
        sum(vm.storage_gb for vm in vms),
        "",
        f"${total_os_cost:.2f}",
    ]

    if comparison_provider != "none":
        summary_row.extend(
            [
                "",
                f"${total_comparison_cost:.2f}" if total_comparison_cost > 0 else "N/A",
                f"${(total_comparison_cost - total_os_cost):.2f}"
                if total_comparison_cost > 0
                else "N/A",
            ]
        )

    rows.append(summary_row)

    table = tabulate(rows, headers=headers, tablefmt="grid")
    return table


def generate_csv_report(
    vms: List[VM],
    comparison_provider: str,
    provider_pricing: Dict,
) -> str:
    """Generate a CSV report"""
    output = []

    headers = [
        "VM Name",
        "Flavor",
        "Cores",
        "RAM (MB)",
        "Storage (GB)",
        "GPU Type",
        "GPU Count",
        "Has Floating IP",
        "OpenStack Cost",
    ]

    # Add comparison columns only if not 'none'
    if comparison_provider != "none":
        provider_display = comparison_provider.upper()
        headers.extend(
            [f"{provider_display} Flavor", f"{provider_display} Cost", "Savings"]
        )

    output.append(headers)

    total_os_cost = 0.0
    total_comparison_cost = 0.0

    for vm in vms:
        os_cost = vm.get_cost("openstack")
        row_data = [
            vm.name,
            vm.flavor,
            vm.cores,
            vm.ram_mb,
            vm.storage_gb,
            vm.gpu_type or "",
            vm.gpu_count,
            "Yes" if vm.floating_ip else "No",
            f"{os_cost:.2f}",
        ]

        if comparison_provider != "none":
            row_data.extend(
                [
                    vm.comparison_flavor or "",
                    f"{vm.comparison_price:.2f}" if vm.comparison_price else "",
                    f"{vm.comparison_price - os_cost:.2f}"
                    if vm.comparison_price
                    else "",
                ]
            )
            if vm.comparison_price:
                total_comparison_cost += vm.comparison_price

        total_os_cost += os_cost
        output.append(row_data)

    # Add summary
    summary = [
        "TOTAL",
        "",
        sum(vm.cores for vm in vms),
        sum(vm.ram_mb for vm in vms),
        sum(vm.storage_gb for vm in vms),
        "",
        "",
        "",
        f"{total_os_cost:.2f}",
    ]

    if comparison_provider != "none":
        summary.extend(
            [
                "",
                f"{total_comparison_cost:.2f}" if total_comparison_cost > 0 else "",
                f"{(total_comparison_cost - total_os_cost):.2f}"
                if total_comparison_cost > 0
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
    provider_pricing: Dict,
    comparison_provider: str,
) -> str:
    """Generate a JSON report"""
    vms_data = []
    total_os_cost = 0.0
    total_comparison_cost = 0.0

    # For 'cheapest', compute best provider once for all VMs
    best_provider = None
    best_provider_details = {}
    if comparison_provider == "cheapest":
        best_provider, total_comparison_cost, best_provider_details = (
            find_cheapest_provider(vms, provider_pricing)
        )

    for vm in vms:
        os_cost = vm.get_cost("openstack")
        vm_data = {
            "name": vm.name,
            "flavor": vm.flavor,
            "cores": vm.cores,
            "ram_mb": vm.ram_mb,
            "storage_gb": vm.storage_gb,
            "gpu": {"type": vm.gpu_type, "count": vm.gpu_count}
            if vm.gpu_type
            else None,
            "floating_ip": vm.floating_ip,
            "costs": {"openstack_monthly": round(os_cost, 2)},
        }

        total_os_cost += os_cost

        if comparison_provider != "none":
            if comparison_provider == "cheapest":
                if vm.name in best_provider_details:
                    comparison_cost, comparison_flavor = best_provider_details[vm.name]
                    vm_data["costs"].update(
                        {
                            "best_provider": best_provider,
                            "best_flavor": comparison_flavor,
                            "best_monthly": round(comparison_cost, 2)
                            if comparison_cost
                            else None,
                            "savings_monthly": round(comparison_cost - os_cost, 2)
                            if comparison_cost
                            else None,
                        }
                    )
            else:
                comparison_cost, comparison_flavor = estimate_cost_by_provider(
                    vm, provider_pricing
                )
                vm_data["costs"].update(
                    {
                        f"{comparison_provider}_flavor": comparison_flavor,
                        f"{comparison_provider}_monthly": round(comparison_cost, 2)
                        if comparison_cost
                        else None,
                        "savings_monthly": round(comparison_cost - os_cost, 2)
                        if comparison_cost
                        else None,
                    }
                )
                if comparison_cost:
                    total_comparison_cost += comparison_cost

        vms_data.append(vm_data)

    # Build summary based on comparison provider
    summary = {
        "total_vms": len(vms),
        "total_cores": sum(vm.cores for vm in vms),
        "total_ram_mb": sum(vm.ram_mb for vm in vms),
        "total_storage_gb": sum(vm.storage_gb for vm in vms),
        "total_gpus": sum(vm.gpu_count for vm in vms),
        "total_cost_openstack": round(total_os_cost, 2),
    }

    if comparison_provider != "none":
        if comparison_provider == "cheapest":
            summary.update(
                {
                    "best_provider": best_provider,
                    f"total_cost_{comparison_provider}": round(total_comparison_cost, 2)
                    if total_comparison_cost and total_comparison_cost > 0
                    else None,
                    "total_savings": round(total_comparison_cost - total_os_cost, 2)
                    if total_comparison_cost and total_comparison_cost > 0
                    else None,
                }
            )
        else:
            summary.update(
                {
                    f"total_cost_{comparison_provider}": round(total_comparison_cost, 2)
                    if total_comparison_cost > 0
                    else None,
                    "total_savings": round(total_comparison_cost - total_os_cost, 2)
                    if total_comparison_cost > 0
                    else None,
                }
            )

    report = {
        "timestamp": datetime.now().isoformat(),
        "comparison_provider": comparison_provider,
        "vms": vms_data,
        "summary": summary,
    }

    return json.dumps(report, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze OpenStack environment and generate cost reports"
    )
    parser.add_argument(
        "vm_regex",
        nargs="?",
        default=None,
        help='Regular expression to filter VMs by name (e.g., "web-.*", "gpu.*")',
    )
    parser.add_argument(
        "--cloud",
        default="software",
        help="OpenStack cloud name (default: software)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json", "all"],
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
        default="cheapest",
        help='Cloud provider to compare costs against (e.g., aws, gce, azure, linode; default: cheapest, use "none" to hide comparison columns)',
    )

    args = parser.parse_args()

    print(f"Connecting to OpenStack cloud: {args.cloud}", file=sys.stderr)

    # Load provider pricing from pricing.csv
    print("Loading prices from pricing.csv", file=sys.stderr)
    provider_pricing = load_all_pricing_data()

    # List VMs
    print(
        f"Listing VMs" + (f" matching: {args.vm_regex}" if args.vm_regex else ""),
        file=sys.stderr,
    )
    vms = list_vms(args.cloud, args.vm_regex if args.vm_regex else None)

    if not vms:
        print("No VMs found matching the criteria", file=sys.stderr)
        sys.exit(0)

    # Populate comparison costs for each VM
    populate_vm_comparison_costs(vms, provider_pricing, args.comparison)

    # Generate reports
    formats = ["table", "csv", "json"] if args.format == "all" else [args.format]

    output_data = {}
    for fmt in formats:
        if fmt == "table":
            output_data["table"] = generate_table_report(
                vms, args.comparison, provider_pricing
            )
        elif fmt == "csv":
            output_data["csv"] = generate_csv_report(
                vms, args.comparison, provider_pricing
            )
        elif fmt == "json":
            output_data["json"] = generate_json_report(
                vms, provider_pricing, args.comparison
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
