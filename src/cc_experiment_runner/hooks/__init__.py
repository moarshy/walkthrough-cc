"""
Hooks for agent execution monitoring and validation.

This module provides:
- Logging hooks: Track all tool calls, messages, and token usage
- Output path validation: Ensure files are written to correct locations
- JSON schema validation: Validate generated JSON against Pydantic schemas
"""

from .logging import AgentLogger, create_logging_hooks
from .output_path_validation import (
    validate_output_path_hook,
    create_output_path_validation_hooks
)
from .json_schema_validation import (
    validate_walkthrough_json_hook,
    create_json_schema_validation_hooks
)

# Legacy compatibility: maintain the old combined function name
def create_walkthrough_generation_hooks():
    """
    Create combined hook configuration for walkthrough generation.

    This combines both output path validation and JSON schema validation
    for backward compatibility.

    Returns:
        Dictionary mapping hook events to HookMatcher lists
    """
    path_hooks = create_output_path_validation_hooks()
    json_hooks = create_json_schema_validation_hooks()

    # Merge the hooks
    combined = {}
    for event, matchers in path_hooks.items():
        combined[event] = matchers
    for event, matchers in json_hooks.items():
        if event in combined:
            combined[event].extend(matchers)
        else:
            combined[event] = matchers

    return combined


__all__ = [
    # Logging
    'AgentLogger',
    'create_logging_hooks',

    # Output path validation
    'validate_output_path_hook',
    'create_output_path_validation_hooks',

    # JSON schema validation
    'validate_walkthrough_json_hook',
    'create_json_schema_validation_hooks',

    # Combined (legacy)
    'create_walkthrough_generation_hooks',
]
