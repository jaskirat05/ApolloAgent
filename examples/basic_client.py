"""
Example Usage of ComfyUI Client

Demonstrates how to use the ComfyUI client functions to:
- Post a prompt
- Track real-time updates
- Get results
- Download images
"""

import json
import time
from pathlib import Path
from comfyui_client import ComfyUIClient, run_workflow_and_wait


def example_1_basic_workflow():
    """Example 1: Basic workflow execution"""
    print("\n=== Example 1: Basic Workflow Execution ===\n")

    # Load your workflow (exported in API format from ComfyUI)
    workflow_path = Path("workflow_api.json")

    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        print("Export a workflow from ComfyUI using 'Save (API Format)'")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Initialize client
    client = ComfyUIClient(server_address="127.0.0.1:8188")

    # Queue the prompt
    response = client.post_prompt(workflow)
    prompt_id = response['prompt_id']
    print(f"✓ Queued prompt with ID: {prompt_id}")

    # Wait a bit for execution
    print("Waiting for execution...")
    time.sleep(5)

    # Get results
    history = client.get_history(prompt_id)
    if prompt_id in history:
        outputs = history[prompt_id].get('outputs', {})
        print(f"✓ Execution completed. Outputs: {list(outputs.keys())}")
    else:
        print("Still processing or no results yet")


def example_2_realtime_tracking():
    """Example 2: Real-time progress tracking"""
    print("\n=== Example 2: Real-time Progress Tracking ===\n")

    workflow_path = Path("workflow_api.json")

    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Define progress callback
    def on_progress(message):
        msg_type = message.get('type')

        if msg_type == 'status':
            print(f"[STATUS] {message.get('data', {})}")

        elif msg_type == 'progress':
            data = message.get('data', {})
            value = data.get('value', 0)
            max_val = data.get('max', 100)
            print(f"[PROGRESS] {value}/{max_val}")

        elif msg_type == 'executing':
            node = message.get('data', {}).get('node')
            if node:
                print(f"[EXECUTING] Node: {node}")
            else:
                print(f"[COMPLETED] Execution finished")

        elif msg_type == 'executed':
            node = message.get('data', {}).get('node')
            print(f"[EXECUTED] Node {node} completed")

        elif msg_type == 'execution_error':
            error = message.get('data', {})
            print(f"[ERROR] {error}")

    # Run workflow with progress tracking
    try:
        result = run_workflow_and_wait(workflow, on_progress=on_progress)
        print(f"\n✓ Workflow completed!")
        print(f"Outputs: {result.get('outputs', {}).keys()}")
    except Exception as e:
        print(f"Error: {e}")


def example_3_download_images():
    """Example 3: Download generated images"""
    print("\n=== Example 3: Download Generated Images ===\n")

    workflow_path = Path("workflow_api.json")

    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        return

    with open(workflow_path) as f:
        workflow = json.load(f)

    client = ComfyUIClient()

    # Queue and wait for completion
    print("Running workflow...")
    result = run_workflow_and_wait(workflow)

    # Extract image information from outputs
    outputs = result.get('outputs', {})

    for node_id, node_output in outputs.items():
        if 'images' in node_output:
            for img_info in node_output['images']:
                filename = img_info['filename']
                subfolder = img_info.get('subfolder', '')
                img_type = img_info.get('type', 'output')

                print(f"\nDownloading: {filename}")

                # Download and save
                output_dir = Path("downloaded_images")
                save_path = output_dir / filename

                client.download_image(
                    filename=filename,
                    subfolder=subfolder,
                    image_type=img_type,
                    save_path=save_path
                )

                print(f"✓ Saved to: {save_path}")


def example_4_upload_and_process():
    """Example 4: Upload image and process it"""
    print("\n=== Example 4: Upload and Process Image ===\n")

    client = ComfyUIClient()

    # Upload an image
    input_image = Path("input.png")

    if not input_image.exists():
        print(f"Error: {input_image} not found")
        return

    print(f"Uploading {input_image}...")
    upload_result = client.upload_image(input_image)
    print(f"✓ Uploaded: {upload_result}")

    # Now you can use the uploaded image in your workflow
    # Modify your workflow JSON to reference the uploaded filename
    # then queue it with client.post_prompt(workflow)


def example_5_queue_management():
    """Example 5: Queue management"""
    print("\n=== Example 5: Queue Management ===\n")

    client = ComfyUIClient()

    # Get current queue status
    queue = client.get_queue()
    print("Queue Status:")
    print(f"  Running: {len(queue.get('queue_running', []))} items")
    print(f"  Pending: {len(queue.get('queue_pending', []))} items")

    # Get system stats
    stats = client.get_system_stats()
    print("\nSystem Stats:")
    print(f"  System: {stats.get('system', {})}")
    print(f"  Devices: {stats.get('devices', [])}")


def example_6_custom_websocket():
    """Example 6: Custom WebSocket handling"""
    print("\n=== Example 6: Custom WebSocket Handling ===\n")

    client = ComfyUIClient()

    # Custom message handler
    def handle_message(message):
        print(f"Received: {message.get('type')} - {message.get('data', {})}")

    def handle_error(error):
        print(f"WebSocket error: {error}")

    # Create WebSocket connection
    ws = client.track_updates(
        on_message=handle_message,
        on_error=handle_error
    )

    print("WebSocket connected. Listening for updates...")
    print("Press Ctrl+C to stop")

    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        ws.close()


if __name__ == "__main__":
    import sys

    examples = {
        "1": ("Basic workflow execution", example_1_basic_workflow),
        "2": ("Real-time progress tracking", example_2_realtime_tracking),
        "3": ("Download generated images", example_3_download_images),
        "4": ("Upload and process image", example_4_upload_and_process),
        "5": ("Queue management", example_5_queue_management),
        "6": ("Custom WebSocket handling", example_6_custom_websocket),
    }

    print("\nComfyUI Client Examples")
    print("=" * 50)
    print("\nAvailable examples:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nSelect example (1-6): ").strip()

    if choice in examples:
        _, example_func = examples[choice]
        try:
            example_func()
        except Exception as e:
            print(f"\nError running example: {e}")
            print("\nMake sure:")
            print("  1. ComfyUI is running on http://127.0.0.1:8188")
            print("  2. Required files (workflow_api.json, input images) exist")
    else:
        print("Invalid choice")
