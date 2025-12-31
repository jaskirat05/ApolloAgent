"""
Chain Engine

Service layer for executing workflow chains using Temporal.
"""

import uuid
from typing import Dict, Any, Optional
from pathlib import Path

from temporalio.client import Client

from temporal_sdk.chains.models import ExecutionPlan, ChainExecutionResult
from temporal_sdk.chains.workflows import ChainExecutorWorkflow, ChainExecutionRequest


class ChainEngine:
    """
    Engine for executing workflow chains

    This provides a simple interface to execute chains using Temporal workflows.
    """

    def __init__(self, temporal_client: Client):
        """
        Initialize chain engine

        Args:
            temporal_client: Connected Temporal client
        """
        self.client = temporal_client

    async def execute_chain(
        self,
        plan: ExecutionPlan,
        initial_parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start chain execution

        Args:
            plan: ExecutionPlan from ChainInterpreter
            initial_parameters: Optional parameters for first step

        Returns:
            Workflow ID for tracking

        Example:
            engine = ChainEngine(temporal_client)
            chain = load_chain("chains/my_chain.yaml")
            plan = create_execution_plan(chain)

            workflow_id = await engine.execute_chain(plan)
            print(f"Chain started: {workflow_id}")
        """
        workflow_id = f"chain-{plan.chain_name}-{uuid.uuid4()}"

        await self.client.start_workflow(
            ChainExecutorWorkflow.run,
            ChainExecutionRequest(
                plan=plan,
                initial_parameters=initial_parameters
            ),
            id=workflow_id,
            task_queue="comfyui-gpu-farm"
        )

        return workflow_id

    async def get_chain_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get current status of a running chain

        Args:
            workflow_id: Chain workflow ID

        Returns:
            Status dict with current level and step results
        """
        handle = self.client.get_workflow_handle(workflow_id)
        status = await handle.query(ChainExecutorWorkflow.get_status)
        return status

    async def get_chain_result(self, workflow_id: str) -> Dict[str, Any]:
        """
        Wait for chain to complete and get result

        Args:
            workflow_id: Chain workflow ID

        Returns:
            ChainExecutionResult as dict
        """
        handle = self.client.get_workflow_handle(workflow_id)
        result = await handle.result()
        # Result is already a dict from Temporal serialization
        return result

    async def cancel_chain(self, workflow_id: str) -> None:
        """
        Cancel a running chain

        Args:
            workflow_id: Chain workflow ID
        """
        handle = self.client.get_workflow_handle(workflow_id)
        await handle.cancel()
