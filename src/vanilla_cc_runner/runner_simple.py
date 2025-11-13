"""
Simplified experiment runner for testing infrastructure.
Skips walkthrough generation - uses pre-made walkthroughs or tests vanilla only.
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

from .schemas import Task, TaskResult, AgentResult, TokenUsage, ToolCallStats
from .harness_docker import DockerHarness

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleExperimentRunner:
    """Simplified runner for testing infrastructure."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        self.docker_harness = DockerHarness()
        
    async def test_vanilla_agent(self, task: Task) -> AgentResult:
        """Test just the vanilla agent (no walkthrough)."""
        logger.info(f"Testing vanilla agent for: {task.id}")
        
        # For now, create minimal test directories
        task_log_dir = self.logs_dir / task.id / "vanilla"
        task_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal repo structure  
        repo_path = self.output_dir / "test_repo"
        repo_path.mkdir(exist_ok=True)
        
        docs_path = repo_path / "docs"
        docs_path.mkdir(exist_ok=True)
        
        # Create a simple test doc
        test_doc = docs_path / task.target_doc
        test_doc.parent.mkdir(parents=True, exist_ok=True)
        test_doc.write_text("# Test Doc\n\nThis is a test.")
        
        # Run vanilla agent
        result = self.docker_harness.run_agent(
            task=task,
            agent_type="vanilla",
            repo_path=repo_path,
            docs_path=docs_path,
            walkthrough_path=None,
            log_dir=task_log_dir
        )
        
        return result


async def test_infrastructure(task: Task):
    """Quick infrastructure test."""
    print("\n" + "="*80)
    print("INFRASTRUCTURE TEST")
    print("="*80 + "\n")
    
    runner = SimpleExperimentRunner(output_dir=Path("test_results"))
    
    print(f"Testing task: {task.id}")
    print(f"Library: {task.library_name}")
    
    result = await runner.test_vanilla_agent(task)
    
    print(f"\nResult: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Exit code: {result.exit_code}")
    
    if result.error_message:
        print(f"Error: {result.error_message}")
    
    return result
