"""
Walkthrough Audit Agent

This agent executes a walkthrough step-by-step using an MCP server that provides
the steps. It identifies gaps, unclear instructions, missing prerequisites, and
other documentation issues by actually following the tutorial like a real developer.
"""

import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    HookMatcher,
)

from .schemas import AuditResult, GapReport
from stackbench.hooks.logging import create_logging_hooks, AgentLogger

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

AUDIT_SYSTEM_PROMPT = """You are an expert software developer tasked with following a tutorial walkthrough to validate its quality.

You have access to an MCP server (namespace: "walkthrough") that provides walkthrough steps one at a time. Your job is to:

1. **Execute each step** exactly as a real developer would
2. **Identify gaps** in documentation (unclear instructions, missing prerequisites, broken commands, etc.)
3. **Report issues** using the report_gap MCP tool
4. **Continue through the walkthrough** even if you encounter issues

IMPORTANT: You MUST use the MCP tools to access the walkthrough. Do NOT manually read the walkthrough JSON file.

AVAILABLE MCP TOOLS (prefix with "mcp__walkthrough__"):
- `mcp__walkthrough__start_walkthrough(walkthrough_path)`: Initialize the walkthrough
- `mcp__walkthrough__next_step()`: Get the next step to execute
- `mcp__walkthrough__walkthrough_status()`: Check your progress
- `mcp__walkthrough__report_gap(gap_type, severity, description, ...)`: Report an issue

GAP TYPES:
- **clarity**: Instructions are vague, ambiguous, or confusing
- **prerequisite**: Missing setup requirements or dependencies
- **logical_flow**: Step references something not created earlier
- **execution_error**: Commands fail or produce errors
- **completeness**: Missing steps or verification procedures
- **cross_reference**: Should link to another doc for details

SEVERITY LEVELS:
- **critical**: Blocks progress completely (cannot continue)
- **warning**: Creates confusion or extra work (can work around)
- **info**: Minor improvement suggestion

YOUR WORKFLOW:

1. **Start**: Call `start_walkthrough(walkthrough_path)` with the provided path
2. **Loop**:
   a. Call `next_step()` to get the next step
   b. Read the step content (contentForUser, contextForAgent, operationsForAgent)
   c. Execute the operations as instructed
   d. If you encounter any issues, call `report_gap(...)` with details
   e. Continue to next step
3. **Complete**: When all steps are done, report final status

IMPORTANT BEHAVIORS:

- **Be thorough**: Actually execute commands, don't skip steps
- **Be honest**: Report gaps even if minor
- **Be specific**: Include error messages, line numbers, exact issues
- **Be helpful**: Suggest fixes when possible
- **Ask for confirmation**: If operations require user interaction (e.g., checking browser), ask user to confirm before proceeding

Remember: Your goal is to improve documentation quality by finding issues a real developer would encounter.
"""

AUDIT_START_PROMPT = """You are about to audit a walkthrough for {library_name} version {library_version}.

Walkthrough file: {walkthrough_path}

Please start the walkthrough and execute each step, reporting any gaps or issues you find.

Follow this process:
1. Call `mcp__walkthrough__start_walkthrough` with the walkthrough path
2. For each step:
   - Call `mcp__walkthrough__next_step` to get step details
   - Execute the operations
   - Report any gaps using `mcp__walkthrough__report_gap`
3. Continue until complete

Begin now by calling the mcp__walkthrough__start_walkthrough tool with walkthrough_path="{walkthrough_path}".
"""


# ============================================================================
# AUDIT AGENT
# ============================================================================

