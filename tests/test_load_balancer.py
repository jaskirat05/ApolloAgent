"""
Test script for load balancer and workflow execution

This script:
1. Registers multiple ComfyUI servers (real + mock)
2. Loads the video workflow
3. Tests load balancer server selection
4. Submits the workflow
5. Cancels the prompt
"""

import sys
import json
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

from gateway.core import ComfyUIClient
from sdk import ComfyUISDK


class MockComfyUIHandler(BaseHTTPRequestHandler):
    """Mock ComfyUI server handler"""

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/system_stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "python_version": "3.10.0",
                "os": "linux",
                "system": {"platform": "mock"},
                "devices": ["Mock GPU"]
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/queue':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "queue_running": [],
                "queue_pending": []
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/object_info':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "KSampler": {},
                "LoadImage": {},
                "SaveImage": {}
            }
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/prompt':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "prompt_id": "mock-prompt-123",
                "number": 1
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/interrupt':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "interrupted"}).encode())

        else:
            self.send_response(404)
            self.end_headers()


def start_mock_server(port=8189):
    """Start a mock ComfyUI server"""
    server = HTTPServer(('localhost', port), MockComfyUIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"✓ Mock server started on localhost:{port}")
    return server


def test_load_balancer():
    """Test the load balancer with multiple servers"""
    print("\n" + "="*60)
    print("Load Balancer Test")
    print("="*60)

    # Start mock server
    print("\nStarting mock ComfyUI server...")
    mock_server = start_mock_server(port=8189)
    time.sleep(1)  # Give server time to start

    # Initialize SDK
    sdk = ComfyUISDK(gateway_url="http://localhost:8000")

    try:
        # Check gateway health
        print("\nChecking gateway health...")
        health = sdk.health_check()
        print(f"✓ Gateway is healthy: {health['status']}")

        # Register real server first (so it gets priority when loads are equal)
        print("\nRegistering procure-x server...")
        try:
            sdk.register_server(
                name="Procure-X Server",
                address="procure-x.testmcp.org",
                description="External ComfyUI instance"
            )
            print("✓ Procure-X server registered")
        except Exception as e:
            print(f"⚠ Procure-X registration: {e}")

        # Register mock server
        print("\nRegistering mock server...")
        try:
            sdk.register_server(
                name="Mock Server",
                address="localhost:8189",
                description="Mock ComfyUI server for testing"
            )
            print("✓ Mock server registered")
        except Exception as e:
            print(f"⚠ Mock server registration: {e}")

        # Get server health
        print("\nChecking all servers health...")
        health = sdk.get_servers_health()

        print(f"\nRegistered servers: {len(health['servers'])}")
        print(f"Available servers: {health['available_count']}")

        for i, server in enumerate(health['servers'], 1):
            status = "✓ online" if server['is_online'] else "✗ offline"
            print(f"\n{i}. {server['address']}: {status}")
            print(f"   Running: {server['queue_running']} jobs")
            print(f"   Pending: {server['queue_pending']} jobs")
            print(f"   Total load: {server['total_load']}")
            if server['error']:
                print(f"   Error: {server['error']}")

        if health['available_count'] == 0:
            print("\n✗ No servers available for testing")
            return

        # Load workflow
        workflow_path = Path("workflows/video_wan2_2_14B_fun_camera_test.json")
        if not workflow_path.exists():
            print(f"\n⚠ Workflow file not found: {workflow_path}")
            print("Skipping workflow execution test")
            return

        print(f"\nLoading workflow: {workflow_path}")
        with open(workflow_path) as f:
            workflow = json.load(f)
        print(f"✓ Workflow loaded ({len(workflow)} nodes)")

        # Test load balancer selection
        print("\n" + "-"*60)
        print("Testing Load Balancer Selection")
        print("-"*60)

        print("\nThe load balancer will select the best server based on:")
        print("  - Server availability (online/offline)")
        print("  - Current queue load (running + pending jobs)")
        print("  - Strategy: least_loaded (default)")

        # Queue workflow (non-blocking)
        print("\nQueuing workflow (async mode)...")
        try:
            job = sdk.execute_workflow_async(workflow)

            print(f"\n✓ Workflow queued!")
            print(f"  Job ID: {job['job_id']}")
            print(f"  Server selected: {job['server_address']}")
            print(f"  Prompt ID: {job['prompt_id']}")
            print(f"  Status: {job['status']}")

            # Track progress via WebSocket
            print("\n" + "-"*60)
            print("Tracking Execution Progress")
            print("-"*60)

            # Create client for WebSocket tracking
            client = ComfyUIClient(server_address=job['server_address'])

            # Track execution
            completed = threading.Event()
            execution_data = {
                "nodes_executed": [],
                "current_node": None,
                "progress": None,
                "error": None
            }

            def handle_progress(message):
                try:
                    msg_type = message.get('type')
                    data = message.get('data', {})

                    # Filter out noisy monitoring events from custom nodes
                    if msg_type == 'crystools.monitor':
                        # Optionally display GPU utilization if you want
                        # gpus = data.get('gpus', [])
                        # if gpus:
                        #     gpu = gpus[0]
                        #     print(f"[GPU] {gpu['gpu_utilization']}% | VRAM: {gpu['vram_used_percent']:.1f}%", end='\r')
                        return

                    if msg_type == 'status':
                        print(f"\n[STATUS] Queue update")

                    elif msg_type == 'execution_start':
                        print(f"\n[START] Execution started")

                    elif msg_type == 'executing':
                    node = data.get('node')
                    prompt_id = data.get('prompt_id')

                    # Check if this is our prompt
                    if prompt_id == job['prompt_id']:
                        if node is None:
                            # Execution completed
                            print(f"\n[COMPLETE] Execution finished!")
                            completed.set()
                        else:
                            execution_data['current_node'] = node
                            print(f"\n[EXECUTING] Node: {node}")

                elif msg_type == 'progress':
                    value = data.get('value', 0)
                    max_val = data.get('max', 100)
                    percentage = (value / max_val * 100) if max_val > 0 else 0
                    execution_data['progress'] = percentage
                    print(f"[PROGRESS] {value}/{max_val} ({percentage:.1f}%)")

                elif msg_type == 'executed':
                    node = data.get('node')
                    output = data.get('output', {})
                    execution_data['nodes_executed'].append(node)
                    print(f"[EXECUTED] Node {node} completed")
                    if 'images' in output:
                        print(f"           Generated {len(output['images'])} image(s)")

                elif msg_type == 'execution_error':
                    # ALWAYS catch execution errors regardless of prompt_id
                    # Sometimes the prompt_id might not be included in error
                    execution_data['error'] = data
                    print(f"\n{'='*60}")
                    print(f"[ERROR] EXECUTION FAILED")
                    print(f"{'='*60}")

                    # Parse and display error details immediately
                    error_type = data.get('exception_type', 'Unknown Error')
                    error_msg = data.get('exception_message', str(data))
                    node_id = data.get('node_id', 'Unknown')
                    node_type = data.get('node_type', 'Unknown')

                    print(f"\nError Type: {error_type}")
                    print(f"Error Message: {error_msg}")
                    print(f"Failed Node ID: {node_id}")
                    print(f"Failed Node Type: {node_type}")

                    # Show traceback if available
                    if 'traceback' in data:
                        print(f"\nTraceback:")
                        traceback_lines = data['traceback']
                        # Show last 10 lines of traceback
                        for line in traceback_lines[-10:]:
                            print(f"  {line}")

                    print(f"{'='*60}\n")
                    completed.set()

                elif msg_type == 'execution_interrupted':
                    # Handle interruption - also check prompt_id loosely
                    execution_data['error'] = {"interrupted": True}
                    print(f"\n[INTERRUPTED] Execution was interrupted")
                    completed.set()

                    elif msg_type == 'execution_cached':
                        nodes = data.get('nodes', [])
                        print(f"[CACHED] {len(nodes)} node(s) used cached results")

                    else:
                        # Log unknown event types for debugging (but not monitoring)
                        if not msg_type.startswith('crystools'):
                            print(f"\n[UNKNOWN EVENT] Type: {msg_type}")

                except Exception as e:
                    # Catch any errors in the message handler itself
                    print(f"\n[HANDLER ERROR] Error processing message: {e}")
                    print(f"Message was: {message}")
                    import traceback
                    traceback.print_exc()

            print("\nConnecting to ComfyUI WebSocket...")

            # Add error handler for WebSocket
            def handle_ws_error(error):
                print(f"\n[WS ERROR] WebSocket error: {error}")
                execution_data['error'] = {"websocket_error": str(error)}
                completed.set()

            ws = client.track_updates(handle_progress, on_error=handle_ws_error)
            ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
            ws_thread.start()

            print("✓ Connected! Waiting for execution to complete...")
            print("(This may take a while for video generation)\n")

            # Wait for completion with timeout
            timeout = 600  # 10 minutes
            if completed.wait(timeout=timeout):
                ws.close()

                if execution_data['error']:
                    print(f"\n{'='*60}")
                    print(f"✗ EXECUTION FAILED")
                    print(f"{'='*60}")

                    error_data = execution_data['error']

                    # Parse error details
                    if 'interrupted' in error_data:
                        print("Reason: Execution was interrupted")
                    elif 'websocket_error' in error_data:
                        print(f"Reason: WebSocket error - {error_data['websocket_error']}")
                    else:
                        print(f"\nError Type: {error_data.get('exception_type', 'Unknown')}")
                        print(f"Error Message: {error_data.get('exception_message', error_data)}")

                        if 'node_id' in error_data:
                            print(f"Failed Node: {error_data['node_id']}")
                        if 'node_type' in error_data:
                            print(f"Node Type: {error_data['node_type']}")

                        # Show traceback if available
                        if 'traceback' in error_data:
                            print(f"\nTraceback:")
                            for line in error_data['traceback']:
                                print(f"  {line}")

                    print(f"\nNodes executed before error: {len(execution_data['nodes_executed'])}")
                    if execution_data['current_node']:
                        print(f"Last node attempted: {execution_data['current_node']}")

                else:
                    print(f"\n{'='*60}")
                    print(f"✓ EXECUTION COMPLETED SUCCESSFULLY")
                    print(f"{'='*60}")
                    print(f"\nNodes executed: {len(execution_data['nodes_executed'])}")

                    # Get final results
                    final_status = sdk.get_job_status(job['job_id'])
                    print(f"Final job status: {final_status['status']}")

                    if final_status.get('images'):
                        print(f"\nGenerated images: {len(final_status['images'])}")
                        for i, img_url in enumerate(final_status['images'], 1):
                            print(f"  {i}. {img_url}")
            else:
                ws.close()
                print(f"\n{'='*60}")
                print(f"⚠ TIMEOUT")
                print(f"{'='*60}")
                print(f"Execution did not complete within {timeout} seconds")
                print(f"Nodes executed: {len(execution_data['nodes_executed'])}")
                print(f"\nThe workflow may still be running on the server.")
                print(f"Check status with: sdk.get_job_status('{job['job_id']}')")

            print("\n" + "="*60)
            print("✓ Load balancer test completed!")
            print("="*60)

        except Exception as e:
            print(f"\n✗ Workflow execution failed: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print("\nCleaning up...")
        mock_server.shutdown()
        print("✓ Mock server stopped")


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("ComfyUI Load Balancer & Workflow Test")
    print("="*60)
    print("\nThis test will:")
    print("  1. Start a mock ComfyUI server (localhost:8189)")
    print("  2. Register mock and real servers with gateway")
    print("  3. Load the video workflow")
    print("  4. Test load balancer server selection")
    print("  5. Queue the workflow")
    print("  6. Cancel the prompt")
    print("\nMake sure the gateway is running:")
    print("  cd backend && uv run main.py")

    input("\nPress Enter to start test...")

    test_load_balancer()


if __name__ == "__main__":
    main()
