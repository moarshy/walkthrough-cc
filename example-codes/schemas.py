"""
Pydantic schemas for walkthrough validation system.

These models define the structure for:
- Walkthrough generation (from documentation)
- Walkthrough execution (step-by-step audit)
- Gap reporting (issues found during audit)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# WALKTHROUGH STRUCTURE (Based on demo-nextjs-walkthrough.json)
# ============================================================================

class ContentFields(BaseModel):
    """Content fields for a walkthrough step."""
    version: str = Field(default="v1", description="Content schema version")
    contentForUser: str = Field(description="User-facing content (markdown)")
    contextForAgent: str = Field(description="Background context for the agent")
    operationsForAgent: str = Field(description="Concrete operations/commands to execute")
    introductionForAgent: str = Field(description="Purpose and goals of this step")


class WalkthroughStep(BaseModel):
    """A single step in a walkthrough."""
    title: str = Field(description="Step title")
    contentFields: ContentFields = Field(description="Content for this step")
    displayOrder: int = Field(description="Order in which this step appears (1-indexed)")
    createdAt: int = Field(description="Unix timestamp (milliseconds)")
    updatedAt: int = Field(description="Unix timestamp (milliseconds)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    nextStepReference: Optional[int] = Field(None, description="Reference to next step (None if last)")


class WalkthroughMetadata(BaseModel):
    """Metadata about the walkthrough."""
    title: str = Field(description="Walkthrough title")
    description: str = Field(description="Walkthrough description")
    type: str = Field(default="quickstart", description="Type of walkthrough")
    status: str = Field(default="published", description="Publication status")
    createdAt: int = Field(description="Unix timestamp (milliseconds)")
    updatedAt: int = Field(description="Unix timestamp (milliseconds)")
    estimatedDurationMinutes: int = Field(description="Estimated time to complete")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class Walkthrough(BaseModel):
    """Complete walkthrough structure."""
    walkthrough: WalkthroughMetadata = Field(description="Walkthrough metadata")
    steps: List[WalkthroughStep] = Field(description="Ordered list of steps")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Export metadata")


class WalkthroughExport(BaseModel):
    """Top-level structure for exported walkthrough JSON."""
    version: str = Field(default="1.0", description="Export format version")
    exportedAt: str = Field(description="ISO 8601 timestamp")
    walkthrough: WalkthroughMetadata = Field(description="Walkthrough metadata")
    steps: List[WalkthroughStep] = Field(description="Ordered list of steps")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Export metadata")

    @classmethod
    def from_walkthrough(cls, walkthrough: Walkthrough) -> "WalkthroughExport":
        """Create export format from walkthrough."""
        return cls(
            version="1.0",
            exportedAt=datetime.now().isoformat() + "Z",
            walkthrough=walkthrough.walkthrough,
            steps=walkthrough.steps,
            metadata=walkthrough.metadata
        )


# ============================================================================
# GAP REPORTING (Audit Results)
# ============================================================================

class GapReport(BaseModel):
    """A gap or issue identified during walkthrough execution."""
    step_number: int = Field(description="Step where gap was found (1-indexed)")
    step_title: str = Field(description="Title of the step")
    gap_type: str = Field(
        description=(
            "Type of gap: 'clarity' | 'prerequisite' | 'logical_flow' | "
            "'execution_error' | 'completeness' | 'cross_reference'"
        )
    )
    severity: str = Field(description="Severity: 'critical' | 'warning' | 'info'")
    description: str = Field(description="Detailed description of the gap")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix or improvement")
    context: Optional[str] = Field(None, description="Additional context (error messages, etc.)")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="When gap was identified")


class AuditResult(BaseModel):
    """Result of auditing a walkthrough."""
    walkthrough_id: str = Field(description="Walkthrough identifier")
    walkthrough_title: str = Field(description="Walkthrough title")
    library_name: str = Field(description="Library being validated")
    library_version: str = Field(description="Library version")
    started_at: str = Field(description="ISO 8601 timestamp")
    completed_at: str = Field(description="ISO 8601 timestamp")
    duration_seconds: float = Field(description="Total audit duration")

    total_steps: int = Field(description="Total steps in walkthrough")
    completed_steps: int = Field(description="Steps successfully completed")
    failed_steps: int = Field(description="Steps that failed")

    success: bool = Field(description="Whether audit completed successfully")
    gaps: List[GapReport] = Field(default_factory=list, description="All gaps found")

    # Gap counts by type
    clarity_gaps: int = Field(default=0, description="Count of clarity issues")
    prerequisite_gaps: int = Field(default=0, description="Count of prerequisite issues")
    logical_flow_gaps: int = Field(default=0, description="Count of logical flow issues")
    execution_gaps: int = Field(default=0, description="Count of execution errors")
    completeness_gaps: int = Field(default=0, description="Count of completeness issues")
    cross_reference_gaps: int = Field(default=0, description="Count of cross-reference issues")

    # Gap counts by severity
    critical_gaps: int = Field(default=0, description="Critical issues")
    warning_gaps: int = Field(default=0, description="Warnings")
    info_gaps: int = Field(default=0, description="Informational notes")

    execution_log: Optional[str] = Field(None, description="Full execution log")
    agent_log_path: Optional[str] = Field(None, description="Path to detailed agent logs")

    def model_post_init(self, __context: Any) -> None:
        """Calculate gap counts after initialization."""
        # Count by type
        for gap in self.gaps:
            if gap.gap_type == "clarity":
                self.clarity_gaps += 1
            elif gap.gap_type == "prerequisite":
                self.prerequisite_gaps += 1
            elif gap.gap_type == "logical_flow":
                self.logical_flow_gaps += 1
            elif gap.gap_type == "execution_error":
                self.execution_gaps += 1
            elif gap.gap_type == "completeness":
                self.completeness_gaps += 1
            elif gap.gap_type == "cross_reference":
                self.cross_reference_gaps += 1

            # Count by severity
            if gap.severity == "critical":
                self.critical_gaps += 1
            elif gap.severity == "warning":
                self.warning_gaps += 1
            elif gap.severity == "info":
                self.info_gaps += 1


# ============================================================================
# MCP SERVER STATE
# ============================================================================

class WalkthroughSession(BaseModel):
    """Active walkthrough session state for MCP server."""
    walkthrough_id: str = Field(description="Unique walkthrough identifier")
    walkthrough: Walkthrough = Field(description="The walkthrough being executed")
    current_step_index: int = Field(default=0, description="Current step index (0-based)")
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Session start time")
    gaps_reported: List[GapReport] = Field(default_factory=list, description="Gaps reported so far")

    @property
    def current_step_number(self) -> int:
        """Get current step number (1-indexed)."""
        return self.current_step_index + 1

    @property
    def total_steps(self) -> int:
        """Get total number of steps."""
        return len(self.walkthrough.steps)

    @property
    def is_complete(self) -> bool:
        """Check if walkthrough is complete."""
        return self.current_step_index >= self.total_steps

    @property
    def progress_percentage(self) -> float:
        """Get progress as percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step_index / self.total_steps) * 100
