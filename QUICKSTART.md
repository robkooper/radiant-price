# Quick Start Guide

## 30-Second Setup

```bash
cd /Users/kooper/git/ncsa/rate-calc
pip install -r requirements.txt
python openstack_analyzer.py aifarms
```

That's it! You should see a table of all VMs with their costs.

## Common Commands

### See all VMs
```bash
python openstack_analyzer.py aifarms
```

### GPU VMs only
```bash
python openstack_analyzer.py cori --vm-regex ".*gpu.*"
```

### Save to CSV
```bash
python openstack_analyzer.py aifarms --format csv --output report.csv
```

### Save to JSON
```bash
python openstack_analyzer.py cori --format json --output report.json
```

### All formats at once
```bash
python openstack_analyzer.py aifarms --format all --output report
# Creates: report.table, report.csv, report.json
```

### With AWS pricing comparison
```bash
python openstack_analyzer.py cori --aws-pricing
```

## What You Get

### Table Output
```
+---+--------+-------+--------+----------+---------+--------+
| VM Name | Status | Cores | Storage | GPU | OS Cost | AWS Cost |
+---+--------+-------+--------+----------+---------+--------+
```

### CSV Output (for Excel)
```
VM Name,Status,Cores,Storage,GPU,OpenStack Cost,AWS Cost
```

### JSON Output (for automation)
```json
{
  "vms": [...],
  "summary": {
    "total_vms": 5,
    "total_cores": 20,
    "total_cost_openstack": 1243.56,
    "total_cost_aws": 2847.32
  }
}
```

## Understanding GPU Detection

The tool automatically finds VMs with GPUs in their names:

- `gpu-ml-01` → GPU detected
- `a100-server` → A100 detected (24 cores)
- `v100-training` → V100 detected (8 cores)
- `gpu.a100.x2` → 2 A100s detected
- `compute-1` → No GPU

GPU cores are **not** added to the CPU count to avoid double-counting.

## Understanding Costs

### OpenStack Cost Breakdown
```
VM with 4 cores, 50GB storage, floating IP, no GPU:
- Instance cost:     $5.46
- Core cost:         4 × $5.03 = $20.12
- Storage cost:      50 × $0.14 = $7.00
- Floating IP cost:  $0.42
- Total:             $33.00/month
```

### With A100 GPU
```
VM with 4 cores, 50GB storage, 1 A100:
- Instance cost:     $5.46
- Core cost:         4 × $5.03 = $20.12
- Storage cost:      50 × $0.14 = $7.00
- GPU cost:          1 × $546.45 = $546.45
- Total:             $579.03/month
```

**Note**: GPU cores (24 for A100, 8 for V100) are not counted in the "4 cores"

## Filter Examples

### Specific project
```bash
python openstack_analyzer.py aifarms --vm-regex "^project-"
```

### Multiple patterns
```bash
python openstack_analyzer.py cori --vm-regex "^(web|api)-"
```

### Everything except test
```bash
python openstack_analyzer.py aifarms --vm-regex "^(?!test-)"
```

## Batch Processing Multiple Clouds

```bash
#!/bin/bash
for cloud in aifarms cori clowder gies mark software mmli; do
    echo "Analyzing $cloud..."
    python openstack_analyzer.py $cloud \
        --format csv \
        --output "reports/${cloud}_$(date +%Y%m%d).csv"
done
```

## Troubleshooting

**Q: "Error: Could not parse OpenStack server list"**
- Check OpenStack CLI: `which openstack`
- Test credentials: `openstack --os-cloud=aifarms server list`

**Q: GPU not detected**
- Verify VM name contains 'gpu', 'a100', or 'v100'
- Check exact name: `openstack --os-cloud=cori server list | grep gpu`

**Q: Costs don't match manually**
- Check cores: Don't include GPU cores
- Check storage: In GB
- Check floating IPs: Each adds $0.42
- Calculate: cores × 5.03 + storage × 0.14 + gpu × price + 5.46

**Q: Need different pricing**
- Edit PRICING dict in openstack_analyzer.py
- See CONFIG.md for details

## Integration Examples

### Get total cost for alerting
```bash
python openstack_analyzer.py cori --format json | \
  jq '.summary.total_cost_openstack'
```

### Check if exceeds budget
```bash
total=$(python openstack_analyzer.py aifarms --format json | \
  jq '.summary.total_cost_openstack')
if (( $(echo "$total > 2000" | bc -l) )); then
  echo "Alert: Costs exceed budget!"
fi
```

### Get GPU count
```bash
python openstack_analyzer.py cori --format json | \
  jq '.summary.total_gpus'
```

## Real-World Examples

### Daily cost tracking
```bash
# Create timestamped report daily
python openstack_analyzer.py aifarms \
  --format csv \
  --output "costs/$(date +%Y%m%d).csv"
```

### Compare clouds
```bash
echo "=== AIFARMS ===" && \
python openstack_analyzer.py aifarms --format json | \
  jq '.summary | {vcpus: .total_cores, cost: .total_cost_openstack}'

echo "=== CORI ===" && \
python openstack_analyzer.py cori --format json | \
  jq '.summary | {vcpus: .total_cores, cost: .total_cost_openstack}'
```

### Export for accounting
```bash
python openstack_analyzer.py aifarms \
  --vm-regex "^prod-" \
  --format csv \
  --output prod_systems.csv

# Open in Excel and pivot by owner/department
```

## Next Steps

1. Run: `python openstack_analyzer.py [your-cloud]`
2. Review the output
3. Try different formats: `--format csv`, `--format json`
4. Filter by pattern: `--vm-regex "gpu.*"`
5. Save reports: `--output report.csv`
6. Check README.md for more advanced usage

## Getting Help

- Quick reference: Run `python openstack_analyzer.py --help`
- Full docs: See README.md
- Configuration: See CONFIG.md
- Features: See FEATURES.md
- Examples: See example_usage.sh

---

That's it! You're ready to analyze your OpenStack environment.
