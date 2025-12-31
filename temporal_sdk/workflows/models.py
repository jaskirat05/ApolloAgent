"""
Workflow SDK Models

Data models for the Workflow SDK providing a clean API for working with ComfyUI workflows.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class WorkflowParameter:
    """
    Represents a mutable parameter in a workflow

    Attributes:
        key: Full parameter key (e.g., "93.text")
        node_id: ComfyUI node ID
        input_key: Input key in the node
        default_value: Default value from workflow
        type: Python type name (str, int, float, bool)
        node_class: ComfyUI node class (e.g., "CLIPTextEncode")
        node_title: Human-readable node title
        description: Parameter description
        category: Parameter category (prompts, dimensions, sampling, etc.)
    """
    key: str
    node_id: str
    input_key: str
    default_value: Any
    type: str
    node_class: str
    node_title: str
    description: str
    category: str


@dataclass
class WorkflowOutput:
    """
    Represents the output of a workflow

    Attributes:
        node_id: Node ID that produces output
        output_type: Type of output ("video" or "image")
        node_class: ComfyUI node class (SaveVideo, SaveImage, etc.)
        node_title: Human-readable title
        format: Output format
        filename_prefix: Filename prefix/pattern
    """
    node_id: str
    output_type: str
    node_class: str
    node_title: str
    format: str
    filename_prefix: str


class Workflow:
    """
    Represents a ComfyUI workflow with methods to access and execute it

    This class provides a clean, object-oriented interface to ComfyUI workflows,
    making it easy to discover parameters, get prompts, and execute workflows
    programmatically.

    Example:
        workflow = find_workflow_by_name("video_wan2_2_14B_i2v")

        # Get basic info
        print(f"Workflow: {workflow.name}")
        print(f"Output: {workflow.output_type}")

        # Get prompts
        prompts = workflow.get_prompts()
        print(f"Positive: {prompts['positive']}")
        print(f"Negative: {prompts['negative']}")

        # Get all parameters
        params = workflow.get_all_parameters()

        # Execute with custom parameters
        result = workflow.execute({
            "93.text": "Custom prompt",
            "98.width": 1024
        })
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: List[WorkflowParameter],
        output: Optional[WorkflowOutput],
        workflow_hash: str
    ):
        """
        Initialize a Workflow instance

        Args:
            name: Workflow name
            description: Workflow description
            parameters: List of mutable parameters
            output: Workflow output information
            workflow_hash: SHA256 hash of the workflow
        """
        self._name = name
        self._description = description
        self._parameters = parameters
        self._output = output
        self._workflow_hash = workflow_hash

        # Index parameters by category for quick access
        self._params_by_category: Dict[str, List[WorkflowParameter]] = {}
        for param in parameters:
            category = param.category
            if category not in self._params_by_category:
                self._params_by_category[category] = []
            self._params_by_category[category].append(param)

    @property
    def name(self) -> str:
        """Get workflow name"""
        return self._name

    @property
    def description(self) -> str:
        """Get workflow description"""
        return self._description

    @property
    def output_type(self) -> Optional[str]:
        """Get output type ('video' or 'image')"""
        return self._output.output_type if self._output else None

    @property
    def output(self) -> Optional[WorkflowOutput]:
        """Get full output information"""
        return self._output

    @property
    def workflow_hash(self) -> str:
        """Get workflow hash"""
        return self._workflow_hash

    def get_all_parameters(self) -> List[WorkflowParameter]:
        """
        Get all mutable parameters

        Returns:
            List of all WorkflowParameter objects
        """
        return self._parameters.copy()

    def get_parameters_by_category(self, category: str) -> List[WorkflowParameter]:
        """
        Get parameters filtered by category

        Args:
            category: Category name (e.g., "prompts", "dimensions", "sampling")

        Returns:
            List of WorkflowParameter objects in that category
        """
        return self._params_by_category.get(category, []).copy()

    def get_prompts(self) -> Dict[str, Optional[WorkflowParameter]]:
        """
        Get positive and negative prompts if available

        Returns:
            Dictionary with 'positive' and 'negative' keys.
            Values are WorkflowParameter objects or None if not found.

        Example:
            prompts = workflow.get_prompts()
            if prompts['positive']:
                print(f"Positive prompt: {prompts['positive'].default_value}")
            if prompts['negative']:
                print(f"Negative prompt: {prompts['negative'].default_value}")
        """
        prompt_params = self._params_by_category.get("prompts", [])

        positive = None
        negative = None

        for param in prompt_params:
            desc_lower = param.description.lower()
            title_lower = param.node_title.lower()

            if "positive" in desc_lower or "positive" in title_lower:
                positive = param
            elif "negative" in desc_lower or "negative" in title_lower:
                negative = param

        return {
            "positive": positive,
            "negative": negative
        }

    def get_parameter_by_key(self, key: str) -> Optional[WorkflowParameter]:
        """
        Get a specific parameter by its key

        Args:
            key: Parameter key (e.g., "93.text")

        Returns:
            WorkflowParameter if found, None otherwise
        """
        for param in self._parameters:
            if param.key == key:
                return param
        return None

    def get_categories(self) -> List[str]:
        """
        Get list of all parameter categories

        Returns:
            List of category names
        """
        return list(self._params_by_category.keys())

    def get_parameter_count(self) -> int:
        """
        Get total number of mutable parameters

        Returns:
            Number of parameters
        """
        return len(self._parameters)

    def has_parameter(self, key: str) -> bool:
        """
        Check if a parameter exists and is mutable

        Args:
            key: Parameter key (e.g., "93.text")

        Returns:
            True if parameter exists and is mutable, False otherwise
        """
        return self.get_parameter_by_key(key) is not None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert workflow to dictionary representation

        Returns:
            Dictionary with workflow information
        """
        return {
            "name": self._name,
            "description": self._description,
            "output": {
                "type": self._output.output_type,
                "node_id": self._output.node_id,
                "node_class": self._output.node_class,
                "format": self._output.format
            } if self._output else None,
            "parameters": [
                {
                    "key": p.key,
                    "default_value": p.default_value,
                    "type": p.type,
                    "description": p.description,
                    "category": p.category
                }
                for p in self._parameters
            ],
            "parameter_count": len(self._parameters),
            "categories": self.get_categories()
        }

    def __repr__(self) -> str:
        """String representation of workflow"""
        return (
            f"Workflow(name='{self._name}', "
            f"output_type='{self.output_type}', "
            f"parameters={len(self._parameters)})"
        )

    def __str__(self) -> str:
        """Human-readable string representation"""
        output_info = f" → {self.output_type}" if self.output_type else ""
        return f"{self._name}{output_info} ({len(self._parameters)} parameters)"
