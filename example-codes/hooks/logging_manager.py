"""
Logging Manager for StackBench agents.

Handles logging directory setup and organization.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime


class LoggingManager:
    """Manages logging directories and files for agent runs."""

    def __init__(self, run_dir: Path):
        """
        Initialize the logging manager.

        Args:
            run_dir: Root directory for the run (contains repo/, results/, logs/)
        """
        self.run_dir = Path(run_dir)
        self.logs_dir = self.run_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def get_agent_log_dir(self, agent_type: str) -> Path:
        """
        Get or create the log directory for a specific agent type.

        Args:
            agent_type: Type of agent (extraction, api_validation, code_validation)

        Returns:
            Path to the agent's log directory
        """
        agent_log_dir = self.logs_dir / agent_type
        agent_log_dir.mkdir(parents=True, exist_ok=True)
        return agent_log_dir

    def get_document_log_path(self, agent_type: str, document_name: str, log_type: str = "agent") -> Path:
        """
        Get the log file path for a specific document.

        Args:
            agent_type: Type of agent (extraction, api_validation, code_validation)
            document_name: Name of the document being processed (e.g., "quickstart.md")
            log_type: Type of log ("agent" for message log, "tools" for tool calls)

        Returns:
            Path to the log file
        """
        agent_log_dir = self.get_agent_log_dir(agent_type)

        # Remove extension and sanitize filename
        doc_stem = Path(document_name).stem

        if log_type == "agent":
            return agent_log_dir / f"{doc_stem}_agent.log"
        elif log_type == "tools":
            return agent_log_dir / f"{doc_stem}_tools.jsonl"
        else:
            raise ValueError(f"Unknown log_type: {log_type}")

    def get_summary_path(self, agent_type: str) -> Path:
        """
        Get the path to the summary file for an agent type.

        Args:
            agent_type: Type of agent (extraction, api_validation, code_validation)

        Returns:
            Path to the summary file
        """
        agent_log_dir = self.get_agent_log_dir(agent_type)
        return agent_log_dir / "summary.json"

    def create_summary(self, agent_type: str, stats: dict) -> None:
        """
        Create a summary file for an agent's logging session.

        Args:
            agent_type: Type of agent
            stats: Dictionary with statistics (documents_processed, total_tool_calls, etc.)
        """
        summary_path = self.get_summary_path(agent_type)

        summary = {
            "agent_type": agent_type,
            "timestamp": datetime.now().isoformat(),
            "run_dir": str(self.run_dir),
            "stats": stats
        }

        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

    def cleanup(self):
        """Clean up any temporary resources (currently a no-op)."""
        pass
