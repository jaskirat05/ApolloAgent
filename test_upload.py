"""
Test ComfyUI Upload Functionality

Tests uploading a file to ComfyUI's input directory.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.append(str(Path(__file__).parent))

from temporal_gateway.clients.comfy import ComfyUIClient


async def test_upload():
    """Test uploading a file to ComfyUI"""

    print("=" * 70)
    print("Testing ComfyUI Upload")
    print("=" * 70)

    # Server address
    server = "http://procure-x.testmcp.org"

    print(f"\n1. Creating client for {server}...")
    client = ComfyUIClient(server)
    print(f"   ✓ Client created")

    # Create test file content
    test_content = b"This is a test file for upload"
    test_filename = "test_upload.txt"

    print(f"\n2. Uploading test file: {test_filename}")
    try:
        result = await client.upload_file(
            file_data=test_content,
            filename=test_filename,
            subfolder="",
            overwrite=True
        )

        print(f"   ✓ Upload successful!")
        print(f"   Response: {result}")

    except Exception as e:
        print(f"   ✗ Upload failed!")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_upload())
