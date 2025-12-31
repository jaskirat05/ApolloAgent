"""
Test ComfyUI Client Directly

Test the new ComfyUI client without Temporal to debug tracking issues.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path

# Add project to path
sys.path.append(str(Path(__file__).parent))

from temporal_gateway.clients.comfy import ComfyUIClient
from temporal_gateway.workflow_registry import get_registry

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')


async def test_client():
    """Test the ComfyUI client with imageSave workflow"""

    print("=" * 70)
    print("Testing ComfyUI Client")
    print("=" * 70)

    # 1. Load imageSave workflow
    print("\n1. Loading imageSave workflow...")
    registry = get_registry()
    workflow_json = registry.apply_overrides("imageSave", {
        "1.video": "ComfyUI_00012_.mp4",
        "1.select_every_nth": 1,
        "1.skip_first_frames": 0,
        "1.frame_load_cap": 1
    })
    print(f"   ✓ Workflow loaded")

    # 2. Create client
    server = "http://procure-x.testmcp.org"
    print(f"\n2. Creating client for {server}...")
    client = ComfyUIClient(server)
    print(f"   ✓ Client created with ID: {client.client_id}")

    # 3. Execute workflow
    print("\n3. Executing workflow...")
    print("   This should complete quickly (imageSave is fast)")

    def on_progress(update):
        print(f"   Progress: node={update.current_node}")

    try:
        print("   Calling execute_workflow...")
        result = await client.execute_workflow(
            workflow=workflow_json,
            progress_callback=on_progress,
            timeout=10.0  # Short timeout for debugging
        )

        print("   execute_workflow returned!")
        print("\n4. Result:")
        print(f"   Status: {result.status}")
        print(f"   Prompt ID: {result.prompt_id}")
        print(f"   Server: {result.server_address}")

        if result.is_success:
            print(f"   ✓ SUCCESS!")
            print(f"\n   Outputs:")
            print(json.dumps(result.outputs, indent=2))
        else:
            print(f"   ✗ FAILED!")
            print(f"   Error: {result.error}")

    except Exception as e:
        print(f"\n   ✗ Exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_client())
