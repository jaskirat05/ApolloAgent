"""
Chain Executor Workflow

Temporal workflow that executes chain plans by orchestrating child ComfyUI workflows.
"""

from dataclasses import dataclass
from typing import Dict, Any
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import with workflow.unsafe for Temporal
with workflow.unsafe.imports_passed_through():
    from ...chains.models import ExecutionPlan, StepResult, ChainExecutionResult
    from ..comfy_workflow import ComfyUIWorkflow, WorkflowExecutionRequest
    from ...activities import (
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
        create_approval_request_activity,
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

        # Approval state
        self.approval_decision = None
        self.approval_decided_by = None
        self.approval_parameters = {}
        self.approval_comment = None

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

    async def _wait_for_approval(
        self,
        step_id: str,
        workflow_db_id: str,
        artifact_ids: list,
        approval_config: dict,
        node
    ) -> tuple[str, dict]:
        """
        Wait for approval with regeneration support

        Args:
            step_id: Step identifier
            workflow_db_id: Database workflow ID
            artifact_ids: List of artifact IDs to approve
            approval_config: Approval configuration from YAML
            node: Execution node for regeneration

        Returns:
            Tuple of (decision, parameters) - parameters will be new params if rejected
        """
        timeout_hours = approval_config.get('timeout_hours', 24)
        on_rejected = approval_config.get('on_rejected', 'stop')
        max_retries = approval_config.get('max_retries', 0)
        retry_count = 0

        while True:
            # Reset approval state
            self.approval_decision = None
            self.approval_parameters = {}

            # Create approval request for the artifact
            # Assuming first artifact for now (can be extended for multiple)
            artifact_id = artifact_ids[0] if artifact_ids else None

            if not artifact_id:
                workflow.logger.warning(f"Step {step_id}: No artifacts to approve, auto-approving")
                return "approved", {}

            # Create approval request in DB
            approval_request_data = await workflow.execute_activity(
                create_approval_request_activity,
                args=[
                    artifact_id,
                    workflow.info().workflow_id,
                    f"https://your-domain.com/artifacts/{artifact_id}",  # artifact_view_url
                    self._chain_id,  # chain_id
                    step_id,  # step_id
                    workflow.info().run_id,  # temporal_run_id
                    168,  # link_expiration_hours (1 week default)
                    node.workflow,  # workflow_name
                    None,  # server (can add if needed)
                    self._step_results.get(step_id, {}).parameters if hasattr(self._step_results.get(step_id), 'parameters') else {},  # parameters
                    approval_config,  # approval_config
                ],
                start_to_close_timeout=timedelta(seconds=30)
            )

            workflow.logger.info(
                f"Step {step_id}: Approval request created, "
                f"token: {approval_request_data['token'][:16]}..."
            )

            # WAIT for approval signal with timeout
            try:
                await workflow.wait_condition(
                    lambda: self.approval_decision is not None,
                    timeout=timedelta(hours=timeout_hours)
                )

                # Signal received!
                if self.approval_decision == "approved":
                    workflow.logger.info(f"Step {step_id}: Approved by {self.approval_decided_by}")
                    return "approved", {}

                elif self.approval_decision == "rejected":
                    workflow.logger.info(
                        f"Step {step_id}: Rejected by {self.approval_decided_by}"
                        f" with comment: {self.approval_comment}"
                    )

                    # Handle rejection based on policy
                    if on_rejected == 'regenerate' and retry_count < max_retries:
                        workflow.logger.info(
                            f"Step {step_id}: Regenerating "
                            f"(attempt {retry_count + 1}/{max_retries})"
                        )
                        retry_count += 1
                        # Return rejected with new parameters to trigger regeneration
                        return "rejected", self.approval_parameters

                    elif on_rejected == 'skip':
                        workflow.logger.info(f"Step {step_id}: Skipping due to rejection")
                        raise Exception(f"Step {step_id} skipped due to approval rejection")

                    else:  # 'stop' or exhausted retries
                        raise Exception(
                            f"Step {step_id} stopped due to approval rejection "
                            f"after {retry_count} retries"
                        )

            except TimeoutError:
                # Timeout - no decision received
                workflow.logger.warning(
                    f"Step {step_id}: Approval timeout after {timeout_hours} hours"
                )
                timeout_action = approval_config.get('timeout_action', 'auto_reject')

                if timeout_action == 'auto_approve':
                    workflow.logger.info(f"Step {step_id}: Auto-approving due to timeout")
                    return "approved", {}
                else:
                    raise Exception(f"Step {step_id} timeout - no approval received")

    async def _execute_step(self, node) -> StepResult:
        """
        Execute a single step as a child workflow with approval support

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

            # Check if step requires approval
            requires_approval = node.parameters.get('requires_approval', False)
            approval_config = node.parameters.get('approval', {}) if requires_approval else None

            # Regeneration loop for approval rejections
            regeneration_params = None
            while True:
                # 2. Resolve templates in parameters using activity
                # Merge with regeneration params if this is a retry
                current_params = {**node.parameters}
                if regeneration_params:
                    current_params.update(regeneration_params)

                resolved_params = await workflow.execute_activity(
                    resolve_chain_templates,
                    args=[current_params, self._step_results],
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

    @workflow.signal
    async def approval_decision_signal(
        self,
        decision: str,
        decided_by: str,
        parameters: dict = None,
        comment: str = None
    ):
        """
        Signal handler for approval decisions

        Called by external approval system when user approves/rejects

        Args:
            decision: 'approved' or 'rejected'
            decided_by: Identifier of who made the decision
            parameters: New parameters for regeneration (if rejected)
            comment: Optional comment
        """
        workflow.logger.info(f"Received approval decision: {decision} by {decided_by}")
        self.approval_decision = decision
        self.approval_decided_by = decided_by
        self.approval_parameters = parameters or {}
        self.approval_comment = comment

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
