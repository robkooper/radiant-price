# OpenStack Environment Analyzer

A comprehensive tool for analyzing OpenStack cloud environments and generating detailed cost reports with AWS pricing comparisons.

## Features

- **VM Discovery & Filtering**: List all VMs in an OpenStack environment, with optional regex filtering
- **Resource Tracking**: Automatically extract CPU cores, RAM, storage, and GPU information
- **GPU Detection**: Intelligently detects GPUs (A100, V100) in VM names and handles them separately from CPU cores
- **Cost Analysis**:
  - Calculate OpenStack monthly costs based on your organization's pricing structure
  - Compare with equivalent AWS EC2 costs
  - Show per-VM and aggregate costs
- **Multiple Output Formats**: Table (terminal), CSV, JSON, or generate all formats at once
- **AWS Pricing Integration**: Pull real AWS pricing data and compare equivalent instance types
- **Dual Cost Models**:
  - Instance-based pricing (match to specific AWS instance types)
  - Resource-based pricing (calculate from raw vCPU/memory/GPU costs)

## Requirements

- Python 3.7+
- OpenStack CLI (`openstack` command available)
- Configured OpenStack credentials/clouds.yaml

### Python Dependencies

```bash
pip install -r requirements.txt
```

Dependencies:
- `requests`: For AWS pricing API calls
- `tabulate`: For formatted table output
- `openstacksdk`: Optional, for direct OpenStack API access

## Installation

```bash
# Clone or download the repository
cd rate-calc

# Install dependencies
pip install -r requirements.txt

# Make script executable (optional)
chmod +x openstack_analyzer.py
```

## Usage

### Basic Usage

```bash
# Analyze all VMs in a cloud
python openstack_analyzer.py aifarms

# List VMs matching a regex pattern
python openstack_analyzer.py aifarms --vm-regex "web-.*"
python openstack_analyzer.py cori --vm-regex "gpu.*"
```

### Output Formats

```bash
# Default: Pretty table output
python openstack_analyzer.py aifarms

# CSV format
python openstack_analyzer.py aifarms --format csv

# JSON format
python openstack_analyzer.py aifarms --format json

# Generate all formats
python openstack_analyzer.py aifarms --format all
```

### Saving Reports

```bash
# Save to file
python openstack_analyzer.py aifarms --output report

# With all formats, creates: report.table, report.csv, report.json
python openstack_analyzer.py aifarms --format all --output report
```

### AWS Pricing

```bash
# Include AWS pricing comparison (uses cached pricing by default)
python openstack_analyzer.py aifarms

# Attempt to fetch fresh AWS pricing data (requires internet)
python openstack_analyzer.py aifarms --aws-pricing
```

### Complete Example

```bash
python openstack_analyzer.py cori \
    --vm-regex "gpu.*" \
    --format all \
    --output cori_gpu_analysis \
    --aws-pricing
```

This generates:
- `cori_gpu_analysis.table` - ASCII table
- `cori_gpu_analysis.csv` - Spreadsheet-ready format
- `cori_gpu_analysis.json` - Machine-readable format

## Pricing Configuration

The tool uses pricing from `usage.sh` in the parent directory:

```
Instance (V):       $5.46/month per instance
Core (C):           $5.03/month per core
Flash Storage (F):  $0.14/month per GB
Floating IP (P):    $0.42/month per IP
GPU A100 (GA):      $546.45/month per GPU
GPU V100 (GV):      $291.34/month per GPU
```

### Customizing Pricing

Edit the `PRICING` dictionary at the top of `openstack_analyzer.py`:

```python
PRICING = {
    'instance': 5.46,    # Your instance cost
    'core': 5.03,        # Your core cost
    'flash': 0.14,       # Your storage cost
    # ... etc
}
```

## GPU Detection

The tool automatically detects GPUs by looking for keywords in VM names:

- **A100 GPUs**: Names containing `a100` or `a_100` → matched as A100
- **V100 GPUs**: Names containing `v100` or `v_100` → matched as V100
- **Generic GPU**: Names containing `gpu` → marked as GPU

For GPU instances named like `gpu.a100.x2`, the tool:
1. Detects it's an A100 GPU instance with 2 GPUs
2. Doesn't double-count the GPU cores as regular CPU cores
3. Applies the correct GPU pricing

**Note**: GPU cores are NOT included in the CPU core count. A VM with 24 cores + 1 A100 GPU (24 GPU cores) shows as 24 cores, not 48.

## AWS Pricing Comparison

The tool provides two AWS pricing comparison methods:

### 1. Instance-Based Pricing (Default)
Matches your OpenStack VMs to equivalent AWS EC2 instance types:
- Looks for instance types with similar vCPU and memory
- Shows the exact AWS instance type that would be equivalent
- Includes EBS storage costs

### 2. Resource-Based Pricing
Calculates cost from raw AWS resource pricing:
- vCPU: ~$39/month per core
- Memory: ~$4.31/month per GB
- Storage: $0.10/month per GB
- GPUs: A100 ~$2,978/month, V100 ~$1,810/month

## Output Examples

### Table Format

