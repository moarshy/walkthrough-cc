#!/usr/bin/env python3
"""
Batch Experiment Runner: Run multiple tasks in parallel with configurable workers.

Usage:
    python run_batch_experiment.py                           # Run all tasks, 3 workers
    python run_batch_experiment.py --workers 5               # Run all tasks, 5 workers
    python run_batch_experiment.py --tasks 1 2 3             # Run specific tasks
    python run_batch_experiment.py --workers 2 --tasks 1-5   # Run tasks 1-5 with 2 workers
    python run_batch_experiment.py --difficulty beginner     # Run only beginner tasks
"""

import os
import sys
import json
import uuid
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Import from our cc_experiment_runner package
from cc_experiment_runner import (
    Task,
    DockerHarness,
    WalkthroughGenerator,
    RepositoryManager,
)

load_dotenv()

if not os.getenv('ANTHROPIC_API_KEY'):
    print("❌ ANTHROPIC_API_KEY not in .env")
    sys.exit(1)


def load_tasks_from_file(task_file: Path) -> List[Dict[str, Any]]:
    """Load tasks from JSON file."""
    with open(task_file) as f:
        data = json.load(f)
    return data.get("tasks", []), data.get("metadata", {})


def filter_tasks(
    tasks: List[Dict[str, Any]],
    task_ids: List[str] = None,
    difficulty: str = None
) -> List[Dict[str, Any]]:
    """Filter tasks by IDs or difficulty."""
    filtered = tasks

    if task_ids:
        filtered = [t for t in filtered if t["instance_id"] in task_ids]

    if difficulty:
        filtered = [t for t in filtered if t.get("difficulty") == difficulty]

    return filtered


def parse_task_range(task_str: str, total_tasks: int) -> List[int]:
    """Parse task specification like '1-5' or '1,3,5'."""
    task_nums = []

    for part in task_str.split(','):
        part = part.strip()
        if '-' in part:
            # Range: "1-5"
            start, end = part.split('-')
            task_nums.extend(range(int(start), int(end) + 1))
        else:
            # Single task: "3"
            task_nums.append(int(part))

    # Convert to instance IDs (fastapi-01-*, fastapi-02-*, etc.)
    return [f"fastapi-{num:02d}-" for num in task_nums]


