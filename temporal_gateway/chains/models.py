"""
Chain Models

Data models for workflow chain definitions and execution plans.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator


class ChainStepDefinition(BaseModel):
    """
    Represents a single step in a chain definition (from YAML)

    Attributes:
        id: Unique step identifier
        workflow: Name of the workflow to execute
        parameters: Parameters to pass to the workflow (can contain Jinja2 templates)
        depends_on: List of step IDs this step depends on
        condition: Optional Jinja2 expression to evaluate before executing (e.g., "{{ step1.score > 0.8 }}")
        description: Optional human-readable description
    """
    id: str = Field(..., description="Unique step identifier")
    workflow: str = Field(..., description="Workflow name to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Workflow parameters")
    depends_on: List[str] = Field(default_factory=list, description="Step IDs this depends on")
    condition: Optional[str] = Field(None, description="Jinja2 condition expression")
    description: Optional[str] = Field(None, description="Step description")

    @validator('id')
    def validate_id(cls, v):
        """Ensure step ID is valid"""
        if not v or not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Invalid step ID: {v}. Must be alphanumeric with _ or -")
        return v


class ChainDefinition(BaseModel):
    """
    Represents a complete chain definition (from YAML)

    Attributes:
        name: Chain name
        description: Human-readable description
        steps: List of steps in the chain
        metadata: Optional metadata (tags, version, etc.)
    """
    name: str = Field(..., description="Chain name")
    description: Optional[str] = Field(None, description="Chain description")
    steps: List[ChainStepDefinition] = Field(..., description="Chain steps")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")

    @validator('steps')
    def validate_steps(cls, steps):
        """Ensure step IDs are unique"""
        step_ids = [step.id for step in steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Duplicate step IDs found")
        return steps


@dataclass
class ExecutionNode:
    """
    Represents a node in the execution plan DAG

    Attributes:
        step_id: Step identifier
        workflow: Workflow name to execute
        parameters: Resolved parameters (templates already resolved)
        condition: Condition expression (if any)
        dependencies: Set of step IDs this node depends on
        level: Execution level (0 = no deps, 1 = depends on level 0, etc.)
    """
    step_id: str
    workflow: str
    parameters: Dict[str, Any]
    condition: Optional[str]
    dependencies: Set[str] = field(default_factory=set)
    level: int = 0


@dataclass
class ExecutionPlan:
    """
    Represents a validated, sorted execution plan

    This is the intermediate representation between chain definition and Temporal execution.

    Attributes:
        chain_name: Name of the chain
        nodes: List of execution nodes in topological order
        levels: Dict mapping level number to list of node IDs that can run in parallel
        dependency_graph: Dict mapping step_id to set of dependencies
    """
    chain_name: str
    nodes: List[ExecutionNode]
    levels: Dict[int, List[str]]  # level -> [step_ids that can run in parallel]
    dependency_graph: Dict[str, Set[str]]

    def get_node(self, step_id: str) -> Optional[ExecutionNode]:
        """Get execution node by step ID"""
        for node in self.nodes:
            if node.step_id == step_id:
                return node
        return None

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get groups of steps that can run in parallel

        Returns:
            List of lists, where each inner list contains step IDs that can run concurrently
        """
        max_level = max(self.levels.keys()) if self.levels else 0
        return [self.levels.get(level, []) for level in range(max_level + 1)]

    def get_total_levels(self) -> int:
        """Get total number of execution levels"""
        return len(self.levels)


@dataclass
class StepResult:
    """
    Result of executing a single step

    Attributes:
        step_id: Step identifier
        workflow: Workflow name that was executed
        status: Execution status (completed, failed, skipped)
        output: Step output data
        parameters: Parameters used for execution
        server_address: Server where step executed (for file transfers)
        workflow_db_id: Database workflow ID (for artifact retrieval)
        error: Error message if failed
        execution_time: Time taken in seconds
    """
    step_id: str
    workflow: str
    status: str  # "completed", "failed", "skipped"
    output: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    server_address: Optional[str] = None
    workflow_db_id: Optional[str] = None  # Database workflow ID for artifact tracking
    error: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class ChainExecutionResult:
    """
    Result of executing an entire chain

    Attributes:
        chain_name: Name of the chain
        status: Overall status (completed, failed, partial)
        step_results: Dict mapping step_id to StepResult
        total_execution_time: Total time in seconds
        error: Error message if chain failed
    """
    chain_name: str
    status: str  # "completed", "failed", "partial"
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    total_execution_time: Optional[float] = None
    error: Optional[str] = None

    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """Get result for a specific step"""
        return self.step_results.get(step_id)

    def get_successful_steps(self) -> List[str]:
        """Get list of step IDs that completed successfully"""
        return [
            step_id for step_id, result in self.step_results.items()
            if result.status == "completed"
        ]

    def get_failed_steps(self) -> List[str]:
        """Get list of step IDs that failed"""
        return [
            step_id for step_id, result in self.step_results.items()
            if result.status == "failed"
        ]
