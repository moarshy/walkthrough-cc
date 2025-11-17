"""
Harness modules for running agents in controlled environments.

This module provides:
- Docker-based execution harness for isolated agent runs
- In-container validation (see run_agent_in_container.py)
"""

from .docker_harness import DockerHarness

__all__ = [
    'DockerHarness',
]