def run_single_task_experiment(
    task_dict: Dict[str, Any],
    experiment_root: Path,
    shared_repo_dir: Path,
    harness: DockerHarness
) -> Dict[str, Any]:
    """Run a single task experiment (vanilla + walkthrough)."""
    instance_id = task_dict["instance_id"]
    start_time = time.time()

    print(f"\n{'='*70}")
    print(f"🚀 Task: {instance_id}")
    print(f"{'='*70}")

    # Create task directory
    task_dir = experiment_root / instance_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Convert dict to Task object
    task = Task(**task_dict)

    try:
        # Step 1: Use shared repository
        print(f"[{instance_id}] Step 1/5: Using shared repository...")

        repo_dir = shared_repo_dir
        docs_path = repo_dir / task.docs_folder
        target_doc_path = docs_path / task.target_doc

        if not target_doc_path.exists():
            raise FileNotFoundError(f"Target doc not found: {target_doc_path}")

        print(f"[{instance_id}] ✅ Repository ready")
        print(f"[{instance_id}]    Docs: {docs_path}")
        print(f"[{instance_id}]    Target doc: {target_doc_path}")

        # Step 2: Generate walkthrough
        print(f"[{instance_id}] Step 2/5: Generating walkthrough...")

        walkthrough_dir = task_dir / "walkthroughs"
        walkthrough_dir.mkdir(exist_ok=True)
        walkthrough_file = walkthrough_dir / f"{task.instance_id}.json"

        generator = WalkthroughGenerator(api_key=os.getenv('ANTHROPIC_API_KEY'))

        walkthrough = generator.generate_from_file(
            doc_path=target_doc_path,
            library_name="FastAPI",
            task_description=f"Set up FastAPI following {task.target_doc}",
            output_file=walkthrough_file,
            repo_path=repo_dir,
            docs_folder=task.docs_folder
        )

        print(f"[{instance_id}] ✅ Walkthrough generated")
        print(f"[{instance_id}]    Steps: {len(walkthrough.get('steps', []))}")

        # Step 3 & 4: Run BOTH agents in parallel
        print(f"[{instance_id}] Step 3/5: Running VANILLA and WALKTHROUGH agents in parallel...")

        # Setup workspaces
        vanilla_workspace = task_dir / "vanilla_workspace"
        vanilla_workspace.mkdir(exist_ok=True)

        walkthrough_workspace = task_dir / "walkthrough_workspace"
        walkthrough_workspace.mkdir(exist_ok=True)

        # Setup logs
        vanilla_logs = task_dir / "vanilla_logs"
        vanilla_logs.mkdir(exist_ok=True)

        walkthrough_logs = task_dir / "walkthrough_logs"
        walkthrough_logs.mkdir(exist_ok=True)

        # Run both agents in parallel
        def run_vanilla():
            print(f"[{instance_id}]   → Starting VANILLA agent...")
            return harness.run_agent(
                task=task,
                agent_type="vanilla",
                repo_path=vanilla_workspace,
                docs_path=docs_path,
                walkthrough_path=None,
                log_dir=vanilla_logs
            )

        def run_walkthrough():
            print(f"[{instance_id}]   → Starting WALKTHROUGH agent...")
            return harness.run_agent(
                task=task,
                agent_type="walkthrough",
                repo_path=walkthrough_workspace,
                docs_path=docs_path,
                walkthrough_path=walkthrough_file,
                log_dir=walkthrough_logs
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            vanilla_future = executor.submit(run_vanilla)
            walkthrough_future = executor.submit(run_walkthrough)

            vanilla_result = vanilla_future.result()
            walkthrough_result = walkthrough_future.result()

        print(f"[{instance_id}] ✅ Agents completed")
        print(f"[{instance_id}]    Vanilla: {'SUCCESS' if vanilla_result.success else 'FAILED'} ({vanilla_result.duration_seconds:.1f}s)")
        print(f"[{instance_id}]    Walkthrough: {'SUCCESS' if walkthrough_result.success else 'FAILED'} ({walkthrough_result.duration_seconds:.1f}s)")

        # Step 5: Save results
        print(f"[{instance_id}] Step 5/5: Saving results...")

        results = {
            "task_id": instance_id,
            "difficulty": task_dict.get("difficulty", "unknown"),
            "started_at": datetime.now().isoformat(),
            "duration_seconds": time.time() - start_time,
            "vanilla": {
                "success": vanilla_result.success,
                "agent_completed": vanilla_result.agent_completed,
                "validation_passed": vanilla_result.validation_passed,
                "duration": vanilla_result.duration_seconds,
                "tokens": {
                    "total": vanilla_result.token_usage.total_tokens,
                    "input": vanilla_result.token_usage.input_tokens,
                    "output": vanilla_result.token_usage.output_tokens,
                    "cache_creation": vanilla_result.token_usage.cache_creation_input_tokens,
                    "cache_read": vanilla_result.token_usage.cache_read_input_tokens
                },
                "tool_calls": vanilla_result.tool_calls.total_calls,
                "errors": vanilla_result.tool_calls.total_errors,
                "error_message": vanilla_result.error_message
            },
            "walkthrough": {
                "success": walkthrough_result.success,
                "agent_completed": walkthrough_result.agent_completed,
                "validation_passed": walkthrough_result.validation_passed,
                "duration": walkthrough_result.duration_seconds,
                "tokens": {
                    "total": walkthrough_result.token_usage.total_tokens,
                    "input": walkthrough_result.token_usage.input_tokens,
                    "output": walkthrough_result.token_usage.output_tokens,
                    "cache_creation": walkthrough_result.token_usage.cache_creation_input_tokens,
                    "cache_read": walkthrough_result.token_usage.cache_read_input_tokens
                },
                "tool_calls": walkthrough_result.tool_calls.total_calls,
                "errors": walkthrough_result.tool_calls.total_errors,
                "error_message": walkthrough_result.error_message
            }
        }

        results_file = task_dir / "results.json"
        results_file.write_text(json.dumps(results, indent=2))

        print(f"[{instance_id}] ✅ Results saved: {results_file}")
        print(f"[{instance_id}] 🎉 Task completed in {time.time() - start_time:.1f}s")

        return results

    except Exception as e:
        print(f"[{instance_id}] ❌ Task failed: {e}")
        import traceback
        traceback.print_exc()

        error_results = {
            "task_id": instance_id,
            "difficulty": task_dict.get("difficulty", "unknown"),
            "started_at": datetime.now().isoformat(),
            "duration_seconds": time.time() - start_time,
            "error": str(e),
            "success": False
        }

        results_file = task_dir / "results.json"
        results_file.write_text(json.dumps(error_results, indent=2))

        return error_results


def main():
    parser = argparse.ArgumentParser(
        description="Run batch experiments on multiple tasks in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_batch_experiment.py                           # Run all tasks, 3 workers
  python run_batch_experiment.py --workers 5               # Run all tasks, 5 workers
  python run_batch_experiment.py --tasks 1 2 3             # Run specific tasks (1, 2, 3)
  python run_batch_experiment.py --tasks 1-5               # Run tasks 1 through 5
  python run_batch_experiment.py --difficulty beginner     # Run only beginner tasks
  python run_batch_experiment.py --workers 2 --tasks 1-3   # Run tasks 1-3 with 2 workers
        """
    )

    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3)"
    )

    parser.add_argument(
        "--tasks", "-t",
        type=str,
        nargs="+",
        help="Specific tasks to run (e.g., '1 2 3' or '1-5')"
    )

    parser.add_argument(
        "--difficulty", "-d",
        choices=["beginner", "intermediate", "advanced"],
        help="Run only tasks of specific difficulty"
    )

    parser.add_argument(
        "--task-file",
        type=Path,
        default=Path("tasks/fastapi_tasks.json"),
        help="Path to tasks JSON file (default: tasks/fastapi_tasks.json)"
    )

    args = parser.parse_args()

    # Load tasks
    if not args.task_file.exists():
        print(f"❌ Task file not found: {args.task_file}")
        sys.exit(1)

    tasks, metadata = load_tasks_from_file(args.task_file)

    # Filter tasks based on arguments
    if args.tasks:
        # Parse task range/list
        task_filter = []
        for task_spec in args.tasks:
            if '-' in task_spec:
                # Range like "1-5"
                task_filter.extend(parse_task_range(task_spec, len(tasks)))
            else:
                # Single task number
                task_filter.append(f"fastapi-{int(task_spec):02d}-")

        # Filter tasks by prefix match
        tasks = [t for t in tasks if any(t["instance_id"].startswith(prefix) for prefix in task_filter)]

    if args.difficulty:
        tasks = filter_tasks(tasks, difficulty=args.difficulty)

    if not tasks:
        print("❌ No tasks matched the filter criteria")
        sys.exit(1)

    print("="*70)
    print("BATCH EXPERIMENT: Vanilla vs Walkthrough")
    print("="*70)
    print(f"📋 Library: {metadata.get('library', 'Unknown')} v{metadata.get('version', 'Unknown')}")
    print(f"📊 Tasks to run: {len(tasks)}")
    print(f"👥 Parallel workers: {args.workers}")
    print(f"📁 Task file: {args.task_file}")
    if args.difficulty:
        print(f"🎯 Difficulty filter: {args.difficulty}")
    print("="*70 + "\n")

    # Show task list
    print("Tasks to run:")
    for i, task in enumerate(tasks, 1):
        difficulty = task.get("difficulty", "unknown")
        print(f"  {i}. {task['instance_id']} ({difficulty})")
    print()

    # Generate batch UUID
    batch_id = str(uuid.uuid4())[:8]
    batch_dir = Path("experiments") / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    print(f"🆔 Batch ID: {batch_id}")
    print(f"📁 Batch directory: {batch_dir}\n")

    # Initialize shared resources
    repo_manager = RepositoryManager(base_data_dir=batch_dir)
    harness = DockerHarness()

    # Clone repository once (all tasks use the same FastAPI repo)
    print("📦 Cloning shared repository...")
    first_task = tasks[0]
    repo_context = repo_manager.clone_repository(
        repo_url=first_task["repo_url"],
        branch=first_task.get("branch", "master"),
        run_id="shared_repo",  # Single shared repo
        library_name="FastAPI",
        library_version="0.100",
        docs_path=first_task["docs_folder"]
    )
    shared_repo_dir = repo_context.repo_dir
    print(f"✅ Repository cloned: {shared_repo_dir}")
    print(f"   Commit: {repo_context.commit_hash}\n")

    # Run tasks in parallel
    batch_start = time.time()
    all_results = []

    print(f"🚀 Starting {len(tasks)} tasks with {args.workers} parallel workers...\n")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                run_single_task_experiment,
                task,
                batch_dir,
                shared_repo_dir,
                harness
            ): task for task in tasks
        }

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                print(f"❌ Task {task['instance_id']} generated an exception: {e}")
                all_results.append({
                    "task_id": task["instance_id"],
                    "error": str(e),
                    "success": False
                })

    batch_duration = time.time() - batch_start

    # Generate batch summary
    print(f"\n{'='*70}")
    print("BATCH SUMMARY")
    print(f"{'='*70}")

    total_tasks = len(all_results)
    vanilla_successes = sum(1 for r in all_results if r.get("vanilla", {}).get("success", False))
    walkthrough_successes = sum(1 for r in all_results if r.get("walkthrough", {}).get("success", False))
    both_successes = sum(1 for r in all_results if r.get("vanilla", {}).get("success", False) and r.get("walkthrough", {}).get("success", False))

    print(f"Total tasks: {total_tasks}")
    print(f"Vanilla successes: {vanilla_successes}/{total_tasks} ({vanilla_successes/total_tasks*100:.1f}%)")
    print(f"Walkthrough successes: {walkthrough_successes}/{total_tasks} ({walkthrough_successes/total_tasks*100:.1f}%)")
    print(f"Both succeeded: {both_successes}/{total_tasks} ({both_successes/total_tasks*100:.1f}%)")
    print(f"Total duration: {batch_duration:.1f}s ({batch_duration/60:.1f} minutes)")
    print(f"Average per task: {batch_duration/total_tasks:.1f}s")

    # Token summary
    total_vanilla_tokens = sum(r.get("vanilla", {}).get("tokens", {}).get("total", 0) for r in all_results)
    total_walkthrough_tokens = sum(r.get("walkthrough", {}).get("tokens", {}).get("total", 0) for r in all_results)

    print(f"\nToken usage:")
    print(f"  Vanilla: {total_vanilla_tokens:,}")
    print(f"  Walkthrough: {total_walkthrough_tokens:,}")
    print(f"  Total: {total_vanilla_tokens + total_walkthrough_tokens:,}")

    # Save batch summary
    batch_summary = {
        "batch_id": batch_id,
        "started_at": datetime.now().isoformat(),
        "duration_seconds": batch_duration,
        "workers": args.workers,
        "total_tasks": total_tasks,
        "filters": {
            "difficulty": args.difficulty,
            "task_ids": args.tasks
        },
        "results": all_results,
        "summary": {
            "vanilla_successes": vanilla_successes,
            "walkthrough_successes": walkthrough_successes,
            "both_successes": both_successes,
            "vanilla_success_rate": vanilla_successes / total_tasks if total_tasks > 0 else 0,
            "walkthrough_success_rate": walkthrough_successes / total_tasks if total_tasks > 0 else 0,
            "total_vanilla_tokens": total_vanilla_tokens,
            "total_walkthrough_tokens": total_walkthrough_tokens
        }
    }

    batch_summary_file = batch_dir / "batch_summary.json"
    batch_summary_file.write_text(json.dumps(batch_summary, indent=2))

    print(f"\n📊 Batch summary saved: {batch_summary_file}")
    print(f"📁 Results directory: {batch_dir}")
    print("="*70 + "\n")

    # Exit with error code if any task failed
    if vanilla_successes < total_tasks or walkthrough_successes < total_tasks:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
