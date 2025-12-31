"""
CRUD operations module

Imports all CRUD functions from individual entity files
"""

from .chain import (
    create_chain,
    get_chain,
    get_chain_by_temporal_id,
    update_chain_status,
    list_chains,
    delete_chain,
)

from .workflow import (
    create_workflow,
    get_workflow,
    get_workflow_by_prompt,
    get_workflow_by_step,
    get_workflows_by_chain,
    update_workflow_status,
    update_workflow_latest_artifact,
    list_workflows,
    delete_workflow,
)

from .artifact import (
    create_artifact,
    get_artifact,
    get_latest_artifact,
    get_artifacts_by_workflow,
    get_artifact_versions,
    update_artifact_latest_flag,
    approve_artifact,
    reject_artifact,
    list_artifacts,
    delete_artifact,
)

from .transfer import (
    create_transfer,
    get_transfer,
    update_transfer_status,
    list_transfers,
    delete_transfer,
)

__all__ = [
    # Chain
    "create_chain",
    "get_chain",
    "get_chain_by_temporal_id",
    "update_chain_status",
    "list_chains",
    "delete_chain",
    # Workflow
    "create_workflow",
    "get_workflow",
    "get_workflow_by_prompt",
    "get_workflow_by_step",
    "get_workflows_by_chain",
    "update_workflow_status",
    "update_workflow_latest_artifact",
    "list_workflows",
    "delete_workflow",
    # Artifact
    "create_artifact",
    "get_artifact",
    "get_latest_artifact",
    "get_artifacts_by_workflow",
    "get_artifact_versions",
    "update_artifact_latest_flag",
    "approve_artifact",
    "reject_artifact",
    "list_artifacts",
    "delete_artifact",
    # Transfer
    "create_transfer",
    "get_transfer",
    "update_transfer_status",
    "list_transfers",
    "delete_transfer",
]
