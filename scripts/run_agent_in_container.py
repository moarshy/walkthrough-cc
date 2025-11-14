#!/usr/bin/env python3
"""
Wrapper script to run agent inside Docker container.

Called by harness_docker.py with: agent_type, task_json, api_key
Sets up environment and runs the appropriate agent (vanilla or walkthrough).
"""

import sys
import os
import json
import asyncio
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 run_agent_in_container.py <agent_type> <task_json> <api_key>", file=sys.stderr)
        sys.exit(1)

    agent_type = sys.argv[1]
    task_json = sys.argv[2]  # Currently unused - task info comes from mounted files
    api_key = sys.argv[3]

    if agent_type not in ["vanilla", "walkthrough"]:
        print(f"Invalid agent type: {agent_type}", file=sys.stderr)
        sys.exit(1)

    # Set API key in environment
    os.environ['ANTHROPIC_API_KEY'] = api_key

    # Add app directory to Python path
    sys.path.insert(0, '/app')

    # Import agent components
    from cc_experiment_runner.agent_hooks import AgentLogger
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

    # Run appropriate agent
    if agent_type == "vanilla":
        result = asyncio.run(run_vanilla_agent(logger))
    else:  # walkthrough
        result = asyncio.run(run_walkthrough_agent(logger))

    # Save metrics
    metrics_file = log_dir / "metrics.json"
    with open(metrics_file, 'w') as f:
        stats = logger.get_stats()
        stats['agent_type'] = agent_type
        stats['token_usage'] = result
        json.dump(stats, f, indent=2)

    # Exit with success if no error, otherwise fail
    exit_code = 1 if result.get('error') else 0
    sys.exit(exit_code)
