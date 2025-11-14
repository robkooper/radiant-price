#!/bin/bash
# Example usage scenarios for the OpenStack Analyzer

echo "=== OpenStack Environment Analyzer - Example Usage ==="
echo ""

# Example 1: Basic usage - analyze all VMs
echo "1. Analyze all VMs in a cloud:"
echo "   python openstack_analyzer.py aifarms"
echo ""

# Example 2: Filter by regex
echo "2. Analyze only GPU VMs:"
echo "   python openstack_analyzer.py cori --vm-regex '.*gpu.*'"
echo ""

# Example 3: Export as CSV
echo "3. Export analysis as CSV for spreadsheet:"
echo "   python openstack_analyzer.py aifarms --format csv --output analysis.csv"
echo ""

# Example 4: JSON for programmatic use
echo "4. Get JSON output for further processing:"
echo "   python openstack_analyzer.py cori --format json | jq '.summary'"
echo ""

# Example 5: All formats at once
echo "5. Generate all report formats:"
echo "   python openstack_analyzer.py aifarms --format all --output aifarms_report"
echo "   # Creates: aifarms_report.table, aifarms_report.csv, aifarms_report.json"
echo ""

# Example 6: With AWS pricing
echo "6. Include AWS cost comparison:"
echo "   python openstack_analyzer.py cori --aws-pricing"
echo ""

# Example 7: Batch analysis
echo "7. Analyze multiple clouds:"
echo "   for cloud in aifarms cori clowder gies; do"
echo "       python openstack_analyzer.py \$cloud --format csv --output \${cloud}_report.csv"
echo "   done"
echo ""

# Example 8: Filter multiple patterns
echo "8. Complex filtering - analysis and web servers:"
echo "   python openstack_analyzer.py aifarms --vm-regex '^(analysis-|web-)'"
echo ""

# Example 9: Get specific summary data
echo "9. Extract total cost with jq:"
echo "   python openstack_analyzer.py cori --format json | jq '.summary.total_cost_openstack'"
echo ""

# Example 10: Save high-volume analysis
echo "10. Large deployment analysis with timestamped output:"
echo "    python openstack_analyzer.py aifarms --format all --output \"reports/\$(date +%Y%m%d_%H%M%S)_analysis\""
echo ""

echo "For more information, see README.md"
