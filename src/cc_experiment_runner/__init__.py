"""
CC Experiment - Vanilla vs Walkthrough Claude Code Comparison
==============================================================

A self-contained Python package for comparing vanilla Claude Code (docs only) vs
walkthrough-powered Claude Code (docs + structured walkthroughs).

Components:
- schemas: Data models for tasks, results, and metrics
- harness_docker: Docker container management for agent execution
- agent: Agent runner (executes inside container)
- walkthrough_generator: Generates walkthroughs with code snippet resolution
- repository_manager: Git repository cloning and management
"""

__version__ = "0.1.0"

from .schemas import (
    Task,
    TaskValidation,
    AgentResult,
    TaskResult,
    ExperimentResults,
    TokenUsage,
    ToolCallStats,
)

# Conditional imports - only load host-side modules when not in container
# (WalkthroughGenerator, RepositoryManager, DockerHarness not needed inside containers)
try:
    from .agents import WalkthroughGenerator
    from .repository_manager import RepositoryManager, RunContext
    from .harness_docker import DockerHarness
    __all__ = [
        "Task",
        "TaskValidation",
        "AgentResult",
        "TaskResult",
        "ExperimentResults",
        "TokenUsage",
        "ToolCallStats",
        "DockerHarness",
        "WalkthroughGenerator",
        "RepositoryManager",
        "RunContext",
    ]
except ImportError:
    # Inside container - only need schemas
    __all__ = [
        "Task",
        "TaskValidation",
        "AgentResult",
        "TaskResult",
        "ExperimentResults",
        "TokenUsage",
        "ToolCallStats",
    ]
