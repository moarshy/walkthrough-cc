"""
Vanilla Agent - Sets up projects using only raw documentation.

This agent reads documentation and executes setup steps without structured walkthroughs.
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


SYSTEM_PROMPT = """You are a software development assistant helping to set up projects based on their documentation.

YOUR ROLE:
You help developers set up projects by reading documentation and executing the necessary steps to get the project running.

CAPABILITIES:
- Read: Read files in the workspace
- Write: Create new files
- Edit: Modify existing files
- Bash: Run shell commands
- Glob: Find files by pattern
- Grep: Search file contents

APPROACH:
1. Read the provided documentation carefully
2. Follow the instructions step-by-step to set up the project
3. Execute all necessary commands (install dependencies, build, run tests, start server)
4. Verify the setup works correctly after each major step
5. Report success or failure with details

GUIDELINES:
- Be thorough: Don't skip steps from the documentation
- Be careful: Check for errors after each command
- Be adaptive: If something fails, try alternative approaches
- Be validating: Confirm the project actually works (server responds, tests pass, etc.)

SUCCESS CRITERIA:
- All installation steps completed
- Project builds successfully (if applicable)
- Server starts and responds (if applicable)
- Tests pass (if applicable)
"""

USER_PROMPT = """Please set up the {library_name} v{library_version} project.

CONTEXT:
- Documentation location: /workspace/docs
- Target documentation file: /workspace/docs/{target_doc}
- Working directory: /workspace/repo

TASK:
Read the documentation at /workspace/docs/{target_doc} and follow all the setup steps to get the project running.
Execute all necessary commands, verify your work, and report the results.
"""


async def run_vanilla_agent(logger: AgentLogger) -> Dict[str, Any]:
    """
    Run the vanilla agent (documentation-only approach).

    Args:
        logger: AgentLogger instance for logging

    Returns:
        Token usage dictionary with keys: input_tokens, output_tokens,
        cache_creation_input_tokens, cache_read_input_tokens, total_tokens
    """
    # Get environment variables
    task_id = os.getenv('TASK_ID', 'unknown')
    target_doc = os.getenv('TARGET_DOC', '')
    library_name = os.getenv('LIBRARY_NAME', '')
    library_version = os.getenv('LIBRARY_VERSION', '')

    print(f"🚀 Starting vanilla agent")
    print(f"   Task: {task_id}")
    print(f"   Library: {library_name} v{library_version}")
    print(f"   Target doc: {target_doc}")

    logger.log_message("Agent started: vanilla")
    logger.log_message(f"Task: {task_id}")

    # Prepare prompts
    system_prompt = SYSTEM_PROMPT
    user_prompt = USER_PROMPT.format(
        library_name=library_name,
        library_version=library_version,
        target_doc=target_doc
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
            print("✅ Vanilla agent completed successfully")

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
        print("⚠️  Vanilla agent interrupted")
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "total_tokens": 0,
            "error": "interrupted"
        }

    except Exception as e:
        error_msg = f"Vanilla agent failed: {e}"
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
