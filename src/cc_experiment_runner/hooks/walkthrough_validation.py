"""
Walkthrough validation hooks for guiding JSON generation.

These hooks ensure the walkthrough generator agent creates properly
structured JSON files in the correct location.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from claude_agent_sdk import HookContext, HookMatcher
from pydantic import ValidationError

from ..schemas import Walkthrough


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
        import os
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


async def validate_walkthrough_json_hook(
    input_data: Dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> Dict[str, Any]:
    """
    Post-tool hook to validate walkthrough JSON structure.

    Checks that the generated JSON has the required structure:
    - walkthrough object with title
    - steps array with required fields for each step

    Args:
        input_data: Tool call data including content written
        tool_use_id: Unique ID for this tool use
        context: Hook execution context

    Returns:
        Hook output with feedback message or empty dict
    """
    if input_data.get('tool_name') == 'Write':
        content = input_data.get('tool_input', {}).get('content', '')
        file_path = input_data.get('tool_input', {}).get('file_path', '')

        try:
            data = json.loads(content)

            # Validate using Pydantic schema
            try:
                walkthrough = Walkthrough(**data)

                # Validation passed!
                feedback = f'✅ Valid walkthrough JSON with {len(walkthrough.steps)} steps'

                # Write success log
                write_hook_log(
                    hook_name="validate_walkthrough_json",
                    status="SUCCESS",
                    details=(
                        f"Agent: walkthrough_generator\n"
                        f"File: {file_path}\n"
                        f"Title: {walkthrough.walkthrough.title}\n"
                        f"Steps: {len(walkthrough.steps)}\n"
                        f"Validation: Passed Pydantic schema validation"
                    )
                )

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PostToolUse',
                        'feedbackMessage': feedback
                    }
                }

            except ValidationError as e:
                # Pydantic validation failed
                error_details = []
                for error in e.errors():
                    field = " -> ".join(str(x) for x in error['loc'])
                    msg = error['msg']
                    error_details.append(f"  • {field}: {msg}")

                feedback = (
                    f'❌ Walkthrough schema validation failed:\n\n'
                    f'{chr(10).join(error_details)}\n\n'
                    f'Please fix the validation errors and ensure all required fields are present.'
                )

                # Write failure log
                write_hook_log(
                    hook_name="validate_walkthrough_json",
                    status="FAILED",
                    details=(
                        f"Agent: walkthrough_generator\n"
                        f"File: {file_path}\n"
                        f"Validation errors:\n{chr(10).join(error_details)}"
                    )
                )

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PostToolUse',
                        'feedbackMessage': feedback
                    }
                }

        except json.JSONDecodeError as e:
            feedback = (
                f'❌ Invalid JSON syntax: {str(e)}\n\n'
                f'Please fix the JSON syntax errors.'
            )

            # Write failure log
            write_hook_log(
                hook_name="validate_walkthrough_json",
                status="FAILED",
                details=(
                    f"Agent: walkthrough_generator\n"
                    f"File: {file_path}\n"
                    f"JSON syntax error: {str(e)}"
                )
            )

            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PostToolUse',
                    'feedbackMessage': feedback
                }
            }

    return {}


def create_walkthrough_generation_hooks() -> Dict[str, list]:
    """
    Create hook configuration for walkthrough generation.

    Returns:
        Dictionary mapping hook events to HookMatcher lists
    """
    return {
        'PreToolUse': [
            HookMatcher(matcher='Write', hooks=[validate_output_path_hook])
        ],
        'PostToolUse': [
            HookMatcher(matcher='Write', hooks=[validate_walkthrough_json_hook])
        ]
    }
