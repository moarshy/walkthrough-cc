"""
Agent wrapper that runs inside Docker containers.

This script is executed inside the container and handles:
- Setting up the appropriate system prompt (vanilla or walkthrough)
- Running the Claude Code agent
- Logging messages and tool calls
- Exiting with proper status code
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path
from typing import Literal
from datetime import datetime

# Ensure example-codes is in path for reusing hooks
sys.path.insert(0, '/agent_wrapper/hooks')

try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        UserMessage,
        TextBlock,
    )
except ImportError as e:
    print(f"ERROR: Failed to import claude_agent_sdk: {e}", file=sys.stderr)
    print("Make sure Claude Code CLI is installed", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# PROMPTS
# ============================================================================

VANILLA_SYSTEM_PROMPT = """You are a software development assistant helping to set up a project based on
its documentation.

CONTEXT:
- Documentation: /workspace/docs
- Target doc: {target_doc}
- Library: {library_name} v{library_version}

YOUR TASK:
1. Read the target documentation file: /workspace/docs/{target_doc}
2. Follow the instructions step-by-step to set up the project
3. Execute all necessary commands (install dependencies, build, run tests, start server)
4. Verify the setup works correctly
5. Report success or failure with details

GUIDELINES:
- Be thorough: Don't skip steps from the documentation
- Be careful: Check for errors after each command
- Be adaptive: If something fails, try alternative approaches
- Be validating: Confirm the project actually works (server responds, tests pass, etc.)

AVAILABLE TOOLS:
- Read: Read files in the workspace
- Write: Create new files
- Edit: Modify existing files
- Bash: Run shell commands
- Glob: Find files by pattern
- Grep: Search file contents

SUCCESS CRITERIA:
- All installation steps completed
- Project builds successfully (if applicable)
- Server starts and responds (if applicable)
- Tests pass (if applicable)
"""

WALKTHROUGH_SYSTEM_PROMPT = """You are a software development assistant with access to a structured walkthrough
for setting up a project.

CONTEXT:
- Repository code: /workspace/repo
- Documentation: /workspace/docs
- Structured walkthrough: /workspace/walkthrough.json
- Library: {library_name} v{library_version}

The walkthrough provides step-by-step guidance with:
- contentForUser: User-facing instructions (markdown)
- contextForAgent: Background knowledge (what to expect, how things work)
- operationsForAgent: Specific commands and actions to execute
- introductionForAgent: Purpose and goals of each step

YOUR TASK:
1. Read and parse /workspace/walkthrough.json
2. Execute each step in order (by displayOrder)
3. For each step:
   - Read the contextForAgent to understand what you're doing
   - Read the operationsForAgent for specific commands
   - Execute the operations carefully
   - Verify success before moving to next step
4. Report overall success or failure with details

GUIDELINES:
- Follow the walkthrough structure: It's been validated and designed for agents
- Use operationsForAgent as your primary guide
- contextForAgent helps you understand WHY you're doing each step
- If a step fails, try to diagnose and fix before giving up
- Validate after each step (check files exist, servers respond, etc.)

AVAILABLE TOOLS:
- Read: Read files in the workspace
- Write: Create new files
- Edit: Modify existing files
- Bash: Run shell commands
- Glob: Find files by pattern
- Grep: Search file contents

SUCCESS CRITERIA:
- All steps completed successfully
- All validations pass
- Final project is functional (server running, tests passing, etc.)
"""


VANILLA_USER_PROMPT = """Please set up the project following the documentation in /workspace/docs/{target_doc}.

Read the documentation carefully and execute all steps to get the project running.
When you're done, verify that everything works and report the results.
"""

WALKTHROUGH_USER_PROMPT = """Please set up the project by following the structured walkthrough in /workspace/walkthrough.json.

The walkthrough contains step-by-step instructions designed for AI agents.
Execute each step carefully, validate your work, and report the results.
"""


# ============================================================================
# LOGGING
# ============================================================================

class SimpleLogger:
    """Simple logger for agent execution."""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.messages_file = self.log_dir / "messages.jsonl"
        self.tools_file = self.log_dir / "tools.jsonl"
        self.agent_log = self.log_dir / "agent.log"

    def log_message(self, role: str, content: str):
        """Log a message."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content[:500]  # Truncate long messages
        }
        with open(self.messages_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def log_tool(self, tool_name: str, args: dict, result: str = None):
        """Log a tool call."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "args": str(args)[:200],  # Truncate
            "result": str(result)[:200] if result else None
        }
        with open(self.tools_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def log_text(self, message: str):
        """Log to agent.log."""
        timestamp = datetime.now().isoformat()
        with open(self.agent_log, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")


# ============================================================================
# AGENT EXECUTION
# ============================================================================

async def run_agent(agent_type: Literal["vanilla", "walkthrough"]) -> int:
    """
    Run the agent.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    # Get environment variables
    task_id = os.getenv('TASK_ID', 'unknown')
    target_doc = os.getenv('TARGET_DOC', '')
    library_name = os.getenv('LIBRARY_NAME', '')
    library_version = os.getenv('LIBRARY_VERSION', '')

    print(f"🚀 Starting {agent_type} agent")
    print(f"   Task: {task_id}")
    print(f"   Library: {library_name} v{library_version}")
    print(f"   Target doc: {target_doc}")

    # Setup logging
    logger = SimpleLogger(Path('/workspace/logs'))
    logger.log_text(f"Agent started: {agent_type}")
    logger.log_text(f"Task: {task_id}")

    # Prepare prompts
    if agent_type == "vanilla":
        system_prompt = VANILLA_SYSTEM_PROMPT.format(
            target_doc=target_doc,
            library_name=library_name,
            library_version=library_version
        )
        user_prompt = VANILLA_USER_PROMPT.format(target_doc=target_doc)
    else:  # walkthrough
        system_prompt = WALKTHROUGH_SYSTEM_PROMPT.format(
            library_name=library_name,
            library_version=library_version
        )
        user_prompt = WALKTHROUGH_USER_PROMPT

    # Configure Claude SDK
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        cwd="/workspace/repo"
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            logger.log_text("Sending initial prompt")
            logger.log_message("user", user_prompt)

            # Send initial prompt
            await client.query(user_prompt)

            # Receive and process responses
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text = block.text
                            print(f"Assistant: {text[:100]}...")
                            logger.log_message("assistant", text)

                # TODO: Hook into tool calls for better logging
                # For now, we rely on the SDK's built-in logging

            logger.log_text("Agent completed successfully")
            print("✅ Agent completed successfully")
            return 0

    except KeyboardInterrupt:
        logger.log_text("Agent interrupted by user")
        print("⚠️  Agent interrupted")
        return 130

    except Exception as e:
        error_msg = f"Agent failed: {e}"
        logger.log_text(error_msg)
        print(f"❌ {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python agent_wrapper.py <vanilla|walkthrough>", file=sys.stderr)
        return 1

    agent_type = sys.argv[1]
    if agent_type not in ["vanilla", "walkthrough"]:
        print(f"Invalid agent type: {agent_type}", file=sys.stderr)
        return 1

    # Check API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    # Run agent
    exit_code = asyncio.run(run_agent(agent_type))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
