"""
Output path validation hook for walkthrough generator.

This hook ensures the walkthrough generator agent writes files to the
correct location with proper naming conventions.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from claude_agent_sdk import HookContext, HookMatcher


def write_hook_log(hook_name: str, status: str, details: str, log_dir: Path = None):
    """
    Write hook execution log to a text file.

    Args:
        hook_name: Name of the hook (e.g., "validate_output_path")
        status: "SUCCESS" or "FAILED" or "DENIED"
        details: Additional details about the execution
        log_dir: Directory to write logs (defaults to WALKTHROUGH_HOOKS_LOG_DIR env var)
    """
    if log_dir is None:
        # First, check for environment variable set by walkthrough generator
        env_log_dir = os.environ.get('WALKTHROUGH_HOOKS_LOG_DIR')

        if env_log_dir:
            log_dir = Path(env_log_dir)
        else:
            # Fallback: use current working directory
            cwd = Path.cwd()
            if (cwd / "walkthroughs").exists():
                log_dir = cwd / "walkthroughs" / "hooks_logs"
            else:
                log_dir = cwd / "walkthroughs" / "hooks_logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()
    log_file = log_dir / f"{hook_name}.txt"

    with open(log_file, 'a') as f:
        f.write(f"{'='*70}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Hook: {hook_name}\n")
        f.write(f"Status: {status}\n")
        f.write(f"Details:\n{details}\n")
        f.write(f"{'='*70}\n\n")


async def validate_output_path_hook(
    input_data: Dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> Dict[str, Any]:
    """
    Pre-tool hook to validate Write tool is using correct output path.

    Ensures the agent writes to the correct location (walkthroughs/{filename}.json)
    and provides feedback if the path is wrong.

    Args:
        input_data: Tool call data including tool_name and tool_input
        tool_use_id: Unique ID for this tool use
        context: Hook execution context

    Returns:
        Hook output with permission decision or empty dict
    """
    if input_data.get('tool_name') == 'Write':
        file_path = input_data.get('tool_input', {}).get('file_path', '')

        # Expected pattern: walkthroughs/{task-id}.json
        if not file_path.startswith('walkthroughs/') or not file_path.endswith('.json'):
            reason = (
                f'❌ Invalid file path: "{file_path}"\n\n'
                f'You must write to: walkthroughs/{{task-id}}.json\n'
                f'Example: walkthroughs/fastapi-first-steps.json\n\n'
                f'Do NOT use absolute paths. Use the relative path from the working directory.'
            )

            # Write hook log
            write_hook_log(
                hook_name="validate_output_path",
                status="DENIED",
                details=f"Agent: walkthrough_generator\nFile path: {file_path}\nReason: Path validation failed"
            )

            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny',
                    'permissionDecisionReason': reason
                }
            }
        else:
            # Path is valid
            write_hook_log(
                hook_name="validate_output_path",
                status="SUCCESS",
                details=f"Agent: walkthrough_generator\nFile path: {file_path}\nValidation: Path format is correct"
            )

    return {}


def create_output_path_validation_hooks() -> Dict[str, list]:
    """
    Create hook configuration for output path validation.

    Returns:
        Dictionary mapping hook events to HookMatcher lists
    """
    return {
        'PreToolUse': [
            HookMatcher(matcher='Write', hooks=[validate_output_path_hook])
        ]
    }
