# Configuration Guide

## Pricing Configuration

### OpenStack Pricing (from usage.sh)

The tool reads pricing from the `PRICING` dictionary in `openstack_analyzer.py`. The default values match your organization's structure:

```python
PRICING = {
    'instance': 5.46,    # V - per instance per month
    'core': 5.03,        # C - per core per month (excluding GPU cores)
    'flash': 0.14,       # F - per GB storage per month
    'floating_ip': 0.42, # P - per floating IP per month
    'a100': 546.45,      # GA - per A100 GPU per month
    'v100': 291.34,      # GV - per V100 GPU per month
}
```

### GPU Specifications

GPU core counts are defined in:

```python
GPU_SPECS = {
    'a100': {'cores': 24, 'name': 'A100'},
    'v100': {'cores': 8, 'name': 'V100'},
}
```

These are used to avoid double-counting GPU cores as regular CPU cores.

## AWS Pricing Configuration

### Instance Pricing Table

Located in `aws_pricing.py`, the `AWS_INSTANCE_PRICING` dictionary contains hourly rates for EC2 instances:

```python
AWS_INSTANCE_PRICING = {
    't3.micro': {'vcpu': 1, 'memory_gb': 1, 'hourly': 0.0104},
    't3.small': {'vcpu': 2, 'memory_gb': 2, 'hourly': 0.0208},
    # ... more instances ...
    'p4d.24xlarge': {'vcpu': 96, 'memory_gb': 1152, 'gpu': {'type': 'A100', 'count': 8}, 'hourly': 32.77},
}
```

Supported instance families:
- **T3**: Burstable general-purpose (t3.micro through t3.2xlarge)
- **M5**: General-purpose (m5.large through m5.4xlarge)
- **C5**: Compute-optimized (c5.large through c5.4xlarge)
- **P3**: GPU instances with V100s (p3.2xlarge through p3.16xlarge)
- **P4D**: GPU instances with A100s (p4d.24xlarge)

### Storage Costs

EBS storage in AWS is estimated at:
- **gp3 (General Purpose)**: $0.10/GB/month
- Modify in the `estimate_aws_cost_by_specs()` function if needed

### Resource-Based AWS Pricing

For instances without a specific match, resource-based pricing is used:

```python
# Approximate AWS on-demand pricing (hourly)
vCPU:         $0.0535/hour  → $39.05/month
GB Memory:    $0.0059/hour  → $4.31/month
EBS Storage:  $0.10/GB/month
GPU A100:     $4.08/hour    → $2,978.40/month
GPU V100:     $2.48/hour    → $1,810.40/month
```

## Customizing for Your Environment

### Scenario 1: Your OpenStack Has Different Pricing

Edit the `PRICING` dictionary:

```python
PRICING = {
    'instance': 8.00,      # If your instance cost is $8/month
    'core': 7.50,          # If your core cost is $7.50/month
    'flash': 0.20,         # If your storage cost is $0.20/GB
    'floating_ip': 0.50,   # Etc.
    'a100': 600.00,
    'v100': 300.00,
}
```

Then run the tool - it will automatically use these new prices.

### Scenario 2: Adding Support for Different GPU Types

1. Add to `GPU_SPECS`:
```python
GPU_SPECS = {
    'a100': {'cores': 24, 'name': 'A100'},
    'v100': {'cores': 8, 'name': 'V100'},
    't4': {'cores': 1, 'name': 'T4'},  # Add T4 GPU
    'h100': {'cores': 40, 'name': 'H100'},  # Add H100 GPU
}
```

2. Add pricing:
```python
PRICING = {
    # ... existing prices ...
    't4': 35.00,        # T4 GPU cost per month
    'h100': 800.00,     # H100 GPU cost per month
}
```

3. Update detection in `detect_gpu()` function:
```python
gpu_patterns = {
    'a100': r'a100|a_100',
    'v100': r'v100|v_100',
    't4': r't4|tesla.?4',  # New pattern
    'h100': r'h100|hopper',  # New pattern
    'gpu': r'gpu',
}
```

### Scenario 3: Using Real-Time AWS Pricing

The tool has infrastructure to fetch real AWS pricing. To enable:

1. Use the `--aws-pricing` flag when running:
```bash
python openstack_analyzer.py cori --aws-pricing
```

2. This will attempt to fetch from AWS pricing API (may be slow)

3. Update `fetch_aws_pricing()` and `fetch_real_aws_pricing()` functions for your use case

### Scenario 4: Adding More AWS Instance Types

Edit `aws_pricing.py` and add to `AWS_INSTANCE_PRICING`:

```python
AWS_INSTANCE_PRICING = {
    # ... existing instances ...

    # Custom instances for your needs
    'r6i.2xlarge': {
        'vcpu': 8,
        'memory_gb': 64,
        'hourly': 0.60
    },
    'm6a.4xlarge': {
        'vcpu': 16,
        'memory_gb': 64,
        'hourly': 0.765
    },
}
```

The tool will then consider these instances when matching OpenStack VMs to AWS equivalents.

## Cloud-Specific Configuration

Different OpenStack clouds may have different GPU configurations. The original `usage.sh` handles this:

