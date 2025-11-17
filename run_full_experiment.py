#!/usr/bin/env python3
"""
Full Experiment Pipeline: Generate walkthrough → Run vanilla → Run walkthrough → Compare

Follows the plan.md architecture:
1. Download repository using RepositoryManager
2. Generate walkthrough using WalkthroughGenerator Claude Code agent
3. Run vanilla CC agent in Docker
4. Run walkthrough CC agent in Docker
5. Compare results
"""

import os
import sys
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

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

print("="*70)
print("FULL EXPERIMENT: Vanilla vs Walkthrough")
print("="*70 + "\n")

# Task definition
task = Task(
    id="fastapi-first-steps",
    library_name="FastAPI",
    library_version="0.100",
    repo_url="https://github.com/tiangolo/fastapi",
    branch="master",
    docs_folder="docs/en/docs",
    target_doc="tutorial/first-steps.md",
    validation=TaskValidation(type="command", command="uvicorn main:app --reload", port=8000, timeout=30)
)

# Generate UUID for this experiment run (use short form for readability)
experiment_name = str(uuid.uuid4())[:8]

# Setup experiment directory with UUID
experiment_dir = Path("experiments") / experiment_name
experiment_dir.mkdir(parents=True, exist_ok=True)

print(f"🆔 Experiment: {experiment_name}")
print(f"📁 Directory: {experiment_dir}\n")

