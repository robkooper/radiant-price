#!/usr/bin/env python3
"""
Update cloud provider pricing in pricing.csv.

Fetches current pricing from cloud provider APIs and matches OpenStack flavors
to the cheapest available instances, updating pricing.csv with the results.

Usage:
    python3 update.py openstack --core 5.03 --flash 0.14 --a100 546.45 --v100 291.34
    python3 update.py openstack --core 5.03 --flash 0.14 --dry-run
    python3 update.py aws                          # Update AWS pricing
    python3 update.py aws --dry-run                # Preview changes
    python3 update.py all                          # Update all providers
    python3 update.py aws gcp azure                # Update multiple providers

Supported providers: aws, gcp, azure, linode, vultr, hetzner, digitalocean
Special: openstack [--core PRICE] [--flash PRICE] [--a100 PRICE] [--v100 PRICE]
         Update OpenStack pricing by flavor type (only update specified flags)
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Tuple


# Color codes for terminal output
class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


from providers import (
    fetch_aws_pricing,
    fetch_azure_pricing,
    fetch_digitalocean_pricing,
    fetch_gcp_pricing,
    fetch_hetzner_pricing,
    fetch_linode_pricing,
    fetch_vultr_pricing,
    get_aws_storage_price,
    get_digitalocean_storage_price,
    get_gcp_storage_price,
    get_hetzner_storage_price,
    get_linode_storage_price,
    get_vultr_storage_price,
)
from providers.matcher import (
    find_matches,
    load_openstack_flavors,
    update_csv_with_matches,
)

PROVIDERS = {
    "aws": {"fetch": fetch_aws_pricing, "storage_price": get_aws_storage_price},
    "linode": {
        "fetch": fetch_linode_pricing,
        "storage_price": get_linode_storage_price,
    },
    "azure": {"fetch": fetch_azure_pricing, "storage_price": 0.05},
    "gcp": {"fetch": fetch_gcp_pricing, "storage_price": get_gcp_storage_price},
    "vultr": {"fetch": fetch_vultr_pricing, "storage_price": get_vultr_storage_price},
    "hetzner": {
        "fetch": fetch_hetzner_pricing,
        "storage_price": get_hetzner_storage_price,
    },
    "digitalocean": {
        "fetch": fetch_digitalocean_pricing,
        "storage_price": get_digitalocean_storage_price,
    },
}


def update_openstack_pricing(
    csv_file: str,
    core_price: float = None,
    flash_price: float = None,
    a100_price: float = None,
    v100_price: float = None,
    dry_run: bool = False,
) -> Tuple[int, list]:
    """
    Update OpenStack pricing in CSV by flavor type.

    Args:
        csv_file: Path to pricing.csv
        core_price: New compute price per month for CPU flavors (None to skip)
        flash_price: New storage price per GB for flash flavor (None to skip)
        a100_price: New monthly price for A100 GPU flavor (None to skip)
        v100_price: New monthly price for V100 GPU flavor (None to skip)
        dry_run: If True, don't write file

    Returns:
        Tuple of (number updated, list of changes)
    """
    rows = []
    fieldnames = []

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        rows = list(reader)

    changes = []

    for row in rows:
        if row["Cloud"].strip().lower() != "openstack":
            continue

        flavor = row["Flavor"].strip().lower()

        # Determine which price to apply based on flavor
        new_price = None
        field_name = "Compute_Price_Per_Month"

        if flavor == "flash" and flash_price is not None:
            new_price = f"{flash_price:.2f}"
            field_name = "Storage_Price_Per_GB_Per_Month"
        elif "a100" in flavor and a100_price is not None:
            new_price = f"{a100_price:.2f}"
            field_name = "Compute_Price_Per_Month"
        elif "v100" in flavor and v100_price is not None:
            new_price = f"{v100_price:.2f}"
            field_name = "Compute_Price_Per_Month"
        elif (
            not flavor.startswith("gpu.")
            and "a100" not in flavor
            and "v100" not in flavor
            and flavor != "floating_ip"
            and core_price is not None
        ):
            new_price = f"{core_price:.2f}"
            field_name = "Compute_Price_Per_Month"

        # Apply the price update if determined
        if new_price is not None:
            old_value = row.get(field_name, "")
            if old_value != new_price:
                changes.append(
                    {
                        "flavor": row["Flavor"].strip(),
                        "field": field_name,
                        "old_value": old_value,
                        "new_value": new_price,
                    }
                )
                row[field_name] = new_price

    if not dry_run and changes:
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return len(changes), changes


def main():
    parser = argparse.ArgumentParser(
        description="Update cloud provider pricing in pricing.csv",
        epilog="""
