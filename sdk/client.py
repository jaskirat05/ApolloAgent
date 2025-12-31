"""
ComfyUI SDK

Simple Python SDK for executing ComfyUI workflows via the gateway API.
Handles server selection, execution, and image retrieval automatically.
"""

import requests
import time
import json
import threading
import websocket
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path


class WorkflowJob:
    """
    Represents a workflow execution job with WebSocket tracking capabilities

    This class wraps job information and provides methods to track real-time
    updates from ComfyUI during async execution.
    """

    def __init__(
        self,
        job_data: Dict[str, Any],
        gateway_url: str,
        session: requests.Session
    ):
        """
        Initialize a WorkflowJob

        Args:
            job_data: Job information from gateway
            gateway_url: Gateway URL for API calls
            session: Requests session for API calls
        """
        self.job_data = job_data
        self.gateway_url = gateway_url
        self.session = session
        self._ws_thread = None
        self._ws_app = None
        self._tracking_active = False

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to job data"""
        return self.job_data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get job data with default"""
        return self.job_data.get(key, default)

    @property
    def job_id(self) -> str:
        """Get job ID"""
        return self.job_data["job_id"]

    @property
    def prompt_id(self) -> Optional[str]:
        """Get prompt ID"""
        return self.job_data.get("prompt_id")

    @property
    def server_address(self) -> str:
        """Get server address"""
        return self.job_data["server_address"]

    @property
    def status(self) -> str:
        """Get current status"""
        return self.job_data["status"]

    def refresh_status(self) -> Dict[str, Any]:
        """
        Refresh job status from gateway

        Returns:
            Updated job status
        """
        response = self.session.get(f"{self.gateway_url}/workflow/status/{self.job_id}")
        response.raise_for_status()
        self.job_data = response.json()
        return self.job_data

    def track_updates(
        self,
        message_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
        error_handler: Optional[Callable[[Exception], None]] = None,
        block: bool = False
    ) -> threading.Thread:
        """
        Track real-time WebSocket updates for this job

        Spawns a background thread that connects to ComfyUI's WebSocket and
        processes execution events in real-time.

        Args:
            message_handler: Custom handler for WebSocket messages.
                If None, uses generic handler that logs and prints to console.
                Signature: (message: Dict[str, Any]) -> None
            error_handler: Custom handler for errors.
                If None, prints errors to console.
                Signature: (error: Exception) -> None
            block: If True, blocks until execution completes.
                If False, returns thread immediately (default).

        Returns:
            The background thread tracking updates

        Example:
            >>> # Use default generic handler
            >>> job = sdk.execute_workflow_async(workflow)
            >>> job.track_updates(block=True)  # Blocks and prints everything

            >>> # Use custom handler
            >>> def my_handler(msg):
            ...     if msg['type'] == 'progress':
            ...         print(f"Progress: {msg['data']['value']}")
            >>> job.track_updates(message_handler=my_handler)
        """
        if self._tracking_active:
            raise RuntimeError("Already tracking updates for this job")

        if not self.prompt_id:
            raise RuntimeError("Cannot track updates: no prompt_id available")

        # Use generic handler if none provided
        if message_handler is None:
            message_handler = self._create_generic_handler()

        if error_handler is None:
            error_handler = self._create_generic_error_handler()

        # WebSocket URL
        ws_url = f"ws://{self.server_address}/ws"

        # Create completion event
        completion_event = threading.Event()

        def on_message(ws, message):
            try:
                data = json.loads(message)
                msg_type = data.get('type')

               

                # Check for completion
                if msg_type == 'executing':
                    node_data = data.get('data', {})
                    if node_data.get('node') is None and node_data.get('prompt_id') == self.prompt_id:
                        completion_event.set()

                elif msg_type in ('execution_error', 'execution_interrupted'):
                    completion_event.set()
                 # Call user handler
                message_handler(data)

            except Exception as e:
                error_handler(e)

        def on_error(ws, error):
            error_handler(error)

        def on_close(ws, close_status_code, close_msg):
            self._tracking_active = False
            completion_event.set()

        def on_open(ws):
            self._tracking_active = True

        # Create WebSocket app
        self._ws_app = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        # Start WebSocket in background thread
        def run_websocket():
            self._ws_app.run_forever()

        self._ws_thread = threading.Thread(target=run_websocket, daemon=True)
        self._ws_thread.start()

        if block:
            # Wait for completion
            completion_event.wait()
            self.stop_tracking()

        return self._ws_thread

    def stop_tracking(self):
        """Stop WebSocket tracking"""
        if self._ws_app:
            self._ws_app.close()
        self._tracking_active = False

    def _create_generic_handler(self) -> Callable[[Dict[str, Any]], None]:
        """
        Create a generic message handler that logs and prints to console

        Returns:
            Generic message handler function
        """
        def generic_handler(message: Dict[str, Any]):
            msg_type = message.get('type')
            data = message.get('data', {})
            timestamp = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]

            # Print different message types with appropriate formatting
            if msg_type == 'executing':
                node = data.get('node')
                if node is None:
                    print(f"[{timestamp}] Execution completed")
                else:
                    print(f"[{timestamp}] Executing node: {node}")

            elif msg_type == 'executed':
                node = data.get('node')
                print(f"[{timestamp}] Node completed: {node}")

            elif msg_type == 'progress':
                value = data.get('value', 0)
                max_val = data.get('max', 100)
                percent = (value / max_val * 100) if max_val > 0 else 0
                print(f"[{timestamp}] Progress: {value}/{max_val} ({percent:.1f}%)", end='\r')

            elif msg_type == 'execution_start':
                print(f"[{timestamp}] Execution started")

            elif msg_type == 'execution_cached':
                nodes = data.get('nodes', [])
                print(f"[{timestamp}] {len(nodes)} node(s) cached")

            elif msg_type == 'execution_error':
                error_msg = data.get('exception_message', 'Unknown error')
                print(f"\n[{timestamp}] ERROR: {error_msg}")

            elif msg_type == 'execution_interrupted':
                print(f"\n[{timestamp}] Execution interrupted")

            else:
                # Log all other message types
                print(f"[{timestamp}] {msg_type}: {data}")

        return generic_handler

    def _create_generic_error_handler(self) -> Callable[[Exception], None]:
        """
        Create a generic error handler that prints to console

        Returns:
            Generic error handler function
        """
        def generic_error_handler(error: Exception):
            timestamp = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] WebSocket Error: {error}")

        return generic_error_handler

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.job_data.copy()


