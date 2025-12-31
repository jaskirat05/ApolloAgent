"""
Workflow Execution API Routes

Endpoints for executing and tracking ComfyUI workflows.
"""

import uuid
import json
import threading
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import StreamingResponse

from ..models import (
    QueuePromptRequest,
    PromptResponse,
    ExecuteWorkflowRequest,
    WorkflowExecutionResponse
)
from ..core import ComfyUIClient, load_balancer, image_storage
from ..observability import create_log_from_history

router = APIRouter(tags=["workflow"])

# Job tracking (in-memory)
jobs: Dict[str, Dict[str, Any]] = {}

# Active WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}


@router.post("/prompt/queue", response_model=PromptResponse)
async def queue_prompt(request: QueuePromptRequest):
    """
    Queue a workflow for execution on a specific ComfyUI server

    Args:
        request: Queue prompt request with workflow and server address

    Returns:
        Prompt response with prompt_id and server info
    """
    try:
        client = ComfyUIClient(server_address=request.server_address)
        response = client.post_prompt(request.workflow)

        return PromptResponse(
            prompt_id=response['prompt_id'],
            server_address=request.server_address,
            number=response.get('number', 0),
            queued_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue prompt: {str(e)}")


@router.get("/prompt/{server_address}/{prompt_id}")
async def get_prompt_status(server_address: str, prompt_id: str):
    """
    Get status and results for a specific prompt

    Args:
        server_address: ComfyUI server address
        prompt_id: Prompt ID to query

    Returns:
        Prompt history and results
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        history = client.get_history(prompt_id)

        if prompt_id not in history:
            return {
                "status": "not_found",
                "prompt_id": prompt_id,
                "message": "Prompt not found or still processing"
            }

        return {
            "status": "completed",
            "prompt_id": prompt_id,
            "server_address": server_address,
            "data": history[prompt_id]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prompt status: {str(e)}")


@router.post("/batch/queue")
async def queue_batch_prompts(
    workflows: List[Dict[str, Any]] = Body(..., description="List of workflows"),
    server_address: str = Body(..., description="ComfyUI server address")
):
    """
    Queue multiple workflows for batch processing

    Args:
        workflows: List of workflow definitions
        server_address: ComfyUI server address

    Returns:
        List of queued prompt IDs
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        results = []

        for workflow in workflows:
            response = client.post_prompt(workflow)
            results.append({
                "prompt_id": response['prompt_id'],
                "number": response.get('number', 0)
            })

        return {
            "status": "queued",
            "server_address": server_address,
            "count": len(results),
            "prompts": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue batch: {str(e)}")


@router.post("/workflow/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(request: ExecuteWorkflowRequest):
    """
    Execute a workflow with automatic server selection and image retrieval

    This is the main SDK endpoint that:
    1. Selects the best available server
    2. Queues the workflow
    3. Waits for completion (if requested)
    4. Downloads and stores images
    5. Returns image URLs

    Args:
        request: Workflow execution request

    Returns:
        Execution response with image URLs
    """
    # Generate job ID
    job_id = str(uuid.uuid4())

    # Select best server
    server_address = load_balancer.get_best_server(strategy=request.strategy)

    if not server_address:
        raise HTTPException(status_code=503, detail="No available ComfyUI servers")

    # Create job entry first
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "server_address": server_address,
        "prompt_id": None,
        "images": [],
        "queued_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "log_file_path": None,
        "workflow": request.workflow  # Store for logging later
    }

    try:
        # Queue the workflow
        client = ComfyUIClient(server_address=server_address)
        response = client.post_prompt(request.workflow)
        prompt_id = response['prompt_id']

        # Update job entry with prompt_id
        jobs[job_id]["prompt_id"] = prompt_id

        if not request.wait_for_completion:
            # Return immediately
            return WorkflowExecutionResponse(**jobs[job_id])

        # Wait for completion
        completed = threading.Event()
        error_msg = None

        def handle_message(data):
            nonlocal error_msg
            msg_type = data.get('type')

            if msg_type == 'executing':
                node_data = data.get('data', {})
                if node_data.get('node') is None and node_data.get('prompt_id') == prompt_id:
                    completed.set()

            elif msg_type == 'execution_error':
                error_msg = data.get('data', {})
                completed.set()
            

        # Start WebSocket in background
        ws = client.track_updates(handle_message)
        ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
        ws_thread.start()

        # Wait for completion
        completed.wait()
        ws.close()

        if error_msg:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = error_msg
            raise HTTPException(status_code=500, detail=f"Execution failed: {error_msg}")

        # Get results
        history = client.get_history(prompt_id)
        history_data = history.get(prompt_id, {})

        # Create log from history
        log_file_path = create_log_from_history(
            prompt_id=prompt_id,
            server_address=server_address,
            workflow=request.workflow,
            history_data=history_data
        )

        # Download and store images
        stored_images = image_storage.download_and_store_images(
            prompt_id=prompt_id,
            server_address=server_address,
            history_data=history_data
        )

        # Generate image URLs
        base_url = "http://localhost:8000"  # TODO: Make this configurable
        image_urls = [
            f"{base_url}/images/{img['filename']}"
            for img in stored_images
        ]

        # Update job
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["images"] = image_urls
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        jobs[job_id]["log_file_path"] = str(log_file_path)

        return WorkflowExecutionResponse(**jobs[job_id])

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@router.get("/workflow/status/{job_id}")
async def get_workflow_status(job_id: str):
    """
    Get the status of a workflow execution job

    For async jobs (queued status), this polls ComfyUI's history endpoint
    to check if execution is complete and updates the job status.

    Args:
        job_id: Job ID

    Returns:
        Job status and results
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # If job is still queued (async mode), poll ComfyUI for updates
    if job["status"] == "queued" and job["prompt_id"]:
        try:
            client = ComfyUIClient(server_address=job["server_address"])

            # Poll history endpoint
            history = client.get_history(job["prompt_id"])

            # Check if execution is complete
            if job["prompt_id"] in history:
                history_data = history[job["prompt_id"]]

                # Create log from history
                log_file_path = create_log_from_history(
                    prompt_id=job["prompt_id"],
                    server_address=job["server_address"],
                    workflow=job["workflow"],
                    history_data=history_data
                )
                job["log_file_path"] = str(log_file_path)

                # Check for errors
                if "status" in history_data and history_data["status"].get("completed") == False:
                    # Execution failed
                    job["status"] = "failed"
                    job["error"] = history_data.get("status", {}).get("messages", [])
                    job["completed_at"] = datetime.utcnow().isoformat()

                elif "outputs" in history_data and history_data["outputs"]:
                    # Execution completed successfully
                    # Download and store images
                    stored_images = image_storage.download_and_store_images(
                        prompt_id=job["prompt_id"],
                        server_address=job["server_address"],
                        history_data=history_data
                    )

                    # Generate image URLs
                    base_url = "http://localhost:8000"  # TODO: Make configurable
                    image_urls = [
                        f"{base_url}/images/{img['filename']}"
                        for img in stored_images
                    ]

                    # Update job status
                    job["status"] = "completed"
                    job["images"] = image_urls
                    job["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            # Don't fail if polling fails, just return current status
            # The job might still be executing
            pass

    # Remove workflow from response (too large)
    response_job = {k: v for k, v in job.items() if k != "workflow"}
    return response_job


@router.get("/workflow/logs/{job_id}")
async def get_workflow_logs(job_id: str):
    """
    Get the log file contents for a workflow execution

    Args:
        job_id: Job ID

    Returns:
        Log file contents as JSON lines
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if not job.get("log_file_path"):
        raise HTTPException(status_code=404, detail="Log file not available yet")

    log_path = Path(job["log_file_path"])

    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    # Read and return log contents
    log_entries = []
    with open(log_path, 'r') as f:
        for line in f:
            try:
                log_entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass

    return {
        "job_id": job_id,
        "log_file_path": str(log_path),
        "log_entries": log_entries,
        "entry_count": len(log_entries)
    }


@router.get("/images/{filename}")
async def serve_image(filename: str):
    """
    Serve a stored image

    Args:
        filename: Image filename

    Returns:
        Image file stream
    """
    image_path = image_storage.get_image_path(filename)

    if not image_path:
        raise HTTPException(status_code=404, detail="Image not found")

    return StreamingResponse(
        iter([image_path.read_bytes()]),
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename={filename}"
        }
    )


@router.websocket("/ws/{server_address}/{prompt_id}")
async def websocket_endpoint(websocket: WebSocket, server_address: str, prompt_id: str):
    """
    WebSocket endpoint for real-time updates from ComfyUI

    Connects to ComfyUI WebSocket and forwards messages to client

    Args:
        websocket: WebSocket connection
        server_address: ComfyUI server address
        prompt_id: Prompt ID to track
    """
    await websocket.accept()

    connection_key = f"{server_address}:{prompt_id}"

    if connection_key not in active_connections:
        active_connections[connection_key] = []
    active_connections[connection_key].append(websocket)

    try:
        # Create ComfyUI client
        client = ComfyUIClient(server_address=server_address)

        # Track if execution completed
        completed = asyncio.Event()

        # Message handler
        def handle_message(data):
            msg_type = data.get('type')

            # Send to WebSocket client
            asyncio.create_task(websocket.send_json(data))

            # Check for completion
            if msg_type == 'executing':
                node_data = data.get('data', {})
                if node_data.get('node') is None:
                    completed.set()

        # Start ComfyUI WebSocket in background
        ws_app = client.track_updates(handle_message)
        ws_thread = threading.Thread(target=ws_app.run_forever, daemon=True)
        ws_thread.start()

        # Wait for completion or client disconnect
        while not completed.is_set():
            try:
                # Keep connection alive and check for client messages
                message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                if message == "close":
                    break
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

        ws_app.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"message": str(e)}
        })
    finally:
        if connection_key in active_connections:
            active_connections[connection_key].remove(websocket)
            if not active_connections[connection_key]:
                del active_connections[connection_key]
