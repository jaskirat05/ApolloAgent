"""
Test Sync and Async Workflow Execution with Logging

Tests both synchronous and asynchronous workflow execution modes
with integrated per-prompt logging.
"""

import sys
import json
import time
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

from sdk import ComfyUISDK
from gateway.core import ComfyUIClient
from gateway.observability import PromptLogger, PromptLogReader, find_prompt_logs


def test_sync_execution():
    """Test synchronous workflow execution with automatic real-time tracking"""
    print("\n" + "="*60)
    print("TEST 1: Synchronous Workflow Execution with Auto-Tracking")
    print("="*60)

    sdk = ComfyUISDK(gateway_url="http://localhost:8000")

    # Load workflow
    workflow_path = Path(__file__).parent.parent / "workflows" / "video_wan2_2_14B_fun_camera_test.json"

    if not workflow_path.exists():
        print(f"✗ Workflow not found: {workflow_path}")
        return False

    print(f"\nLoading workflow: {workflow_path.name}")
    with open(workflow_path) as f:
        workflow = json.load(f)
    print(f"✓ Workflow loaded ({len(workflow)} nodes)")

    # Register server
    print("\nRegistering procure-x server...")
    try:
        sdk.register_server(
            name="Procure-X Server",
            address="procure-x.testmcp.org",
            description="External ComfyUI instance for testing"
        )
        print("✓ Server registered")
    except Exception as e:
        print(f"⚠ Server already registered: {e}")

    # Check server health
    print("\nChecking server health...")
    health = sdk.get_servers_health()
    available = [s for s in health['servers'] if s['is_online']]

    if not available:
        print("✗ No servers available")
        return False

    print(f"✓ {len(available)} server(s) online")
    for server in available:
        print(f"  - {server['address']}: load={server['total_load']}")

    # Execute workflow synchronously
    # Note: Sync mode now automatically tracks and prints progress in real-time
    print("\n" + "-"*60)
    print("Starting synchronous execution...")
    print("Real-time progress tracking will appear below:")
    print("-"*60)

    start_time = time.time()

    try:
        # Sync mode automatically tracks and prints progress
        result = sdk.execute_workflow(
            workflow=workflow,
            wait=True,
            strategy="least_loaded"
        )

        duration = time.time() - start_time

        print(f"\n✓ TEST 1 PASSED")
        print(f"Duration: {duration:.2f}s")
        print(f"Images: {len(result.get('images', []))}")
        print(f"Log file: {result.get('log_file_path', 'N/A')}")

        return True

    except Exception as e:
        duration = time.time() - start_time
        print(f"\n✗ TEST 1 FAILED")
        print(f"Duration: {duration:.2f}s")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_async_execution():
    """Test asynchronous workflow execution with real-time tracking"""
    print("\n\n" + "="*60)
    print("TEST 2: Asynchronous Workflow Execution with track_updates()")
    print("="*60)

    sdk = ComfyUISDK(gateway_url="http://localhost:8000")

    # Load workflow
    workflow_path = Path(__file__).parent.parent / "workflows" / "video_wan2_2_14B_fun_camera_test.json"

    print(f"\nLoading workflow: {workflow_path.name}")
    with open(workflow_path) as f:
        workflow = json.load(f)
    print(f"✓ Workflow loaded ({len(workflow)} nodes)")

    # Execute workflow asynchronously
    print("\n" + "-"*60)
    print("Executing workflow ASYNCHRONOUSLY (wait=False)")
    print("-"*60)

    start_time = time.time()

    try:
        # Start async execution - returns WorkflowJob
        job = sdk.execute_workflow_async(
            workflow=workflow,
            strategy="least_loaded"
        )

        queue_time = time.time() - start_time

        print(f"\n✓ Workflow queued in {queue_time:.2f}s")
        print(f"  Job ID: {job.job_id}")
        print(f"  Prompt ID: {job.prompt_id}")
        print(f"  Server: {job.server_address}")
        print(f"  Status: {job.status}")

        # Track real-time updates with generic handler (blocks until completion)
        print("\n" + "-"*60)
        print("Tracking real-time updates...")
        print("-"*60)

        job.track_updates(block=True)  # Uses generic handler that prints everything

        # Get final status
        final_status = job.refresh_status()
        duration = time.time() - start_time

        print(f"\n✓ TEST 2 PASSED")
        print(f"Total Duration: {duration:.2f}s")
        print(f"Status: {final_status['status']}")
        print(f"Images: {len(final_status.get('images', []))}")
        print(f"Log file: {final_status.get('log_file_path', 'N/A')}")

        return final_status['status'] == 'completed'

    except Exception as e:
        print(f"\n✗ TEST 2 FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_manual_logging():
    """Test workflow execution with manual logging - logs EVERYTHING"""
    print("\n\n" + "="*60)
    print("TEST 3: Direct Execution with Complete Logging")
    print("="*60)

    server_address = "procure-x.testmcp.org"

    # Load workflow
    workflow_path = Path(__file__).parent.parent / "workflows" / "video_wan2_2_14B_i2v.json"

    print(f"\nLoading workflow: {workflow_path.name}")
    with open(workflow_path) as f:
        workflow = json.load(f)
    print(f"✓ Workflow loaded ({len(workflow)} nodes)")

    print(f"\nConnecting to {server_address}...")
    client = ComfyUIClient(server_address=server_address)

    # Queue workflow
    print("Queueing workflow...")
    response = client.post_prompt(workflow)
    prompt_id = response['prompt_id']
    print(f"✓ Queued with prompt_id: {prompt_id}")

    # Create logger
    print("\nInitializing logger...")
    logger = PromptLogger(
        prompt_id=prompt_id,
        server_address=server_address,
        workflow=workflow
    )
    print(f"✓ Logging to: {logger.get_log_file_path().name}")
    logger.log_queued()

    # Track execution - LOG EVERYTHING without filtering
    print("\nTracking execution...")
    print("(Logging ALL WebSocket events without filtering)")
    import threading

    completed = threading.Event()
    error_occurred = False

    def handle_message(message):
        nonlocal error_occurred
        msg_type = message.get('type')
        data = message.get('data', {})

        # LOG EVERYTHING - no filtering
        logger.log_websocket_event(msg_type, data)

        # Simple completion detection
        if msg_type == 'executing':
            node = data.get('node')
            if node is None:
                completed.set()
            else:
                print(f"[EXECUTING] Node: {node}")

        elif msg_type == 'executed':
            node = data.get('node')
            print(f"[EXECUTED] Node: {node}")

        elif msg_type == 'progress':
            value = data.get('value', 0)
            max_val = data.get('max', 100)
            percent = (value / max_val * 100) if max_val > 0 else 0
            print(f"[PROGRESS] {value}/{max_val} ({percent:.1f}%)", end='\r')

        elif msg_type == 'execution_error':
            error_occurred = True
            print(f"\n[ERROR] {data.get('exception_message', 'Unknown error')}")
            completed.set()

        elif msg_type == 'execution_interrupted':
            error_occurred = True
            print(f"\n[INTERRUPTED] Execution was interrupted")
            completed.set()

    # Start WebSocket
    logger.log_websocket_connected()
    ws = client.track_updates(handle_message)
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()

    # Wait for completion
    start_time = time.time()
    timeout = 600

    if completed.wait(timeout=timeout):
        ws.close()
        duration = time.time() - start_time

        print(f"\n\n{'='*60}")
        if error_occurred:
            print(f"✗ EXECUTION FAILED")
        else:
            print(f"✓ EXECUTION COMPLETED")
        print(f"{'='*60}")
        print(f"Duration: {duration:.2f}s")

        # Analyze logs
        print("\n" + "-"*60)
        print("Log Analysis")
        print("-"*60)
        reader = PromptLogReader(logger.get_log_file_path())
        summary = reader.get_summary()

        print(f"\nPrompt ID: {summary['prompt_id']}")
        print(f"Status: {summary['status']}")
        print(f"Total Events Logged: {summary['total_events']}")
        print(f"Workflow Nodes: {summary['workflow_node_count']}")
        print(f"Nodes Executed: {summary['nodes_executed']}")

        if summary['error']:
            print(f"\nError Details:")
            print(f"  Node: {summary['error']['node_id']}")
            print(f"  Type: {summary['error']['error_type']}")
            print(f"  Message: {summary['error']['error_message']}")

        print("\nFirst 10 Timeline Events:")
        for event in reader.get_execution_timeline()[:10]:
            timestamp = event['timestamp'].split('T')[1][:12]
            print(f"  {timestamp} | {event['event']:25} | {event['details']}")

        return not error_occurred
    else:
        ws.close()
        print(f"\n\n⚠ Timeout after {timeout}s")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("ComfyUI SDK Tests - Real-time WebSocket Tracking")
    print("="*60)
    print("\nThis test suite demonstrates:")
    print("  1. Sync execution with automatic real-time progress tracking")
    print("  2. Async execution with job.track_updates() method")
    print("  3. Direct ComfyUI client with manual logging (legacy)")
    print("\nNew Features:")
    print("  - Sync mode: Automatically tracks and prints progress in real-time")
    print("  - Async mode: WorkflowJob.track_updates() for custom tracking")
    print("  - Generic handler: Logs and prints all WebSocket events")
    print("  - Custom handlers: Optional message_handler and error_handler")
    print("\nMake sure:")
    print("  - Gateway is running: uv run run_gateway.py")
    print("  - procure-x.testmcp.org server is accessible")

    input("\nPress Enter to start tests...")

    results = {
        "Sync with Auto-Tracking": test_sync_execution(),
        "Async with track_updates()": test_async_execution(),
        "Direct with Manual Logging": test_with_manual_logging()
    }

    # Summary
    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:30} {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")

    # Show log files
    print("\n" + "-"*60)
    print("Generated Log Files")
    print("-"*60)
    log_files = find_prompt_logs()
    print(f"\nFound {len(log_files)} log file(s):")
    for log_file in log_files[:5]:
        print(f"  - {log_file.name}")

    if log_files:
        print(f"\nLogs directory: {log_files[0].parent}")
        print("\nTo analyze a log file:")
        print(f"  python -m gateway.observability.log_reader {log_files[0]}")


if __name__ == "__main__":
    main()
