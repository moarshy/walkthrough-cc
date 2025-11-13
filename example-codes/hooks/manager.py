"""
Hook Manager for StackBench agents.

Combines validation hooks and logging hooks into a unified configuration.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from claude_agent_sdk import HookMatcher

from .logging import create_logging_hooks, AgentLogger
from .validation import (
    create_extraction_validation_hook,
    create_validation_output_hook,
    create_api_completeness_validation_hook
)


class HookManager:
    """Manages all hooks for an agent (validation + logging)."""

    def __init__(
        self,
        agent_type: str,
        logger: Optional[AgentLogger] = None,
        output_dir: Optional[Path] = None,
        validation_log_dir: Optional[Path] = None
    ):
        """
        Initialize the hook manager.

        Args:
            agent_type: Type of agent (extraction, api_validation, code_validation,
                       clarity_validation, api_completeness, readme_llm_generation)
            logger: Optional AgentLogger for logging hooks
            output_dir: Optional output directory for validation hooks
            validation_log_dir: Optional directory for validation hook tracking logs
        """
        self.agent_type = agent_type
        self.logger = logger
        self.output_dir = Path(output_dir) if output_dir else None
        self.validation_log_dir = Path(validation_log_dir) if validation_log_dir else None

    def create_hooks(self) -> Dict[str, Any]:
        """
        Create combined hooks configuration for the agent.

        Returns:
            Dictionary with PreToolUse and PostToolUse hook configurations
        """
        hooks = {
            'PreToolUse': [],
            'PostToolUse': []
        }

        # Add validation hooks
        if self.agent_type == "extraction":
            validation_hook = create_extraction_validation_hook(
                output_dir=self.output_dir,
                log_dir=self.validation_log_dir
            )
            hooks['PreToolUse'].append(
                HookMatcher(
                    matcher="Write",  # Only validate Write operations
                    hooks=[validation_hook]
                )
            )

        elif self.agent_type in ["api_validation", "code_validation", "clarity_validation"]:
            validation_hook = create_validation_output_hook(
                output_dir=self.output_dir,
                log_dir=self.validation_log_dir
            )
            hooks['PreToolUse'].append(
                HookMatcher(
                    matcher="Write",  # Only validate Write operations
                    hooks=[validation_hook]
                )
            )

        elif self.agent_type == "api_completeness":
            validation_hook = create_api_completeness_validation_hook(
                output_dir=self.output_dir,
                log_dir=self.validation_log_dir
            )
            hooks['PreToolUse'].append(
                HookMatcher(
                    matcher="Write",  # Only validate Write operations
                    hooks=[validation_hook]
                )
            )

        elif self.agent_type == "readme_llm_generation":
            # README.LLM generation agent
            # Validation will be added when generator agent is implemented
            # For now, just allow logging hooks to work
            pass

        # Add logging hooks (if logger provided)
        if self.logger:
            logging_hooks = create_logging_hooks(self.logger)
            hooks['PreToolUse'].extend(logging_hooks['PreToolUse'])
            hooks['PostToolUse'].extend(logging_hooks['PostToolUse'])

        return hooks


def create_agent_hooks(
    agent_type: str,
    logger: Optional[AgentLogger] = None,
    output_dir: Optional[Path] = None,
    validation_log_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Convenience function to create hooks for an agent.

    Args:
        agent_type: Type of agent (extraction, api_validation, code_validation, clarity_validation)
        logger: Optional AgentLogger for logging hooks
        output_dir: Optional output directory for validation hooks
        validation_log_dir: Optional directory for validation hook tracking logs

    Returns:
        Dictionary with hook configurations
    """
    manager = HookManager(agent_type, logger, output_dir, validation_log_dir)
    return manager.create_hooks()
