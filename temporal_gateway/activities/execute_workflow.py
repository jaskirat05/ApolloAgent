"""
Activity: Execute workflow with hybrid tracking
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

from temporalio import activity

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from temporal_gateway.clients.comfy import ComfyUIClient


@activity.defn
async def execute_and_track_workflow(
    server_address: str,
    workflow_json: Dict[str, Any],
    workflow_name: Optional[str] = None,
    timeout: float = 1800.0
) -> Dict[str, Any]:
    """
    Activity: Execute workflow using new ComfyUI client with hybrid tracking

    This activity uses the new ComfyUI client that:
    - Runs WebSocket and HTTP polling concurrently
    - Handles fast-completing workflows (race conditions)
    - Returns result from whichever source succeeds first

    Args:
        server_address: ComfyUI server address
        workflow_json: Workflow definition JSON
        workflow_name: Optional workflow name for logging
        timeout: Execution timeout in seconds

    Returns:
        Dict with execution result
    """
    activity.logger.info(f"[V3] Executing workflow on {server_address}")
    if workflow_name:
        activity.logger.info(f"[V3] Workflow name: {workflow_name}")

    # Create client
    client = ComfyUIClient(server_address)

    try:
        # Progress callback to send heartbeats
        def on_progress(update):
            try:
                activity.heartbeat({
                    "current_node": update.current_node,
                    "progress": update.progress
                })
            except Exception:
                # Heartbeat may fail - ignore
                pass

        # Execute workflow with tracking
        result = await client.execute_workflow(
            workflow=workflow_json,
            progress_callback=on_progress,
            timeout=timeout
        )

        if result.is_success:
            activity.logger.info(f"[V3] Workflow completed successfully")

            return {
                "status": "completed",
                "prompt_id": result.prompt_id,
                "server_address": server_address,
                "outputs": result.outputs
            }
        else:
            activity.logger.error(f"[V3] Workflow failed: {result.error}")
            return {
                "status": "failed",
                "prompt_id": result.prompt_id,
                "server_address": server_address,
                "error": result.error
            }

    finally:
        await client.close()
