#!/usr/bin/env python3
"""
Wrapper script to run agent inside Docker container.

Called by harness_docker.py with: agent_type, task_json, api_key
Sets up environment and delegates to agent.py main().
"""

import sys
import os

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 run_agent_in_container.py <agent_type> <task_json> <api_key>", file=sys.stderr)
        sys.exit(1)

    agent_type = sys.argv[1]
    task_json = sys.argv[2]  # Currently unused - task info comes from mounted files
    api_key = sys.argv[3]

    # Set API key in environment
    os.environ['ANTHROPIC_API_KEY'] = api_key

    # Import and run agent
    # We need to add the app directory to Python path
    sys.path.insert(0, '/app')

    from cc_experiment_runner.agent import main

    # Override sys.argv to pass just agent_type to agent.main()
    sys.argv = ['agent.py', agent_type]

    sys.exit(main())
