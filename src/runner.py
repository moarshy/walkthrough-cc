"""
Experiment runner that orchestrates vanilla CC vs walkthrough CC comparison.

Workflow for each task:
1. Clone repository
2. Generate walkthrough from target doc
3. Run vanilla agent in Docker
4. Run walkthrough agent in Docker
5. Collect and compare results
"""

import sys
import time
import json
import logging
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add example-codes to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "example-codes"))

from repository.manager import RepositoryManager
from walkthrough_generate_agent import WalkthroughGenerateAgent

from .schemas import Task, TaskResult, ExperimentResults, TokenUsage
from .harness_docker import DockerHarness

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Orchestrates the vanilla vs walkthrough experiment."""

    def __init__(
        self,
        tasks: List[Task],
        output_dir: Path,
        parallel_workers: int = 1,
        timeout_seconds: int = 7200
    ):
        """
        Initialize experiment runner.

        Args:
            tasks: List of tasks to run
            output_dir: Output directory for results
            parallel_workers: Number of tasks to run in parallel
            timeout_seconds: Timeout per agent execution
        """
        self.tasks = tasks
        self.output_dir = Path(output_dir)
        self.parallel_workers = parallel_workers
        self.timeout_seconds = timeout_seconds

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.walkthroughs_dir = self.output_dir / "walkthroughs"
        self.walkthroughs_dir.mkdir(exist_ok=True)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.repos_dir = self.output_dir / "repos"
        self.repos_dir.mkdir(exist_ok=True)

        # Initialize components
        self.repo_manager = RepositoryManager(base_data_dir=self.repos_dir)
        self.docker_harness = DockerHarness(timeout_seconds=timeout_seconds)

        logger.info(f"Experiment runner initialized")
        logger.info(f"  Tasks: {len(tasks)}")
        logger.info(f"  Parallel workers: {parallel_workers}")
        logger.info(f"  Output: {output_dir}")

    async def run_experiment(self) -> ExperimentResults:
        """
        Run the full experiment.

        Returns:
            ExperimentResults with all task results and summary
        """
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        started_at = datetime.now().isoformat()

        logger.info(f"\n{'='*80}")
        logger.info(f"Starting Experiment: {experiment_id}")
        logger.info(f"{'='*80}\n")

        # Verify Docker image exists
        if not self.docker_harness.verify_image_exists():
            raise RuntimeError(
                f"Docker image not found: {self.docker_harness.image_name}\n"
                f"Build it first with: docker build -t {self.docker_harness.image_name} ."
            )

        # Run tasks
        if self.parallel_workers > 1:
            task_results = await self._run_tasks_parallel()
        else:
            task_results = await self._run_tasks_sequential()

        # Calculate summary
        duration = time.time() - start_time
        summary = ExperimentResults.calculate_summary(task_results)

        # Create experiment results
        results = ExperimentResults(
            experiment_id=experiment_id,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            duration_seconds=duration,
            parallel_workers=self.parallel_workers,
            timeout_seconds=self.timeout_seconds,
            tasks=task_results,
            summary=summary,
            output_dir=self.output_dir,
            walkthroughs_dir=self.walkthroughs_dir,
            logs_dir=self.logs_dir
        )

        # Save results
        results_file = self.output_dir / f"{experiment_id}_results.json"
        with open(results_file, 'w') as f:
            json.dump(results.model_dump(mode='json'), f, indent=2, default=str)

        logger.info(f"\n{'='*80}")
        logger.info(f"Experiment Complete: {experiment_id}")
        logger.info(f"{'='*80}\n")
        self._print_summary(summary)
        logger.info(f"\nResults saved to: {results_file}")

        return results

    async def _run_tasks_sequential(self) -> List[TaskResult]:
        """Run tasks one at a time."""
        results = []
        for i, task in enumerate(self.tasks, 1):
            logger.info(f"\n[{i}/{len(self.tasks)}] Running task: {task.id}")
            result = await self.run_single_task(task)
            results.append(result)
        return results

    async def _run_tasks_parallel(self) -> List[TaskResult]:
        """Run tasks in parallel using ThreadPoolExecutor."""
        logger.info(f"Running {len(self.tasks)} tasks with {self.parallel_workers} workers")

        results = []
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(asyncio.run, self.run_single_task(task)): task
                for task in self.tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"✓ Task completed: {task.id}")
                except Exception as e:
                    logger.error(f"✗ Task failed: {task.id} - {e}")

        return results

    async def run_single_task(self, task: Task) -> TaskResult:
        """
        Run a single task (vanilla + walkthrough).

        Args:
            task: Task definition

        Returns:
            TaskResult with both agent results
        """
        task_start = time.time()
        started_at = datetime.now().isoformat()

        logger.info(f"  Library: {task.library_name} v{task.library_version}")
        logger.info(f"  Repo: {task.repo_url}")
        logger.info(f"  Doc: {task.target_doc}")

        # Setup task directories
        task_log_dir = self.logs_dir / task.id
        task_log_dir.mkdir(exist_ok=True)

        try:
            # Step 1: Clone repository
            logger.info(f"  📦 Cloning repository...")
            repo_context = self.repo_manager.clone_repository(
                repo_url=task.repo_url,
                branch=task.branch,
                run_id=f"task_{task.id}",
                library_name=task.library_name,
                library_version=task.library_version,
                docs_path=task.docs_folder
            )
            repo_path = repo_context.repo_dir
            docs_path = repo_path / task.docs_folder

            # Step 2: Generate walkthrough
            logger.info(f"  📝 Generating walkthrough...")
            walkthrough_start = time.time()

            generator = WalkthroughGenerateAgent(
                output_folder=self.walkthroughs_dir,
                library_name=task.library_name,
                library_version=task.library_version
            )

            doc_path = docs_path / task.target_doc
            walkthrough = await generator.generate_walkthrough(
                doc_path=doc_path,
                walkthrough_id=task.id
            )

            walkthrough_duration = time.time() - walkthrough_start
            walkthrough_path = self.walkthroughs_dir / f"{task.id}.json"

            # Extract token usage from walkthrough generation
            # (This would require modifying WalkthroughGenerateAgent to return tokens)
            generation_tokens = TokenUsage()  # Placeholder

            logger.info(f"  ✅ Walkthrough generated ({walkthrough_duration:.1f}s)")

            # Step 3: Run vanilla agent
            logger.info(f"  🤖 Running vanilla agent...")
            vanilla_log_dir = task_log_dir / "vanilla"
            vanilla_log_dir.mkdir(exist_ok=True)

            vanilla_result = self.docker_harness.run_agent(
                task=task,
                agent_type="vanilla",
                repo_path=repo_path,
                docs_path=docs_path,
                walkthrough_path=None,
                log_dir=vanilla_log_dir
            )

            status = "✅" if vanilla_result.success else "❌"
            logger.info(f"  {status} Vanilla agent: {vanilla_result.duration_seconds:.1f}s")

            # Step 4: Run walkthrough agent
            logger.info(f"  🤖 Running walkthrough agent...")
            walkthrough_log_dir = task_log_dir / "walkthrough"
            walkthrough_log_dir.mkdir(exist_ok=True)

            walkthrough_result = self.docker_harness.run_agent(
                task=task,
                agent_type="walkthrough",
                repo_path=repo_path,
                docs_path=docs_path,
                walkthrough_path=walkthrough_path,
                log_dir=walkthrough_log_dir
            )

            status = "✅" if walkthrough_result.success else "❌"
            logger.info(f"  {status} Walkthrough agent: {walkthrough_result.duration_seconds:.1f}s")

            # Determine comparison categories
            both_succeeded = vanilla_result.success and walkthrough_result.success
            both_failed = (not vanilla_result.success) and (not walkthrough_result.success)
            vanilla_only = vanilla_result.success and (not walkthrough_result.success)
            walkthrough_only = (not vanilla_result.success) and walkthrough_result.success

            # Create task result
            task_duration = time.time() - task_start
            return TaskResult(
                task_id=task.id,
                task=task,
                walkthrough_generated=True,
                walkthrough_path=walkthrough_path,
                generation_duration_seconds=walkthrough_duration,
                generation_tokens=generation_tokens,
                vanilla_result=vanilla_result,
                walkthrough_result=walkthrough_result,
                both_succeeded=both_succeeded,
                both_failed=both_failed,
                vanilla_only_success=vanilla_only,
                walkthrough_only_success=walkthrough_only,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                total_duration_seconds=task_duration
            )

        except Exception as e:
            logger.error(f"  ❌ Task failed: {e}")
            import traceback
            traceback.print_exc()

            # Return error result
            return TaskResult(
                task_id=task.id,
                task=task,
                walkthrough_generated=False,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                total_duration_seconds=time.time() - task_start
            )

        finally:
            # Cleanup repo
            try:
                self.repo_manager.cleanup_run(f"task_{task.id}")
            except Exception as e:
                logger.warning(f"  Failed to cleanup repo: {e}")

    def _print_summary(self, summary):
        """Print experiment summary."""
        print(f"\n📊 EXPERIMENT SUMMARY")
        print(f"{'='*80}\n")

        print(f"Tasks: {summary.total_tasks}")
        print(f"\nSuccess Rates:")
        print(f"  Vanilla:      {summary.vanilla_successes}/{summary.total_tasks} ({summary.vanilla_success_rate*100:.1f}%)")
        print(f"  Walkthrough:  {summary.walkthrough_successes}/{summary.total_tasks} ({summary.walkthrough_success_rate*100:.1f}%)")
        print(f"  Improvement:  {summary.success_rate_improvement*100:+.1f}%")

        print(f"\nComparison:")
        print(f"  Both succeeded:        {summary.both_succeeded}")
        print(f"  Both failed:           {summary.both_failed}")
        print(f"  Vanilla only success:  {summary.vanilla_only_success}")
        print(f"  Walkthrough only:      {summary.walkthrough_only_success}")

        print(f"\nEfficiency:")
        print(f"  Avg vanilla time:      {summary.avg_vanilla_duration_seconds:.1f}s")
        print(f"  Avg walkthrough time:  {summary.avg_walkthrough_duration_seconds:.1f}s")
        print(f"  Time reduction:        {summary.time_reduction*100:+.1f}%")

        print(f"\nToken Usage:")
        print(f"  Total vanilla:         {summary.total_vanilla_tokens:,}")
        print(f"  Total walkthrough:     {summary.total_walkthrough_tokens:,} (incl. generation)")
        print(f"  Token increase:        {summary.token_increase*100:+.1f}%")

        print(f"\nTool Calls:")
        print(f"  Avg vanilla:           {summary.avg_vanilla_tool_calls:.1f}")
        print(f"  Avg walkthrough:       {summary.avg_walkthrough_tool_calls:.1f}")

    def cleanup(self):
        """Cleanup resources."""
        try:
            self.docker_harness.cleanup()
        except Exception as e:
            logger.warning(f"Failed to cleanup: {e}")
