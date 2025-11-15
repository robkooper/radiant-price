"""Google Cloud Platform pricing fetcher.

Note: GCP's Cloud Billing API requires authentication (API key + enabled billing).
This module uses embedded pricing that should be updated periodically from:
https://cloud.google.com/compute/all-pricing

Prices are for us-east1 region, on-demand, per month (730 hours).
"""

from typing import Dict

# Embedded GCP pricing (live API requires authentication)
# Last updated: 2024
# Source: https://cloud.google.com/compute/all-pricing
GCP_PRICING = {
    "n1-standard-1": {
        "cores": 1,
        "memory_gb": 3.75,
        "price": 24.68,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-2": {
        "cores": 2,
        "memory_gb": 7.5,
        "price": 49.37,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-4": {
        "cores": 4,
        "memory_gb": 15,
        "price": 98.74,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-8": {
        "cores": 8,
        "memory_gb": 30,
        "price": 197.47,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-16": {
        "cores": 16,
        "memory_gb": 60,
        "price": 394.95,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-32": {
        "cores": 32,
        "memory_gb": 120,
        "price": 789.90,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-64": {
        "cores": 64,
        "memory_gb": 240,
        "price": 1579.80,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-standard-96": {
        "cores": 96,
        "memory_gb": 360,
        "price": 2369.70,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-2": {
        "cores": 2,
        "memory_gb": 13,
        "price": 61.72,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-4": {
        "cores": 4,
        "memory_gb": 26,
        "price": 123.44,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-8": {
        "cores": 8,
        "memory_gb": 52,
        "price": 246.88,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-16": {
        "cores": 16,
        "memory_gb": 104,
        "price": 493.77,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-32": {
        "cores": 32,
        "memory_gb": 208,
        "price": 987.54,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-64": {
        "cores": 64,
        "memory_gb": 416,
        "price": 1975.08,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highmem-96": {
        "cores": 96,
        "memory_gb": 624,
        "price": 2962.62,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-2": {
        "cores": 2,
        "memory_gb": 1.8,
        "price": 24.68,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-4": {
        "cores": 4,
        "memory_gb": 3.6,
        "price": 49.37,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-8": {
        "cores": 8,
        "memory_gb": 7.2,
        "price": 98.74,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-16": {
        "cores": 16,
        "memory_gb": 14.4,
        "price": 197.47,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-32": {
        "cores": 32,
        "memory_gb": 28.8,
        "price": 394.95,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-64": {
        "cores": 64,
        "memory_gb": 57.6,
        "price": 789.90,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n1-highcpu-96": {
        "cores": 96,
        "memory_gb": 86.4,
        "price": 1184.85,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    # N2 series (newer, better performance than N1)
    "n2-standard-2": {
        "cores": 2,
        "memory_gb": 8,
        "price": 56.94,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-4": {
        "cores": 4,
        "memory_gb": 16,
        "price": 113.87,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-8": {
        "cores": 8,
        "memory_gb": 32,
        "price": 227.74,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-16": {
        "cores": 16,
        "memory_gb": 64,
        "price": 455.48,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-32": {
        "cores": 32,
        "memory_gb": 128,
        "price": 910.96,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-48": {
        "cores": 48,
        "memory_gb": 192,
        "price": 1366.44,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-64": {
        "cores": 64,
        "memory_gb": 256,
        "price": 1821.92,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-standard-80": {
        "cores": 80,
        "memory_gb": 320,
        "price": 2277.40,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    # N2 high-memory
    "n2-highmem-2": {
        "cores": 2,
        "memory_gb": 16,
        "price": 71.54,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-4": {
        "cores": 4,
        "memory_gb": 32,
        "price": 143.07,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-8": {
        "cores": 8,
        "memory_gb": 64,
        "price": 286.14,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-16": {
        "cores": 16,
        "memory_gb": 128,
        "price": 572.28,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-32": {
        "cores": 32,
        "memory_gb": 256,
        "price": 1144.56,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-48": {
        "cores": 48,
        "memory_gb": 384,
        "price": 1716.84,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-64": {
        "cores": 64,
        "memory_gb": 512,
        "price": 2289.12,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "n2-highmem-80": {
        "cores": 80,
        "memory_gb": 640,
        "price": 2861.40,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    # E2 series (cost-optimized)
    "e2-standard-2": {
        "cores": 2,
        "memory_gb": 8,
        "price": 38.69,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "e2-standard-4": {
        "cores": 4,
        "memory_gb": 16,
        "price": 77.38,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "e2-standard-8": {
        "cores": 8,
        "memory_gb": 32,
        "price": 154.76,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "e2-standard-16": {
        "cores": 16,
        "memory_gb": 64,
        "price": 309.52,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "e2-standard-32": {
        "cores": 32,
        "memory_gb": 128,
        "price": 619.04,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    # C2 series (compute-optimized)
    "c2-standard-4": {
        "cores": 4,
        "memory_gb": 16,
        "price": 122.63,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "c2-standard-8": {
        "cores": 8,
        "memory_gb": 32,
        "price": 245.26,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "c2-standard-16": {
        "cores": 16,
        "memory_gb": 64,
        "price": 490.52,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "c2-standard-30": {
        "cores": 30,
        "memory_gb": 120,
        "price": 919.73,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    "c2-standard-60": {
        "cores": 60,
        "memory_gb": 240,
        "price": 1839.46,
        "gpu_count": 0,
        "gpu_model": "",
        "gpu_memory": 0,
    },
    # GCP A2 instances with A100 GPUs
    "a2-highgpu-1g": {
        "cores": 12,
        "memory_gb": 85,
        "price": 1460.00,
        "gpu_count": 1,
        "gpu_model": "NVIDIA A100",
        "gpu_memory": 40,
    },
    "a2-highgpu-2g": {
        "cores": 24,
        "memory_gb": 170,
        "price": 2920.00,
        "gpu_count": 2,
        "gpu_model": "NVIDIA A100",
        "gpu_memory": 80,
    },
    "a2-highgpu-4g": {
        "cores": 48,
        "memory_gb": 340,
        "price": 5840.00,
        "gpu_count": 4,
        "gpu_model": "NVIDIA A100",
        "gpu_memory": 160,
    },
    "a2-highgpu-8g": {
        "cores": 96,
        "memory_gb": 680,
        "price": 11680.00,
        "gpu_count": 8,
        "gpu_model": "NVIDIA A100",
        "gpu_memory": 320,
    },
}


def get_gcp_flavor_prices() -> Dict[str, Dict]:
    """
    Fetch GCP Compute Engine pricing.

    Note: GCP's live API requires authentication. Using embedded pricing.
    For current pricing, check: https://cloud.google.com/compute/pricing

    Returns:
        Dict of {instance_type: {cores, memory_gb, price}}
    """
    print(f"[GCP] Using embedded pricing (API requires authentication)")

    try:
        print(f"      ✓ Loaded {len(GCP_PRICING)} GCP instance types")
        return GCP_PRICING.copy()

    except Exception as e:
        print(f"      ✗ Error: {e}")
        return {}


def get_gcp_storage_prices() -> Dict[str, float]:
    """
    Get GCP Persistent Disk storage pricing.

    Currently hardcoded as GCP pricing is complex and region-dependent.
    Uses pd-standard pricing for us-central1 region.

    Returns:
        Dict with storage prices per GB per month, e.g., {"flash": 0.04}
    """
    # GCP Persistent Disk pricing (as of 2024):
    # pd-standard: $0.04/GB/month in us-central1
    # pd-balanced: $0.10/GB/month in us-central1
    # pd-ssd: $0.17/GB/month in us-central1

    # Using pd-standard as the baseline (most cost-effective)
    return {"flash": 0.04}
