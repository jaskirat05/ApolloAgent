"""
Activity: Select best available ComfyUI server
"""

import sys
from pathlib import Path

from temporalio import activity

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from gateway.core import load_balancer


@activity.defn
async def select_best_server(strategy: str) -> str:
    """
    Activity: Select the best available ComfyUI server

    Args:
        strategy: Selection strategy ("least_loaded", "round_robin", "random")

    Returns:
        Server address with http:// prefix (e.g., "http://procure-x.testmcp.org")

    Raises:
        Exception: If no servers are available
    """
    activity.logger.info(f"Selecting server with strategy: {strategy}")

    # Use existing load balancer
    server_address = load_balancer.get_best_server(strategy=strategy)

    if not server_address:
        raise Exception("No available ComfyUI servers")

    # Ensure server address has http:// prefix for new client
    if not server_address.startswith(('http://', 'https://')):
        server_address = f"http://{server_address}"

    activity.logger.info(f"Selected server: {server_address}")
    return server_address
