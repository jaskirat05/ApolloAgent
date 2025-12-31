"""
ComfyUI HTTP Client

Handles all HTTP API calls to ComfyUI server.
"""

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ComfyHTTPClient:
    """HTTP client for ComfyUI REST API"""

    def __init__(self, server_address: str):
        self.server_address = server_address.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)

    async def queue_prompt(self, workflow: Dict[str, Any], client_id: str) -> Dict[str, Any]:
        """
        Submit a workflow to the queue

        Args:
            workflow: ComfyUI workflow JSON
            client_id: Client identifier

        Returns:
            Response dict with prompt_id
        """
        url = f"{self.server_address}/prompt"
        payload = {
            "prompt": workflow,
            "client_id": client_id
        }

        logger.debug(f"POST {url}")
        response = await self.client.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    async def get_history(self, prompt_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution history

        Args:
            prompt_id: Optional specific prompt ID to fetch

        Returns:
            History dict
        """
        if prompt_id:
            url = f"{self.server_address}/history/{prompt_id}"
        else:
            url = f"{self.server_address}/history"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_queue(self) -> Dict[str, Any]:
        """Get current queue status"""
        url = f"{self.server_address}/queue"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def download_file(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output"
    ) -> bytes:
        """
        Download a file from ComfyUI server

        Args:
            filename: Name of the file
            subfolder: Subfolder within the output directory
            folder_type: Type of folder (output, temp, input)

        Returns:
            File content as bytes
        """
        params = {
            "filename": filename,
            "type": folder_type
        }

        if subfolder:
            params["subfolder"] = subfolder

        url = f"{self.server_address}/view"

        logger.debug(f"GET {url} with params {params}")
        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.content

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        subfolder: str = "",
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Upload a file to ComfyUI input directory

        Args:
            file_data: File content as bytes
            filename: Name for the uploaded file
            subfolder: Target subfolder in input directory
            overwrite: Whether to overwrite existing files

        Returns:
            Upload response dict
        """
        url = f"{self.server_address}/upload/image"

        files = {"image": (filename, file_data, "image/png")}
        data = {
            "subfolder": subfolder,
            "overwrite": str(overwrite).lower()
        }

        logger.debug(f"POST {url} - uploading {filename}")
        response = await self.client.post(url, files=files, data=data)
        response.raise_for_status()

        return response.json()

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        url = f"{self.server_address}/system_stats"

        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_object_info(self, node_class: Optional[str] = None) -> Dict[str, Any]:
        """
        Get node definitions and available nodes

        Args:
            node_class: Optional specific node class to get info for

        Returns:
            Dict of node definitions with inputs, outputs, and parameters
            If node_class is specified, returns info for that specific node
            Otherwise returns all available nodes
        """
        if node_class:
            url = f"{self.server_address}/object_info/{node_class}"
        else:
            url = f"{self.server_address}/object_info"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_models(self) -> list[str]:
        """
        Get list of available model categories

        Returns:
            List of model category names (e.g., ['checkpoints', 'loras', 'vae'])
        """
        url = f"{self.server_address}/models"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_models_by_category(self, category: str) -> list[str]:
        """
        Get list of models in a specific category

        Args:
            category: Model category (e.g., 'checkpoints', 'loras', 'vae')

        Returns:
            List of model filenames in that category
        """
        url = f"{self.server_address}/models/{category}"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_embeddings(self) -> list[str]:
        """
        Get list of available embeddings

        Returns:
            List of embedding names
        """
        url = f"{self.server_address}/embeddings"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_extensions(self) -> list[str]:
        """
        Get list of available extensions

        Returns:
            List of extension names
        """
        url = f"{self.server_address}/extensions"

        logger.debug(f"GET {url}")
        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
