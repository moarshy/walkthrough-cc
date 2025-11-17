"""
Schemas for vanilla CC vs walkthrough CC experiment.

Defines data structures for:
- Task definitions
- Agent results (vanilla and walkthrough)
- Experiment results and comparison metrics
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from pathlib import Path


# ============================================================================
# TASK DEFINITION (SetupBench-style)
# ============================================================================

class Task(BaseModel):
    """
    SetupBench-inspired task definition with deterministic validation.

    This schema combines repository setup with independent validation,
    allowing both vanilla and walkthrough agents to be evaluated objectively.
    """
    # Core identification
    instance_id: str = Field(description="Unique task identifier (e.g., 'fastapi-first-steps')")

    # Repository details
    repo_url: str = Field(description="GitHub repository URL")
    branch: str = Field(default="main", description="Branch to clone (e.g., 'main', 'master')")
    base_commit: str = Field(description="Specific commit hash for reproducibility")
    language: str = Field(description="Programming language (e.g., 'python', 'javascript')")

    # Environment specification
    base_image: str = Field(default="ubuntu:22.04", description="Docker base image")

    # Task description
    problem_statement: str = Field(description="Full task description with constraints and requirements")
    notes: str = Field(description="Brief task summary for humans")

    # Documentation paths (for walkthrough generation)
    docs_folder: str = Field(description="Path to docs within repo (e.g., 'docs/en')")
    target_doc: str = Field(description="Specific doc file (e.g., 'tutorial/first-steps.md')")

    # Validation (SetupBench-style deterministic validation)
    success_command: str = Field(description="Shell command to verify task completion")
    timeout_seconds: int = Field(default=300, description="Validation timeout in seconds")

    # Ground truth (optional but valuable for analysis)
    build_commands: Optional[List[str]] = Field(None, description="Expected build steps for reference")

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# ============================================================================
# AGENT EXECUTION RESULTS
# ============================================================================

class TokenUsage(BaseModel):
    """Token usage for an agent run (matching setupbench-cc)."""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class ToolCallStats(BaseModel):
    """Statistics on tool calls."""
    total_calls: int = 0
    bash_calls: int = 0
    read_calls: int = 0
    write_calls: int = 0
    edit_calls: int = 0
    glob_calls: int = 0
    grep_calls: int = 0

    # Error tracking
    total_errors: int = 0
    bash_errors: int = 0
    read_errors: int = 0
    write_errors: int = 0
    edit_errors: int = 0
    glob_errors: int = 0
    grep_errors: int = 0

    # Error details (list of error occurrences)
    error_details: List[Dict[str, Any]] = Field(default_factory=list)


class AgentResult(BaseModel):
    """
    Result of running a single agent with SetupBench-style validation.

    Tracks both agent execution (did it complete?) and independent validation
    (did the setup actually work?). True success requires both.
    """
    agent_type: Literal["vanilla", "walkthrough"]
    task_id: str

    # Agent execution outcome
    agent_completed: bool = Field(description="Did agent finish without errors?")
    duration_seconds: float
    exit_code: int

    # Independent validation outcome (SetupBench-style)
    validation_passed: bool = Field(description="Did validation command succeed?")
    validation_output: Optional[str] = Field(None, description="Output from success_command")
    validation_exit_code: Optional[int] = Field(None, description="Exit code from success_command")
    validation_duration: Optional[float] = Field(None, description="Time spent validating (seconds)")

    # Overall success (BOTH agent_completed AND validation_passed must be True)
    success: bool = Field(description="True if both agent completed AND validation passed")

    # Error info
    error_message: Optional[str] = None
    error_type: Optional[str] = None

    # Resource usage
    token_usage: TokenUsage
    tool_calls: ToolCallStats

    # Timing
    started_at: str
    completed_at: str

    # Logs
    log_dir: Path
    messages_file: Optional[Path] = None
    tools_file: Optional[Path] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None


class TaskResult(BaseModel):
    """Combined result for a task (both vanilla and walkthrough)."""
    task_id: str
    task: Task

    # Generation phase
    walkthrough_generated: bool
    walkthrough_path: Optional[Path] = None
    generation_duration_seconds: Optional[float] = None
    generation_tokens: Optional[TokenUsage] = None

    # Execution results
    vanilla_result: Optional[AgentResult] = None
    walkthrough_result: Optional[AgentResult] = None

    # Comparison
    both_succeeded: bool = False
    both_failed: bool = False
    vanilla_only_success: bool = False
    walkthrough_only_success: bool = False

    # Timing
    started_at: str
    completed_at: str
    total_duration_seconds: float


# ============================================================================
# EXPERIMENT RESULTS
# ============================================================================

class ExperimentSummary(BaseModel):
    """Summary statistics for the experiment."""
    total_tasks: int

    # Success rates
    vanilla_successes: int
    vanilla_failures: int
    vanilla_success_rate: float

    walkthrough_successes: int
    walkthrough_failures: int
    walkthrough_success_rate: float

    # Comparison
    success_rate_improvement: float  # (walkthrough - vanilla) / vanilla
    both_succeeded: int
    both_failed: int
    vanilla_only_success: int
    walkthrough_only_success: int

    # Efficiency
    avg_vanilla_duration_seconds: float
    avg_walkthrough_duration_seconds: float
    time_reduction: float  # (vanilla - walkthrough) / vanilla

    # Cost
    total_vanilla_tokens: int
    total_walkthrough_tokens: int
    total_generation_tokens: int
    avg_vanilla_tokens_per_task: float
    avg_walkthrough_tokens_per_task: float
    token_increase: float  # (total_walkthrough + generation - vanilla) / vanilla

    # Tool usage
    avg_vanilla_tool_calls: float
    avg_walkthrough_tool_calls: float


class ExperimentResults(BaseModel):
    """Complete results for an experiment run."""
    experiment_id: str
    started_at: str
    completed_at: str
    duration_seconds: float

    # Configuration
    parallel_workers: int = 1
    timeout_seconds: int = 7200

    # Results
    tasks: List[TaskResult]
    summary: ExperimentSummary

    # Paths
    output_dir: Path
    walkthroughs_dir: Path
    logs_dir: Path

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def calculate_summary(cls, tasks: List[TaskResult]) -> ExperimentSummary:
        """Calculate summary statistics from task results."""
        total = len(tasks)

        # Count successes/failures
        vanilla_successes = sum(1 for t in tasks if t.vanilla_result and t.vanilla_result.success)
        vanilla_failures = sum(1 for t in tasks if t.vanilla_result and not t.vanilla_result.success)

        walkthrough_successes = sum(1 for t in tasks if t.walkthrough_result and t.walkthrough_result.success)
        walkthrough_failures = sum(1 for t in tasks if t.walkthrough_result and not t.walkthrough_result.success)

        # Calculate rates
        vanilla_rate = vanilla_successes / total if total > 0 else 0.0
        walkthrough_rate = walkthrough_successes / total if total > 0 else 0.0

        # Comparison counts
        both_succeeded = sum(1 for t in tasks if t.both_succeeded)
        both_failed = sum(1 for t in tasks if t.both_failed)
        vanilla_only = sum(1 for t in tasks if t.vanilla_only_success)
        walkthrough_only = sum(1 for t in tasks if t.walkthrough_only_success)

        # Timing
        vanilla_durations = [t.vanilla_result.duration_seconds for t in tasks if t.vanilla_result]
        walkthrough_durations = [t.walkthrough_result.duration_seconds for t in tasks if t.walkthrough_result]

        avg_vanilla_time = sum(vanilla_durations) / len(vanilla_durations) if vanilla_durations else 0.0
        avg_walkthrough_time = sum(walkthrough_durations) / len(walkthrough_durations) if walkthrough_durations else 0.0

        # Tokens
        total_vanilla_tokens = sum(
            t.vanilla_result.token_usage.total_tokens for t in tasks if t.vanilla_result
        )
        total_walkthrough_tokens = sum(
            t.walkthrough_result.token_usage.total_tokens for t in tasks if t.walkthrough_result
        )
        total_generation_tokens = sum(
            t.generation_tokens.total_tokens for t in tasks if t.generation_tokens
        )

        avg_vanilla_tokens = total_vanilla_tokens / total if total > 0 else 0.0
        avg_walkthrough_tokens = (total_walkthrough_tokens + total_generation_tokens) / total if total > 0 else 0.0

        # Tool calls
        vanilla_tool_calls = [
            t.vanilla_result.tool_calls.total_calls for t in tasks if t.vanilla_result
        ]
        walkthrough_tool_calls = [
            t.walkthrough_result.tool_calls.total_calls for t in tasks if t.walkthrough_result
        ]

        avg_vanilla_tools = sum(vanilla_tool_calls) / len(vanilla_tool_calls) if vanilla_tool_calls else 0.0
        avg_walkthrough_tools = sum(walkthrough_tool_calls) / len(walkthrough_tool_calls) if walkthrough_tool_calls else 0.0

        return ExperimentSummary(
            total_tasks=total,
            vanilla_successes=vanilla_successes,
            vanilla_failures=vanilla_failures,
            vanilla_success_rate=vanilla_rate,
            walkthrough_successes=walkthrough_successes,
            walkthrough_failures=walkthrough_failures,
            walkthrough_success_rate=walkthrough_rate,
            success_rate_improvement=(walkthrough_rate - vanilla_rate) / vanilla_rate if vanilla_rate > 0 else 0.0,
            both_succeeded=both_succeeded,
            both_failed=both_failed,
            vanilla_only_success=vanilla_only,
            walkthrough_only_success=walkthrough_only,
            avg_vanilla_duration_seconds=avg_vanilla_time,
            avg_walkthrough_duration_seconds=avg_walkthrough_time,
            time_reduction=(avg_vanilla_time - avg_walkthrough_time) / avg_vanilla_time if avg_vanilla_time > 0 else 0.0,
            total_vanilla_tokens=total_vanilla_tokens,
            total_walkthrough_tokens=total_walkthrough_tokens + total_generation_tokens,
            total_generation_tokens=total_generation_tokens,
            avg_vanilla_tokens_per_task=avg_vanilla_tokens,
            avg_walkthrough_tokens_per_task=avg_walkthrough_tokens,
            token_increase=(avg_walkthrough_tokens - avg_vanilla_tokens) / avg_vanilla_tokens if avg_vanilla_tokens > 0 else 0.0,
            avg_vanilla_tool_calls=avg_vanilla_tools,
            avg_walkthrough_tool_calls=avg_walkthrough_tools
        )
