"""
Workflow Tracking Module

This module provides a clean, reusable interface for tracking ComfyUI workflow
execution via WebSocket connections.

Key features:
- Configurable message type filtering
- Clean separation from Temporal activities
- Reusable in any context (not just Temporal)
- Easy to test and maintain
"""

import asyncio
import threading
import time
import logging
from typing import Dict, Any, Optional, Set, Callable
from pathlib import Path
import sys

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

from gateway.core import ComfyUIClient

# Setup logging
logger = logging.getLogger(__name__)


# Default message types to track
DEFAULT_TRACKED_MESSAGES = {
    'executing',
    'executed',
    'progress',
    'execution_start',
    'execution_cached',
    'execution_error',
    'execution_interrupted',
    'status'
}


class WorkflowTracker:
    """
    Tracks ComfyUI workflow execution via WebSocket

    This class handles:
    - WebSocket connection management
    - Message filtering (by prompt_id and message type)
    - Execution state tracking
    - Completion detection

    Example:
        tracker = WorkflowTracker(
            prompt_id="abc-123",
            server_address="server-1.example.com",
            client_id="client-xyz",
            tracked_message_types={'executing', 'progress', 'execution_error'}
        )

        result = await tracker.track(
            heartbeat_callback=lambda data: print(f"Progress: {data}")
        )
    """

    def __init__(
        self,
        prompt_id: str,
        server_address: str,
        client_id: str,
        tracked_message_types: Optional[Set[str]] = None,
        timeout: int = 1800  # 30 minutes default
    ):
        """
        Initialize workflow tracker

        Args:
            prompt_id: ComfyUI prompt ID to track
            server_address: ComfyUI server address
            client_id: Client ID for WebSocket (must match the one used to queue)
            tracked_message_types: Set of message types to process
                                   (None = use defaults)
            timeout: Maximum time to wait for completion (seconds)
        """
        self.prompt_id = prompt_id
        self.server_address = server_address
        self.client_id = client_id
        self.timeout = timeout

        # Configure which message types to track
        self.tracked_message_types = tracked_message_types or DEFAULT_TRACKED_MESSAGES

        # Create ComfyUI client
        self.client = ComfyUIClient(
            server_address=server_address,
            client_id=client_id
        )

        # Execution state
        self.completed = asyncio.Event()
        self.error_occurred = False
        self.error_data = None
        self.current_node = None
        self.progress = 0.0

        # WebSocket management
        self._ws = None
        self._ws_thread = None
        self._ws_connected = threading.Event()
        self._ws_error = None

        # Track start time
        self._start_time = None

    async def track(
        self,
        heartbeat_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Track workflow execution until completion

        This is the main entry point. It:
        1. Checks if workflow already completed (race condition)
        2. Connects to WebSocket
        3. Waits for completion while sending heartbeats
        4. Returns final result

        Args:
            heartbeat_callback: Optional callback for sending heartbeats
                                Called periodically with current state

        Returns:
            {
                "status": "completed" | "failed",
                "history": {...},  # ComfyUI history data
                "error": {...} | None
            }

        Raises:
            Exception: If WebSocket fails to connect or timeout occurs
        """
        self._start_time = time.time()
        logger.info(f"Starting workflow tracking for prompt_id: {self.prompt_id}")
        logger.info(f"Tracking message types: {self.tracked_message_types}")

        # Step 1: Check if already completed (race condition handling)
        early_result = await self._check_workflow_history()
        if early_result:
            logger.info("Workflow already completed before WebSocket connected")
            return early_result

        # Step 2: Connect to WebSocket
        self._connect_websocket()

        try:
            # Step 3: Wait for completion with heartbeats
            await self._wait_for_completion(heartbeat_callback)

            # Step 4: Get final history from ComfyUI
            history = self.client.get_history(self.prompt_id)
            history_data = history.get(self.prompt_id, {})

            # Step 5: Build and return result
            return self._build_result(history_data)

        finally:
            # Always close WebSocket
            self._close_websocket()
            elapsed = time.time() - self._start_time
            logger.info(f"Tracking completed in {elapsed:.2f}s")

    def _should_process_message(self, message: Dict[str, Any]) -> bool:
        """
        Check if a message should be processed based on filters

        Filters:
        1. Skip monitoring messages (always)
        2. Filter by message type (configurable)
        3. Filter by prompt_id (always)

        Args:
            message: WebSocket message from ComfyUI

        Returns:
            True if message should be processed, False otherwise
        """
        msg_type = message.get('type')
        data = message.get('data', {})

        # Always skip monitoring messages (noisy)
        if msg_type == 'crystools.monitor':
            return False

        # Filter by message type (configurable)
        if msg_type not in self.tracked_message_types:
            logger.debug(f"Skipping untracked message type: {msg_type}")
            return False

        # Filter by prompt_id - only process messages for OUR prompt
        msg_prompt_id = data.get('prompt_id')
        if msg_prompt_id and msg_prompt_id != self.prompt_id:
            logger.debug(f"Skipping message for different prompt_id: {msg_prompt_id}")
            return False

        return True

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Process a WebSocket message from ComfyUI

        This is the callback invoked by the WebSocket client for each message.
        It filters and routes messages to specific handlers.

        Args:
            message: WebSocket message from ComfyUI
        """
        # Apply filters
        if not self._should_process_message(message):
            return

        msg_type = message.get('type')
        data = message.get('data', {})

        logger.info(f"[WS] Processing: {msg_type}")

        # Route to specific handler based on message type
        if msg_type == 'executing':
            self._handle_executing(data)
        elif msg_type == 'executed':
            self._handle_executed(data)
        elif msg_type == 'progress':
            self._handle_progress(data)
        elif msg_type == 'execution_start':
            self._handle_execution_start(data)
        elif msg_type == 'execution_cached':
            self._handle_execution_cached(data)
        elif msg_type == 'execution_error':
            self._handle_execution_error(data)
        elif msg_type == 'execution_interrupted':
            self._handle_execution_interrupted(data)
        elif msg_type == 'status':
            self._handle_status(data)
        else:
            logger.warning(f"No handler for message type: {msg_type}")

    # ========================================================================
    # Message Handlers - Each handles a specific message type
    # ========================================================================

    def _handle_executing(self, data: Dict[str, Any]) -> None:
        """Handle 'executing' message - node started or workflow completed"""
        node = data.get('node')
        if node is None:
            # Node is None means workflow completed
            logger.info("✓ Execution completed")
            self.completed.set()
        else:
            # Node execution started
            self.current_node = node
            logger.info(f"→ Executing node: {node}")

    def _handle_executed(self, data: Dict[str, Any]) -> None:
        """Handle 'executed' message - node finished successfully"""
        node = data.get('node')
        logger.info(f"✓ Node completed: {node}")

    def _handle_progress(self, data: Dict[str, Any]) -> None:
        """Handle 'progress' message - update progress percentage"""
        value = data.get('value', 0)
        max_val = data.get('max', 100)
        self.progress = (value / max_val) if max_val > 0 else 0
        logger.info(f"Progress: {value}/{max_val} ({self.progress*100:.1f}%)")

    def _handle_execution_start(self, data: Dict[str, Any]) -> None:
        """Handle 'execution_start' message - workflow started"""
        logger.info("▶ Execution started")

    def _handle_execution_cached(self, data: Dict[str, Any]) -> None:
        """Handle 'execution_cached' message - nodes loaded from cache"""
        nodes = data.get('nodes', [])
        logger.info(f"⚡ {len(nodes)} node(s) cached")

    def _handle_execution_error(self, data: Dict[str, Any]) -> None:
        """Handle 'execution_error' message - workflow failed"""
        logger.error("=" * 60)
        logger.error("EXECUTION ERROR DETECTED")
        logger.error(f"Message: {data.get('exception_message', 'Unknown')}")
        logger.error(f"Node: {data.get('node_id', 'Unknown')}")
        logger.error("=" * 60)

        self.error_occurred = True
        self.error_data = data
        self.completed.set()

    def _handle_execution_interrupted(self, data: Dict[str, Any]) -> None:
        """Handle 'execution_interrupted' message - workflow cancelled"""
        logger.error(f"✗ Execution interrupted: {data}")

        self.error_occurred = True
        self.error_data = {"message": "Execution interrupted", "data": data}
        self.completed.set()

    def _handle_status(self, data: Dict[str, Any]) -> None:
        """Handle 'status' message - ComfyUI status update"""
        status_info = data.get('status', {})
        logger.info(f"Status update: {status_info}")

    # ========================================================================
    # WebSocket Connection Management
    # ========================================================================

    def _connect_websocket(self) -> None:
        """
        Establish WebSocket connection to ComfyUI

        Raises:
            Exception: If connection fails within 10 seconds
        """
        logger.info(f"Connecting to WebSocket: {self.client.ws_url}")

        def on_open(ws):
            """WebSocket opened callback"""
            elapsed = time.time() - self._start_time
            logger.info(f"✓ WebSocket connected ({elapsed:.2f}s)")
            self._ws_connected.set()

        def on_error(ws, error):
            """WebSocket error callback"""
            logger.error(f"✗ WebSocket error: {error}")
            self._ws_error = error

        def on_close(ws, close_status_code, close_msg):
            """WebSocket closed callback"""
            logger.info(f"WebSocket closed: code={close_status_code}, msg={close_msg}")

        # Start WebSocket tracking
        self._ws = self.client.track_updates(self._handle_message)

        # Override callbacks
        original_on_open = self._ws.on_open
        self._ws.on_open = lambda ws_obj: (
            on_open(ws_obj),
            original_on_open(ws_obj) if original_on_open else None
        )
        self._ws.on_error = on_error
        self._ws.on_close = on_close

        # Start WebSocket in background thread
        self._ws_thread = threading.Thread(
            target=self._ws.run_forever,
            daemon=True
        )
        self._ws_thread.start()

        # Wait for connection (with timeout)
        if not self._ws_connected.wait(timeout=10):
            self._ws.close()
            raise Exception("WebSocket failed to connect within 10 seconds")

        logger.info("WebSocket ready, waiting for execution messages...")

    def _close_websocket(self) -> None:
        """Close WebSocket connection"""
        if self._ws:
            logger.info("Closing WebSocket connection")
            self._ws.close()
            self._ws = None

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _check_workflow_history(self) -> Optional[Dict[str, Any]]:
        """
        Check if workflow already completed (race condition handling)

        Sometimes the workflow finishes before WebSocket connects.
        This checks the history API to see if it's already done.

        Returns:
            Result dict if workflow already finished, None otherwise
        """
        try:
            history = self.client.get_history(self.prompt_id)
            if self.prompt_id in history:
                history_data = history[self.prompt_id]
                status = history_data.get('status', {}).get('status_str', 'unknown')

                logger.info(f"Workflow already in history with status: {status}")

                if status == 'success':
                    return {
                        "status": "completed",
                        "history": history_data,
                        "error": None
                    }
                elif status == 'error':
                    return {
                        "status": "failed",
                        "history": history_data,
                        "error": history_data.get('status', {})
                    }
        except Exception as e:
            # No history yet - this is expected for new workflows
            logger.debug(f"No history yet (expected): {e}")

        return None

    async def _wait_for_completion(
        self,
        heartbeat_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """
        Wait for workflow completion while sending heartbeats

        Args:
            heartbeat_callback: Optional callback to invoke with current state

        Raises:
            Exception: If timeout is exceeded
        """
        loop_start = time.time()

        while not self.completed.is_set():
            # Check timeout
            elapsed = time.time() - self._start_time
            if elapsed > self.timeout:
                raise Exception(f"Execution timeout after {self.timeout} seconds")

            # Send heartbeat if callback provided
            if heartbeat_callback:
                try:
                    heartbeat_data = {
                        "prompt_id": self.prompt_id,
                        "current_node": self.current_node,
                        "progress": self.progress,
                        "elapsed": elapsed
                    }
                    heartbeat_callback(heartbeat_data)
                except Exception as e:
                    # Don't fail on heartbeat errors
                    logger.warning(f"Heartbeat callback failed: {e}")

            # Wait 1 second before next heartbeat
            await asyncio.sleep(1)

    def _build_result(self, history_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build final result dict

        Args:
            history_data: ComfyUI history data for this prompt

        Returns:
            Standardized result dict
        """
        if self.error_occurred:
            return {
                "status": "failed",
                "history": history_data,
                "error": self.error_data
            }
        else:
            return {
                "status": "completed",
                "history": history_data,
                "error": None
            }

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current tracking state (useful for debugging/monitoring)

        Returns:
            Dict with current state
        """
        elapsed = time.time() - self._start_time if self._start_time else 0

        return {
            "prompt_id": self.prompt_id,
            "current_node": self.current_node,
            "progress": self.progress,
            "error_occurred": self.error_occurred,
            "completed": self.completed.is_set(),
            "elapsed_seconds": elapsed
        }
