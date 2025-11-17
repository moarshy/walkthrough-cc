"""
Vanilla Agent - Sets up projects using only raw documentation.

This agent reads documentation and executes setup steps without structured walkthroughs.
"""

import sys
import os
from typing import Dict, Any, Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

from ..hooks import AgentLogger, create_logging_hooks


SYSTEM_PROMPT = """You are in a benchmark that evaluates your ability to interpret documentation and complete setup tasks in a minimal environment.

**Environment Details:**
You are operating inside a fresh {base_image} container with minimal preinstalled tools.

**Key Constraints:**
- Install all required dependencies globally using system package managers (apt, pip, npm, etc.)
- Do NOT create or use virtual environments (no venv, conda, or containerization)
- Your setup should be non-interactive and suitable for headless CI environments
- You have root privileges - no need to use sudo
- Assume minimal preinstalled tools - install everything explicitly

**Your Task:**
{problem_statement}

**Available Tools:**
- Read: Read files and documentation
- Write: Create new files
- Edit: Modify existing files
- Bash: Execute shell commands
- Glob: Find files by pattern
- Grep: Search file contents

**Approach:**
1. Read the provided documentation carefully
2. Install all required system dependencies and tools
3. Follow setup instructions step-by-step
4. Verify each major step works before proceeding
5. Test that the final setup meets the success criteria

**Critical Guidelines:**
- **Persistent Installation**: Everything must persist across shell sessions
  - Use system package managers (apt-get, pip, npm, etc.)
  - Install globally, NOT in virtual environments or --user mode
  - Avoid temporary installations

- **Complete Setup**: Install ALL required tools and dependencies
  - Runtime dependencies (Python, Node, databases, etc.)
  - Build tools (compilers, headers, build-essential)
  - Test frameworks and validation tools
  - Don't skip anything needed for validation!

- **Verify Your Work**: Test installations before finishing
  - Run commands in fresh contexts to verify persistence
  - Ensure the validation command would succeed

- **No Assumptions**: This is a minimal environment
  - Don't assume git, curl, or build-essential are installed
  - Install everything explicitly

**Success Criteria:**
Your work will be validated by running this command in a fresh shell:
```
{success_command}
```

Ensure this command will succeed after your setup is complete.
"""

USER_PROMPT = """Complete the setup task for {library_name} v{library_version}.

**Documentation Location:**
/workspace/docs/{target_doc}

**Working Directory:**
/testbed (create all project files here)

**Instructions:**
1. Read the documentation at /workspace/docs/{target_doc}
2. Follow all setup steps described in the documentation
3. Install all dependencies globally (system-wide, no virtual environments)
4. Create necessary files in /testbed
5. Verify your setup works as expected

Remember: Install everything globally and work directly in /testbed.
"""


async def run_vanilla_agent(
    logger: AgentLogger,
    task_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run the vanilla agent (documentation-only approach).

    Args:
        logger: AgentLogger instance for logging
        task_data: Optional task metadata dictionary

    Returns:
        Token usage dictionary with keys: input_tokens, output_tokens,
        cache_creation_input_tokens, cache_read_input_tokens, total_tokens
    """
    # Get task information (from task_data if provided, else environment variables)
    if task_data:
        task_id = task_data.get('instance_id', 'unknown')
        target_doc = task_data.get('target_doc', '')
        library_name = task_data.get('library_name', 'Library')
        library_version = task_data.get('library_version', '1.0')
        base_image = task_data.get('base_image', 'ubuntu:22.04')
        problem_statement = task_data.get('problem_statement', '')
        success_command = task_data.get('success_command', '')
    else:
        # Fallback to environment variables for backward compatibility
        task_id = os.getenv('TASK_ID', 'unknown')
        target_doc = os.getenv('TARGET_DOC', '')
        library_name = os.getenv('LIBRARY_NAME', 'Library')
        library_version = os.getenv('LIBRARY_VERSION', '1.0')
        base_image = os.getenv('BASE_IMAGE', 'ubuntu:22.04')
        problem_statement = os.getenv('PROBLEM_STATEMENT', '')
        success_command = os.getenv('SUCCESS_COMMAND', '')

    print(f"🚀 Starting vanilla agent")
    print(f"   Task: {task_id}")
    print(f"   Library: {library_name} v{library_version}")
    print(f"   Target doc: {target_doc}")

    logger.log_message("Agent started: vanilla")
    logger.log_message(f"Task: {task_id}")

    # Prepare prompts with all template variables
    system_prompt = SYSTEM_PROMPT.format(
        base_image=base_image,
        problem_statement=problem_statement,
        success_command=success_command
    )
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
        cwd="/testbed",  # Matches SetupBench convention
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