class WalkthroughAuditAgent:
    """Agent that audits walkthroughs by executing them step-by-step."""

    def __init__(
        self,
        output_folder: Path,
        library_name: str,
        library_version: str,
        mcp_server_path: Optional[Path] = None,
    ):
        """
        Initialize the audit agent.

        Args:
            output_folder: Path to save audit results
            library_name: Name of the library being validated
            library_version: Version of the library
            mcp_server_path: Optional path to MCP server script (default: auto-detect)
        """
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.library_name = library_name
        self.library_version = library_version

        # Auto-detect MCP server path
        if mcp_server_path:
            self.mcp_server_path = Path(mcp_server_path)
        else:
            # Default to mcp_server.py in same directory
            self.mcp_server_path = Path(__file__).parent / "mcp_server.py"

        if not self.mcp_server_path.exists():
            raise FileNotFoundError(f"MCP server not found at: {self.mcp_server_path}")

        print(f"🔍 Walkthrough Audit Agent initialized")
        print(f"   Library: {library_name} v{library_version}")
        print(f"   Output: {output_folder}")
        print(f"   MCP Server: {self.mcp_server_path}")

    async def audit_walkthrough(
        self,
        walkthrough_path: Path,
        working_directory: Optional[Path] = None
    ) -> AuditResult:
        """
        Audit a walkthrough by executing it step-by-step.

        Args:
            walkthrough_path: Path to the walkthrough JSON file
            working_directory: Optional working directory for execution (default: temp dir)

        Returns:
            AuditResult containing all gaps found and execution details
        """
        print(f"\n🔄 Auditing walkthrough: {walkthrough_path.name}")

        # Set working directory
        if not working_directory:
            import tempfile
            working_directory = Path(tempfile.mkdtemp(prefix="walkthrough_audit_"))
            print(f"   Working directory: {working_directory}")

        # Prepare timestamps
        started_at = datetime.now().isoformat()

        # Setup logging hooks
        log_dir = self.output_folder / "agent_logs"
        logger = AgentLogger(
            log_file=log_dir / "audit.log",
            tools_log_file=log_dir / "audit_tools.jsonl"
        )
        logging_hooks = create_logging_hooks(logger)

        # Create hooks dictionary
        hooks = {
            'PreToolUse': logging_hooks['PreToolUse'],
            'PostToolUse': logging_hooks['PostToolUse']
        }

        # Create Claude SDK client with MCP server
        options = ClaudeAgentOptions(
            system_prompt=AUDIT_SYSTEM_PROMPT,
            allowed_tools=["Bash", "Read", "Write", "Glob"],  # Allow execution tools
            permission_mode="bypassPermissions",  # Bypass permissions for MCP tool calls
            cwd=str(working_directory),
            hooks=hooks,
            mcp_servers={
                "walkthrough": {
                    "command": "uv",
                    "args": ["run", "python", "-m", "stackbench.walkthroughs.mcp_server"],
                }
            }
        )

        gaps: List[GapReport] = []
        completed_steps = 0
        failed_steps = 0
        success = False
        execution_log = []

        try:
            async with ClaudeSDKClient(options=options) as client:
                # Start audit
                start_prompt = AUDIT_START_PROMPT.format(
                    library_name=self.library_name,
                    library_version=self.library_version,
                    walkthrough_path=str(walkthrough_path.absolute())
                )

                await client.query(start_prompt)

                # Collect responses and track execution
                response_count = 0
                max_responses = 100  # Safety limit

                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        response_count += 1

                        # Log the message
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                execution_log.append({
                                    "timestamp": datetime.now().isoformat(),
                                    "type": "assistant_message",
                                    "content": block.text[:500]  # Truncate for summary
                                })

                        # Check if agent has completed
                        message_text = ""
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                message_text += block.text.lower()

                        # Check for completion signals
                        if any(signal in message_text for signal in [
                            "all steps completed",
                            "walkthrough complete",
                            "audit complete",
                            "status\": \"complete"
                        ]):
                            print("✅ Audit completed successfully")
                            success = True
                            break

                        # Safety check
                        if response_count >= max_responses:
                            print(f"⚠️  Reached maximum response limit ({max_responses})")
                            break

        except Exception as e:
            print(f"❌ Audit failed with error: {e}")
            execution_log.append({
                "timestamp": datetime.now().isoformat(),
                "type": "error",
                "content": str(e)
            })

        # Calculate duration
        completed_at = datetime.now().isoformat()
        started_dt = datetime.fromisoformat(started_at)
        completed_dt = datetime.fromisoformat(completed_at)
        duration_seconds = (completed_dt - started_dt).total_seconds()

        # Load walkthrough to get metadata
        with open(walkthrough_path, 'r', encoding='utf-8') as f:
            walkthrough_data = json.load(f)

        walkthrough_title = walkthrough_data.get("walkthrough", {}).get("title", "Unknown")
        total_steps = len(walkthrough_data.get("steps", []))

        # Load gaps from MCP server session file
        session_file = walkthrough_path.parent / f"{walkthrough_path.stem}_session.json"
        if session_file.exists():
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)

                # Extract gaps from session
                for gap_data in session_data.get("gaps", []):
                    gap = GapReport(
                        step_number=gap_data["step_number"],
                        step_title=gap_data["step_title"],
                        gap_type=gap_data["gap_type"],
                        severity=gap_data["severity"],
                        description=gap_data["description"],
                        suggested_fix=gap_data.get("suggested_fix"),
                        context=gap_data.get("context"),
                        timestamp=gap_data.get("timestamp")
                    )
                    gaps.append(gap)

                # Update completion stats from session
                completed_steps = session_data.get("completed_steps", 0)
                failed_steps = total_steps - completed_steps if not session_data.get("is_complete", False) else 0

                logger.log_message(f"Loaded {len(gaps)} gaps from MCP session file", level="INFO")
                logger.log_message(f"Completed steps: {completed_steps}/{total_steps}", level="INFO")
            except Exception as e:
                logger.log_message(f"Warning: Failed to load MCP session file: {e}", level="WARNING")
        else:
            logger.log_message(f"Warning: MCP session file not found at {session_file}", level="WARNING")

        # Log final statistics
        logger.log_message("=== Audit Completed ===", level="INFO")
        logger.log_message(f"Duration: {duration_seconds:.1f}s", level="INFO")
        logger.log_message(f"Total steps: {total_steps}", level="INFO")
        logger.log_message(f"Success: {success}", level="INFO")
        stats = logger.get_stats()
        logger.log_message(f"Tool calls: {stats['tool_calls']}, Messages: {stats['messages_logged']}, Errors: {stats['errors']}", level="INFO")

        # Create audit result
        result = AuditResult(
            walkthrough_id=walkthrough_path.stem,
            walkthrough_title=walkthrough_title,
            library_name=self.library_name,
            library_version=self.library_version,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(duration_seconds, 2),
            total_steps=total_steps,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            success=success,
            gaps=gaps,
            execution_log=json.dumps(execution_log, indent=2),
            agent_log_path=str(log_dir / "audit.log")
        )

        # Save result
        output_file = self.output_folder / f"{walkthrough_path.stem}_audit.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n✅ Audit result saved: {output_file.name}")
        print(f"   Duration: {duration_seconds:.1f}s")
        print(f"   Steps: {completed_steps}/{total_steps}")
        print(f"   Gaps: {len(gaps)} ({result.critical_gaps} critical, {result.warning_gaps} warnings)")

        return result

    async def audit_multiple_walkthroughs(
        self,
        walkthrough_paths: List[Path],
        working_directory: Optional[Path] = None
    ) -> List[AuditResult]:
        """
        Audit multiple walkthroughs.

        Args:
            walkthrough_paths: List of paths to walkthrough JSON files
            working_directory: Optional working directory for execution

        Returns:
            List of AuditResult objects
        """
        print(f"\n📚 Auditing {len(walkthrough_paths)} walkthroughs...")

        results = []
        for i, walkthrough_path in enumerate(walkthrough_paths, 1):
            print(f"\n[{i}/{len(walkthrough_paths)}] Processing: {walkthrough_path.name}")

            try:
                result = await self.audit_walkthrough(walkthrough_path, working_directory)
                results.append(result)
            except Exception as e:
                print(f"❌ Failed to audit {walkthrough_path.name}: {e}")
                continue

        print(f"\n✨ Audited {len(results)}/{len(walkthrough_paths)} walkthroughs")

        # Generate summary
        total_gaps = sum(len(r.gaps) for r in results)
        total_critical = sum(r.critical_gaps for r in results)
        total_warnings = sum(r.warning_gaps for r in results)

        print(f"   Total gaps: {total_gaps} ({total_critical} critical, {total_warnings} warnings)")

        return results
