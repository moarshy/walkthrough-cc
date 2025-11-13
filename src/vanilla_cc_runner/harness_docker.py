"""
Docker harness for running vanilla and walkthrough agents in isolated containers.

Manages container lifecycle, resource limits, logging, and cleanup.
"""

import os
import time
import json
import docker
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from datetime import datetime

from .schemas import Task, AgentResult, TokenUsage, ToolCallStats

logger = logging.getLogger(__name__)


class DockerHarness:
    """Manages Docker containers for agent execution."""

    def __init__(
        self,
        image_name: str = "cc-experiment:latest",
        mem_limit: str = "8g",
        cpu_count: int = 4,
        timeout_seconds: int = 7200
    ):
        """
        Initialize Docker harness.

        Args:
            image_name: Docker image to use
            mem_limit: Memory limit (e.g., "8g")
            cpu_count: Number of CPUs
            timeout_seconds: Max execution time (default 2 hours)
        """
        self.image_name = image_name
        self.mem_limit = mem_limit
        self.cpu_count = cpu_count
        self.timeout_seconds = timeout_seconds

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            logger.info(f"Docker client initialized")
        except docker.errors.DockerException as e:
            raise RuntimeError(f"Failed to connect to Docker: {e}")

        # Verify API key
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set!")

    def run_agent(
        self,
        task: Task,
        agent_type: Literal["vanilla", "walkthrough"],
        repo_path: Path,
        docs_path: Path,
        walkthrough_path: Optional[Path],
        log_dir: Path
    ) -> AgentResult:
        """
        Run an agent in a Docker container.

        Args:
            task: Task definition
            agent_type: "vanilla" or "walkthrough"
            repo_path: Path to cloned repository
            docs_path: Path to docs folder
            walkthrough_path: Path to walkthrough.json (walkthrough agent only)
            log_dir: Directory for agent logs

        Returns:
            AgentResult with execution details
        """
        start_time = time.time()
        started_at = datetime.now().isoformat()

        container_name = f"cc-agent-{task.id}-{agent_type}-{int(time.time())}"

        logger.info(f"🐳 Starting {agent_type} agent for task {task.id}")
        logger.info(f"   Container: {container_name}")

        # Setup volumes
        volumes = {
            str(repo_path.absolute()): {'bind': '/workspace/repo', 'mode': 'rw'},
            str(docs_path.absolute()): {'bind': '/workspace/docs', 'mode': 'ro'},
            str(log_dir.absolute()): {'bind': '/workspace/logs', 'mode': 'rw'},
        }

        # Add walkthrough for walkthrough agent
        if agent_type == "walkthrough" and walkthrough_path:
            volumes[str(walkthrough_path.absolute())] = {
                'bind': '/workspace/walkthrough.json',
                'mode': 'ro'
            }

        # Setup environment
        environment = {
            'ANTHROPIC_API_KEY': self.api_key,
            'TASK_ID': task.id,
            'AGENT_TYPE': agent_type,
            'TARGET_DOC': task.target_doc,
            'LIBRARY_NAME': task.library_name,
            'LIBRARY_VERSION': task.library_version,
            'NODE_PATH': '/usr/local/lib/node_modules',
            'PYTHONUNBUFFERED': '1',
        }

        container = None
        try:
            # Create and start container
            container = self.docker_client.containers.run(
                image=self.image_name,
                command=['python3', '/agent_wrapper/run_agent.py', agent_type],
                volumes=volumes,
                environment=environment,
                mem_limit=self.mem_limit,
                cpu_count=self.cpu_count,
                detach=True,
                network_mode='bridge',
                name=container_name,
                working_dir='/workspace/repo'
            )

            logger.info(f"   Container started: {container.id[:12]}")

            # Wait for completion with timeout
            exit_code = self._wait_for_container(container, self.timeout_seconds)

            # Collect logs
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')

            # Save logs
            container_log_file = log_dir / f"{agent_type}_container.log"
            with open(container_log_file, 'w') as f:
                f.write(logs)

            logger.info(f"   Container exited: code {exit_code}")

            # Parse execution results
            duration = time.time() - start_time
            success = exit_code == 0

            # Extract token usage and tool calls from logs
            token_usage, tool_calls = self._parse_agent_logs(log_dir)

            # Determine error
            error_message = None
            error_type = None
            if not success:
                error_message = self._extract_error_from_logs(logs, exit_code)
                error_type = self._classify_error(exit_code, error_message)

            return AgentResult(
                agent_type=agent_type,
                task_id=task.id,
                success=success,
                duration_seconds=duration,
                exit_code=exit_code,
                error_message=error_message,
                error_type=error_type,
                token_usage=token_usage,
                tool_calls=tool_calls,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                log_dir=log_dir,
                messages_file=log_dir / f"{agent_type}_messages.jsonl",
                tools_file=log_dir / f"{agent_type}_tools.jsonl"
            )

        except docker.errors.ImageNotFound:
            error_msg = f"Docker image not found: {self.image_name}"
            logger.error(f"❌ {error_msg}")
            return self._create_error_result(
                task, agent_type, started_at, start_time, log_dir,
                error_msg, "ImageNotFound"
            )

        except Exception as e:
            error_msg = f"Container execution failed: {e}"
            logger.error(f"❌ {error_msg}")
            return self._create_error_result(
                task, agent_type, started_at, start_time, log_dir,
                error_msg, "ContainerError"
            )

        finally:
            # Cleanup container
            if container:
                try:
                    container.stop(timeout=10)
                    container.remove(force=True)
                    logger.info(f"   Container cleaned up")
                except Exception as e:
                    logger.warning(f"   Failed to cleanup container: {e}")

    def _wait_for_container(self, container, timeout: int) -> int:
        """Wait for container to finish with timeout."""
        try:
            result = container.wait(timeout=timeout)
            return result['StatusCode']
        except Exception as e:
            logger.warning(f"   Container timeout or error: {e}")
            # Force stop
            container.stop(timeout=10)
            return 124  # Timeout exit code

    def _parse_agent_logs(self, log_dir: Path) -> tuple[TokenUsage, ToolCallStats]:
        """Parse token usage and tool calls from agent logs."""
        token_usage = TokenUsage()
        tool_calls = ToolCallStats()

        # Try to parse tools.jsonl
        tools_file = log_dir / "tools.jsonl"
        if tools_file.exists():
            try:
                with open(tools_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        tool_event = json.loads(line)

                        # Count tool calls
                        tool_name = tool_event.get('tool', '').lower()
                        tool_calls.total_calls += 1

                        if 'bash' in tool_name:
                            tool_calls.bash_calls += 1
                        elif 'read' in tool_name:
                            tool_calls.read_calls += 1
                        elif 'write' in tool_name:
                            tool_calls.write_calls += 1
                        elif 'edit' in tool_name:
                            tool_calls.edit_calls += 1
                        elif 'glob' in tool_name:
                            tool_calls.glob_calls += 1
                        elif 'grep' in tool_name:
                            tool_calls.grep_calls += 1

            except Exception as e:
                logger.warning(f"Failed to parse tools.jsonl: {e}")

        # Try to parse messages.jsonl for token usage
        messages_file = log_dir / "messages.jsonl"
        if messages_file.exists():
            try:
                with open(messages_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        msg = json.loads(line)

                        # Look for usage information
                        usage = msg.get('usage', {})
                        if usage:
                            token_usage.input_tokens += usage.get('input_tokens', 0)
                            token_usage.output_tokens += usage.get('output_tokens', 0)
                            token_usage.cache_read_tokens += usage.get('cache_read_input_tokens', 0)
                            token_usage.cache_creation_tokens += usage.get('cache_creation_input_tokens', 0)

            except Exception as e:
                logger.warning(f"Failed to parse messages.jsonl: {e}")

        # Calculate total tokens
        token_usage.total_tokens = (
            token_usage.input_tokens +
            token_usage.output_tokens +
            token_usage.cache_creation_tokens
        )

        return token_usage, tool_calls

    def _extract_error_from_logs(self, logs: str, exit_code: int) -> str:
        """Extract error message from container logs."""
        # Look for common error patterns
        lines = logs.split('\n')

        error_indicators = ['error:', 'exception:', 'traceback', 'failed:', '❌']

        for line in reversed(lines[-50:]):  # Check last 50 lines
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in error_indicators):
                return line.strip()[:200]  # Truncate to 200 chars

        # Default messages based on exit code
        if exit_code == 124:
            return "Agent execution timed out"
        elif exit_code == 137:
            return "Container killed (SIGKILL) - likely OOM"
        elif exit_code == 143:
            return "Container terminated (SIGTERM)"
        else:
            return f"Agent exited with code {exit_code}"

    def _classify_error(self, exit_code: int, error_message: Optional[str]) -> str:
        """Classify error type based on exit code and message."""
        if exit_code == 124:
            return "timeout"
        elif exit_code == 137:
            return "oom"
        elif exit_code == 143:
            return "sigterm"
        elif error_message and 'api' in error_message.lower():
            return "api_error"
        elif error_message and ('network' in error_message.lower() or 'connection' in error_message.lower()):
            return "network_error"
        else:
            return "unknown"

    def _create_error_result(
        self,
        task: Task,
        agent_type: str,
        started_at: str,
        start_time: float,
        log_dir: Path,
        error_message: str,
        error_type: str
    ) -> AgentResult:
        """Create an error result."""
        return AgentResult(
            agent_type=agent_type,
            task_id=task.id,
            success=False,
            duration_seconds=time.time() - start_time,
            exit_code=-1,
            error_message=error_message,
            error_type=error_type,
            token_usage=TokenUsage(),
            tool_calls=ToolCallStats(),
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            log_dir=log_dir
        )

    def verify_image_exists(self) -> bool:
        """Check if Docker image exists."""
        try:
            self.docker_client.images.get(self.image_name)
            return True
        except docker.errors.ImageNotFound:
            return False

    def cleanup(self):
        """Cleanup Docker resources."""
        try:
            self.docker_client.close()
        except Exception as e:
            logger.warning(f"Failed to close Docker client: {e}")
