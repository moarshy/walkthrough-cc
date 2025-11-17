#!/usr/bin/env python3
"""
Wrapper script to run agent inside Docker container.

Called by harness_docker.py with: agent_type, task_json, api_key
Sets up environment, runs the appropriate agent, then runs validation in the same container.

This ensures both agent execution and validation happen in the same environment.
"""

import sys
import os
import json
import asyncio
import subprocess
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 run_agent_in_container.py <agent_type> <task_json> <api_key>", file=sys.stderr)
        sys.exit(1)

    agent_type = sys.argv[1]
    task_json = sys.argv[2]  # Task JSON containing success_command for validation
    api_key = sys.argv[3]

    if agent_type not in ["vanilla", "walkthrough"]:
        print(f"Invalid agent type: {agent_type}", file=sys.stderr)
        sys.exit(1)

    # Set API key in environment
    os.environ['ANTHROPIC_API_KEY'] = api_key

    # Add app directory to Python path
    sys.path.insert(0, '/app')

    # Import agent components
    from cc_experiment_runner.hooks import AgentLogger
    from cc_experiment_runner.agents import run_vanilla_agent, run_walkthrough_agent

    # Setup logging paths (mounted at /logs in container)
    log_dir = Path("/logs")
    log_file = log_dir / f"{agent_type}_agent.log"
    tools_log_file = log_dir / "tools.jsonl"
    messages_log_file = log_dir / f"{agent_type}_messages.jsonl"

    # Create logger
    logger = AgentLogger(
        log_file=log_file,
        tools_log_file=tools_log_file,
        messages_log_file=messages_log_file
    )

    # Parse task JSON to get success_command and other metadata
    task_data = json.loads(task_json)
    success_command = task_data.get('success_command', '')

    # Add library name/version if not present (for compatibility with Task schema)
    if 'library_name' not in task_data:
        # Extract from repo_url if available (e.g., github.com/owner/library)
        repo_url = task_data.get('repo_url', '')
        if repo_url:
            task_data['library_name'] = repo_url.rstrip('/').split('/')[-1]
        else:
            task_data['library_name'] = 'Library'
    if 'library_version' not in task_data:
        task_data['library_version'] = '1.0'
    if 'base_image' not in task_data:
        task_data['base_image'] = 'ubuntu:22.04'

    # Run appropriate agent with task_data
    print(f"🤖 Running {agent_type} agent...")
    if agent_type == "vanilla":
        result = asyncio.run(run_vanilla_agent(logger, task_data))
    else:  # walkthrough
        result = asyncio.run(run_walkthrough_agent(logger, task_data))

    # Determine if agent completed successfully
    agent_completed = not result.get('error')
    agent_exit_code = 0 if agent_completed else 1

    print(f"{'✅' if agent_completed else '❌'} Agent {'completed' if agent_completed else 'failed'}")

    # ========== RUN VALIDATION IN SAME CONTAINER ==========
    # This ensures validation runs in the same environment as the agent
    validation_passed = False
    validation_output = ""
    validation_exit_code = -1

    if agent_completed and success_command:
        print(f"🔍 Running validation in same container...")
        print(f"   Command: {success_command}")

        try:
            # Cleanup: Kill all background jobs and their child processes
            # This ensures validation runs in a clean state without port/resource conflicts
            # Generic approach: Works for uvicorn, node, rails, django, etc.
            print(f"   Cleaning up background processes...")

            cleanup_command = """#!/bin/bash
# Kill all background processes started during agent execution
# Generic approach: Works for uvicorn, node, rails, django, flask, etc.

# Kill any processes listening on common development ports
# This catches web servers regardless of how they were started
# Note: xargs -r is not portable (GNU vs BSD), so we use explicit check
for port in 8000 8080 3000 3001 4200 5000 8888; do
    pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
done

# Also try to kill common server processes by name
pkill -9 -f "uvicorn|gunicorn|flask|fastapi|django" 2>/dev/null || true
pkill -9 -f "node.*server|npm.*start" 2>/dev/null || true
pkill -9 -f "rails.*server" 2>/dev/null || true

# Wait for ports to be released
sleep 2
"""
            subprocess.run(
                cleanup_command,
                shell=True,
                cwd="/testbed",
                capture_output=True,
                timeout=10
            )

            # Run validation command in /testbed with process group isolation
            # start_new_session=True creates a new process group, preventing
            # background jobs from persisting beyond the validation command
            validation_result = subprocess.run(
                success_command,
                shell=True,
                cwd="/testbed",
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                start_new_session=True  # Isolate process group for clean cleanup
            )

            validation_output = validation_result.stdout + validation_result.stderr
            validation_exit_code = validation_result.returncode
            validation_passed = "Setup successful" in validation_output

            print(f"{'✅' if validation_passed else '❌'} Validation {'passed' if validation_passed else 'failed'}")

        except subprocess.TimeoutExpired:
            validation_output = "Validation timed out after 300s"
            validation_exit_code = -1
            validation_passed = False
            print(f"❌ Validation timed out")

        except Exception as e:
            validation_output = f"Validation error: {e}"
            validation_exit_code = -1
            validation_passed = False
            print(f"❌ Validation error: {e}")
    else:
        if not agent_completed:
            validation_output = "Validation skipped - agent did not complete"
            print(f"⏭️  Validation skipped (agent failed)")
        else:
            validation_output = "Validation skipped - no success_command provided"
            print(f"⏭️  Validation skipped (no command)")

    # Write validation log
    validation_log = log_dir / f"{agent_type}_validation.log"
    with open(validation_log, 'w') as f:
        f.write("=== Validation Log ===\n")
        f.write(f"Task ID: {task_data.get('instance_id', 'unknown')}\n")
        f.write(f"Command: {success_command}\n")
        f.write(f"Workspace: /testbed\n")
        f.write(f"Exit Code: {validation_exit_code}\n")
        f.write(f"Success: {validation_passed}\n")
        f.write(f"\n=== Output ===\n")
        f.write(validation_output)
        f.write(f"\n=== End Log ===\n")

    # Save metrics
    metrics_file = log_dir / "metrics.json"
    with open(metrics_file, 'w') as f:
        stats = logger.get_stats()
        stats['agent_type'] = agent_type
        stats['token_usage'] = result
        stats['agent_completed'] = agent_completed
        stats['validation_passed'] = validation_passed
        stats['validation_exit_code'] = validation_exit_code
        stats['overall_success'] = agent_completed and validation_passed
        json.dump(stats, f, indent=2)

    # Exit with success only if BOTH agent and validation passed
    overall_success = agent_completed and validation_passed
    exit_code = 0 if overall_success else 1

    print(f"\n{'🎉' if overall_success else '❌'} Overall: {'SUCCESS' if overall_success else 'FAILED'}")
    print(f"   Agent: {'✅' if agent_completed else '❌'}")
    print(f"   Validation: {'✅' if validation_passed else '❌'}")

    sys.exit(exit_code)
