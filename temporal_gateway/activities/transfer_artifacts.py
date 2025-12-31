"""
Activity: Transfer artifacts from local storage to target server
"""

import sys
from pathlib import Path
from typing import List

from temporalio import activity

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from temporal_gateway.clients.comfy import ComfyUIClient
from temporal_gateway.database import (
    get_session,
    get_latest_artifact,
    create_transfer,
    update_transfer_status,
)
from temporal_gateway.database.crud.artifact import get_artifact


@activity.defn
async def transfer_artifacts_from_storage(
    source_workflow_id: str,
    target_server: str,
    artifact_ids: List[str],
    target_workflow_id: str = None
) -> list[str]:
    """
    Activity: Transfer artifacts from local storage to target server's input directory

    NEW BEHAVIOR: Instead of server-to-server transfer, we:
    1. Read artifacts from local database
    2. Load files from local storage
    3. Upload to target server

    This enables:
    - Human-in-the-loop workflows (edit artifacts before upload)
    - Single source of truth (local storage)
    - Resilience to server restarts

    Args:
        source_workflow_id: Source workflow ID (to fetch artifacts from DB)
        target_server: Target ComfyUI server address
        artifact_ids: List of artifact IDs to transfer (or ["latest"])
        target_workflow_id: Optional target workflow ID for linking transfer

    Returns:
        List of filenames now available in target server's input/ directory
    """
    activity.logger.info(f"Transferring {len(artifact_ids)} artifact(s) from workflow {source_workflow_id} to {target_server}")

    try:
        target_client = ComfyUIClient(target_server)
        transferred_filenames = []

        with get_session() as session:
            for artifact_id in artifact_ids:
                # Handle special "latest" keyword
                if artifact_id == "latest":
                    artifact = get_latest_artifact(session, source_workflow_id)
                else:
                    artifact = get_artifact(session, artifact_id)

                if not artifact:
                    activity.logger.warning(f"Artifact {artifact_id} not found, skipping")
                    continue

                # Create transfer record
                transfer = create_transfer(
                    session=session,
                    artifact_id=artifact.id,
                    source_workflow_id=source_workflow_id,
                    target_server=target_server,
                    target_workflow_id=target_workflow_id,
                    target_subfolder=artifact.subfolder,
                    status="uploading"
                )

                try:
                    # Read file from local storage
                    local_path = Path(artifact.local_path)
                    if not local_path.exists():
                        raise FileNotFoundError(f"Local file not found: {local_path}")

                    file_data = local_path.read_bytes()
                    activity.logger.info(f"Uploading: {artifact.filename} from local storage to {target_server}/input/")

                    # Upload to target server's input directory
                    upload_result = await target_client.upload_file(
                        file_data=file_data,
                        filename=artifact.filename,  # Use original filename
                        subfolder=artifact.subfolder,
                        overwrite=True
                    )

                    transferred_filenames.append(artifact.filename)
                    activity.logger.info(f"✓ Uploaded: {artifact.filename} ({len(file_data)} bytes)")

                    # Update transfer status
                    update_transfer_status(session, transfer.id, "completed")

                except Exception as upload_error:
                    activity.logger.error(f"Failed to upload artifact {artifact.id}: {upload_error}")
                    update_transfer_status(session, transfer.id, "failed", str(upload_error))
                    raise

        await target_client.close()

        activity.logger.info(f"Successfully transferred {len(transferred_filenames)} file(s)")
        return transferred_filenames

    except Exception as e:
        activity.logger.error(f"Failed to transfer files: {e}")
        raise


@activity.defn
async def transfer_outputs_to_input(
    source_server: str,
    target_server: str,
    output_files: list[dict]
) -> list[str]:
    """
    Activity: Transfer output files from source server to target server (LEGACY)

    DEPRECATED: Use transfer_artifacts_from_storage() for new workflows.
    This is kept for backwards compatibility with existing chains.

    Args:
        source_server: Source ComfyUI server address
        target_server: Target ComfyUI server address
        output_files: List of output file info

    Returns:
        List of transferred filenames
    """
    activity.logger.warning("Using legacy transfer_outputs_to_input - consider migrating to transfer_artifacts_from_storage")

    try:
        source_client = ComfyUIClient(source_server)
        target_client = ComfyUIClient(target_server)
        transferred_filenames = []

        for file_info in output_files:
            filename = file_info['filename']
            subfolder = file_info.get('subfolder', '')
            file_type = file_info.get('type', 'output')

            activity.logger.info(f"Transferring: {filename} from {source_server}/{file_type}/ to {target_server}/input/")

            # Download from source server
            file_data = await source_client.download_file(
                filename=filename,
                subfolder=subfolder,
                folder_type=file_type
            )

            # Upload to target server's input directory
            await target_client.upload_file(
                file_data=file_data,
                filename=filename,
                subfolder=subfolder,
                overwrite=True
            )

            transferred_filenames.append(filename)
            activity.logger.info(f"✓ Transferred: {filename} ({len(file_data)} bytes)")

        await source_client.close()
        await target_client.close()

        activity.logger.info(f"Successfully transferred {len(transferred_filenames)} file(s)")
        return transferred_filenames

    except Exception as e:
        activity.logger.error(f"Failed to transfer files: {e}")
        raise
