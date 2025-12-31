"""
SDK for Temporal-based ComfyUI Gateway

Simpler SDK that leverages Temporal's durable execution.
"""

import requests
import time
from typing import Dict, Any, Optional


class TemporalComfyUISDK:
    """
    SDK for Temporal-based ComfyUI execution

    Much simpler than the original SDK because Temporal handles:
    - State persistence
    - Retry logic
    - Progress tracking
    - Crash recovery
    """

    def __init__(self, gateway_url: str = "http://localhost:8001"):
        """
        Initialize SDK

        Args:
            gateway_url: URL of Temporal gateway
        """
        self.gateway_url = gateway_url.rstrip('/')
        self.session = requests.Session()

    def execute_workflow(
        self,
        workflow: Dict[str, Any],
        strategy: str = "least_loaded",
        wait: bool = True,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute a ComfyUI workflow

        Args:
            workflow: Workflow definition
            strategy: Server selection strategy
            wait: Whether to wait for completion
            poll_interval: How often to poll for status (seconds)
            timeout: Maximum wait time (seconds)

        Returns:
            Execution result with images and log path
        """
        # Start workflow
        payload = {
            "workflow": workflow,
            "strategy": strategy
        }

        response = self.session.post(
            f"{self.gateway_url}/workflow/execute",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        workflow_id = result["workflow_id"]

        print(f"Workflow started: {workflow_id}")
        print(f"Temporal UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")

        if not wait:
            return {"workflow_id": workflow_id, "status": "started"}

        # Poll for completion
        return self.wait_for_completion(workflow_id, poll_interval, timeout)

    def wait_for_completion(
        self,
        workflow_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Wait for workflow to complete

        Args:
            workflow_id: Workflow ID to wait for
            poll_interval: How often to poll (seconds)
            timeout: Maximum wait time (seconds)

        Returns:
            Final execution result
        """
        start_time = time.time()

        while True:
            status = self.get_status(workflow_id)

            # Print progress
            if status.get("current_node"):
                print(f"[{status['status']}] Node: {status['current_node']}, Progress: {status.get('progress', 0)*100:.1f}%")

            # Check if done
            if status["status"] in ("completed", "failed", "cancelled"):
                print(f"\nWorkflow {status['status']}!")
                return status

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Workflow did not complete within {timeout}s")

            time.sleep(poll_interval)

    def get_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get current workflow status

        Args:
            workflow_id: Workflow ID

        Returns:
            Status dictionary
        """
        response = self.session.get(f"{self.gateway_url}/workflow/status/{workflow_id}")
        response.raise_for_status()
        return response.json()

    def cancel_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Cancel a running workflow

        Args:
            workflow_id: Workflow ID to cancel

        Returns:
            Cancellation result
        """
        response = self.session.post(f"{self.gateway_url}/workflow/cancel/{workflow_id}")
        response.raise_for_status()
        return response.json()

    def register_server(
        self,
        name: str,
        address: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a ComfyUI server"""
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

    def list_servers(self) -> Dict[str, Any]:
        """List all registered servers"""
        response = self.session.get(f"{self.gateway_url}/servers")
        response.raise_for_status()
        return response.json()

    def get_servers_health(self) -> Dict[str, Any]:
        """Get health of all servers"""
        response = self.session.get(f"{self.gateway_url}/servers/health")
        response.raise_for_status()
        return response.json()
