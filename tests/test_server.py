"""
Test script to register and verify procure-x.testmcp.org server

This script:
1. Tests direct connection to the ComfyUI server
2. Retrieves system stats and health info
3. Registers the server with the gateway (if running)
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent))

from comfyui_client import ComfyUIClient
from comfyui_sdk import ComfyUISDK


def test_direct_connection(server_address: str):
    """Test direct connection to ComfyUI server"""
    print(f"\n{'='*60}")
    print(f"Testing Direct Connection to {server_address}")
    print(f"{'='*60}\n")

    try:
        client = ComfyUIClient(server_address=server_address)

        # Test 1: Get system stats
        print("Test 1: Fetching system stats...")
        stats = client.get_system_stats()
        print("✓ System stats retrieved successfully!")
        print(f"\nSystem Information:")
        print(f"  Python Version: {stats.get('python_version', 'N/A')}")
        print(f"  OS: {stats.get('os', 'N/A')}")

        system_info = stats.get('system', {})
        if system_info:
            print(f"  System: {system_info}")

        devices = stats.get('devices', [])
        if devices:
            print(f"\nDevices:")
            for device in devices:
                print(f"  - {device}")

        # Test 2: Get queue status
        print("\nTest 2: Fetching queue status...")
        queue = client.get_queue()
        running = len(queue.get('queue_running', []))
        pending = len(queue.get('queue_pending', []))
        print(f"✓ Queue status retrieved successfully!")
        print(f"  Running: {running} jobs")
        print(f"  Pending: {pending} jobs")

        # Test 3: Get object info (available nodes)
        print("\nTest 3: Fetching available nodes...")
        try:
            nodes = client.get_object_info()
            node_count = len(nodes) if isinstance(nodes, dict) else 0
            print(f"✓ Object info retrieved successfully!")
            print(f"  Available nodes: {node_count}")

            # Show first 5 nodes
            if isinstance(nodes, dict) and node_count > 0:
                print("\n  Sample nodes:")
                for i, node_name in enumerate(list(nodes.keys())[:5]):
                    print(f"    - {node_name}")
                if node_count > 5:
                    print(f"    ... and {node_count - 5} more")
        except Exception as e:
            print(f"⚠ Could not fetch nodes: {e}")

        print(f"\n{'='*60}")
        print("✓ Server is healthy and responding!")
        print(f"{'='*60}\n")

        return True, stats

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ Connection failed!")
        print(f"{'='*60}")
        print(f"\nError: {e}")
        print(f"\nPossible issues:")
        print(f"  1. Server is not running")
        print(f"  2. Server address is incorrect")
        print(f"  3. Server is not accessible (firewall/network)")
        print(f"  4. Server is not a ComfyUI instance")
        print(f"\n{'='*60}\n")
        return False, None


def register_with_gateway(server_address: str, gateway_url: str = "http://localhost:8000"):
    """Register server with the gateway"""
    print(f"\n{'='*60}")
    print(f"Registering with Gateway at {gateway_url}")
    print(f"{'='*60}\n")

    try:
        sdk = ComfyUISDK(gateway_url=gateway_url)

        # Check if gateway is running
        print("Checking gateway health...")
        health = sdk.health_check()
        print(f"✓ Gateway is healthy: {health['status']}")

        # Register server
        print(f"\nRegistering server: {server_address}...")
        result = sdk.register_server(
            name="Procure-X Server",
            address=server_address,
            description="External ComfyUI instance at procure-x.testmcp.org"
        )

        print("✓ Server registered successfully!")
        print(f"\nServer details:")
        print(f"  Name: {result['server']['name']}")
        print(f"  Address: {result['server']['address']}")
        print(f"  Description: {result['server']['description']}")

        # Get server health from load balancer
        print("\nChecking server health from gateway...")
        health = sdk.get_servers_health()

        print(f"\nAll registered servers ({health['available_count']} available):")
        for server in health['servers']:
            status = "✓ online" if server['is_online'] else "✗ offline"
            print(f"  {server['address']}: {status}")
            print(f"    Load: {server['total_load']} jobs (running: {server['queue_running']}, pending: {server['queue_pending']})")
            if server['error']:
                print(f"    Error: {server['error']}")

        print(f"\n{'='*60}")
        print("✓ Registration complete!")
        print(f"{'='*60}\n")

        return True

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ Gateway registration failed!")
        print(f"{'='*60}")
        print(f"\nError: {e}")
        print(f"\nMake sure the gateway is running:")
        print(f"  cd backend")
        print(f"  python main.py")
        print(f"\n{'='*60}\n")
        return False


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("ComfyUI Server Registration & Testing")
    print("="*60)

    # Server to test
    server_address = "procure-x.testmcp.org"

    # Note: procure-x.testmcp.org might need a port number
    # Common ComfyUI ports: 8188 (default), 8080, 3000
    # Let's try with default port first
    if ":" not in server_address:
        print(f"\nNote: No port specified. Trying default ComfyUI port 8188")
        server_address = f"{server_address}"

    print(f"\nTarget server: {server_address}")

    # Test direct connection
    success, stats = test_direct_connection(server_address)

    if not success:
        # Try without port
        original_server = "procure-x.testmcp.org"
        print(f"\nRetrying without port specification: {original_server}")
        success, stats = test_direct_connection(original_server)

        if success:
            server_address = original_server

    # If connection successful, try to register with gateway
    if success:
        print("\n✓ Server is accessible and responding correctly!")

        response = input("\nWould you like to register this server with the gateway? (y/n): ").strip().lower()

        if response == 'y':
            register_with_gateway(server_address)
        else:
            print("\nSkipping gateway registration.")
            print("\nTo register later, use:")
            print(f"  sdk.register_server('Procure-X', '{server_address}')")

    else:
        print("\n✗ Server is not accessible. Cannot register with gateway.")
        print("\nPlease verify:")
        print(f"  1. Server address: {server_address}")
        print(f"  2. Server is running")
        print(f"  3. Firewall/network allows connection")
        print(f"  4. Port number is correct (default: 8188)")


if __name__ == "__main__":
    main()
