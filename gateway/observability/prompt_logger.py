"""
Prompt Logger using structlog

Creates detailed per-prompt log files in JSONL format for debug agent consumption.
Each workflow execution gets its own log file with complete event history.
"""

import structlog
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class PromptLogger:
    """Logger for individual prompt executions"""

    def __init__(self, prompt_id: str, server_address: str, workflow: Dict[str, Any]):
        """
        Initialize logger for a specific prompt

        Args:
            prompt_id: Unique prompt ID
            server_address: ComfyUI server address
            workflow: Complete workflow definition
        """
        self.prompt_id = prompt_id
        self.server_address = server_address
        self.workflow = workflow

        # Create log directory
        log_dir = Path(__file__).parent / "logs" / "prompts"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"{timestamp}_{prompt_id}.jsonl"

        # Configure structlog for this prompt
        self.logger = self._setup_logger()

        # Log initial workflow submission
        self.log_workflow_submitted()

    def _setup_logger(self):
        """Configure structlog with JSON output to file"""
        # Configure structlog processors
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(structlog.stdlib.logging.DEBUG),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Create logger with bound context
        logger = structlog.get_logger()
        logger = logger.bind(
            prompt_id=self.prompt_id,
            server=self.server_address
        )

        return logger

    def _write_to_file(self, data: Dict[str, Any]):
        """Write a log entry to the JSONL file"""
        with open(self.log_file, 'a') as f:
            json.dump(data, f, default=str)
            f.write('\n')

    def log_workflow_submitted(self):
        """Log workflow submission"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "workflow.submitted",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "workflow": self.workflow,
            "workflow_node_count": len(self.workflow),
            "workflow_nodes": list(self.workflow.keys())
        }
        self._write_to_file(entry)

    def log_server_selected(self, strategy: str, available_servers: int):
        """Log server selection"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "server.selected",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "strategy": strategy,
            "available_servers": available_servers
        }
        self._write_to_file(entry)

    def log_queued(self):
        """Log workflow queued on ComfyUI"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "workflow.queued",
            "prompt_id": self.prompt_id,
            "server": self.server_address
        }
        self._write_to_file(entry)

    def log_websocket_connected(self):
        """Log WebSocket connection established"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "websocket.connected",
            "prompt_id": self.prompt_id,
            "server": self.server_address
        }
        self._write_to_file(entry)

    def log_websocket_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log any WebSocket event from ComfyUI

        Args:
            event_type: Type of event (e.g., 'executing', 'progress', 'executed')
            data: Event data payload
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": f"ws.{event_type}",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "event_type": event_type,
            "data": data
        }
        self._write_to_file(entry)

    def log_node_executing(self, node_id: str):
        """Log node execution started"""
        node_info = self.workflow.get(node_id, {})
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "node.executing",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "node_id": node_id,
            "node_class_type": node_info.get("class_type"),
            "node_inputs": node_info.get("inputs", {})
        }
        self._write_to_file(entry)

    def log_node_executed(self, node_id: str, output: Optional[Dict] = None):
        """Log node execution completed"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "node.executed",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "node_id": node_id,
            "output": output
        }
        self._write_to_file(entry)

    def log_progress(self, value: int, max_value: int):
        """Log execution progress"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "execution.progress",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "progress_value": value,
            "progress_max": max_value,
            "progress_percent": round((value / max_value * 100), 2) if max_value > 0 else 0
        }
        self._write_to_file(entry)

    def log_execution_error(self, error_data: Dict[str, Any]):
        """
        Log execution error with full context

        Args:
            error_data: Complete error data from ComfyUI
        """
        # Extract key error information
        node_id = error_data.get('node_id', 'unknown')
        node_info = self.workflow.get(node_id, {})

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "execution.error",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "error": {
                "node_id": node_id,
                "node_type": error_data.get('node_type'),
                "exception_type": error_data.get('exception_type'),
                "exception_message": error_data.get('exception_message'),
                "traceback": error_data.get('traceback', []),
            },
            "node_context": {
                "class_type": node_info.get("class_type"),
                "inputs": node_info.get("inputs", {}),
            },
            "full_error_data": error_data
        }
        self._write_to_file(entry)

    def log_execution_complete(self, duration_ms: Optional[int] = None,
                              nodes_executed: int = 0):
        """Log successful execution completion"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "execution.complete",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "duration_ms": duration_ms,
            "nodes_executed": nodes_executed
        }
        self._write_to_file(entry)

    def log_images_downloaded(self, images: list):
        """Log images downloaded and stored"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "images.downloaded",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "image_count": len(images),
            "images": images
        }
        self._write_to_file(entry)

    def log_workflow_failed(self, reason: str, error: Optional[Dict] = None):
        """Log workflow failure"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "workflow.failed",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "reason": reason,
            "error": error
        }
        self._write_to_file(entry)

    def log_workflow_success(self, image_urls: list):
        """Log workflow success with results"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "workflow.success",
            "prompt_id": self.prompt_id,
            "server": self.server_address,
            "image_urls": image_urls,
            "image_count": len(image_urls)
        }
        self._write_to_file(entry)

    def get_log_file_path(self) -> Path:
        """Get the path to this prompt's log file"""
        return self.log_file

    def get_log_contents(self) -> list:
        """
        Read and parse the entire log file

        Returns:
            List of log entries (dicts)
        """
        entries = []
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries


# Helper function to create a prompt logger
def create_prompt_logger(prompt_id: str, server_address: str,
                        workflow: Dict[str, Any]) -> PromptLogger:
    """
    Create a new prompt logger

    Args:
        prompt_id: Unique prompt ID
        server_address: ComfyUI server address
        workflow: Complete workflow definition

    Returns:
        PromptLogger instance
    """
    return PromptLogger(prompt_id, server_address, workflow)
