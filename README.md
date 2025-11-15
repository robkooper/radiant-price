# Radiant Price - OpenStack Cloud Cost Analyzer

Compare OpenStack VM costs across multiple cloud providers (AWS, GCP, Azure, Linode, Hetzner, Vultr, DigitalOcean).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Analyze all VMs in a cloud
python3 estimate.py --cloud software

# Filter specific VMs (supports multiple patterns)
python3 estimate.py "software-dev-.*" --cloud software

# Compare with cheapest alternative provider
python3 estimate.py --cloud software --comparison cheapest

# Export to CSV
python3 estimate.py --cloud software --format csv --output report.csv
```

## Example Output

```bash
$ python3 estimate.py "software-.*" --cloud software --comparison cheapest
```

| VM Name | Flavor | Cores | RAM (GB) | Storage (GB) | OS Cost | HETZNER Flavor | HETZNER Cost | Savings |
|---|---|---|---|---|---|---|---|---|
| software-controlplane-01 | gp.medium | 2 | 8 | 40 | $   15.66 | ccx13 | $   17.09 | $    1.43 |
| software-controlplane-02 | gp.medium | 2 | 8 | 40 | $   15.66 | ccx13 | $   17.09 | $    1.43 |
| software-controlplane-03 | gp.medium | 2 | 8 | 40 | $   15.66 | ccx13 | $   17.09 | $    1.43 |
| software-worker-01 | gp.large | 4 | 16 | 80 + 228 | $   63.24 | ccx23 | $   44.99 | $  -18.25 |
| software-worker-02 | gp.large | 4 | 16 | 80 + 270 | $   69.12 | ccx23 | $   47.09 | $  -22.03 |
| software-worker-03 | gp.large | 4 | 16 | 80 + 228 | $   63.24 | ccx23 | $   44.99 | $  -18.25 |
| software-worker-04 | gp.large | 4 | 16 | 80 + 101 | $   45.46 | ccx23 | $   38.64 | $   -6.82 |
| software-worker-05 | gp.large | 4 | 16 | 80 + 8 | $   32.44 | ccx23 | $   33.99 | $    1.55 |
| software-worker-06 | gp.xlarge | 8 | 32 | 80 + 486 | $  119.48 | ccx33 | $   84.39 | $  -35.09 |
| software-worker-07 | gp.xlarge | 8 | 32 | 80 + 370 | $  103.24 | ccx33 | $   78.59 | $  -24.65 |
| **TOTAL** |  | 42 | 168 | 680 + 1691 | $  543.20 |  | $  423.95 | $ -119.25 |

## Features

- **Multi-Cloud Comparison**: Compare costs across AWS, GCP, Azure, Linode, Hetzner, Vultr, and DigitalOcean
- **Automatic Flavor Matching**: Intelligently matches OpenStack flavors to equivalent cloud instances
- **GPU Support**: Detects and prices A100, V100, and other GPU configurations
- **Multiple Output Formats**: Table, CSV, JSON, or all formats at once
- **Regex Filtering**: Filter VMs by name patterns (supports multiple patterns)
- **Cost Breakdown**: Per-VM and aggregate monthly cost calculations

## Usage

### Basic Commands

```bash
# List all VMs with OpenStack pricing
python3 estimate.py --cloud software

# Compare specific VMs against AWS
python3 estimate.py "web-.*" "api-.*" --cloud software --comparison aws

# Find the cheapest provider alternative
python3 estimate.py --cloud software --comparison cheapest

# Skip provider comparison
python3 estimate.py --cloud software --comparison none
```

### Output Formats

```bash
# Default: Table output to console
python3 estimate.py --cloud software

# CSV format
python3 estimate.py --cloud software --format csv --output costs.csv

# JSON format
python3 estimate.py --cloud software --format json --output costs.json

# Generate all formats at once
python3 estimate.py --cloud software --format all --output report
# Creates: report.table, report.csv, report.json
```

### Available Comparison Providers

- `cheapest` - Automatically finds the cheapest alternative (excludes OpenStack)
- `aws` - Amazon Web Services
- `gcp` - Google Cloud Platform
- `azure` - Microsoft Azure
- `linode` - Linode
- `hetzner` - Hetzner Cloud
- `vultr` - Vultr
- `digitalocean` - DigitalOcean
- `none` - No comparison, OpenStack pricing only

## Requirements

- Python 3.7+
- OpenStack CLI (`openstack` command)
- Configured `~/.config/openstack/clouds.yaml`

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

All pricing data is stored in `pricing.csv`. This file contains:
- OpenStack flavor definitions and pricing
- Cloud provider instance types matched to OpenStack flavors
- Storage pricing for each provider

### Update Pricing Data

```bash
# Update specific provider pricing
python3 update.py aws

# Preview changes before applying
python3 update.py aws --dry-run

# Update all providers
python3 update.py all
```

## GPU Detection

The tool automatically detects GPUs from VM names:
- **A100**: Matches `a100`, `a_100` in VM names
- **V100**: Matches `v100`, `v_100` in VM names
- **Count parsing**: `gpu.a100.x2` → 2× A100 GPUs

GPU cores are tracked separately and NOT counted as CPU cores to avoid double-counting.

## Project Structure

```
radiant-price/
├── estimate.py          # Main analysis tool
├── update.py            # Pricing data updater
├── pricing.csv          # Central pricing database
├── requirements.txt     # Python dependencies
└── providers/           # Cloud provider pricing modules
    ├── matcher.py       # Flavor matching logic
    ├── aws.py          # AWS pricing fetcher
    ├── gcp.py          # GCP pricing fetcher
    ├── azure.py        # Azure pricing fetcher
    ├── linode.py       # Linode pricing fetcher
    ├── hetzner.py      # Hetzner pricing fetcher
    ├── vultr.py        # Vultr pricing fetcher
    └── digitalocean.py # DigitalOcean pricing fetcher
```

## Advanced Examples

### Batch Processing

```bash
# Analyze multiple clouds
for cloud in aifarms cori clowder software; do
    python3 estimate.py --cloud $cloud --format csv --output "reports/${cloud}.csv"
done
```

### Cost Monitoring

```bash
# Get total monthly cost as JSON
python3 estimate.py --cloud software --format json | \
    jq '.summary.openstack_total'
```

### Filter by Pattern

```bash
# Production VMs only
python3 estimate.py "^prod-.*" --cloud software

# Multiple patterns (matches ANY)
python3 estimate.py "web-.*" "api-.*" "db-.*" --cloud software

# GPU VMs only
python3 estimate.py ".*gpu.*|.*a100.*|.*v100.*" --cloud software
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive guide for AI assistants and developers
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guide for adding new cloud providers
- **[QUICKSTART.md](QUICKSTART.md)** - Quick reference guide

## Troubleshooting

**Error: pricing.csv not found**
```bash
# Ensure you're in the correct directory
cd /path/to/radiant-price
ls pricing.csv
```

**Error: OpenStack connection failed**
```bash
# Test OpenStack CLI connectivity
openstack --os-cloud=software server list

# Check your clouds.yaml configuration
cat ~/.config/openstack/clouds.yaml
```

**VMs not found**
```bash
# Verify VM names in OpenStack
openstack --os-cloud=software server list | grep "your-pattern"

# Try without regex filter first
python3 estimate.py --cloud software
```

## License

Internal use at NCSA.

## Support

For issues or questions, see the documentation files above or contact the development team.
