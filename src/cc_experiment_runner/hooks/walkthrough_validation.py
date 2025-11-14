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
        log_dir: Directory to write logs (defaults to current working directory/hooks_logs)
    """
    if log_dir is None:
        log_dir = Path.cwd() / "walkthroughs" / "hooks_logs"

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

        try:
            data = json.loads(content)

            # Validate required top-level fields
            if 'walkthrough' not in data:
                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PostToolUse',
                        'feedbackMessage': (
                            '❌ Missing "walkthrough" object at root level.\n\n'
                            'Required structure:\n'
                            '{\n'
                            '  "walkthrough": { "title": "...", ... },\n'
                            '  "steps": [...]\n'
                            '}'
                        )
                    }
                }

            if 'steps' not in data or not isinstance(data['steps'], list):
                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PostToolUse',
                        'feedbackMessage': (
                            '❌ Missing or invalid "steps" array.\n\n'
                            'Required: "steps" must be an array of step objects'
                        )
                    }
                }

            # Validate step structure
            required_step_fields = [
                'contentForUser',
                'contextForAgent',
                'operationsForAgent',
                'introductionForAgent'
            ]

            for i, step in enumerate(data['steps']):
                missing_fields = [f for f in required_step_fields if f not in step]
                if missing_fields:
                    return {
                        'hookSpecificOutput': {
                            'hookEventName': 'PostToolUse',
                            'feedbackMessage': (
                                f'❌ Step {i+1} missing required fields: {", ".join(missing_fields)}\n\n'
                                f'Each step must have:\n'
                                f'- contentForUser (markdown for users)\n'
                                f'- contextForAgent (background knowledge)\n'
                                f'- operationsForAgent (executable commands)\n'
                                f'- introductionForAgent (step purpose)'
                            )
                        }
                    }

            # Validation passed
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PostToolUse',
                    'feedbackMessage': f'✅ Valid walkthrough JSON with {len(data["steps"])} steps'
                }
            }

        except json.JSONDecodeError as e:
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PostToolUse',
                    'feedbackMessage': (
                        f'❌ Invalid JSON syntax: {str(e)}\n\n'
                        f'Please fix the JSON syntax errors.'
                    )
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
