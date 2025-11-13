"""
Logging hooks for StackBench agents.

Provides PreToolUse and PostToolUse hooks that log all tool calls and results.
Also provides a message logger for capturing full conversation transcripts.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class ToolLogEntry:
    """Log entry for a tool call and its result."""
    timestamp: str
    event_type: str  # "pre_tool" or "post_tool"
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    tool_use_id: Optional[str] = None
    error: Optional[str] = None


class AgentLogger:
    """Logger for agent execution, including messages and tool calls."""

    def __init__(self, log_file: Path, tools_log_file: Path):
        """
        Initialize the agent logger.

        Args:
            log_file: Path to the agent message log file
            tools_log_file: Path to the tools JSONL log file
        """
        self.log_file = Path(log_file)
        self.tools_log_file = Path(tools_log_file)

        # Ensure parent directories exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.tools_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize log files
        self.log_file.touch(exist_ok=True)
        self.tools_log_file.touch(exist_ok=True)

        # Track statistics
        self.stats = {
            "tool_calls": 0,
            "messages_logged": 0,
            "errors": 0
        }

    def log_message(self, message: str, level: str = "INFO"):
        """
        Log a message to the agent log file.

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR, etc.)
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        with open(self.log_file, 'a') as f:
            f.write(log_entry)

        self.stats["messages_logged"] += 1

    def log_tool_call(self, entry: ToolLogEntry):
        """
        Log a tool call to the JSONL tools log file.

        Args:
            entry: ToolLogEntry with tool call information
        """
        with open(self.tools_log_file, 'a') as f:
            f.write(json.dumps(asdict(entry)) + '\n')

        self.stats["tool_calls"] += 1

        if entry.error:
            self.stats["errors"] += 1

    def get_stats(self) -> Dict[str, int]:
        """Get logging statistics."""
        return self.stats.copy()


def create_logging_hooks(logger: AgentLogger):
    """
    Create PreToolUse and PostToolUse hooks for logging.

    Args:
        logger: AgentLogger instance to use for logging

    Returns:
        Dictionary with hook configurations
    """

    async def pre_tool_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Hook that runs before tool execution."""
        try:
            tool_name = input_data.get('tool_name', 'unknown')
            tool_input = input_data.get('tool_input', {})

            # Create detailed log message with key parameters
            details = []
            if tool_name == "Read":
                file_path = tool_input.get('file_path', 'unknown')
                details.append(f"file={file_path}")
                if 'offset' in tool_input:
                    details.append(f"offset={tool_input['offset']}")
                if 'limit' in tool_input:
                    details.append(f"limit={tool_input['limit']}")
            elif tool_name == "Write":
                file_path = tool_input.get('file_path', 'unknown')
                content_len = len(tool_input.get('content', ''))
                details.append(f"file={file_path}, bytes={content_len}")
            elif tool_name == "Bash":
                command = tool_input.get('command', '')[:100]  # First 100 chars
                details.append(f"cmd='{command}'")
            elif tool_name == "Glob":
                pattern = tool_input.get('pattern', '')
                path = tool_input.get('path', 'cwd')
                details.append(f"pattern='{pattern}', path={path}")
            elif tool_name == "Grep":
                pattern = tool_input.get('pattern', '')
                path = tool_input.get('path', 'cwd')
                details.append(f"pattern='{pattern}', path={path}")
            else:
                # For other tools, show first few keys
                keys = list(tool_input.keys())[:3]
                details.append(f"params={keys}")

            detail_str = ", ".join(details) if details else "no params"

            # Log to agent log with details
            logger.log_message(f"PRE-TOOL: {tool_name} ({detail_str})", level="DEBUG")

            # Log to tools JSONL
            entry = ToolLogEntry(
                timestamp=datetime.now().isoformat(),
                event_type="pre_tool",
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=tool_use_id
            )
            logger.log_tool_call(entry)

        except Exception as e:
            logger.log_message(f"Error in pre_tool_hook: {e}", level="ERROR")

        # Always allow the tool to proceed
        return {}

    async def post_tool_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Hook that runs after tool execution."""
        try:
            tool_name = input_data.get('tool_name', 'unknown')
            tool_input = input_data.get('tool_input', {})
            tool_output = input_data.get('tool_output', {})

            # Check for errors first
            error = None
            if isinstance(tool_output, dict):
                if tool_output.get('is_error'):
                    error = str(tool_output.get('content', 'Unknown error'))

            # Create detailed log message with output information
            details = []
            if error:
                details.append(f"error='{error[:100]}'")  # First 100 chars of error
            elif tool_name == "Read":
                file_path = tool_input.get('file_path', 'unknown')
                if isinstance(tool_output, dict):
                    content = tool_output.get('content', '')
                    if isinstance(content, str):
                        lines = content.count('\n') + 1 if content else 0
                        bytes_read = len(content)
                        details.append(f"file={file_path}, lines={lines}, bytes={bytes_read}")
                    else:
                        details.append(f"file={file_path}")
                else:
                    details.append(f"file={file_path}")
            elif tool_name == "Write":
                file_path = tool_input.get('file_path', 'unknown')
                content_len = len(tool_input.get('content', ''))
                details.append(f"file={file_path}, bytes_written={content_len}")
            elif tool_name == "Bash":
                if isinstance(tool_output, dict):
                    content = tool_output.get('content', '')
                    exit_code = tool_output.get('exit_code', 'unknown')
                    output_len = len(str(content))
                    details.append(f"exit_code={exit_code}, output_bytes={output_len}")
                else:
                    details.append("completed")
            elif tool_name == "Glob":
                if isinstance(tool_output, dict):
                    content = tool_output.get('content', '')
                    if isinstance(content, str):
                        matches = len(content.splitlines()) if content else 0
                        details.append(f"matches={matches}")
                    else:
                        details.append("completed")
                else:
                    details.append("completed")
            elif tool_name == "Grep":
                if isinstance(tool_output, dict):
                    content = tool_output.get('content', '')
                    if isinstance(content, str):
                        matches = len(content.splitlines()) if content else 0
                        details.append(f"matches={matches}")
                    else:
                        details.append("completed")
                else:
                    details.append("completed")
            else:
                details.append("completed")

            detail_str = ", ".join(details) if details else "no output"

            # Log to agent log with details
            if error:
                logger.log_message(f"POST-TOOL: {tool_name} ({detail_str})", level="ERROR")
            else:
                logger.log_message(f"POST-TOOL: {tool_name} ({detail_str})", level="DEBUG")

            # Log to tools JSONL
            entry = ToolLogEntry(
                timestamp=datetime.now().isoformat(),
                event_type="post_tool",
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                tool_use_id=tool_use_id,
                error=error
            )
            logger.log_tool_call(entry)

        except Exception as e:
            logger.log_message(f"Error in post_tool_hook: {e}", level="ERROR")

        # Always allow to proceed
        return {}

    from claude_agent_sdk import HookMatcher

    return {
        'PreToolUse': [
            HookMatcher(hooks=[pre_tool_hook])  # Match all tools
        ],
        'PostToolUse': [
            HookMatcher(hooks=[post_tool_hook])  # Match all tools
        ]
    }
