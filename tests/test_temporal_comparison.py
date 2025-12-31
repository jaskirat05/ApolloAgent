"""
Comparison Test: Original Gateway vs Temporal Gateway

This test compares both implementations side by side.
"""

import json
import sys
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

from sdk import ComfyUISDK
from temporal_sdk.client import TemporalComfyUISDK


def test_original_gateway():
    """Test original FastAPI gateway"""
    print("\n" + "="*70)
    print("TEST 1: Original Gateway (FastAPI + In-Memory State)")
    print("="*70)

    sdk = ComfyUISDK(gateway_url="http://localhost:8000")

    # Load workflow
    workflow_path = Path(__file__).parent.parent / "workflows" / "video_wan2_2_14B_i2v.json"

    if not workflow_path.exists():
        print(f"✗ Workflow not found: {workflow_path}")
        return False

    print(f"\nLoading workflow: {workflow_path.name}")
    with open(workflow_path) as f:
        workflow = json.load(f)
    print(f"✓ Workflow loaded ({len(workflow)} nodes)")

    # Register server
    print("\nRegistering procure-x server...")
    # Execute
    print("\n" + "-"*70)
    print("Executing workflow...")
    print("-"*70)

    try:
        result = sdk.execute_workflow(
            workflow=workflow,
            wait=True,
            strategy="least_loaded",
            track_progress=False  # Disable WebSocket tracking for cleaner output
        )

        print(f"\n✓ ORIGINAL GATEWAY SUCCESS")
        print(f"Job ID: {result['job_id']}")
        print(f"Prompt ID: {result.get('prompt_id')}")
        print(f"Status: {result['status']}")
        print(f"Images: {len(result.get('images', []))}")
        print(f"Log: {result.get('log_file_path')}")

        return True

    except Exception as e:
        print(f"\n✗ ORIGINAL GATEWAY FAILED")
        print(f"Error: {e}")
        return False


def test_temporal_gateway():
    """Test Temporal-based gateway"""
    print("\n\n" + "="*70)
    print("TEST 2: Temporal Gateway (Durable Execution + PostgreSQL)")
    print("="*70)

    sdk = TemporalComfyUISDK(gateway_url="http://localhost:8001")

    # Load workflow
    workflow_path = Path(__file__).parent.parent / "workflows" / "video_wan2_2_14B_i2v.json"

    print(f"\nLoading workflow: {workflow_path.name}")
    with open(workflow_path) as f:
        workflow = json.load(f)
    print(f"✓ Workflow loaded ({len(workflow)} nodes)")

    # Register server
    print("\nRegistering procure-x server...")
   

    # Execute
    print("\n" + "-"*70)
    print("Executing workflow via Temporal...")
    print("-"*70)

    try:
        result = sdk.execute_workflow(
            workflow=workflow,
            wait=True,
            strategy="least_loaded"
        )

        print(f"\n✓ TEMPORAL GATEWAY SUCCESS")
        print(f"Workflow ID: {result.get('workflow_id')}")
        print(f"Prompt ID: {result.get('prompt_id')}")
        print(f"Status: {result['status']}")
        print(f"Server: {result.get('server_address')}")
        print(f"Images: {len(result.get('images', []))}")
        print(f"Log: {result.get('log_file_path')}")

        return True

    except Exception as e:
        print(f"\n✗ TEMPORAL GATEWAY FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run comparison tests"""
    print("\n" + "="*70)
    print("ComfyAutomate Gateway Comparison Test")
    print("="*70)
    print("\nComparing:")
    print("  1. Original Gateway (port 8000) - In-memory state")
    print("  2. Temporal Gateway (port 8001) - Durable execution")
    print("\nPrerequisites:")
    print("  - Original gateway running: uv run run_gateway.py")
    print("  - Temporal server running: temporal server start-dev")
    print("  - Temporal worker running: python temporal_gateway/worker.py")
    print("  - Temporal gateway running: python temporal_gateway/main.py")
    print("  - procure-x.testmcp.org server accessible")

    input("\nPress Enter to start comparison tests...")

    results = {
        
        "Temporal Gateway": test_temporal_gateway()
    }

    # Summary
    print("\n\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)

    for gateway_name, passed in results.items():
        status = "✓ SUCCESS" if passed else "✗ FAILED"
        print(f"{gateway_name:25} {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} gateways passed")

    # Key differences
    print("\n" + "="*70)
    print("KEY DIFFERENCES")
    print("="*70)
    print("\nOriginal Gateway:")
    print("  ✓ Simpler setup (no Temporal Server needed)")
    print("  ✓ Direct WebSocket tracking")
    print("  ✗ State lost on crash")
    print("  ✗ No automatic retries")
    print("  ✗ Manual state management")
    print("  ✗ No built-in UI")

    print("\nTemporal Gateway:")
    print("  ✓ Durable execution (survives crashes)")
    print("  ✓ Automatic retries")
    print("  ✓ Beautiful UI (http://localhost:8233)")
    print("  ✓ Complete audit trail")
    print("  ✓ Query workflow state anytime")
    print("  ✗ Requires Temporal Server")
    print("  ✗ More complex setup")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
