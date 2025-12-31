"""
Workflow SDK Service Layer

Provides functions to discover, load, and execute ComfyUI workflows.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add parent to path to import workflow_registry
sys.path.append(str(Path(__file__).parent.parent.parent))

from temporal_gateway.workflow_registry import get_registry
from temporal_sdk.workflows.models import Workflow, WorkflowParameter, WorkflowOutput


def find_workflow_by_name(workflow_name: str) -> Optional[Workflow]:
    """
    Find a workflow by name and return a Workflow object

    Args:
        workflow_name: Name of the workflow (e.g., "video_wan2_2_14B_i2v")

    Returns:
        Workflow object if found, None otherwise

    Example:
        workflow = find_workflow_by_name("video_wan2_2_14B_i2v")
        if workflow:
            print(f"Found: {workflow.name}")
            print(f"Output: {workflow.output_type}")
            print(f"Parameters: {workflow.get_parameter_count()}")
        else:
            print("Workflow not found")
    """
    registry = get_registry()
    info = registry.get_workflow_info(workflow_name)

    if not info:
        return None

    # Convert registry data to SDK models
    parameters = [
        WorkflowParameter(
            key=p["key"],
            node_id=p["node_id"],
            input_key=p["input_key"],
            default_value=p["default_value"],
            type=p["type"],
            node_class=p["node_class"],
            node_title=p["node_title"],
            description=p["description"],
            category=p["category"]
        )
        for p in info["parameters"]
    ]

    output = None
    if info["output"]:
        output = WorkflowOutput(
            node_id=info["output"]["node_id"],
            output_type=info["output"]["output_type"],
            node_class=info["output"]["node_class"],
            node_title=info["output"]["node_title"],
            format=info["output"]["format"],
            filename_prefix=info["output"]["filename_prefix"]
        )

    # Get workflow hash
    workflow_hash = registry.workflow_hashes.get(workflow_name, "unknown")

    return Workflow(
        name=workflow_name,
        description=info["description"],
        parameters=parameters,
        output=output,
        workflow_hash=workflow_hash
    )


def list_all_workflows() -> List[Workflow]:
    """
    List all available workflows

    Returns:
        List of Workflow objects for all discovered workflows

    Example:
        workflows = list_all_workflows()
        for wf in workflows:
            print(f"{wf.name}: {wf.output_type} ({wf.get_parameter_count()} params)")
    """
    registry = get_registry()
    workflow_list = registry.list_workflows()

    workflows = []
    for wf_summary in workflow_list:
        workflow = find_workflow_by_name(wf_summary["name"])
        if workflow:
            workflows.append(workflow)

    return workflows


def get_workflow_names() -> List[str]:
    """
    Get list of all available workflow names

    Returns:
        List of workflow names

    Example:
        names = get_workflow_names()
        print(f"Available workflows: {', '.join(names)}")
    """
    registry = get_registry()
    workflow_list = registry.list_workflows()
    return [wf["name"] for wf in workflow_list]


def refresh_workflows() -> int:
    """
    Refresh workflow registry (re-scan workflows directory)

    Useful when workflows have been added or modified.

    Returns:
        Number of workflows discovered

    Example:
        count = refresh_workflows()
        print(f"Discovered {count} workflows")
    """
    registry = get_registry()
    summary = registry.reload()
    return summary["discovered"]
