"""
Example usage of the Chain SDK

This demonstrates how to load, validate, and inspect chain definitions.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporal_sdk.chains import (
    load_chain,
    create_execution_plan,
    validate_chain,
    get_execution_summary,
    discover_chains
)


def example_load_chain():
    """Example: Load a chain from YAML"""
    print("=" * 60)
    print("Example 1: Load Chain from YAML")
    print("=" * 60)

    chain = load_chain("chains/parallel_example.yaml")

    print(f"\nChain: {chain.name}")
    print(f"Description: {chain.description}")
    print(f"Total Steps: {len(chain.steps)}")

    print("\nSteps:")
    for step in chain.steps:
        deps = f" (depends on: {', '.join(step.depends_on)})" if step.depends_on else ""
        print(f"  - {step.id}: {step.workflow}{deps}")


def example_validate_chain():
    """Example: Validate a chain"""
    print("\n" + "=" * 60)
    print("Example 2: Validate Chain")
    print("=" * 60)

    chain = load_chain("chains/parallel_example.yaml")
    result = validate_chain(chain)

    if result['valid']:
        print("\n✓ Chain is valid!")
    else:
        print("\n✗ Chain has errors:")
        for error in result['errors']:
            print(f"  - {error}")


def example_execution_plan():
    """Example: Create execution plan and inspect parallel groups"""
    print("\n" + "=" * 60)
    print("Example 3: Create Execution Plan")
    print("=" * 60)

    chain = load_chain("chains/parallel_example.yaml")
    plan = create_execution_plan(chain)

    print(f"\nChain: {plan.chain_name}")
    print(f"Total Steps: {len(plan.nodes)}")
    print(f"Execution Levels: {plan.get_total_levels()}")

    print("\nParallel Execution Groups:")
    for level, group in enumerate(plan.get_parallel_groups()):
        print(f"  Level {level}: {', '.join(group)}")
        print(f"    → These {len(group)} step(s) will run in parallel")


def example_execution_summary():
    """Example: Get execution summary"""
    print("\n" + "=" * 60)
    print("Example 4: Get Execution Summary")
    print("=" * 60)

    chain = load_chain("chains/parallel_example.yaml")
    plan = create_execution_plan(chain)
    summary = get_execution_summary(plan)

    print(f"\nChain: {summary['chain_name']}")
    print(f"Total Steps: {summary['total_steps']}")
    print(f"Execution Levels: {summary['total_levels']}")
    print(f"\nExecution Order: {' → '.join(summary['execution_order'])}")
    print(f"\nParallel Groups:")
    for i, group in enumerate(summary['parallel_groups']):
        print(f"  Level {i}: [{', '.join(group)}]")


def example_discover_chains():
    """Example: Discover all chains in a directory"""
    print("\n" + "=" * 60)
    print("Example 5: Discover Chains")
    print("=" * 60)

    chains = discover_chains("chains/")

    print(f"\nFound {len(chains)} chain(s):\n")
    for chain_info in chains:
        print(f"  {chain_info['name']}:")
        print(f"    Description: {chain_info['description'][:60]}...")
        print(f"    Steps: {chain_info['steps']}")
        print(f"    Path: {chain_info['path']}")
        print()


def example_inspect_node_details():
    """Example: Inspect individual nodes in execution plan"""
    print("\n" + "=" * 60)
    print("Example 6: Inspect Node Details")
    print("=" * 60)

    chain = load_chain("chains/parallel_example.yaml")
    plan = create_execution_plan(chain)

    print("\nDetailed Node Information:\n")
    for node in plan.nodes:
        print(f"Step ID: {node.step_id}")
        print(f"  Workflow: {node.workflow}")
        print(f"  Level: {node.level}")
        print(f"  Dependencies: {node.dependencies if node.dependencies else 'None'}")
        print(f"  Condition: {node.condition if node.condition else 'None'}")
        print(f"  Parameters: {list(node.parameters.keys())}")
        print()


if __name__ == "__main__":
    # Run all examples
    example_load_chain()
    example_validate_chain()
    example_execution_plan()
    example_execution_summary()
    example_discover_chains()
    example_inspect_node_details()

    print("=" * 60)
    print("Examples Complete!")
    print("=" * 60)
