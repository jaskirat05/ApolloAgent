"""
Test script to execute the conditional video generation chain
"""

import asyncio
import httpx
import json
import time


async def test_image_edit_pipeline():
    """Test the image edit to video pipeline chain"""

    base_url = "http://localhost:8001"

    print("=" * 70)
    print("Testing Image Edit to Video Pipeline Chain")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. List available chains
        print("\n1. Listing available chains...")
        response = await client.get(f"{base_url}/chains")
        chains = response.json()
        print(f"   Found {chains['count']} chain(s):")
        for chain in chains['chains']:
            print(f"   - {chain['name']}: {chain.get('description', '')[:60]}...")

        # 2. Get chain details
        print("\n2. Getting chain details...")
        response = await client.get(f"{base_url}/chains/image-edit-to-video-pipeline")

        if response.status_code != 200:
            print(f"   ERROR: {response.status_code} - {response.text}")
            return

        chain_details = response.json()
        print(f"   Chain: {chain_details.get('name', 'Unknown')}")
        print(f"   Steps: {len(chain_details['steps'])}")
        print(f"   Execution Levels: {chain_details['execution_plan']['total_levels']}")
        print(f"   Parallel Groups: {chain_details['execution_plan']['parallel_groups']}")

        for step in chain_details['steps']:
            print(f"   - {step['id']}: {step['workflow']}")
            print(f"     Prompt: {step['parameters'].get('prompt', 'N/A')}")

        # 3. Execute chain
        print("\n3. Starting chain execution...")
        response = await client.post(
            f"{base_url}/chains/image-edit-to-video-pipeline/execute",
            json={"parameters": {}}
        )

        if response.status_code != 200:
            print(f"   ERROR: {response.status_code} - {response.text}")
            return

        execution = response.json()
        workflow_id = execution['workflow_id']

        print(f"   ✓ Chain started!")
        print(f"   Workflow ID: {workflow_id}")
        print(f"   Total Steps: {execution['total_steps']}")
        print(f"   Parallel Groups: {execution['parallel_groups']}")

        # 4. Monitor status
        print("\n4. Monitoring execution status...")
        print("   (Press Ctrl+C to stop monitoring)\n")

        try:
            last_status = None
            while True:
                response = await client.get(f"{base_url}/chains/status/{workflow_id}")

                if response.status_code != 200:
                    print(f"   ERROR getting status: {response.status_code}")
                    break

                status = response.json()

                # Print status if changed
                current_status = json.dumps(status, sort_keys=True)
                if current_status != last_status:
                    print(f"   Status: {status.get('status', 'unknown')}")
                    print(f"   Current Level: {status.get('current_level', 0)}")
                    print(f"   Completed Steps: {status.get('completed_steps', 0)}")

                    if 'step_statuses' in status:
                        print(f"   Step Statuses:")
                        for step_id, step_status in status['step_statuses'].items():
                            print(f"     - {step_id}: {step_status}")

                    print()
                    last_status = current_status

                # Check if completed
                if status.get('status') in ['completed', 'failed']:
                    print(f"   Chain {status.get('status')}!")
                    break

                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\n   Monitoring stopped by user")

        # 5. Get final result
        print("\n5. Getting final result...")
        response = await client.get(f"{base_url}/chains/result/{workflow_id}")

        if response.status_code != 200:
            print(f"   ERROR: {response.status_code} - {response.text}")
            return

        result = response.json()

        print(f"   Chain: {result['chain_name']}")
        print(f"   Status: {result['status']}")
        print(f"   Successful Steps: {result['successful_steps']}")
        print(f"   Failed Steps: {result['failed_steps']}")

        if result.get('error'):
            print(f"   Error: {result['error']}")

        print(f"\n   Step Results:")
        for step_id, step_result in result['step_results'].items():
            print(f"\n   {step_id}:")
            print(f"     Status: {step_result['status']}")
            print(f"     Workflow: {step_result['workflow']}")

            if step_result.get('output'):
                output = step_result['output']
                print(f"     Output Type: {output.get('type', 'unknown')}")
                if output.get('video'):
                    print(f"     Video File: {output['video']}")
                if output.get('image'):
                    print(f"     Image File: {output['image']}")

            if step_result.get('error'):
                print(f"     Error: {step_result['error']}")

    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_image_edit_pipeline())
