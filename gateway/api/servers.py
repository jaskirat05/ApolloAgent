"""
Server Management API Routes

Endpoints for registering and managing ComfyUI servers.
"""

from fastapi import APIRouter, HTTPException, Query, File, UploadFile
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Dict

from ..models import ComfyUIServer
from ..core import ComfyUIClient, load_balancer

router = APIRouter(prefix="/servers", tags=["servers"])

# Server registry (in-memory)
registered_servers: Dict[str, ComfyUIServer] = {}


@router.post("/register")
async def register_server(server: ComfyUIServer):
    """Register a ComfyUI server"""
    try:
        # Test connection
        client = ComfyUIClient(server_address=server.address)
        stats = client.get_system_stats()

        # Register server in both registries
        registered_servers[server.address] = server
        load_balancer.register_server(server.address)

        return {
            "status": "registered",
            "server": server.dict(),
            "system_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to server: {str(e)}")


@router.get("")
async def list_servers():
    """List all registered ComfyUI servers"""
    return {
        "servers": [server.dict() for server in registered_servers.values()],
        "count": len(registered_servers)
    }


@router.delete("/{server_address}")
async def unregister_server(server_address: str):
    """Unregister a ComfyUI server"""
    if server_address in registered_servers:
        del registered_servers[server_address]
        load_balancer.unregister_server(server_address)
        return {"status": "unregistered", "server_address": server_address}
    raise HTTPException(status_code=404, detail="Server not found")


@router.get("/health")
async def get_servers_health():
    """Get health status of all registered servers"""
    return {
        "servers": load_balancer.get_all_servers_health(),
        "available_count": len(load_balancer.get_available_servers())
    }


@router.get("/stats/{server_address}")
async def get_system_stats(server_address: str):
    """
    Get system statistics from a ComfyUI server

    Args:
        server_address: ComfyUI server address

    Returns:
        System and device statistics
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        stats = client.get_system_stats()

        return {
            "server_address": server_address,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")


@router.get("/nodes/{server_address}")
async def get_object_info(server_address: str):
    """
    Get available nodes from a ComfyUI server

    Args:
        server_address: ComfyUI server address

    Returns:
        Node definitions with inputs, outputs, and parameters
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        nodes = client.get_object_info()

        return {
            "server_address": server_address,
            "nodes": nodes,
            "node_count": len(nodes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get object info: {str(e)}")


@router.get("/queue/{server_address}")
async def get_queue_status(server_address: str):
    """
    Get queue status for a specific ComfyUI server

    Args:
        server_address: ComfyUI server address

    Returns:
        Queue status with running and pending prompts
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        queue = client.get_queue()

        return {
            "server_address": server_address,
            "queue_running": queue.get('queue_running', []),
            "queue_pending": queue.get('queue_pending', []),
            "running_count": len(queue.get('queue_running', [])),
            "pending_count": len(queue.get('queue_pending', []))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")


@router.post("/interrupt/{server_address}")
async def interrupt_prompt(server_address: str):
    """
    Interrupt the currently executing prompt on a server

    Args:
        server_address: ComfyUI server address
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        client.interrupt()
        return {"status": "interrupted", "server_address": server_address}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to interrupt: {str(e)}")


@router.get("/image/download/{server_address}")
async def download_image(
    server_address: str,
    filename: str = Query(..., description="Image filename"),
    subfolder: str = Query("", description="Subfolder path"),
    image_type: str = Query("output", description="Image type: output, input, or temp")
):
    """
    Download an image from a ComfyUI server

    Args:
        server_address: ComfyUI server address
        filename: Image filename
        subfolder: Subfolder path
        image_type: Type of image (output, input, temp)

    Returns:
        Image file stream
    """
    try:
        client = ComfyUIClient(server_address=server_address)
        image_data = client.download_image(
            filename=filename,
            subfolder=subfolder,
            image_type=image_type
        )

        return StreamingResponse(
            iter([image_data]),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download image: {str(e)}")


@router.post("/image/upload/{server_address}")
async def upload_image(
    server_address: str,
    file: UploadFile = File(...),
    subfolder: str = Query("", description="Target subfolder"),
    overwrite: bool = Query(False, description="Overwrite existing file")
):
    """
    Upload an image to a ComfyUI server

    Args:
        server_address: ComfyUI server address
        file: Image file to upload
        subfolder: Target subfolder
        overwrite: Whether to overwrite existing files

    Returns:
        Upload confirmation with filename
    """
    try:
        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/{file.filename}")
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # Upload to ComfyUI
        client = ComfyUIClient(server_address=server_address)
        result = client.upload_image(
            image_path=temp_path,
            subfolder=subfolder,
            overwrite=overwrite
        )

        # Clean up temp file
        temp_path.unlink()

        return {
            "status": "uploaded",
            "server_address": server_address,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
