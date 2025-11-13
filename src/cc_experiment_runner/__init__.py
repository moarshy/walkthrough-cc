"""
CC Experiment - Vanilla vs Walkthrough Claude Code Comparison
==============================================================

A Python package for comparing vanilla Claude Code (docs only) vs
walkthrough-powered Claude Code (docs + structured walkthroughs).

Components:
- schemas: Data models for tasks, results, and metrics
- harness_docker: Docker container management for agent execution  
- agent_wrapper: Agent runner (executes inside container)
- runner: Main experiment orchestrator
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
    from .walkthrough_generator import WalkthroughGenerator
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
