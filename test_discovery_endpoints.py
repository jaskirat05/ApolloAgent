"""
Test ComfyUI Discovery Endpoints

Tests the new endpoints for discovering available nodes and models
"""

import asyncio
from temporal_gateway.clients.comfy import ComfyUIClient


async def test_discovery_endpoints():
    """Test all discovery endpoints"""

    client = ComfyUIClient("http://procure-x.testmcp.org")

    try:
        print("=" * 70)
        print("ComfyUI Discovery Endpoints Test")
        print("=" * 70)

        # 1. Get all available nodes
        print("\n1. Getting all available nodes...")
        nodes = await client.get_object_info()
        print(f"   ✓ Found {len(nodes)} nodes")
        print(f"   Sample nodes: {list(nodes.keys())[:5]}")

        # 2. Get specific node info
        print("\n2. Getting KSampler node details...")
        ksampler = await client.get_object_info("KSampler")
        if "KSampler" in ksampler:
            node_info = ksampler["KSampler"]
            print(f"   ✓ Category: {node_info.get('category')}")
            print(f"   ✓ Output: {node_info.get('output')}")
            print(f"   ✓ Required inputs: {len(node_info.get('input', {}).get('required', {}))}")

        # 3. Get model categories
        print("\n3. Getting model categories...")
        categories = await client.get_models()
        print(f"   ✓ Found {len(categories)} categories")
        print(f"   Categories: {categories[:10]}")

        # 4. Get models by category
        print("\n4. Getting models in different categories...")

        test_categories = ['vae', 'diffusion_models', 'loras', 'controlnet']
        for category in test_categories:
            try:
                models = await client.get_models_by_category(category)
                print(f"   ✓ {category}: {len(models)} models")
                if models:
                    print(f"      Examples: {models[:2]}")
            except Exception as e:
                print(f"   ✗ {category}: {e}")

        # 5. Get embeddings
        print("\n5. Getting available embeddings...")
        try:
            embeddings = await client.get_embeddings()
            print(f"   ✓ Found {len(embeddings)} embeddings")
            if embeddings:
                print(f"   Examples: {embeddings[:5]}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

        # 6. Get extensions
        print("\n6. Getting available extensions...")
        try:
            extensions = await client.get_extensions()
            print(f"   ✓ Found {len(extensions)} extensions")
            if extensions:
                print(f"   Examples: {extensions[:5]}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

        print("\n" + "=" * 70)
        print("Test Complete!")
        print("=" * 70)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_discovery_endpoints())
