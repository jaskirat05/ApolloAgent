"""
ComfyUI WebSocket Client

Handles real-time updates from ComfyUI server via WebSocket.
"""

import json
import logging
import asyncio
from typing import Dict, Any, AsyncIterator, Optional
import websockets

logger = logging.getLogger(__name__)


class ComfyWebSocketClient:
    """WebSocket client for ComfyUI real-time updates"""

    def __init__(self, server_address: str, client_id: str):
        # Convert HTTP URL to WebSocket URL
        self.ws_url = server_address.replace('http://', 'ws://').replace('https://', 'wss://')
        self.ws_url = f"{self.ws_url.rstrip('/')}/ws?clientId={client_id}"
        self.client_id = client_id

    async def listen(self, prompt_id: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Listen to WebSocket messages

        Args:
            prompt_id: Optional prompt ID to filter messages

        Yields:
            Message dictionaries from WebSocket
        """
        logger.info(f"Connecting to WebSocket: {self.ws_url}")

        try:
            async with websockets.connect(self.ws_url) as websocket:
                logger.info("WebSocket connected successfully")

                while True:
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=1.0  # 1 second timeout to allow cancellation
                        )

                        data = json.loads(message)

                        # If filtering by prompt_id, only yield relevant messages
                        if prompt_id:
                            msg_prompt_id = data.get('data', {}).get('prompt_id')
                            if msg_prompt_id and msg_prompt_id != prompt_id:
                                continue

                        yield data

                    except asyncio.TimeoutError:
                        # Timeout allows cancellation, continue listening
                        continue

                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        break

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            # Don't raise - let the tracker handle fallback to polling
