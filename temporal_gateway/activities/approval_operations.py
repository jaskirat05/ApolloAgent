"""
Activities: Approval operations for artifact approval workflow
"""

from typing import Dict, Any, Optional
from temporalio import activity

from ..database import get_session
from ..database.crud.approval import create_approval_request


@activity.defn
async def create_approval_request_activity(
    artifact_id: str,
    temporal_workflow_id: str,
    artifact_view_url: str,
    chain_id: Optional[str] = None,
    step_id: Optional[str] = None,
    temporal_run_id: Optional[str] = None,
    link_expiration_hours: Optional[int] = None,
    workflow_name: Optional[str] = None,
    server: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    approval_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Activity: Create approval request in database

    Args:
        artifact_id: ID of artifact to approve
        temporal_workflow_id: Temporal workflow ID to signal when decision made
        artifact_view_url: URL where approvers can view the artifact
        chain_id: Optional chain context
        step_id: Optional step identifier in chain
        temporal_run_id: Optional Temporal run ID
        link_expiration_hours: Optional hours until approval link expires
        workflow_name: Name of workflow that generated the artifact
        server: Server address where workflow was executed
        parameters: Parameters used for workflow execution
        approval_config: Approval configuration from chain YAML

    Returns:
        Dict with approval request details (id, token, etc.)
    """
    activity.logger.info(f"Creating approval request for artifact: {artifact_id}")

    try:
        with get_session() as session:
            # Build config metadata
            config_metadata = {
                'step_id': step_id,
                'workflow_name': workflow_name,
                'server': server,
                'parameters': parameters or {},
                'approval_config': approval_config or {},
            }

            # Create approval request
            approval_request = create_approval_request(
                session=session,
                artifact_id=artifact_id,
                temporal_workflow_id=temporal_workflow_id,
                artifact_view_url=artifact_view_url,
                chain_id=chain_id,
                step_id=step_id,
                temporal_run_id=temporal_run_id,
                link_expiration_hours=link_expiration_hours,
                config_metadata=config_metadata,
            )

            activity.logger.info(
                f"✓ Created approval request: {approval_request.id}, "
                f"token: {approval_request.approval_link_token[:16]}..."
            )

            return {
                "id": approval_request.id,
                "token": approval_request.approval_link_token,
                "artifact_view_url": approval_request.artifact_view_url,
                "link_expires_at": approval_request.link_expires_at.isoformat() if approval_request.link_expires_at else None,
                "created_at": approval_request.created_at.isoformat() if approval_request.created_at else None,
            }

    except Exception as e:
        activity.logger.error(f"Failed to create approval request: {e}")
        raise
