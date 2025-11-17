"""
Walkthrough Agent - Sets up projects using structured walkthroughs.

This agent follows AI-generated step-by-step walkthroughs with detailed context and operations.
"""

import sys
import os
from typing import Dict, Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

from ..hooks import AgentLogger, create_logging_hooks


SYSTEM_PROMPT = """You are a software development assistant specialized in following structured walkthroughs to set up projects.

YOUR ROLE:
You execute structured walkthroughs that provide detailed, step-by-step guidance for setting up software projects.

WALKTHROUGH STRUCTURE:
Each walkthrough contains steps with these fields:
- contentForUser: User-facing instructions (markdown)
- contextForAgent: Background knowledge (what to expect, how things work)
- operationsForAgent: Specific commands and actions to execute
- introductionForAgent: Purpose and goals of each step

CAPABILITIES:
- Read: Read files in the workspace
- Write: Create new files
- Edit: Modify existing files
- Bash: Run shell commands
- Glob: Find files by pattern
- Grep: Search file contents

APPROACH:
1. Read and parse the walkthrough JSON file
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

WORKSPACE MANAGEMENT:
⚠️ IMPORTANT: You are working in a cloned repository that contains the library's SOURCE CODE and documentation.
To avoid conflicts with the library's own files, you MUST:
1. Create a NEW subdirectory called 'project/' for your work
2. Do ALL your work inside the 'project/' directory
3. NEVER create files in the repository root (it contains the library source)

Example structure:
/workspace/repo/
├── [library source code files]  ← DO NOT MODIFY
├── docs/                         ← READ for learning
└── project/                      ← YOUR WORK GOES HERE
    ├── main.py
    ├── requirements.txt
    └── [your other files]

SUCCESS CRITERIA:
- All steps completed successfully
- All validations pass
- Final project is functional (server running, tests passing, etc.)
"""

USER_PROMPT = """Please set up the {library_name} v{library_version} project using the structured walkthrough.

CONTEXT:
- Walkthrough file: /workspace/walkthrough.json
- Documentation location: /workspace/docs
- Repository root: /workspace/repo (contains library source code)
- Your workspace: /workspace/repo/project (create this directory)

TASK:
1. Create a 'project/' directory in /workspace/repo for your work
2. Read the walkthrough at /workspace/walkthrough.json
3. Execute each step in order inside the 'project/' directory
4. Validate your work after each step and report final results

IMPORTANT: Work exclusively in /workspace/repo/project/ to avoid conflicts with the library source code.
"""


async def run_walkthrough_agent(logger: AgentLogger) -> Dict[str, Any]:
    """
    Run the walkthrough agent (structured walkthrough approach).

    Args:
        logger: AgentLogger instance for logging

    Returns:
        Token usage dictionary with keys: input_tokens, output_tokens,
        cache_creation_input_tokens, cache_read_input_tokens, total_tokens
    """
    # Get environment variables
    task_id = os.getenv('TASK_ID', 'unknown')
    library_name = os.getenv('LIBRARY_NAME', '')
    library_version = os.getenv('LIBRARY_VERSION', '')

    print(f"🚀 Starting walkthrough agent")
    print(f"   Task: {task_id}")
    print(f"   Library: {library_name} v{library_version}")
    print(f"   Walkthrough: /workspace/walkthrough.json")

    logger.log_message("Agent started: walkthrough")
    logger.log_message(f"Task: {task_id}")

    # Prepare prompts
    system_prompt = SYSTEM_PROMPT
    user_prompt = USER_PROMPT.format(
        library_name=library_name,
        library_version=library_version
    )

    # Create logging hooks
    hooks = create_logging_hooks(logger)

    # Configure Claude SDK with hooks
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        cwd="/workspace/repo",
        hooks=hooks
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            logger.log_message("Sending initial prompt")

            # Log user message
            logger.log_conversation_message("user", user_prompt)

            # Send initial prompt
            response = await client.query(user_prompt)

            # Receive and process responses
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    # Log assistant message
                    message_content = []
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text = block.text
                            print(f"Assistant: {text[:100]}...")
                            message_content.append({"type": "text", "text": text})
                        else:
                            # Handle tool use blocks
                            message_content.append({"type": "ToolUseBlock", "data": str(block)})

                    logger.log_conversation_message("assistant", message_content)

                elif isinstance(message, ResultMessage):
                    # Extract token usage
                    if message.usage:
                        usage = message.usage
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)
                        cache_creation = usage.get("cache_creation_input_tokens", 0)
                        cache_read = usage.get("cache_read_input_tokens", 0)

                        logger.track_tokens(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cache_creation_input_tokens=cache_creation,
                            cache_read_input_tokens=cache_read
                        )

                        logger.log_message(
                            f"Token usage: input={input_tokens}, output={output_tokens}, "
                            f"cache_creation={cache_creation}, cache_read={cache_read}"
                        )

            logger.log_message("Agent completed successfully")
            print("✅ Walkthrough agent completed successfully")

            # Return token usage stats
            stats = logger.get_stats()
            return {
                "input_tokens": stats.get("input_tokens", 0),
                "output_tokens": stats.get("output_tokens", 0),
                "cache_creation_input_tokens": stats.get("cache_creation_input_tokens", 0),
                "cache_read_input_tokens": stats.get("cache_read_input_tokens", 0),
                "total_tokens": stats.get("total_tokens", 0)
            }

    except KeyboardInterrupt:
        logger.log_message("Agent interrupted by user", level="WARNING")
        print("⚠️  Walkthrough agent interrupted")
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "total_tokens": 0,
            "error": "interrupted"
        }

    except Exception as e:
        error_msg = f"Walkthrough agent failed: {e}"
        logger.log_message(error_msg, level="ERROR")
        print(f"❌ {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "total_tokens": 0,
            "error": str(e)
        }