def main():
    # Step 1: Clone repository using RepositoryManager
    print("Step 1/5: Cloning repository...")

    repo_manager = RepositoryManager(base_data_dir=experiment_dir)
    repo_context = repo_manager.clone_repository(
        repo_url=task.repo_url,
        branch=task.branch,
        run_id="repo",  # Simple name: experiments/{uuid}/repo/
        library_name=task.library_name,
        library_version=task.library_version,
        docs_path=task.docs_folder
    )

    repo_dir = repo_context.repo_dir
    docs_path = repo_dir / task.docs_folder
    target_doc_path = docs_path / task.target_doc

    print(f"✅ Repository cloned to: {repo_dir}")
    print(f"   Docs folder: {docs_path}")
    print(f"   Target doc: {target_doc_path}")
    print(f"   Commit: {repo_context.commit_hash}\n")

    try:
        # Step 2: Generate walkthrough using WalkthroughGenerator
        print("Step 2/5: Generating walkthrough...")

        walkthrough_dir = experiment_dir / "walkthroughs"
        walkthrough_dir.mkdir(exist_ok=True)
        walkthrough_file = walkthrough_dir / f"{task.id}.json"

        generator = WalkthroughGenerator(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Generate walkthrough with snippet resolution
        walkthrough = generator.generate_from_file(
            doc_path=target_doc_path,
            library_name=task.library_name,
            task_description=f"Set up {task.library_name} following {task.target_doc}",
            output_file=walkthrough_file,
            repo_path=repo_dir,
            docs_folder=task.docs_folder
        )

        print(f"✅ Walkthrough generated: {walkthrough_file.name}")
        print(f"   Title: {walkthrough.get('walkthrough', {}).get('title', 'N/A')}")
        print(f"   Steps: {len(walkthrough.get('steps', []))}\n")

    except Exception as e:
        print(f"❌ Walkthrough generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 3 & 4: Run BOTH agents in parallel
    print("Step 3/5: Running VANILLA and WALKTHROUGH agents in parallel...\n")
    harness = DockerHarness()

    # Setup workspaces (matching past structure: vanilla_workspace, walkthrough_workspace)
    vanilla_workspace = experiment_dir / "vanilla_workspace"
    vanilla_workspace.mkdir(exist_ok=True)

    walkthrough_workspace = experiment_dir / "walkthrough_workspace"
    walkthrough_workspace.mkdir(exist_ok=True)

    # Setup logs (matching past structure: vanilla_logs, walkthrough_logs)
    vanilla_logs = experiment_dir / "vanilla_logs"
    vanilla_logs.mkdir(exist_ok=True)

    walkthrough_logs = experiment_dir / "walkthrough_logs"
    walkthrough_logs.mkdir(exist_ok=True)

    # Run both agents in parallel using ThreadPoolExecutor
    def run_vanilla():
        print("  → Starting VANILLA agent...")
        return harness.run_agent(
            task=task,
            agent_type="vanilla",
            repo_path=vanilla_workspace,
            docs_path=docs_path,
            walkthrough_path=None,
            log_dir=vanilla_logs
        )

    def run_walkthrough():
        print("  → Starting WALKTHROUGH agent...")
        return harness.run_agent(
            task=task,
            agent_type="walkthrough",
            repo_path=walkthrough_workspace,
            docs_path=docs_path,
            walkthrough_path=walkthrough_file,
            log_dir=walkthrough_logs
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        vanilla_future = executor.submit(run_vanilla)
        walkthrough_future = executor.submit(run_walkthrough)

        # Wait for both to complete
        vanilla_result = vanilla_future.result()
        walkthrough_result = walkthrough_future.result()

    print(f"\n✅ Vanilla: {'SUCCESS' if vanilla_result.success else 'FAILED'}")
    print(f"   Duration: {vanilla_result.duration_seconds:.1f}s")
    print(f"   Total Tokens: {vanilla_result.token_usage.total_tokens:,}")
    print(f"     Input: {vanilla_result.token_usage.input_tokens:,}")
    print(f"     Output: {vanilla_result.token_usage.output_tokens:,}")
    print(f"     Cache Creation: {vanilla_result.token_usage.cache_creation_input_tokens:,}")
    print(f"     Cache Read: {vanilla_result.token_usage.cache_read_input_tokens:,}")

    print(f"\n✅ Walkthrough: {'SUCCESS' if walkthrough_result.success else 'FAILED'}")
    print(f"   Duration: {walkthrough_result.duration_seconds:.1f}s")
    print(f"   Total Tokens: {walkthrough_result.token_usage.total_tokens:,}")
    print(f"     Input: {walkthrough_result.token_usage.input_tokens:,}")
    print(f"     Output: {walkthrough_result.token_usage.output_tokens:,}")
    print(f"     Cache Creation: {walkthrough_result.token_usage.cache_creation_input_tokens:,}")
    print(f"     Cache Read: {walkthrough_result.token_usage.cache_read_input_tokens:,}\n")

    # Step 5: Compare results
    print("Step 5/5: Comparison")
    print("="*70)
    print(f"{'Metric':<25} {'Vanilla':<20} {'Walkthrough':<20}")
    print("-"*70)
    print(f"{'Success':<25} {vanilla_result.success!s:<20} {walkthrough_result.success!s:<20}")
    print(f"{'Duration (s)':<25} {vanilla_result.duration_seconds:<20.1f} {walkthrough_result.duration_seconds:<20.1f}")
    print(f"{'Total Tokens':<25} {vanilla_result.token_usage.total_tokens:<20,} {walkthrough_result.token_usage.total_tokens:<20,}")
    print(f"{'  Input Tokens':<25} {vanilla_result.token_usage.input_tokens:<20,} {walkthrough_result.token_usage.input_tokens:<20,}")
    print(f"{'  Output Tokens':<25} {vanilla_result.token_usage.output_tokens:<20,} {walkthrough_result.token_usage.output_tokens:<20,}")
    print(f"{'  Cache Creation':<25} {vanilla_result.token_usage.cache_creation_input_tokens:<20,} {walkthrough_result.token_usage.cache_creation_input_tokens:<20,}")
    print(f"{'  Cache Read':<25} {vanilla_result.token_usage.cache_read_input_tokens:<20,} {walkthrough_result.token_usage.cache_read_input_tokens:<20,}")
    print(f"{'Tool Calls':<25} {vanilla_result.tool_calls.total_calls:<20} {walkthrough_result.tool_calls.total_calls:<20}")
    print(f"{'Tool Errors':<25} {vanilla_result.tool_calls.total_errors:<20} {walkthrough_result.tool_calls.total_errors:<20}")
    print(f"{'  Bash Errors':<25} {vanilla_result.tool_calls.bash_errors:<20} {walkthrough_result.tool_calls.bash_errors:<20}")
    print(f"{'  Read Errors':<25} {vanilla_result.tool_calls.read_errors:<20} {walkthrough_result.tool_calls.read_errors:<20}")
    print(f"{'  Write Errors':<25} {vanilla_result.tool_calls.write_errors:<20} {walkthrough_result.tool_calls.write_errors:<20}")
    print(f"{'  Edit Errors':<25} {vanilla_result.tool_calls.edit_errors:<20} {walkthrough_result.tool_calls.edit_errors:<20}")
    print("="*70 + "\n")

    # Save results with full token breakdown (matching past structure: results.json at root)
    results = {
        "experiment_id": experiment_name,
        "task": task.id,
        "library": {
            "name": task.library_name,
            "version": task.library_version,
            "repo_url": task.repo_url,
            "branch": task.branch,
            "commit": repo_context.commit_hash
        },
        "vanilla": {
            "success": vanilla_result.success,
            "duration": vanilla_result.duration_seconds,
            "tokens": {
                "total": vanilla_result.token_usage.total_tokens,
                "input": vanilla_result.token_usage.input_tokens,
                "output": vanilla_result.token_usage.output_tokens,
                "cache_creation": vanilla_result.token_usage.cache_creation_input_tokens,
                "cache_read": vanilla_result.token_usage.cache_read_input_tokens
            },
            "tool_calls": vanilla_result.tool_calls.total_calls,
            "errors": {
                "total": vanilla_result.tool_calls.total_errors,
                "bash": vanilla_result.tool_calls.bash_errors,
                "read": vanilla_result.tool_calls.read_errors,
                "write": vanilla_result.tool_calls.write_errors,
                "edit": vanilla_result.tool_calls.edit_errors,
                "glob": vanilla_result.tool_calls.glob_errors,
                "grep": vanilla_result.tool_calls.grep_errors
            }
        },
        "walkthrough": {
            "success": walkthrough_result.success,
            "duration": walkthrough_result.duration_seconds,
            "tokens": {
                "total": walkthrough_result.token_usage.total_tokens,
                "input": walkthrough_result.token_usage.input_tokens,
                "output": walkthrough_result.token_usage.output_tokens,
                "cache_creation": walkthrough_result.token_usage.cache_creation_input_tokens,
                "cache_read": walkthrough_result.token_usage.cache_read_input_tokens
            },
            "tool_calls": walkthrough_result.tool_calls.total_calls,
            "errors": {
                "total": walkthrough_result.tool_calls.total_errors,
                "bash": walkthrough_result.tool_calls.bash_errors,
                "read": walkthrough_result.tool_calls.read_errors,
                "write": walkthrough_result.tool_calls.write_errors,
                "edit": walkthrough_result.tool_calls.edit_errors,
                "glob": walkthrough_result.tool_calls.glob_errors,
                "grep": walkthrough_result.tool_calls.grep_errors
            }
        }
    }

    # Save results.json at experiment root (matching past structure)
    results_file = experiment_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2))
    print(f"📊 Results saved: {results_file}\n")

    # Cleanup Docker and repository
    # print("🧹 Cleaning up...")
    # harness.cleanup()
    # repo_manager.cleanup_run("repo")
    # print("✅ Cleanup complete\n")

    print(f"🎉 Experiment complete: {experiment_dir}\n")

    sys.exit(0 if (vanilla_result.success and walkthrough_result.success) else 1)

if __name__ == "__main__":
    main()
