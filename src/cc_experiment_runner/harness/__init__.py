"""
Harness modules for running agents in controlled environments.

This module provides:
- Docker-based execution harness for isolated agent runs
- Independent validation harness for verifying task completion
"""

from .docker_harness import DockerHarness
from .validation_harness import ValidationHarness

__all__ = [
    'DockerHarness',
    'ValidationHarness',
]
