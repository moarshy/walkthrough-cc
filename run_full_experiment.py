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
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from our cc_experiment_runner package
from cc_experiment_runner import (
    Task,
    TaskValidation,
    DockerHarness,
    WalkthroughGenerator
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
    id="nextjs-getting-started",
    library_name="Next.js",
    library_version="14.0",
    repo_url="https://github.com/vercel/next.js",
    branch="canary",
    docs_folder="docs",
    target_doc="01-app/01-getting-started/01-installation.mdx",
    validation=TaskValidation(type="command", command="npm run dev", port=3000, timeout=60)
)

# Setup output directory
output = Path("results/full_experiment")
output.mkdir(parents=True, exist_ok=True)

print(f"📁 Output: {output}\n")

def main():
    # Step 1: Clone repository
    print("Step 1/5: Cloning repository...")

    repo_dir = output / "repo"
    if repo_dir.exists():
        import shutil
        shutil.rmtree(repo_dir)

    # Clone repo
    import subprocess
    subprocess.run(
        ["git", "clone", "--branch", task.branch, "--depth", "1", task.repo_url, str(repo_dir)],
        check=True,
        capture_output=True
    )

    docs_path = repo_dir / task.docs_folder
    target_doc_path = docs_path / task.target_doc

    print(f"✅ Repository cloned to: {repo_dir}")
    print(f"   Docs folder: {docs_path}")
    print(f"   Target doc: {target_doc_path}\n")

    # Step 2: Generate walkthrough using WalkthroughGenerator
    print("Step 2/5: Generating walkthrough...")

    walkthrough_output_dir = output / "walkthroughs"
    walkthrough_output_dir.mkdir(parents=True, exist_ok=True)
    walkthrough_file = walkthrough_output_dir / f"{task.id}.json"

    generator = WalkthroughGenerator(api_key=os.getenv('ANTHROPIC_API_KEY'))

    try:
        # Read doc content
        doc_content = target_doc_path.read_text()

        walkthrough = generator.generate_from_doc(
            doc_content=doc_content,
            library_name=task.library_name,
            task_description=f"Set up {task.library_name} following {task.target_doc}"
        )

        # Save walkthrough
        walkthrough_file.write_text(json.dumps(walkthrough, indent=2))

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

    # Setup workspaces
    vanilla_workspace = output / "vanilla_workspace"
    vanilla_workspace.mkdir(exist_ok=True)
    vanilla_logs = output / "vanilla_logs"
    vanilla_logs.mkdir(exist_ok=True)

    walkthrough_workspace = output / "walkthrough_workspace"
    walkthrough_workspace.mkdir(exist_ok=True)
    walkthrough_logs = output / "walkthrough_logs"
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

    # Save results with full token breakdown
    results = {
        "task": task.id,
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

    (output / "results.json").write_text(json.dumps(results, indent=2))
    print(f"📊 Results saved: {output}/results.json\n")

    # Cleanup
    harness.cleanup()

    sys.exit(0 if (vanilla_result.success and walkthrough_result.success) else 1)

if __name__ == "__main__":
    main()
