"""
Independent validation harness for deterministic task evaluation.

Inspired by SetupBench's evaluation_harness.py, this module provides
deterministic validation of task completion using success_command execution
in a fresh shell environment.

Supports both local (host) and Docker-based validation for maximum reproducibility.
"""

import subprocess
import os
import time
from pathlib import Path
from typing import Tuple, Optional, Literal
from ..schemas import Task

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class ValidationHarness:
    """
    Validates task completion independently of agent execution.

    This harness runs the success_command to verify that the setup actually works.
    Supports both local (host) and Docker-based validation.

    For reproducibility, Docker validation is recommended as it runs in the
    same environment as the agent.
    """

    def __init__(self, use_docker: bool = False, docker_image: str = "cc-experiment-runner:latest"):
        """
        Initialize validation harness.

        Args:
            use_docker: If True, run validation in Docker container
            docker_image: Docker image to use for validation (if use_docker=True)
        """
        self.use_docker = use_docker
        self.docker_image = docker_image
        self.docker_client = None

        if use_docker:
            if not DOCKER_AVAILABLE:
                raise ImportError("Docker validation requires 'docker' package. Install with: pip install docker")
            self.docker_client = docker.from_env()

    def validate_task(
        self,
        task: Task,
        workspace_dir: Path,
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Run success_command and validate output.

        Routes to either Docker-based or local validation based on use_docker setting.

        Args:
            task: Task definition with success_command
            workspace_dir: Directory where task was executed
            timeout: Optional timeout override (uses task.timeout_seconds if None)

        Returns:
            Tuple of (success: bool, output: str, exit_code: int)
                - success: True if "Setup successful" found in output
                - output: Combined stdout + stderr from command
                - exit_code: Exit code from command (-1 for errors)

        Example:
            >>> harness = ValidationHarness(use_docker=True)
            >>> success, output, code = harness.validate_task(task, Path("./workspace"))
            >>> if success:
            ...     print("Task completed successfully!")
        """
        if self.use_docker:
            return self._validate_in_docker(task, workspace_dir, timeout)
        else:
            return self._validate_local(task, workspace_dir, timeout)

    def _validate_local(
        self,
        task: Task,
        workspace_dir: Path,
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Run validation locally on the host machine.

        ⚠️  WARNING: This runs on the HOST environment, which may differ from
        the agent's Docker environment. Use Docker validation for reproducibility.
        """
        timeout = timeout or task.timeout_seconds

        try:
            # Run success_command in fresh subprocess
            # Using shell=True to support complex bash commands with pipes, &&, etc.
            result = subprocess.run(
                task.success_command,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy()  # Fresh environment
            )

            # Combine stdout and stderr for output
            output = result.stdout + result.stderr
            exit_code = result.returncode

            # SetupBench validation logic: Check for "Setup successful" in output
            # This is the deterministic success criterion
            success = "Setup successful" in output

            return success, output, exit_code

        except subprocess.TimeoutExpired:
            # Command exceeded timeout
            return False, f"Validation command timed out after {timeout}s", -1

        except Exception as e:
            # Unexpected error during validation
            return False, f"Validation failed with error: {e}", -1

    def _validate_in_docker(
        self,
        task: Task,
        workspace_dir: Path,
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Run validation in a Docker container (same environment as agent).

        This ensures validation runs in the same environment as the agent,
        providing true reproducibility and platform independence.

        Args:
            task: Task definition
            workspace_dir: Workspace directory on host
            timeout: Validation timeout

        Returns:
            Tuple of (success, output, exit_code)
        """
        timeout = timeout or task.timeout_seconds
        container_name = f"cc-validation-{task.instance_id}-{int(time.time())}"

        try:
            # Mount workspace as /workspace in container
            volumes = {
                str(workspace_dir.absolute()): {'bind': '/workspace', 'mode': 'rw'}
            }

            # Run validation command in Docker
            # Using bash -c to handle complex commands
            container = self.docker_client.containers.run(
                image=self.docker_image,
                command=['bash', '-c', f'cd /workspace && {task.success_command}'],
                volumes=volumes,
                detach=True,
                remove=False,  # Keep container to get logs
                name=container_name,
                network_mode='bridge'
            )

            # Wait for completion with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
            except Exception as e:
                # Timeout or other error
                container.stop(timeout=5)
                container.remove()
                return False, f"Validation container timed out or failed: {e}", -1

            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')

            # Cleanup
            container.remove()

            # Check for success
            success = "Setup successful" in logs

            return success, logs, exit_code

        except docker.errors.ImageNotFound:
            return False, f"Docker image not found: {self.docker_image}", -1

        except docker.errors.APIError as e:
            return False, f"Docker API error: {e}", -1

        except Exception as e:
            return False, f"Unexpected error during Docker validation: {e}", -1

    def validate_and_log(
        self,
        task: Task,
        workspace_dir: Path,
        log_path: Path
    ) -> Tuple[bool, str, int]:
        """
        Validate task and write detailed log file.

        Convenience method that performs validation and writes a
        structured log file for debugging.

        Args:
            task: Task definition
            workspace_dir: Directory where task was executed
            log_path: Path to write validation log

        Returns:
            Tuple of (success: bool, output: str, exit_code: int)
        """
        success, output, exit_code = self.validate_task(task, workspace_dir)

        # Write validation log
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'w') as f:
            f.write(f"=== Validation Log ===\n")
            f.write(f"Task ID: {task.instance_id}\n")
            f.write(f"Command: {task.success_command}\n")
            f.write(f"Workspace: {workspace_dir}\n")
            f.write(f"Exit Code: {exit_code}\n")
            f.write(f"Success: {success}\n")
            f.write(f"\n=== Output ===\n")
            f.write(output)
            f.write(f"\n=== End Log ===\n")

        return success, output, exit_code


def validate_task_simple(
    success_command: str,
    workspace_dir: Path,
    timeout: int = 300
) -> bool:
    """
    Simple validation function for quick checks.

    Useful for testing validation commands without full Task objects.

    Args:
        success_command: Shell command to execute
        workspace_dir: Working directory
        timeout: Timeout in seconds

    Returns:
        bool: True if "Setup successful" in output

    Example:
        >>> is_valid = validate_task_simple(
        ...     "python3 -c 'import fastapi' && echo 'Setup successful'",
        ...     Path("/workspace"),
        ...     timeout=30
        ... )
    """
    try:
        result = subprocess.run(
            success_command,
            shell=True,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy()
        )

        output = result.stdout + result.stderr
        return "Setup successful" in output

    except (subprocess.TimeoutExpired, Exception):
        return False