class ComfyUISDK:
    """
    Simple SDK for ComfyUI workflow execution

    This SDK abstracts away the complexity of:
    - Server selection
    - Workflow queuing
    - Progress tracking
    - Image downloading

    Example:
        >>> sdk = ComfyUISDK(gateway_url="http://localhost:8000")
        >>> result = sdk.execute_workflow(workflow)
        >>> print(result["images"])  # List of image URLs
    """

    def __init__(self, gateway_url: str = "http://localhost:8000"):
        """
        Initialize the SDK

        Args:
            gateway_url: URL of the ComfyUI gateway API
        """
        self.gateway_url = gateway_url.rstrip('/')
        self.session = requests.Session()

    def execute_workflow(
        self,
        workflow: Dict[str, Any],
        wait: bool = True,
        strategy: str = "least_loaded",
        track_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a ComfyUI workflow

        This is the main SDK method. It automatically:
        1. Selects the best available ComfyUI server
        2. Queues the workflow
        3. Waits for completion (if wait=True) with real-time progress tracking
        4. Downloads and stores images
        5. Returns image URLs

        In sync mode (wait=True), automatically tracks and prints execution
        progress to console in real-time.

        Args:
            workflow: Workflow definition (from ComfyUI API format export)
            wait: Whether to wait for completion (default: True)
            strategy: Server selection strategy:
                - "least_loaded": Choose server with fewest queued items (default)
                - "round_robin": Distribute evenly across servers
                - "random": Random selection
            track_progress: Whether to print real-time progress to console
                (only applies when wait=True, default: True)

        Returns:
            Dictionary with execution results:
            {
                "job_id": "...",
                "status": "completed",
                "server_address": "127.0.0.1:8188",
                "prompt_id": "...",
                "images": ["http://localhost:8000/images/abc.png", ...],
                "queued_at": "2025-01-01T00:00:00",
                "completed_at": "2025-01-01T00:01:00",
                "log_file_path": "/path/to/log.jsonl"
            }

        Example:
            >>> import json
            >>> with open('workflow_api.json') as f:
            ...     workflow = json.load(f)
            >>> result = sdk.execute_workflow(workflow)
            >>> for url in result["images"]:
            ...     print(f"Generated: {url}")
        """
        if wait and track_progress:
            # Sync mode with real-time tracking:
            # Queue the job (non-blocking) and track WebSocket ourselves
            payload = {
                "workflow": workflow,
                "wait_for_completion": False,  # Don't wait in gateway
                "strategy": strategy
            }

            response = self.session.post(
                f"{self.gateway_url}/workflow/execute",
                json=payload
            )

            if not response.ok:
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', error_data)
                    error_msg = f"Gateway Error ({response.status_code}): {error_detail}"
                except:
                    error_msg = f"Gateway Error ({response.status_code}): {response.text}"
                error = requests.HTTPError(error_msg, response=response)
                error.args = (error_msg,)
                raise error

            job_data = response.json()

            # Create WorkflowJob and track updates with blocking
            job = WorkflowJob(job_data, self.gateway_url, self.session)

            # Track updates with generic handler (blocks until completion)
            print(f"\n{'='*60}")
            print(f"Workflow Execution Started")
            print(f"{'='*60}")
            print(f"Job ID: {job.job_id}")
            print(f"Server: {job.server_address}")
            print(f"{'='*60}\n")

            try:
                job.track_updates(block=True)
            except Exception as e:
                print(f"\nTracking error: {e}")

            # Refresh status to get final results
            final_status = job.refresh_status()

            print(f"\n{'='*60}")
            print(f"Execution Complete")
            print(f"{'='*60}")
            print(f"Status: {final_status['status']}")
            if final_status.get('images'):
                print(f"Images: {len(final_status['images'])}")
            if final_status.get('log_file_path'):
                print(f"Log: {final_status['log_file_path']}")
            print(f"{'='*60}\n")

            return final_status

        else:
            # Non-tracking mode (async or no progress tracking)
            payload = {
                "workflow": workflow,
                "wait_for_completion": wait,
                "strategy": strategy
            }

            response = self.session.post(
                f"{self.gateway_url}/workflow/execute",
                json=payload
            )

            # Check for errors and include response body in error message
            if not response.ok:
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', error_data)
                    error_msg = f"Gateway Error ({response.status_code}): {error_detail}"
                except:
                    error_msg = f"Gateway Error ({response.status_code}): {response.text}"

                # Create a proper exception with the detailed message
                error = requests.HTTPError(error_msg, response=response)
                error.args = (error_msg,)  # Ensure str(error) returns our message
                raise error

            return response.json()

    def execute_workflow_async(
        self,
        workflow: Dict[str, Any],
        strategy: str = "least_loaded"
    ) -> WorkflowJob:
        """
        Execute a workflow asynchronously (non-blocking)

        Queues the workflow and returns immediately with a WorkflowJob.
        Use job.track_updates() to monitor real-time progress, or
        job.refresh_status() to poll for completion.

        Args:
            workflow: Workflow definition
            strategy: Server selection strategy

        Returns:
            WorkflowJob object with track_updates() method

        Example:
            >>> # Queue and track with default handler
            >>> job = sdk.execute_workflow_async(workflow)
            >>> print(f"Job queued: {job.job_id}")
            >>> job.track_updates(block=True)  # Blocks and prints progress

            >>> # Queue and track with custom handler
            >>> job = sdk.execute_workflow_async(workflow)
            >>> def my_handler(msg):
            ...     if msg['type'] == 'progress':
            ...         print(f"Progress: {msg['data']['value']}")
            >>> job.track_updates(message_handler=my_handler)

            >>> # Queue and poll manually
            >>> job = sdk.execute_workflow_async(workflow)
            >>> # Do other work...
            >>> status = job.refresh_status()
            >>> if status['status'] == 'completed':
            ...     print(status['images'])
        """
        job_data = self.execute_workflow(workflow, wait=False, strategy=strategy, track_progress=False)
        return WorkflowJob(job_data, self.gateway_url, self.session)

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of an async job

        Args:
            job_id: Job ID from execute_workflow_async()

        Returns:
            Job status dictionary

        Example:
            >>> status = sdk.get_job_status(job_id)
            >>> print(status['status'])  # 'queued', 'completed', or 'failed'
        """
        response = self.session.get(f"{self.gateway_url}/workflow/status/{job_id}")
        response.raise_for_status()
        return response.json()

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Wait for an async job to complete

        Args:
            job_id: Job ID to wait for
            poll_interval: How often to check status (seconds)
            timeout: Maximum time to wait (seconds), None for no timeout

        Returns:
            Completed job status

        Raises:
            TimeoutError: If timeout is exceeded
            RuntimeError: If job failed

        Example:
            >>> job = sdk.execute_workflow_async(workflow)
            >>> result = sdk.wait_for_job(job['job_id'], timeout=300)
            >>> print(result['images'])
        """
        start_time = time.time()

        while True:
            status = self.get_job_status(job_id)

            if status['status'] == 'completed':
                return status

            if status['status'] == 'failed':
                error = status.get('error', 'Unknown error')
                raise RuntimeError(f"Job failed: {error}")

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")

            time.sleep(poll_interval)

    def download_image(self, image_url: str, save_path: Optional[Path] = None) -> bytes:
        """
        Download an image from the gateway

        Args:
            image_url: Image URL from execution results
            save_path: Optional path to save the image

        Returns:
            Image bytes

        Example:
            >>> result = sdk.execute_workflow(workflow)
            >>> for url in result["images"]:
            ...     sdk.download_image(url, save_path=Path(f"output_{i}.png"))
        """
        response = self.session.get(image_url)
        response.raise_for_status()

        image_data = response.content

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(image_data)

        return image_data

    def register_server(
        self,
        name: str,
        address: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new ComfyUI server with the gateway

        Args:
            name: Friendly name for the server
            address: Server address (e.g., '127.0.0.1:8188')
            description: Optional description

        Returns:
            Registration response

        Example:
            >>> sdk.register_server(
            ...     name="Main Server",
            ...     address="127.0.0.1:8188",
            ...     description="Primary ComfyUI instance"
            ... )
        """
        payload = {
            "name": name,
            "address": address,
            "description": description
        }

        response = self.session.post(
            f"{self.gateway_url}/servers/register",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def list_servers(self) -> List[Dict[str, Any]]:
        """
        List all registered ComfyUI servers

        Returns:
            List of server configurations
        """
        response = self.session.get(f"{self.gateway_url}/servers")
        response.raise_for_status()
        return response.json()['servers']

    def get_servers_health(self) -> Dict[str, Any]:
        """
        Get health status of all servers

        Returns:
            Health information for all servers

        Example:
            >>> health = sdk.get_servers_health()
            >>> for server in health['servers']:
            ...     print(f"{server['address']}: {server['total_load']} jobs")
        """
        response = self.session.get(f"{self.gateway_url}/servers/health")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict[str, Any]:
        """
        Check if the gateway is healthy

        Returns:
            Health status
        """
        response = self.session.get(f"{self.gateway_url}/health")
        response.raise_for_status()
        return response.json()


# Convenience functions for one-off usage
def execute_workflow(
    workflow: Dict[str, Any],
    gateway_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Convenience function to execute a workflow without creating SDK instance

    Args:
        workflow: Workflow definition
        gateway_url: Gateway URL

    Returns:
        Execution results

    Example:
        >>> from sdk.client import execute_workflow
        >>> result = execute_workflow(my_workflow)
    """
    sdk = ComfyUISDK(gateway_url=gateway_url)
    return sdk.execute_workflow(workflow)
