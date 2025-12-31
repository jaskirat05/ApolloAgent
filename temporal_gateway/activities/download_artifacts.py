"""
Activity: Download artifacts from ComfyUI and store locally + DB
"""

import sys
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from temporalio import activity

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from gateway.core import image_storage
from temporal_gateway.clients.comfy import ComfyUIClient
from temporal_gateway.database import get_session, create_artifact


@activity.defn
async def download_and_store_images(
    server_address: str,
    output_files: list[Dict[str, Any]],
    workflow_id: Optional[str] = None
) -> list[Dict[str, Any]]:
    """
    Activity: Download generated images/videos from ComfyUI and store locally + DB

    Args:
        server_address: Server address
        output_files: List of output file info from get_server_output_files
        workflow_id: Optional workflow ID to link artifacts to

    Returns:
        List of stored file info with local paths
    """
    activity.logger.info(f"Downloading {len(output_files)} file(s)")

    try:
        client = ComfyUIClient(server_address)
        stored_files = []

        for file_info in output_files:
            filename = file_info['filename']
            subfolder = file_info.get('subfolder', '')
            file_type = file_info.get('type', 'output')

            # Download file
            file_data = await client.download_file(
                filename=filename,
                subfolder=subfolder,
                folder_type=file_type
            )

            # Store locally using image_storage
            file_ext = Path(filename).suffix
            unique_filename = f"{uuid.uuid4().hex[:8]}{file_ext}"
            local_path = image_storage.storage_dir / unique_filename

            local_path.write_bytes(file_data)

            file_dict = {
                "filename": unique_filename,
                "original_filename": filename,
                "local_path": str(local_path),
                "node_id": file_info.get('node_id'),
                "server_address": server_address,
                "downloaded_at": datetime.utcnow().isoformat(),
                "file_size": len(file_data),
                "file_type": _detect_file_type(file_ext),
                "file_format": file_ext.lstrip('.'),
            }

            # If workflow_id provided, save to database
            if workflow_id:
                try:
                    with get_session() as session:
                        artifact = create_artifact(
                            session=session,
                            workflow_id=workflow_id,
                            filename=filename,
                            local_filename=unique_filename,
                            local_path=str(local_path),
                            file_type=file_dict["file_type"],
                            file_format=file_dict["file_format"],
                            file_size=file_dict["file_size"],
                            node_id=file_info.get('node_id'),
                            subfolder=subfolder,
                            comfy_folder_type=file_type,
                            approval_status="auto_approved",
                        )
                        file_dict["artifact_id"] = artifact.id
                        activity.logger.info(f"✓ Saved artifact to DB: {artifact.id}")
                except Exception as db_error:
                    activity.logger.error(f"Failed to save artifact to DB: {db_error}")
                    # Continue even if DB save fails

            stored_files.append(file_dict)

        await client.close()
        activity.logger.info(f"Downloaded {len(stored_files)} file(s)")
        return stored_files

    except Exception as e:
        activity.logger.error(f"Failed to download files: {e}")
        # Don't fail workflow if download fails
        return []


def _detect_file_type(file_ext: str) -> str:
    """Detect file type from extension"""
    ext = file_ext.lower().lstrip('.')
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
        return 'image'
    elif ext in ['mp4', 'avi', 'mov', 'webm', 'mkv']:
        return 'video'
    elif ext in ['mp3', 'wav', 'ogg', 'flac']:
        return 'audio'
    else:
        return 'unknown'