```
╒═════════════════════╤════════╤═══════╤═════════════╤══════════════╤═════════════════════╤═════════════════════╕
│ VM Name             │ Status │ Cores │ RAM (MB)    │ Storage (GB) │ GPU                 │ OS Cost    │ AWS Cost │
╞═════════════════════╪════════╪═══════╪═════════════╪══════════════╪═════════════════════╪════════════╪══════════╡
│ web-001             │ ACTIVE │ 4     │ 8192        │ 50           │ -                   │ $25.66     │ $45.23   │
│ gpu-ml-01           │ ACTIVE │ 8     │ 32768       │ 100          │ 1x A100             │ $546.79    │ $3,201.15│
│ cache-01            │ ACTIVE │ 2     │ 4096        │ 20           │ -                   │ $15.34     │ $18.92   │
├─────────────────────┼────────┼───────┼─────────────┼──────────────┼─────────────────────┼────────────┼──────────┤
│ TOTAL               │        │ 14    │ 45056       │ 170          │                     │ $587.79    │ $3,265.30│
└─────────────────────┴────────┴───────┴─────────────┴──────────────┴─────────────────────┴────────────┴──────────┘
```

### JSON Format

```json
{
  "timestamp": "2024-11-13T15:30:45.123456",
  "vms": [
    {
      "name": "web-001",
      "status": "ACTIVE",
      "cores": 4,
      "ram_mb": 8192,
      "storage_gb": 50,
      "gpu": null,
      "floating_ip": true,
      "costs": {
        "openstack_monthly": 25.66,
        "aws_monthly": 45.23,
        "savings_monthly": 19.57
      }
    }
  ],
  "summary": {
    "total_vms": 3,
    "total_cores": 14,
    "total_ram_mb": 45056,
    "total_storage_gb": 170,
    "total_gpus": 1,
    "total_cost_openstack": 587.79,
    "total_cost_aws": 3265.30,
    "total_savings": 2677.51
  }
}
```

### CSV Format

```csv
VM Name,Status,Cores,RAM (MB),Storage (GB),GPU Type,GPU Count,Has Floating IP,OpenStack Cost,AWS Cost,Savings
web-001,ACTIVE,4,8192,50,,0,Yes,25.66,45.23,19.57
gpu-ml-01,ACTIVE,8,32768,100,A100,1,No,546.79,3201.15,2654.36
cache-01,ACTIVE,2,4096,20,,0,No,15.34,18.92,3.58
TOTAL,,,14,45056,170,,,587.79,3265.30,2677.51
```

## Command-Line Arguments

```
usage: openstack_analyzer.py [-h] [--vm-regex VM_REGEX] [--format {table,csv,json,all}]
                             [--output OUTPUT] [--aws-pricing]
                             cloud

positional arguments:
  cloud                     OpenStack cloud name (e.g., aifarms, cori, etc.)

optional arguments:
  -h, --help                Show this help message and exit
  --vm-regex VM_REGEX       Regular expression to filter VMs by name
  --format {table,csv,json,all}
                            Output format (default: table)
  --output OUTPUT           Output file path (if not specified, prints to stdout)
  --aws-pricing             Fetch real AWS pricing data from AWS API
```

## Advanced Usage

### Filter for GPU VMs Only

```bash
python openstack_analyzer.py cori --vm-regex ".*gpu.*|.*a100.*|.*v100.*"
```

### Export for Financial Analysis

```bash
python openstack_analyzer.py aifarms --format csv --output aifarms_costs.csv
```

Then open in Excel/Google Sheets for pivot tables and analysis.

### Get JSON for Custom Processing

```bash
python openstack_analyzer.py cori --format json | jq '.summary.total_cost_openstack'
# Output: 2458.23
```

### Batch Analysis of Multiple Clouds

```bash
#!/bin/bash
for cloud in aifarms cori clowder gies mark software mmli; do
    python openstack_analyzer.py $cloud --format all --output reports/$cloud
done
```

## Troubleshooting

### "Error: Could not parse OpenStack server list"
- Verify OpenStack CLI is installed: `which openstack`
- Check cloud credentials: `openstack --os-cloud=YOUR_CLOUD server list`
- Ensure your cloud name is correct

### Missing RAM Data
The tool estimates RAM from storage size when exact RAM info isn't available. For more accurate AWS comparisons, OpenStack should provide RAM information directly.

### GPU Not Detected
- Check VM name contains `gpu`, `a100`, `v100`, `A100`, or `V100`
- For counted GPUs, use format like `gpu.a100.x2` (2 A100s)

### AWS Pricing Not Available
- The tool uses cached AWS pricing by default (included in the code)
- Use `--aws-pricing` flag to attempt to fetch fresh data
- An internet connection is required for real-time pricing

## Architecture

```
openstack_analyzer.py   - Main CLI application and report generation
aws_pricing.py          - AWS pricing data and cost calculation module
requirements.txt        - Python dependencies
```

### Key Components

1. **VM Detection**: Uses `openstack server list` and `openstack server show`
2. **Cost Calculation**:
   - OpenStack: Fixed pricing per resource type
   - AWS: Instance matching + resource-based fallback
3. **Report Generation**: Tabulate for tables, json module for JSON, csv module for CSV

## Extending the Tool

### Add More Pricing Rules

Edit the GPU_SPECS and PRICING dictionaries in `openstack_analyzer.py`.

### Custom AWS Pricing

Modify the AWS_INSTANCE_PRICING dictionary in `aws_pricing.py` to reflect your organization's AWS rate.

### Additional Metrics

The VM dataclass can be extended with additional fields:
```python
@dataclass
class VM:
    # ... existing fields ...
    network_bandwidth_mbps: int = 0
    custom_metadata: Dict = None
```

## License

This tool is provided as-is for internal use at NCSA.

## Support

For issues or enhancements, contact the development team.
