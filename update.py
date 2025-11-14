#!/usr/bin/env python3
"""
Update cloud provider pricing in pricing.csv.

Fetches current pricing from cloud provider APIs and matches OpenStack flavors
to the cheapest available instances, updating pricing.csv with the results.

Usage:
    python3 update.py aws              # Update AWS pricing
    python3 update.py aws --dry-run    # Preview changes
    python3 update.py all              # Update all providers
    python3 update.py aws gcp azure    # Update multiple providers

Supported providers: aws, gcp, azure, linode, vultr, hetzner, digitalocean
"""

import argparse
import sys
from pathlib import Path


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
)
from providers.matcher import (
    find_matches,
    load_openstack_flavors,
    update_csv_with_matches,
)

PROVIDERS = {
    "aws": {"fetch": fetch_aws_pricing, "storage_price": 0.10},
    "linode": {"fetch": fetch_linode_pricing, "storage_price": 0.05},
    "azure": {"fetch": fetch_azure_pricing, "storage_price": 0.05},
    "gcp": {"fetch": fetch_gcp_pricing, "storage_price": 0.04},
    "vultr": {"fetch": fetch_vultr_pricing, "storage_price": 0.05},
    "hetzner": {"fetch": fetch_hetzner_pricing, "storage_price": 0.05},
    "digitalocean": {"fetch": fetch_digitalocean_pricing, "storage_price": 0.10},
}


def main():
    parser = argparse.ArgumentParser(
        description="Update cloud provider pricing in pricing.csv",
        epilog="""
Examples:
  python3 update.py aws              # Update AWS pricing
  python3 update.py aws --dry-run    # Preview changes
  python3 update.py all              # Update all providers
  python3 update.py aws gcp azure    # Update multiple providers

Supported providers: aws, gcp, azure, linode, vultr, hetzner, digitalocean
        """,
    )

    parser.add_argument(
        "providers",
        nargs="*",
        default=["all"],
        help="Providers to update (default: all)",
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

    args = parser.parse_args()

    # Validate CSV exists
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: {args.csv} not found", file=sys.stderr)
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
