#!/usr/bin/env python3
"""
Main entry point for running vanilla CC vs walkthrough CC experiments.

Usage:
    # Run all tasks
    python run_experiment.py

    # Run specific tasks
    python run_experiment.py --task-ids nextjs-getting-started react-tutorial

    # Run with parallel workers
    python run_experiment.py --parallel 3

    # Custom output directory
    python run_experiment.py --output results/custom_run
"""

import os
import sys
import json
import argparse
import asyncio
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.schemas import Task
from src.runner import ExperimentRunner

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def load_tasks(tasks_file: Path, task_ids: list = None) -> list[Task]:
    """Load tasks from JSON file."""
    print(f"{BLUE}Loading tasks from: {tasks_file}{RESET}")

    if not tasks_file.exists():
        print(f"{RED}Error: Tasks file not found: {tasks_file}{RESET}")
        sys.exit(1)

    with open(tasks_file, 'r') as f:
        data = json.load(f)

    tasks = [Task(**task_data) for task_data in data['tasks']]

    # Filter by task IDs if specified
    if task_ids:
        tasks = [t for t in tasks if t.id in task_ids]
        if not tasks:
            print(f"{RED}Error: No tasks found matching IDs: {task_ids}{RESET}")
            sys.exit(1)

    print(f"{GREEN}✓{RESET} Loaded {len(tasks)} tasks")
    return tasks


def check_prerequisites():
    """Check that all prerequisites are met."""
    print(f"\n{BOLD}{BLUE}Checking Prerequisites{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

    all_ok = True

    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        print(f"{GREEN}✓{RESET} ANTHROPIC_API_KEY is set")
    else:
        print(f"{RED}✗{RESET} ANTHROPIC_API_KEY not set")
        print(f"  Export it first: export ANTHROPIC_API_KEY=your-key-here")
        all_ok = False

    # Check Docker
    try:
        import docker
        client = docker.from_env()
        client.ping()
        print(f"{GREEN}✓{RESET} Docker is running")
    except Exception as e:
        print(f"{RED}✗{RESET} Docker not available: {e}")
        all_ok = False

    # Check if Docker image exists
    try:
        import docker
        client = docker.from_env()
        try:
            client.images.get("cc-experiment:latest")
            print(f"{GREEN}✓{RESET} Docker image 'cc-experiment:latest' exists")
        except docker.errors.ImageNotFound:
            print(f"{YELLOW}⚠{RESET}  Docker image 'cc-experiment:latest' not found")
            print(f"  Build it with: docker build -t cc-experiment:latest .")
            all_ok = False
    except:
        pass

    # Check Python dependencies
    try:
        import pydantic
        print(f"{GREEN}✓{RESET} pydantic installed")
    except ImportError:
        print(f"{RED}✗{RESET} pydantic not installed")
        print(f"  Install with: pip install pydantic")
        all_ok = False

    try:
        import git
        print(f"{GREEN}✓{RESET} GitPython installed")
    except ImportError:
        print(f"{YELLOW}⚠{RESET}  GitPython not installed (needed for repo cloning)")
        print(f"  Install with: pip install gitpython")
        all_ok = False

    print()
    return all_ok


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run vanilla CC vs walkthrough CC experiment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tasks
  python run_experiment.py

  # Run specific tasks
  python run_experiment.py --task-ids nextjs-getting-started react-tutorial

  # Run with parallel workers
  python run_experiment.py --parallel 3

  # Custom output directory
  python run_experiment.py --output results/custom_run

  # Run with custom timeout
  python run_experiment.py --timeout 3600
        """
    )

    parser.add_argument(
        '--tasks',
        default='experiments/tasks.json',
        help='Path to tasks JSON file (default: experiments/tasks.json)'
    )

    parser.add_argument(
        '--task-ids',
        nargs='+',
        help='Specific task IDs to run (default: all tasks)'
    )

    parser.add_argument(
        '--output',
        default=None,
        help='Output directory (default: results/exp_TIMESTAMP)'
    )

    parser.add_argument(
        '--parallel',
        type=int,
        default=1,
        help='Number of parallel workers (default: 1)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=7200,
        help='Timeout per agent execution in seconds (default: 7200 = 2 hours)'
    )

    parser.add_argument(
        '--skip-checks',
        action='store_true',
        help='Skip prerequisite checks'
    )

    args = parser.parse_args()

    # Print header
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}Vanilla CC vs Walkthrough CC Experiment{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

    # Check prerequisites
    if not args.skip_checks:
        if not check_prerequisites():
            print(f"\n{RED}Prerequisites not met. Fix the issues above and try again.{RESET}")
            print(f"Or use --skip-checks to skip this check (not recommended).\n")
            return 1

    # Load tasks
    tasks_file = Path(args.tasks)
    tasks = load_tasks(tasks_file, args.task_ids)

    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"results/exp_{timestamp}")

    # Print configuration
    print(f"\n{BOLD}Configuration:{RESET}")
    print(f"  Tasks: {len(tasks)}")
    if args.task_ids:
        print(f"  Task IDs: {', '.join(args.task_ids)}")
    print(f"  Parallel workers: {args.parallel}")
    print(f"  Timeout: {args.timeout}s ({args.timeout/60:.1f} min)")
    print(f"  Output: {output_dir}")

    # Confirm
    print(f"\n{YELLOW}This will:${RESET}")
    print(f"  1. Clone {len(tasks)} repositories")
    print(f"  2. Generate {len(tasks)} walkthroughs using Claude Code")
    print(f"  3. Run {len(tasks)*2} agents (vanilla + walkthrough for each task)")
    print(f"  4. Compare results and generate report")
    print(f"\n{YELLOW}Estimated time: {len(tasks) * 15 / args.parallel:.0f}-{len(tasks) * 30 / args.parallel:.0f} minutes{RESET}")
    print(f"{YELLOW}Estimated tokens: ~{len(tasks) * 250000:,} (including generation){RESET}\n")

    response = input(f"Continue? [y/N]: ")
    if response.lower() != 'y':
        print(f"{YELLOW}Aborted.{RESET}")
        return 0

    # Run experiment
    try:
        runner = ExperimentRunner(
            tasks=tasks,
            output_dir=output_dir,
            parallel_workers=args.parallel,
            timeout_seconds=args.timeout
        )

        results = await runner.run_experiment()

        print(f"\n{GREEN}{BOLD}✓ Experiment completed successfully!{RESET}\n")
        return 0

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Experiment interrupted by user.{RESET}")
        return 130

    except Exception as e:
        print(f"\n{RED}Experiment failed: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        try:
            runner.cleanup()
        except:
            pass


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
