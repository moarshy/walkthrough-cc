#!/usr/bin/env python3
"""
run_agent_in_container.py
==========================

Agent execution script that runs INSIDE Docker containers.

This script is executed within the Docker container and runs the Claude Code agent
for either vanilla (docs-only) or walkthrough-powered setup.

Usage:
    python3 /app/run_agent_in_container.py <agent_type> <task_json> <api_key>

Where:
    agent_type: 'vanilla' or 'walkthrough'
    task_json: JSON string with task details
    api_key: Anthropic API key

Output:
    - Writes logs to /logs/
    - Writes metrics to /logs/metrics.json
    - Performs all setup operations in container
"""

import json
import sys
import os
import asyncio
from pathlib import Path

# Add vanilla_cc_runner to path
sys.path.insert(0, '/app')

try:
    from vanilla_cc_runner.agent import run_agent
    from vanilla_cc_runner.agent_hooks import AgentLogger
except ImportError as e:
    print(f"Error importing vanilla_cc_runner: {e}", file=sys.stderr)
    print("Make sure vanilla_cc_runner package is copied to /app/", file=sys.stderr)
    sys.exit(1)


async def main():
    """Main entry point for in-container agent execution."""

    if len(sys.argv) < 4:
        print("Usage: run_agent_in_container.py <agent_type> '<task_json>' '<api_key>'", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    agent_type = sys.argv[1]
    task_json = sys.argv[2]
    api_key = sys.argv[3]

    if agent_type not in ["vanilla", "walkthrough"]:
        print(f"Invalid agent type: {agent_type}. Must be 'vanilla' or 'walkthrough'", file=sys.stderr)
        sys.exit(1)

    try:
        task = json.loads(task_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing task JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Set API key and task environment variables
    os.environ['ANTHROPIC_API_KEY'] = api_key
    os.environ['TASK_ID'] = task.get('id', 'unknown')
    os.environ['TARGET_DOC'] = task.get('target_doc', '')
    os.environ['LIBRARY_NAME'] = task.get('library_name', '')
    os.environ['LIBRARY_VERSION'] = task.get('library_version', '')

    # Setup logging - write to /logs/ (mounted from host)
    log_dir = Path("/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = AgentLogger(
        log_file=log_dir / "agent.log",
        tools_log_file=log_dir / "tools.jsonl"
    )

    logger.log_message(f"Starting in-container agent execution")
    logger.log_message(f"Agent type: {agent_type}")
    logger.log_message(f"Task ID: {task.get('id')}")
    logger.log_message(f"Library: {task.get('library_name')} v{task.get('library_version')}")
    logger.log_message(f"Working directory: {os.getcwd()}")

    # Run agent
    try:
        exit_code = await run_agent(agent_type)

        # Write metrics
        metrics = {
            "agent_type": agent_type,
            "task_id": task.get('id'),
            "exit_code": exit_code,
            **logger.get_stats()
        }

        metrics_file = log_dir / "metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.log_message(f"Agent execution completed with exit code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.log_message(f"Agent execution failed: {e}", level="ERROR")

        # Write error metrics
        metrics = {
            "agent_type": agent_type,
            "task_id": task.get('id'),
            "error": str(e),
            **logger.get_stats()
        }

        metrics_file = log_dir / "metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
