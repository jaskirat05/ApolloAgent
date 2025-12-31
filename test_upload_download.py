"""
Test ComfyUI Upload and Download Cycle

Tests uploading a file to input directory, then downloading it back.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.append(str(Path(__file__).parent))

from temporal_gateway.clients.comfy import ComfyUIClient


async def test_upload_download():
    """Test uploading and downloading a file"""

    print("=" * 70)
    print("Testing ComfyUI Upload/Download Cycle")
    print("=" * 70)

    # Server address
    server = "http://procure-x.testmcp.org"

    print(f"\n1. Creating client for {server}...")
    client = ComfyUIClient(server)
    print(f"   ✓ Client created")

    # Create test file content
    test_content = b"This is a test file - upload/download cycle test"
    test_filename = "test_cycle.png"

    print(f"\n2. Uploading test file: {test_filename}")
    try:
        upload_result = await client.upload_file(
            file_data=test_content,
            filename=test_filename,
            subfolder="",
            overwrite=True
        )

        print(f"   ✓ Upload successful!")
        print(f"   Response: {upload_result}")

    except Exception as e:
        print(f"   ✗ Upload failed!")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        await client.close()
        return

    print(f"\n3. Downloading the uploaded file from input directory...")
    try:
        downloaded_content = await client.download_file(
            filename=test_filename,
            subfolder="",
            folder_type="input"  # Download from input directory
        )

        print(f"   ✓ Download successful!")
        print(f"   Downloaded {len(downloaded_content)} bytes")
        print(f"   Original: {len(test_content)} bytes")

        # Verify content matches
        if downloaded_content == test_content:
            print(f"   ✓ Content matches perfectly!")
        else:
            print(f"   ✗ Content mismatch!")
            print(f"   Original: {test_content}")
            print(f"   Downloaded: {downloaded_content}")

    except Exception as e:
        print(f"   ✗ Download failed!")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_upload_download())
