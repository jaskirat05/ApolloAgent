"""
Chain SDK

Provides tools for defining, validating, and executing workflow chains.

Usage:
    from temporal_sdk.chains import load_chain, create_execution_plan, ChainEngine
    from temporalio.client import Client

    # Load chain definition
    chain = load_chain("chains/video_pipeline.yaml")

    # Create execution plan
    plan = create_execution_plan(chain)

    # Inspect parallel groups
    groups = plan.get_parallel_groups()
    print(f"Parallel execution groups: {groups}")

    # Execute via Chain Engine
    temporal_client = await Client.connect("localhost:7233")
    engine = ChainEngine(temporal_client)
    workflow_id = await engine.execute_chain(plan)
    print(f"Chain started: {workflow_id}")
"""

from temporal_sdk.chains.models import (
    ChainDefinition,
    ChainStepDefinition,
    ExecutionPlan,
    ExecutionNode,
    StepResult,
    ChainExecutionResult
)

from temporal_sdk.chains.interpreter import (
    ChainInterpreter,
    ChainValidationError,
    TemplateResolutionError
)

from temporal_sdk.chains.service import (
    load_chain,
    load_chain_from_dict,
    create_execution_plan,
    validate_chain,
    get_execution_summary,
    discover_chains,
    resolve_step_parameters,
    evaluate_step_condition
)

from temporal_sdk.chains.engine import ChainEngine

from temporal_sdk.chains.workflows import (
    ChainExecutorWorkflow,
    ChainExecutionRequest
)

__all__ = [
    # Models
    "ChainDefinition",
    "ChainStepDefinition",
    "ExecutionPlan",
    "ExecutionNode",
    "StepResult",
    "ChainExecutionResult",

    # Interpreter
    "ChainInterpreter",
    "ChainValidationError",
    "TemplateResolutionError",

    # Service functions
    "load_chain",
    "load_chain_from_dict",
    "create_execution_plan",
    "validate_chain",
    "get_execution_summary",
    "discover_chains",
    "resolve_step_parameters",
    "evaluate_step_condition",

    # Engine
    "ChainEngine",

    # Workflows
    "ChainExecutorWorkflow",
    "ChainExecutionRequest",
]
