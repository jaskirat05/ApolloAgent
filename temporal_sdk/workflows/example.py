"""
Example usage of the Workflow SDK

This demonstrates how to use the SDK to programmatically work with ComfyUI workflows.
"""

from temporal_sdk.workflows.service import find_workflow_by_name, list_all_workflows, get_workflow_names


def example_list_workflows():
    """Example: List all available workflows"""
    print("=" * 60)
    print("Example 1: List All Workflows")
    print("=" * 60)

    workflows = list_all_workflows()

    for workflow in workflows:
        print(f"\n{workflow.name}:")
        print(f"  Output Type: {workflow.output_type}")
        print(f"  Parameters: {workflow.get_parameter_count()}")
        print(f"  Categories: {', '.join(workflow.get_categories())}")


def example_find_workflow():
    """Example: Find a specific workflow and explore it"""
    print("\n" + "=" * 60)
    print("Example 2: Find Workflow by Name")
    print("=" * 60)

    workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

    if not workflow:
        print("Workflow not found!")
        return

    print(f"\nWorkflow: {workflow.name}")
    print(f"Description: {workflow.description}")
    print(f"Output Type: {workflow.output_type}")
    print(f"Hash: {workflow.workflow_hash[:16]}...")

    # Get output info
    if workflow.output:
        print(f"\nOutput Information:")
        print(f"  Node: {workflow.output.node_id} ({workflow.output.node_class})")
        print(f"  Format: {workflow.output.format}")
        print(f"  Filename Prefix: {workflow.output.filename_prefix}")


def example_get_prompts():
    """Example: Get prompts from a workflow"""
    print("\n" + "=" * 60)
    print("Example 3: Get Prompts")
    print("=" * 60)

    workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

    if not workflow:
        print("Workflow not found!")
        return

    prompts = workflow.get_prompts()

    if prompts["positive"]:
        print(f"\nPositive Prompt:")
        print(f"  Key: {prompts['positive'].key}")
        print(f"  Default: {prompts['positive'].default_value[:60]}...")

    if prompts["negative"]:
        print(f"\nNegative Prompt:")
        print(f"  Key: {prompts['negative'].key}")
        print(f"  Default: {prompts['negative'].default_value[:60]}...")


def example_get_parameters_by_category():
    """Example: Get parameters by category"""
    print("\n" + "=" * 60)
    print("Example 4: Get Parameters by Category")
    print("=" * 60)

    workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

    if not workflow:
        print("Workflow not found!")
        return

    # Get dimension parameters
    dimensions = workflow.get_parameters_by_category("dimensions")
    print(f"\nDimension Parameters ({len(dimensions)}):")
    for param in dimensions:
        print(f"  {param.key}: {param.default_value} ({param.description})")

    # Get sampling parameters
    sampling = workflow.get_parameters_by_category("sampling")
    print(f"\nSampling Parameters ({len(sampling)}):")
    for param in sampling[:3]:  # Show first 3
        print(f"  {param.key}: {param.default_value} ({param.description})")
    if len(sampling) > 3:
        print(f"  ... and {len(sampling) - 3} more")


def example_check_parameter():
    """Example: Check if specific parameters exist"""
    print("\n" + "=" * 60)
    print("Example 5: Check Parameter Existence")
    print("=" * 60)

    workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

    if not workflow:
        print("Workflow not found!")
        return

    # Check if specific parameters exist
    params_to_check = ["93.text", "98.width", "999.invalid"]

    for param_key in params_to_check:
        exists = workflow.has_parameter(param_key)
        status = "✓ Exists" if exists else "✗ Not found"
        print(f"{param_key}: {status}")

        if exists:
            param = workflow.get_parameter_by_key(param_key)
            print(f"  Type: {param.type}, Default: {param.default_value}")


def example_to_dict():
    """Example: Convert workflow to dictionary"""
    print("\n" + "=" * 60)
    print("Example 6: Convert to Dictionary")
    print("=" * 60)

    workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

    if not workflow:
        print("Workflow not found!")
        return

    workflow_dict = workflow.to_dict()

    print(f"\nWorkflow as Dictionary:")
    print(f"  Name: {workflow_dict['name']}")
    print(f"  Parameters: {workflow_dict['parameter_count']}")
    print(f"  Output Type: {workflow_dict['output']['type']}")
    print(f"  Categories: {workflow_dict['categories']}")


if __name__ == "__main__":
    # Run all examples
    example_list_workflows()
    example_find_workflow()
    example_get_prompts()
    example_get_parameters_by_category()
    example_check_parameter()
    example_to_dict()

    print("\n" + "=" * 60)
    print("Examples Complete!")
    print("=" * 60)
