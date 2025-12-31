"""
Chain Executor Workflow

Temporal workflow that executes chain plans by orchestrating child ComfyUI workflows.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import with workflow.unsafe for Temporal
with workflow.unsafe.imports_passed_through():
    from temporal_sdk.chains.models import ExecutionPlan, StepResult, ChainExecutionResult
    from temporal_gateway.workflows import ComfyUIWorkflow, WorkflowExecutionRequest
    from temporal_gateway.activities import (
        resolve_chain_templates,
        evaluate_chain_condition,
        apply_workflow_parameters,
        select_best_server,
        transfer_artifacts_from_storage,
        create_chain_record,
        create_workflow_record,
        update_chain_status_activity,
        update_workflow_status_activity,
        get_workflow_artifacts,
    )


@dataclass
class ChainExecutionRequest:
    """Request to execute a chain"""
    plan: ExecutionPlan
    initial_parameters: Dict[str, Any] = None  # Optional parameters for first step


@workflow.defn
class ChainExecutorWorkflow:
    """
    Temporal workflow that executes workflow chains

    This workflow:
    1. Takes an ExecutionPlan from ChainInterpreter
    2. Executes steps level by level (sequential levels, parallel within level)
    3. Resolves Jinja2 templates using previous step results
    4. Evaluates conditions to skip steps
    5. Executes each step as a child ComfyUIWorkflow
    6. Returns ChainExecutionResult with all step results
    """

    def __init__(self):
        self._status = "initializing"
        self._current_level = 0
        self._step_results: Dict[str, StepResult] = {}
        self._chain_id: Optional[str] = None  # Database chain ID
        self._workflow_ids: Dict[str, str] = {}  # Map step_id -> workflow_id

    @workflow.run
    async def run(self, request: ChainExecutionRequest) -> ChainExecutionResult:
        """
        Execute chain plan

        Args:
            request: Chain execution request with ExecutionPlan

        Returns:
            ChainExecutionResult with all step results
        """
        plan = request.plan
        workflow.logger.info(f"Starting chain execution: {plan.chain_name}")
        workflow.logger.info(f"Total levels: {plan.get_total_levels()}")

        try:
            # Create chain record in database
            self._chain_id = await workflow.execute_activity(
                create_chain_record,
                args=[
                    plan.chain_name,
                    workflow.info().workflow_id,
                    workflow.info().run_id,
                    None,  # chain_definition - can add later
                    None,  # description
                ],
                start_to_close_timeout=timedelta(seconds=10)
            )
            workflow.logger.info(f"Created chain record: {self._chain_id}")

            # Execute each level sequentially
            for level_num in range(plan.get_total_levels()):
                self._current_level = level_num
                self._status = f"executing_level_{level_num}"

                # Update chain status in DB
                await workflow.execute_activity(
                    update_chain_status_activity,
                    args=[self._chain_id, self._status, level_num],
                    start_to_close_timeout=timedelta(seconds=10)
                )

                level_steps = plan.levels[level_num]
                workflow.logger.info(f"Level {level_num}: Executing {len(level_steps)} step(s) in parallel")

                # Execute all steps at this level in parallel
                parallel_tasks = []
                for step_id in level_steps:
                    node = plan.get_node(step_id)
                    task = self._execute_step(node)
                    parallel_tasks.append(task)

                # Wait for all parallel steps to complete
                import asyncio
                results = await asyncio.gather(*parallel_tasks)

                # Store results for next level
                for result in results:
                    self._step_results[result.step_id] = result
                    workflow.logger.info(f"Step {result.step_id}: {result.status}")

            # All levels complete
            self._status = "completed"

            # Update final chain status in DB
            await workflow.execute_activity(
                update_chain_status_activity,
                args=[self._chain_id, "completed"],
                start_to_close_timeout=timedelta(seconds=10)
            )

            return ChainExecutionResult(
                chain_name=plan.chain_name,
                status="completed",
                step_results=self._step_results
            )

        except Exception as e:
            self._status = "failed"
            workflow.logger.error(f"Chain execution failed: {e}")

            # Update chain status to failed in DB
            if self._chain_id:
                await workflow.execute_activity(
                    update_chain_status_activity,
                    args=[self._chain_id, "failed", None, str(e)],
                    start_to_close_timeout=timedelta(seconds=10)
                )

            return ChainExecutionResult(
                chain_name=plan.chain_name,
                status="failed",
                step_results=self._step_results,
                error=str(e)
            )

    async def _execute_step(self, node) -> StepResult:
        """
        Execute a single step as a child workflow

        Args:
            node: ExecutionNode from the plan

        Returns:
            StepResult
        """
        step_id = node.step_id
        workflow.logger.info(f"Executing step: {step_id}")

        try:
            # 1. Evaluate condition (if any) using activity
            if node.condition:
                should_execute = await workflow.execute_activity(
                    evaluate_chain_condition,
                    args=[node.condition, self._step_results],
                    start_to_close_timeout=timedelta(seconds=10)
                )

                if not should_execute:
                    workflow.logger.info(f"Step {step_id} skipped (condition failed)")
                    return StepResult(
                        step_id=step_id,
                        workflow=node.workflow,
                        status="skipped"
                    )

            # 2. Resolve templates in parameters using activity
            resolved_params = await workflow.execute_activity(
                resolve_chain_templates,
                args=[node.parameters, self._step_results],
                start_to_close_timeout=timedelta(seconds=10)
            )

            workflow.logger.info(f"Step {step_id}: Resolved parameters")

            # 3. Get workflow JSON and apply parameters using activity
            workflow_json = await workflow.execute_activity(
                apply_workflow_parameters,
                args=[node.workflow, resolved_params],
                start_to_close_timeout=timedelta(seconds=30)
            )

            # 4. Pre-select target server for this step
            target_server = await workflow.execute_activity(
                select_best_server,
                "least_loaded",
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0
                )
            )
            workflow.logger.info(f"Step {step_id}: Selected target server: {target_server}")

            # 5. Transfer artifacts from dependency steps to target server
            if node.dependencies:
                workflow.logger.info(f"Step {step_id}: Processing {len(node.dependencies)} dependency step(s)")

                for dep_step_id in node.dependencies:
                    # Get dependency workflow ID from our tracking
                    dep_workflow_id = self._workflow_ids.get(dep_step_id)

                    if not dep_workflow_id:
                        workflow.logger.warning(f"Dependency {dep_step_id} workflow ID not found - skipping transfer")
                        continue

                    # Get artifact IDs for the dependency workflow
                    artifact_ids = await workflow.execute_activity(
                        get_workflow_artifacts,
                        args=[dep_workflow_id],
                        start_to_close_timeout=timedelta(seconds=10)
                    )

                    if not artifact_ids:
                        workflow.logger.info(f"Dependency {dep_step_id} has no artifacts - skipping transfer")
                        continue

                    workflow.logger.info(f"Transferring {len(artifact_ids)} artifact(s) from {dep_step_id} to {target_server}")

                    # Transfer artifacts from local storage to target server
                    await workflow.execute_activity(
                        transfer_artifacts_from_storage,
                        args=[dep_workflow_id, target_server, artifact_ids, None],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            initial_interval=timedelta(seconds=2),
                            maximum_interval=timedelta(seconds=10),
                            backoff_coefficient=2.0
                        )
                    )

            # 6. Create workflow record in database (before execution)
            # Note: We don't have prompt_id yet, will use placeholder
            workflow_db_id = await workflow.execute_activity(
                create_workflow_record,
                args=[
                    node.workflow,                          # workflow_name
                    target_server,                          # server_address
                    "pending",                              # prompt_id (placeholder)
                    self._chain_id,                         # chain_id
                    step_id,                                # step_id
                    f"{workflow.info().workflow_id}-{step_id}",  # temporal_workflow_id
                    None,                                   # temporal_run_id
                    workflow_json,                          # workflow_definition
                    resolved_params,                        # parameters
                ],
                start_to_close_timeout=timedelta(seconds=10)
            )

            # Store workflow ID for this step
            self._workflow_ids[step_id] = workflow_db_id
            workflow.logger.info(f"Step {step_id}: Created workflow record {workflow_db_id}")

            # 7. Execute as child workflow with pre-selected server
            child_workflow_id = f"{workflow.info().workflow_id}-{step_id}"

            result = await workflow.execute_child_workflow(
                ComfyUIWorkflow.run,
                WorkflowExecutionRequest(
                    workflow_definition=workflow_json,
                    strategy="least_loaded",
                    workflow_name=node.workflow,
                    server_address=target_server,  # Pass pre-selected server
                    workflow_db_id=workflow_db_id,  # Pass DB workflow ID for artifact linking
                ),
                id=child_workflow_id,
                task_queue="comfyui-gpu-farm",
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=10),
                    maximum_interval=timedelta(seconds=60),
                    backoff_coefficient=2.0
                )
            )

            # 8. Update workflow status to completed in DB
            await workflow.execute_activity(
                update_workflow_status_activity,
                args=[workflow_db_id, result.status, result.error if hasattr(result, 'error') else None],
                start_to_close_timeout=timedelta(seconds=10)
            )

            # 9. Return step result with workflow ID
            return StepResult(
                step_id=step_id,
                workflow=node.workflow,
                status=result.status,
                output=result.output,
                parameters=resolved_params,
                server_address=result.server_address,
                workflow_db_id=workflow_db_id,  # Store for artifact retrieval
            )

        except Exception as e:
            workflow.logger.error(f"Step {step_id} failed: {e}")

            # Update workflow status to failed if we created the record
            if step_id in self._workflow_ids:
                await workflow.execute_activity(
                    update_workflow_status_activity,
                    args=[self._workflow_ids[step_id], "failed", str(e)],
                    start_to_close_timeout=timedelta(seconds=10)
                )

            return StepResult(
                step_id=step_id,
                workflow=node.workflow,
                status="failed",
                error=str(e)
            )

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """
        Query current chain execution status

        Returns:
            Status dict with current level and step results
        """
        return {
            "status": self._status,
            "current_level": self._current_level,
            "completed_steps": len(self._step_results),
            "step_statuses": {
                step_id: result.status
                for step_id, result in self._step_results.items()
            }
        }
