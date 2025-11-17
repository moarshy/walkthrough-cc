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

    # Parse task JSON to get success_command
    task_data = json.loads(task_json)
    success_command = task_data.get('success_command', '')

    # Run appropriate agent
    print(f"🤖 Running {agent_type} agent...")
    if agent_type == "vanilla":
        result = asyncio.run(run_vanilla_agent(logger))
    else:  # walkthrough
        result = asyncio.run(run_walkthrough_agent(logger))

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

            cleanup_command = """
# Kill all background jobs started during agent execution
# This finds processes that are detached (no controlling terminal) or running as background jobs
# Works for: web servers (uvicorn, gunicorn, node, rails), databases, daemons, etc.

# Get list of background bash shells (from run_in_background tools)
BG_SHELLS=$(jobs -p 2>/dev/null || true)

# Kill background shells and their entire process trees
for pid in $BG_SHELLS; do
    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        # Kill entire process tree (parent + all children)
        pkill -9 -P $pid 2>/dev/null || true
        kill -9 $pid 2>/dev/null || true
    fi
done

# Also kill any processes listening on network ports (likely servers)
# This catches servers that might not be direct children of bash
lsof -ti:8000-8999 2>/dev/null | xargs -r kill -9 2>/dev/null || true

sleep 1
"""
            subprocess.run(
                cleanup_command,
                shell=True,
                cwd="/workspace/repo",
                capture_output=True,
                timeout=10
            )

            # Run validation command in /workspace/repo
            validation_result = subprocess.run(
                success_command,
                shell=True,
                cwd="/workspace/repo",
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
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
        f.write(f"Workspace: /workspace/repo\n")
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
