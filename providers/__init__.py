"""Cloud provider pricing modules."""

from .aws import get_aws_flavor_prices, get_aws_storage_prices
from .azure import get_azure_flavor_prices, get_azure_storage_prices
from .digitalocean import (
    get_digitalocean_flavor_prices,
    get_digitalocean_storage_prices,
)
from .gcp import get_gcp_flavor_prices, get_gcp_storage_prices
from .hetzner import get_hetzner_flavor_prices, get_hetzner_storage_prices
from .linode import get_linode_flavor_prices, get_linode_storage_prices
from .vultr import get_vultr_flavor_prices, get_vultr_storage_prices

__all__ = [
    "get_aws_flavor_prices",
    "get_aws_storage_prices",
    "get_azure_flavor_prices",
    "get_azure_storage_prices",
    "get_digitalocean_flavor_prices",
    "get_digitalocean_storage_prices",
    "get_gcp_flavor_prices",
    "get_gcp_storage_prices",
    "get_hetzner_flavor_prices",
    "get_hetzner_storage_prices",
    "get_linode_flavor_prices",
    "get_linode_storage_prices",
    "get_vultr_flavor_prices",
    "get_vultr_storage_prices",
]
