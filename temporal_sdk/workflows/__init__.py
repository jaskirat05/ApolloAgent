"""
Workflow SDK

Provides programmatic access to ComfyUI workflows with a clean, object-oriented API.

Usage:
    from temporal_sdk.workflows.service import find_workflow_by_name

    # Get a workflow
    workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

    # Access workflow properties
    print(workflow.name)
    print(workflow.output_type)

    # Get parameters
    prompts = workflow.get_prompts()
    mutables = workflow.get_all_parameters()

    # Execute workflow
    result = workflow.execute({
        "93.text": "A dragon flying",
        "98.width": 1024
    })
"""

from temporal_sdk.workflows.models import Workflow, WorkflowParameter, WorkflowOutput
from temporal_sdk.workflows.service import find_workflow_by_name, list_all_workflows

__all__ = [
    "Workflow",
    "WorkflowParameter",
    "WorkflowOutput",
    "find_workflow_by_name",
    "list_all_workflows"
]