Examples:
  python3 update.py openstack --core 5.03 --flash 0.14 --a100 546.45 --v100 291.34
  python3 update.py openstack --core 5.03 --dry-run
  python3 update.py aws                          # Update AWS pricing
  python3 update.py aws --dry-run                # Preview changes
  python3 update.py all                          # Update all providers
  python3 update.py aws gcp azure                # Update multiple providers

Supported providers: aws, gcp, azure, linode, vultr, hetzner, digitalocean
Special: openstack [--core PRICE] [--flash PRICE] [--a100 PRICE] [--v100 PRICE]
         Update OpenStack pricing by flavor type (only updates specified flags)
        """,
    )

    parser.add_argument(
        "providers",
        nargs="*",
        default=[],
        help="Providers to update (use 'openstack' for OpenStack pricing)",
    )
    parser.add_argument(
        "--csv",
        default="pricing.csv",
        help="Path to pricing.csv file (default: pricing.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating file",
    )
    # OpenStack-specific options
    parser.add_argument(
        "--core",
        type=float,
        default=None,
        help="OpenStack CPU flavor price per month",
    )
    parser.add_argument(
        "--flash",
        type=float,
        default=None,
        help="OpenStack flash storage price per GB per month",
    )
    parser.add_argument(
        "--a100",
        type=float,
        default=None,
        help="OpenStack A100 GPU flavor price per month",
    )
    parser.add_argument(
        "--v100",
        type=float,
        default=None,
        help="OpenStack V100 GPU flavor price per month",
    )

    args = parser.parse_args()

    # Validate CSV exists
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: {args.csv} not found", file=sys.stderr)
        sys.exit(1)

    # Handle OpenStack special case
    if args.providers and args.providers[0].lower() == "openstack":
        # Check if any OpenStack options are provided
        if not any([args.core, args.flash, args.a100, args.v100]):
            print(
                "Error: openstack requires at least one price option (--core, --flash, --a100, --v100)",
                file=sys.stderr,
            )
            sys.exit(1)

        print("=" * 80)
        print("OpenStack Pricing Updater")
        print("=" * 80)
        print()

        updated, changes = update_openstack_pricing(
            args.csv,
            core_price=args.core,
            flash_price=args.flash,
            a100_price=args.a100,
            v100_price=args.v100,
            dry_run=args.dry_run,
        )

        if not changes:
            print("[OPENSTACK] No changes needed")
        else:
            # Group changes by field type
            compute_changes = [
                c for c in changes if c["field"] == "Compute_Price_Per_Month"
            ]
            storage_changes = [
                c for c in changes if c["field"] == "Storage_Price_Per_GB_Per_Month"
            ]

            if compute_changes:
                print(
                    f"[OPENSTACK] Compute Price Updates ({len(compute_changes)} flavors):"
                )
                for change in compute_changes:
                    old = f"{Color.RED}${float(change['old_value']):>8.2f}{Color.RESET}"
                    new = (
                        f"{Color.GREEN}${float(change['new_value']):>8.2f}{Color.RESET}"
                    )
                    print(f"         {change['flavor']:25s} {old} → {new}")

            if storage_changes:
                print(
                    f"[OPENSTACK] Storage Price Updates ({len(storage_changes)} flavors):"
                )
                for change in storage_changes:
                    old = f"{Color.RED}${float(change['old_value']):>7.2f}{Color.RESET}"
                    new = (
                        f"{Color.GREEN}${float(change['new_value']):>7.2f}{Color.RESET}"
                    )
                    print(f"         {change['flavor']:25s} {old}/GB → {new}/GB")

        print()
        print("=" * 80)
        if args.dry_run:
            print(f"DRY RUN - no changes written to {args.csv}")
        else:
            print(f"✓ Updated {args.csv}")
        print("=" * 80)
        return

    # Handle cloud provider updates
    if not args.providers:
        print(
            "Error: No providers specified. Use 'all' or list specific providers",
            file=sys.stderr,
        )
        sys.exit(1)

    # Determine which providers to update
    if args.providers == ["all"]:
        providers_to_update = list(PROVIDERS.keys())
    else:
        providers_to_update = []
        for p in args.providers:
            p_lower = p.lower()
            if p_lower in PROVIDERS:
                providers_to_update.append(p_lower)
            else:
                print(f"Warning: Unknown provider '{p}'", file=sys.stderr)

        if not providers_to_update:
            print(
                f"Error: No valid providers specified. Valid options: {', '.join(PROVIDERS.keys())}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Load OpenStack flavors
    flavors = load_openstack_flavors(args.csv)
    if not flavors:
        print("Error: No OpenStack flavors found in CSV", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("Cloud Provider Pricing Updater")
    print("=" * 80)
    print()

    # Process each provider
    total_added = 0
    for provider in providers_to_update:
        # Fetch pricing
        fetch_func = PROVIDERS[provider]["fetch"]
        provider_pricing = fetch_func()

        if not provider_pricing:
            print(f"[{provider.upper()}] ✗ Failed to fetch pricing\n")
            continue

        # Find matches
        matches = find_matches(flavors, provider_pricing)

        if not matches:
            print(f"[{provider.upper()}] ✗ No matches found\n")
            continue

        # Update CSV
        storage_price = PROVIDERS[provider]["storage_price"]
        # If storage_price is callable (function), call it to get the price
        if callable(storage_price):
            storage_price = storage_price()
        added, changes = update_csv_with_matches(
            args.csv,
            provider,
            matches,
            provider_pricing,
            storage_price,
            args.dry_run,
        )

        # Display results
        print(f"[{provider.upper()}] Fetched {len(provider_pricing)} instances")
        print(f"         Found {len(matches)} matches")

        if not changes:
            print(f"         No changes")
        else:
            for change in changes:
                if change["old_instance"] is None:
                    # New entry
                    print(
                        f"         {Color.GREEN}+{Color.RESET} {change['flavor']:25s} → {change['new_instance']:25s} ${change['new_price']:>10.2f}/mo"
                    )
                else:
                    # Changed entry
                    if change["old_instance"] != change["new_instance"]:
                        old_inst = f"{Color.RED}{change['old_instance']}{Color.RESET}"
                        new_inst = f"{Color.GREEN}{change['new_instance']}{Color.RESET}"
                        old_price = (
                            f"{Color.RED}${change['old_price']:>10.2f}{Color.RESET}"
                        )
                        new_price = (
                            f"{Color.GREEN}${change['new_price']:>10.2f}{Color.RESET}"
                        )
                        print(
                            f"         ✓ {change['flavor']:25s} {old_inst:40s}→{new_inst:35s} {old_price}→{new_price}"
                        )
                    elif change["old_price"] != change["new_price"]:
                        old_price = (
                            f"{Color.RED}${change['old_price']:>10.2f}{Color.RESET}"
                        )
                        new_price = (
                            f"{Color.GREEN}${change['new_price']:>10.2f}{Color.RESET}"
                        )
                        print(
                            f"         ✓ {change['flavor']:25s} {change['new_instance']:20s} {old_price}→{new_price}"
                        )

        total_added += added
        print()

    print("=" * 80)
    if args.dry_run:
        print(f"DRY RUN - no changes written to {args.csv}")
    else:
        print(f"✓ Updated {args.csv}")
    print("=" * 80)


if __name__ == "__main__":
    main()
