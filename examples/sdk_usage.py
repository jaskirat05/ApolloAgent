"""
ComfyUI SDK Examples

Demonstrates how to use the SDK for various use cases.
"""

import json
from pathlib import Path
from comfyui_sdk import ComfyUISDK


def example_1_basic_usage():
    """Example 1: Basic workflow execution"""
    print("\n=== Example 1: Basic Workflow Execution ===\n")

    # Initialize SDK
    sdk = ComfyUISDK(gateway_url="http://localhost:8000")

    # Load workflow (exported in API format from ComfyUI)
    workflow_path = Path("workflow_api.json")

    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        print("Export a workflow from ComfyUI using 'Save (API Format)'")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Execute workflow - that's it!
    # The SDK handles everything: server selection, execution, image download
    result = sdk.execute_workflow(workflow)

    print(f"✓ Workflow completed!")
    print(f"Server used: {result['server_address']}")
    print(f"Job ID: {result['job_id']}")
    print(f"\nGenerated images:")
    for url in result['images']:
        print(f"  - {url}")


def example_2_async_execution():
    """Example 2: Asynchronous execution"""
    print("\n=== Example 2: Asynchronous Execution ===\n")

    sdk = ComfyUISDK()

    workflow_path = Path("workflow_api.json")
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Queue workflow and return immediately
    job = sdk.execute_workflow_async(workflow)

    print(f"✓ Workflow queued!")
    print(f"Job ID: {job['job_id']}")
    print(f"Server: {job['server_address']}")

    # You can do other work here...
    print("\nDoing other work while workflow executes...")

    # Wait for completion
    print("Waiting for completion...")
    result = sdk.wait_for_job(job['job_id'], timeout=300)

    print(f"\n✓ Workflow completed!")
    print(f"Generated {len(result['images'])} images")


def example_3_download_images():
    """Example 3: Download and save images"""
    print("\n=== Example 3: Download and Save Images ===\n")

    sdk = ComfyUISDK()

    workflow_path = Path("workflow_api.json")
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Execute workflow
    result = sdk.execute_workflow(workflow)

    # Download and save images
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    print(f"Downloading {len(result['images'])} images...")

    for i, url in enumerate(result['images']):
        filename = f"output_{i+1}.png"
        save_path = output_dir / filename

        sdk.download_image(url, save_path=save_path)
        print(f"✓ Saved: {save_path}")


def example_4_server_management():
    """Example 4: Register and manage servers"""
    print("\n=== Example 4: Server Management ===\n")

    sdk = ComfyUISDK()

    # Register a new server
    print("Registering ComfyUI server...")
    try:
        result = sdk.register_server(
            name="Main Server",
            address="127.0.0.1:8188",
            description="Primary ComfyUI instance"
        )
        print(f"✓ Server registered: {result['server']['name']}")
    except Exception as e:
        print(f"Note: {e}")

    # List all servers
    print("\nRegistered servers:")
    servers = sdk.list_servers()
    for server in servers:
        print(f"  - {server['name']} ({server['address']})")

    # Check server health
    print("\nServer health:")
    health = sdk.get_servers_health()

    for server in health['servers']:
        status = "✓ online" if server['is_online'] else "✗ offline"
        load = server['total_load']
        print(f"  {server['address']}: {status} (load: {load} jobs)")


def example_5_batch_processing():
    """Example 5: Process multiple workflows"""
    print("\n=== Example 5: Batch Processing ===\n")

    sdk = ComfyUISDK()

    workflow_path = Path("workflow_api.json")
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Process multiple variations
    batch_size = 3

    print(f"Processing {batch_size} workflows...")

    jobs = []
    for i in range(batch_size):
        print(f"Queuing workflow {i+1}...")

        # Queue async
        job = sdk.execute_workflow_async(workflow)
        jobs.append(job)

    print(f"\n✓ Queued {len(jobs)} jobs")

    # Wait for all to complete
    print("\nWaiting for all jobs to complete...")

    results = []
    for i, job in enumerate(jobs):
        print(f"Waiting for job {i+1}/{len(jobs)}...")
        result = sdk.wait_for_job(job['job_id'])
        results.append(result)

    print(f"\n✓ All jobs completed!")
    print(f"Total images generated: {sum(len(r['images']) for r in results)}")


def example_6_error_handling():
    """Example 6: Error handling"""
    print("\n=== Example 6: Error Handling ===\n")

    sdk = ComfyUISDK()

    # Check if gateway is running
    try:
        health = sdk.health_check()
        print(f"✓ Gateway is healthy: {health['status']}")
    except Exception as e:
        print(f"✗ Gateway is not accessible: {e}")
        print("Start the gateway with: cd backend && python main.py")
        return

    # Check if servers are available
    health = sdk.get_servers_health()
    if health['available_count'] == 0:
        print("✗ No ComfyUI servers available")
        print("Register a server:")
        print("  sdk.register_server('Main', '127.0.0.1:8188')")
        return

    print(f"✓ {health['available_count']} server(s) available")

    # Execute with error handling
    workflow_path = Path("workflow_api.json")
    if not workflow_path.exists():
        print(f"✗ Workflow file not found: {workflow_path}")
        return

    try:
        with open(workflow_path) as f:
            workflow = json.load(f)

        result = sdk.execute_workflow(workflow)
        print(f"✓ Execution successful!")
        print(f"Images: {len(result['images'])}")

    except Exception as e:
        print(f"✗ Execution failed: {e}")


def example_7_convenience_function():
    """Example 7: Using convenience function"""
    print("\n=== Example 7: Convenience Function ===\n")

    # For one-off usage, you can use the convenience function
    from comfyui_sdk import execute_workflow

    workflow_path = Path("workflow_api.json")
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Execute directly without creating SDK instance
    result = execute_workflow(workflow)

    print(f"✓ Done!")
    print(f"Images: {result['images']}")


if __name__ == "__main__":
    import sys

    examples = {
        "1": ("Basic workflow execution", example_1_basic_usage),
        "2": ("Asynchronous execution", example_2_async_execution),
        "3": ("Download and save images", example_3_download_images),
        "4": ("Server management", example_4_server_management),
        "5": ("Batch processing", example_5_batch_processing),
        "6": ("Error handling", example_6_error_handling),
        "7": ("Convenience function", example_7_convenience_function),
    }

    print("\nComfyUI SDK Examples")
    print("=" * 50)
    print("\nAvailable examples:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nSelect example (1-7): ").strip()

    if choice in examples:
        _, example_func = examples[choice]
        try:
            example_func()
        except Exception as e:
            print(f"\nError running example: {e}")
            print("\nMake sure:")
            print("  1. Gateway is running: cd backend && python main.py")
            print("  2. ComfyUI server is registered")
            print("  3. workflow_api.json exists")
    else:
        print("Invalid choice")