```bash
# GPUS
A100=0
V100=0
if [ "$OS_CLOUD" == "cori" ]; then
  A100=13
elif [ "$OS_CLOUD" == "clowder" ]; then
  A100=1
elif [ "$OS_CLOUD" == "mmli" ]; then
  V100=1
fi
```

If you want cloud-specific configuration:

1. Create a config file per cloud (optional):
```
configs/
├── aifarms.py
├── cori.py
├── clowder.py
└── ...
```

2. Or add conditionals to the main script:
```python
# In openstack_analyzer.py
if args.cloud == 'cori':
    PRICING['a100'] = 550.00  # Cori-specific pricing
elif args.cloud == 'mmli':
    PRICING['v100'] = 295.00  # MMLI-specific pricing
```

## Performance Tuning

### Reducing VM Discovery Time

If you have hundreds of VMs:

1. Use regex filtering to reduce the number analyzed:
```bash
python openstack_analyzer.py aifarms --vm-regex "^prod-"
```

2. Note: The tool calls `openstack server show` for each VM. This is the bottleneck for large deployments.

### Caching Results

For repeated analysis, save results and process offline:

```bash
# Run once
python openstack_analyzer.py cori --format json --output cori_snapshot.json

# Analyze multiple times without querying OpenStack
cat cori_snapshot.json | jq '.vms | length'  # Count VMs
cat cori_snapshot.json | jq '.summary'  # Get summary
```

## Debugging

### Enable Verbose Output

The tool prints status messages to stderr. Run with standard output redirection:

```bash
python openstack_analyzer.py cori --format table > report.txt 2> debug.log
```

### Check OpenStack Connectivity

Before running the tool:

```bash
# Test OpenStack CLI
openstack --os-cloud=cori server list

# Test specific cloud
openstack --os-cloud=aifarms flavor list
```

If these fail, the analyzer won't work either.

### Validate GPU Detection

Create a test script:

```python
from openstack_analyzer import detect_gpu

test_names = [
    'web-001',
    'gpu-ml-01',
    'a100-server',
    'gpu.a100.x2',
    'v100-training',
    'compute-1'
]

for name in test_names:
    gpu_type, gpu_count = detect_gpu(name)
    print(f"{name}: {gpu_type} × {gpu_count}")
```

Expected output:
```
web-001: None × 0
gpu-ml-01: GPU × 1
a100-server: A100 × 1
gpu.a100.x2: A100 × 2
v100-training: V100 × 1
compute-1: None × 0
```

## Environment Variables

The tool respects these environment variables (passed to OpenStack CLI):

- `OS_CLOUD`: Overrides the cloud argument (not recommended)
- `OS_AUTH_URL`: OpenStack authentication endpoint
- `OS_PROJECT_NAME`: Project to analyze

Example:
```bash
export OS_PROJECT_NAME="my-project"
python openstack_analyzer.py aifarms
```

## Integration with CI/CD

### Generate Reports on Schedule

```bash
#!/bin/bash
# cron job to generate reports daily

cd /path/to/rate-calc

for cloud in aifarms cori clowder gies mark software mmli; do
    timestamp=$(date +%Y%m%d_%H%M%S)
    python openstack_analyzer.py $cloud \
        --format all \
        --output "../reports/${timestamp}_${cloud}"
done

# Optionally upload to storage
aws s3 sync ../reports s3://my-bucket/openstack-reports/
```

### Parse Reports in Scripts

```bash
#!/bin/bash
# Check if any VM exceeds cost threshold

REPORT_JSON="report.json"
THRESHOLD=1000

total=$(jq '.summary.total_cost_openstack' $REPORT_JSON)

if (( $(echo "$total > $THRESHOLD" | bc -l) )); then
    echo "WARNING: OpenStack costs exceed threshold ($total > $THRESHOLD)"
    # Send alert, create ticket, etc.
fi
```

### Integration with Monitoring Systems

Export to systems like Prometheus, Datadog, etc:

```python
# Convert JSON report to Prometheus metrics
import json

with open('report.json') as f:
    data = json.load(f)

for vm in data['vms']:
    print(f"openstack_vm_cost{'{name=\"' + vm['name'] + '\"}'} {vm['costs']['openstack_monthly']}")

print(f"openstack_total_cost {data['summary']['total_cost_openstack']}")
```

## Troubleshooting Configuration Issues

### GPU Detection Not Working

1. Check VM name format in OpenStack:
```bash
openstack server list | grep -i gpu
```

2. Verify patterns in `GPU_SPECS` match your naming

3. Debug by running:
```python
from openstack_analyzer import detect_gpu
print(detect_gpu("your-vm-name"))
```

### Costs Seem Wrong

1. Verify pricing values:
```python
from openstack_analyzer import PRICING
print(PRICING)
```

2. Manual calculation:
   - Check VM cores, storage, GPU count
   - Calculate: cores × $5.03 + storage × $0.14 + gpu_count × gpu_price
   - Compare with reported cost

3. Check for floating IPs adding cost

### AWS Pricing Not Available

1. The tool includes hardcoded AWS pricing as fallback
2. To fetch real pricing, ensure internet access
3. Check if AWS API is available:
```bash
curl -I https://pricing.aws.amazon.com/pricing/us/index.json
```

---

Last Updated: November 13, 2024
