"""
Task loader utility for loading SetupBench-style tasks from JSON files.

This module provides functions to load task definitions from JSON files
and validate them against the Task schema.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from pydantic import ValidationError

from .schemas import Task


class TaskLoadError(Exception):
    """Raised when task loading fails."""
    pass


def load_tasks_from_json(tasks_file: Path) -> List[Task]:
    """
    Load tasks from a JSON file.

    The JSON file should have this structure:
    {
        "metadata": {
            "name": "Task Set Name",
            "description": "Description",
            ...
        },
        "tasks": [
            {
                "instance_id": "task-1",
                "repo_url": "https://github.com/...",
                ...
            },
            ...
        ]
    }

    Args:
        tasks_file: Path to JSON file containing tasks

    Returns:
        List of Task objects

    Raises:
        TaskLoadError: If file doesn't exist, is invalid JSON, or tasks fail validation

    Example:
        >>> tasks = load_tasks_from_json(Path("tasks/fastapi_tasks.json"))
        >>> print(f"Loaded {len(tasks)} tasks")
        >>> for task in tasks:
        ...     print(f"  - {task.instance_id}")
    """
    # Check file exists
    if not tasks_file.exists():
        raise TaskLoadError(f"Task file not found: {tasks_file}")

    # Load JSON
    try:
        with open(tasks_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise TaskLoadError(f"Invalid JSON in {tasks_file}: {e}")

    # Validate structure
    if not isinstance(data, dict):
        raise TaskLoadError(f"Expected JSON object, got {type(data).__name__}")

    if "tasks" not in data:
        raise TaskLoadError(f"Missing 'tasks' key in {tasks_file}")

    if not isinstance(data["tasks"], list):
        raise TaskLoadError(f"'tasks' must be a list, got {type(data['tasks']).__name__}")

    # Parse tasks
    tasks = []
    errors = []

    for i, task_dict in enumerate(data["tasks"]):
        try:
            task = Task(**task_dict)
            tasks.append(task)
        except ValidationError as e:
            errors.append(f"Task {i}: {e}")

    # Report errors if any
    if errors:
        error_msg = f"Failed to load {len(errors)} task(s) from {tasks_file}:\n"
        error_msg += "\n".join(errors)
        raise TaskLoadError(error_msg)

    return tasks


def load_single_task(task_dict: Dict[str, Any]) -> Task:
    """
    Load a single task from a dictionary.

    Useful for testing or loading tasks from other sources.

    Args:
        task_dict: Dictionary with task fields

    Returns:
        Task object

    Raises:
        TaskLoadError: If task validation fails

    Example:
        >>> task_dict = {
        ...     "instance_id": "test-task",
        ...     "repo_url": "https://github.com/example/repo",
        ...     ...
        ... }
        >>> task = load_single_task(task_dict)
    """
    try:
        return Task(**task_dict)
    except ValidationError as e:
        raise TaskLoadError(f"Invalid task: {e}")


def load_task_by_id(tasks_file: Path, instance_id: str) -> Task:
    """
    Load a specific task by its instance_id.

    Args:
        tasks_file: Path to JSON file
        instance_id: ID of task to load

    Returns:
        Task object

    Raises:
        TaskLoadError: If file doesn't exist, task not found, or validation fails

    Example:
        >>> task = load_task_by_id(
        ...     Path("tasks/fastapi_tasks.json"),
        ...     "fastapi-first-steps"
        ... )
    """
    tasks = load_tasks_from_json(tasks_file)

    for task in tasks:
        if task.instance_id == instance_id:
            return task

    raise TaskLoadError(f"Task '{instance_id}' not found in {tasks_file}")


def validate_tasks_file(tasks_file: Path) -> Dict[str, Any]:
    """
    Validate a tasks JSON file and return summary.

    Useful for checking if a tasks file is valid before running experiments.

    Args:
        tasks_file: Path to JSON file

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "task_count": int,
            "task_ids": List[str],
            "errors": List[str]
        }

    Example:
        >>> result = validate_tasks_file(Path("tasks/fastapi_tasks.json"))
        >>> if result["valid"]:
        ...     print(f"All {result['task_count']} tasks are valid!")
        ... else:
        ...     print(f"Errors: {result['errors']}")
    """
    result = {
        "valid": False,
        "task_count": 0,
        "task_ids": [],
        "errors": []
    }

    try:
        tasks = load_tasks_from_json(tasks_file)
        result["valid"] = True
        result["task_count"] = len(tasks)
        result["task_ids"] = [task.instance_id for task in tasks]
    except TaskLoadError as e:
        result["errors"].append(str(e))

    return result
