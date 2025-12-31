"""
ComfyUI Client

Main client interface for interacting with ComfyUI servers.
"""

import uuid
import logging
import httpx
from typing import Dict, Any, Optional, Callable

from temporal_gateway.clients.comfy.models import WorkflowResult, ExecutionStatus, ProgressUpdate
from temporal_gateway.clients.comfy.http import ComfyHTTPClient
from temporal_gateway.clients.comfy.websocket import ComfyWebSocketClient
from temporal_gateway.clients.comfy.tracker import ExecutionTracker

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """
    High-level client for ComfyUI

    Features:
    - Simple workflow execution with automatic tracking
    - Handles fast-completing workflows (race conditions)
    - WebSocket + HTTP polling hybrid approach
    - Progress callbacks

    Usage:
        client = ComfyUIClient("http://localhost:8188")
        result = await client.execute_workflow(workflow_json)
        if result.is_success:
            print(f"Outputs: {result.outputs}")
    """

    def __init__(self, server_address: str, client_id: Optional[str] = None):
        """
        Initialize ComfyUI client

        Args:
            server_address: ComfyUI server address (e.g., "http://localhost:8188")
            client_id: Optional client ID (generated if not provided)
        """
        self.server_address = server_address.rstrip('/')
        self.client_id = client_id or str(uuid.uuid4())

        # Initialize sub-clients
        self.http = ComfyHTTPClient(self.server_address)
        self.ws = ComfyWebSocketClient(self.server_address, self.client_id)

        logger.info(f"ComfyUI client initialized for {self.server_address}")

    async def execute_workflow(
        self,
        workflow: Dict[str, Any],
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None,
        timeout: float = 600.0
    ) -> WorkflowResult:
        """
        Execute a workflow and wait for completion

        Args:
            workflow: ComfyUI workflow JSON
            progress_callback: Optional callback for progress updates
            timeout: Execution timeout in seconds

        Returns:
            WorkflowResult with execution status and outputs
        """
        logger.info("Submitting workflow to ComfyUI")

        # Submit workflow
        response = await self.http.queue_prompt(workflow, self.client_id)
        prompt_id = response.get('prompt_id')

        if not prompt_id:
            return WorkflowResult(
                status=ExecutionStatus.ERROR,
                prompt_id="",
                server_address=self.server_address,
                error="Failed to get prompt_id from server"
            )

        logger.info(f"Workflow queued with prompt_id: {prompt_id}")

        # Track execution
        tracker = ExecutionTracker(
            http_client=self.http,
            ws_client=self.ws,
            prompt_id=prompt_id,
            server_address=self.server_address,
            progress_callback=progress_callback,
            timeout=timeout
        )

        tracking_result = await tracker.track()

        # Build WorkflowResult
        if tracking_result.status == ExecutionStatus.SUCCESS:
            # Extract outputs from history
            outputs = tracking_result.history_data.get('outputs', {})

            return WorkflowResult(
                status=ExecutionStatus.SUCCESS,
                prompt_id=prompt_id,
                server_address=self.server_address,
                outputs=outputs
            )

        else:
            return WorkflowResult(
                status=tracking_result.status,
                prompt_id=prompt_id,
                server_address=self.server_address,
                error=tracking_result.error
            )

    async def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get history for a specific prompt"""
        history = await self.http.get_history(prompt_id)
        return history.get(prompt_id)

    async def download_file(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """Download a file from ComfyUI server"""
        return await self.http.download_file(filename, subfolder, folder_type)

    async def upload_file(self, file_data: bytes, filename: str, subfolder: str = "", overwrite: bool = True) -> Dict[str, Any]:
        """Upload a file to ComfyUI input directory"""
        return await self.http.upload_file(file_data, filename, subfolder, overwrite)

    async def get_object_info(self, node_class: Optional[str] = None) -> Dict[str, Any]:
        """
        Get node definitions and available nodes

        Args:
            node_class: Optional specific node class to get info for

        Returns:
            Dict of node definitions with inputs, outputs, and parameters
        """
        return await self.http.get_object_info(node_class)

    async def get_models(self) -> list[str]:
        """
        Get list of available model categories

        Returns:
            List of model category names (e.g., ['checkpoints', 'loras', 'vae'])
        """
        return await self.http.get_models()

    async def get_models_by_category(self, category: str) -> list[str]:
        """
        Get list of models in a specific category

        Args:
            category: Model category (e.g., 'checkpoints', 'loras', 'vae')

        Returns:
            List of model filenames in that category
        """
        return await self.http.get_models_by_category(category)

    async def get_embeddings(self) -> list[str]:
        """Get list of available embeddings"""
        return await self.http.get_embeddings()

    async def get_extensions(self) -> list[str]:
        """Get list of available extensions"""
        return await self.http.get_extensions()

    async def close(self):
        """Close client connections"""
        await self.http.close()
        # WebSocket closes automatically when connection ends
