"""
Independent validation harness for deterministic task evaluation.

Inspired by SetupBench's evaluation_harness.py, this module provides
deterministic validation of task completion using success_command execution
in a fresh shell environment.
"""

import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional
from ..schemas import Task


class ValidationHarness:
    """
    Validates task completion independently of agent execution.

    This harness runs the success_command in a fresh shell subprocess
    and checks for "Setup successful" pattern in the output, following
    SetupBench's deterministic validation approach.
    """

    def validate_task(
        self,
        task: Task,
        workspace_dir: Path,
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Run success_command in a fresh shell and validate output.

        This method executes the task's success_command independently,
        ensuring that the setup actually works regardless of what the
        agent reported.

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
            >>> harness = ValidationHarness()
            >>> success, output, code = harness.validate_task(task, Path("/workspace"))
            >>> if success:
            ...     print("Task completed successfully!")
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
