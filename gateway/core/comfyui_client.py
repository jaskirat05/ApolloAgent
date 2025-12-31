"""
ComfyUI API Client

A Python client for interacting with ComfyUI backend API endpoints.
Provides functions to queue prompts, track execution, and retrieve results.
"""

import json
import uuid
import requests
import websocket
from typing import Optional, Callable, Dict, Any
from pathlib import Path


class ComfyUIClient:
    """Client for interacting with ComfyUI API"""

    def __init__(self, server_address: str = "127.0.0.1:8188", client_id: Optional[str] = None):
        """
        Initialize ComfyUI client

        Args:
            server_address: ComfyUI server address (default: "127.0.0.1:8188")
            client_id: Unique client ID for tracking updates (auto-generated if not provided)
        """
        self.server_address = server_address
        self.client_id = client_id or str(uuid.uuid4())
        self.http_url = f"http://{server_address}"
        self.ws_url = f"ws://{server_address}/ws?clientId={self.client_id}"

    def post_prompt(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queue a workflow for execution

        Args:
            workflow: Workflow definition (from API format export)

        Returns:
            Response containing prompt_id and other details

        Raises:
            requests.HTTPError: With detailed error message from ComfyUI

        Example:
            >>> client = ComfyUIClient()
            >>> with open('workflow_api.json') as f:
            ...     workflow = json.load(f)
            >>> result = client.post_prompt(workflow)
            >>> print(f"Prompt ID: {result['prompt_id']}")
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        response = requests.post(
            f"{self.http_url}/prompt",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        # Check for errors and include response body in error message
        if not response.ok:
            try:
                error_data = response.json()
                error_msg = f"ComfyUI Error ({response.status_code}): {json.dumps(error_data, indent=2)}"
            except:
                error_msg = f"ComfyUI Error ({response.status_code}): {response.text}"

            # Create a proper exception with the detailed message
            error = requests.HTTPError(error_msg, response=response)
            error.args = (error_msg,)  # Ensure str(error) returns our message
            raise error

        return response.json()

    def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """
        Get execution history and results for a specific prompt

        Args:
            prompt_id: The prompt ID to retrieve history for

        Returns:
            History data including outputs and generated images

        Example:
            >>> client = ComfyUIClient()
            >>> history = client.get_history(prompt_id)
            >>> outputs = history[prompt_id]['outputs']
        """
        response = requests.get(f"{self.http_url}/history/{prompt_id}")
        response.raise_for_status()
        return response.json()

    def get_queue(self) -> Dict[str, Any]:
        """
        Get current queue status

        Returns:
            Queue status with running and pending prompts
        """
        response = requests.get(f"{self.http_url}/queue")
        response.raise_for_status()
        return response.json()

    def interrupt(self) -> None:
        """Stop the currently executing prompt (global interrupt)"""
        response = requests.post(f"{self.http_url}/interrupt")
        response.raise_for_status()

    def cancel_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """
        Cancel a specific prompt from the queue

        Args:
            prompt_id: The prompt ID to cancel

        Returns:
            Response from server

        Note:
            This removes the prompt from the queue. For running prompts,
            use interrupt() instead.
        """
        payload = {"delete": [prompt_id]}
        response = requests.post(f"{self.http_url}/queue", json=payload)
        response.raise_for_status()
        return response.json()

    def track_updates(self, on_message: Callable[[Dict[str, Any]], None],
                     on_error: Optional[Callable[[Exception], None]] = None) -> websocket.WebSocketApp:
        """
        Track real-time updates via WebSocket

        Args:
            on_message: Callback function to handle incoming messages
            on_error: Optional callback for error handling

        Returns:
            WebSocketApp instance (call run_forever() to start)

        Example:
            >>> def handle_message(message):
            ...     if message['type'] == 'progress':
            ...         print(f"Progress: {message['data']}")
            ...     elif message['type'] == 'executed':
            ...         print("Execution completed!")
            >>>
            >>> client = ComfyUIClient()
            >>> ws = client.track_updates(handle_message)
            >>> ws.run_forever()  # Blocking call
        """
        def on_ws_message(ws, message):
            try:
                data = json.loads(message)
                on_message(data)
            except json.JSONDecodeError as e:
                if on_error:
                    on_error(e)

        def on_ws_error(ws, error):
            if on_error:
                on_error(error)

        ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=on_ws_message,
            on_error=on_ws_error
        )

        return ws

    def download_image(self, filename: str, subfolder: str = "",
                      image_type: str = "output", save_path: Optional[Path] = None) -> bytes:
        """
        Download an image from ComfyUI

        Args:
            filename: Name of the image file
            subfolder: Subfolder path (empty string for root)
            image_type: Type of image - 'output', 'input', or 'temp'
            save_path: Optional path to save the image (if None, returns bytes)

        Returns:
            Image data as bytes

        Example:
            >>> client = ComfyUIClient()
            >>> # Download and save
            >>> client.download_image("image.png", save_path=Path("output.png"))
            >>>
            >>> # Get bytes
            >>> image_data = client.download_image("image.png")
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": image_type
        }

        response = requests.get(f"{self.http_url}/view", params=params)
        response.raise_for_status()

        image_data = response.content

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(image_data)

        return image_data

    def upload_image(self, image_path: Path, subfolder: str = "",
                    overwrite: bool = False) -> Dict[str, Any]:
        """
        Upload an image to ComfyUI

        Args:
            image_path: Path to the image file
            subfolder: Target subfolder (empty for root)
            overwrite: Whether to overwrite existing files

        Returns:
            Upload response with filename and details
        """
        image_path = Path(image_path)

        with open(image_path, 'rb') as f:
            files = {'image': (image_path.name, f, 'image/png')}
            data = {
                'subfolder': subfolder,
                'overwrite': str(overwrite).lower()
            }

            response = requests.post(
                f"{self.http_url}/upload/image",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system and device statistics

        Returns:
            System information including Python version, OS, device info
        """
        response = requests.get(f"{self.http_url}/system_stats")
        response.raise_for_status()
        return response.json()

    def get_object_info(self) -> Dict[str, Any]:
        """
        Get definitions of available nodes

        Returns:
            Node definitions with inputs, outputs, and parameters
        """
        response = requests.get(f"{self.http_url}/object_info")
        response.raise_for_status()
        return response.json()

    def get_output_files(self, history_data: Dict[str, Any]) -> list[Dict[str, str]]:
        """
        Extract output file paths from history data (server-side paths)

        This returns the actual paths where ComfyUI saved files on the server,
        NOT local downloads. Use this for chain execution to pass files between workflows.

        Args:
            history_data: History data from get_history() for a specific prompt

        Returns:
            List of file info dicts with server paths:
            [
                {
                    "filename": "output_00001.mp4",
                    "subfolder": "",
                    "type": "output",
                    "node_id": "123"
                }
            ]

        Example:
            >>> history = client.get_history(prompt_id)
            >>> files = client.get_output_files(history[prompt_id])
            >>> print(files[0]['filename'])  # "output_00001.mp4"
        """
        output_files = []
        outputs = history_data.get('outputs', {})

        for node_id, node_output in outputs.items():
            # Check for images
            if 'images' in node_output:
                for img_info in node_output['images']:
                    output_files.append({
                        "filename": img_info['filename'],
                        "subfolder": img_info.get('subfolder', ''),
                        "type": img_info.get('type', 'output'),
                        "node_id": node_id
                    })

            # Check for videos (if different structure)
            if 'videos' in node_output:
                for vid_info in node_output['videos']:
                    output_files.append({
                        "filename": vid_info['filename'],
                        "subfolder": vid_info.get('subfolder', ''),
                        "type": vid_info.get('type', 'output'),
                        "node_id": node_id
                    })

        return output_files





if __name__ == "__main__":
    # Example usage
    print("ComfyUI Client Example")
    print("=" * 50)

    # Initialize client
    client = ComfyUIClient()

    # Check system stats
    try:
        stats = client.get_system_stats()
        print(f"Connected to ComfyUI")
        print(f"System: {stats.get('system', {})}")
    except Exception as e:
        print(f"Error connecting to ComfyUI: {e}")
        print("Make sure ComfyUI is running on http://127.0.0.1:8188")
