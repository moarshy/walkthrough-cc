"""
Hooks for StackBench agents.

Provides validation hooks for JSON schema validation and logging hooks
for capturing agent execution details.
"""

from .logging import create_logging_hooks, AgentLogger
from .logging_manager import LoggingManager
from .validation import (
    create_extraction_validation_hook,
    create_validation_output_hook,
    validate_extraction_json,
    validate_validation_output_json
)
from .manager import HookManager, create_agent_hooks

__all__ = [
    "create_logging_hooks",
    "AgentLogger",
    "LoggingManager",
    "create_extraction_validation_hook",
    "create_validation_output_hook",
    "validate_extraction_json",
    "validate_validation_output_json",
    "HookManager",
    "create_agent_hooks"
]
