#!/usr/bin/env python3
"""
Analyze experiment results and provide detailed failure insights.

Usage:
    python scripts/analyze_experiment.py experiments/124470d3
"""

import json
import sys
from pathlib import Path


def analyze_experiment(experiment_dir: Path):
    """Analyze an experiment and print detailed results."""

    print("="*70)
    print(f"EXPERIMENT ANALYSIS: {experiment_dir.name}")
    print("="*70 + "\n")

    # Load results
    results_file = experiment_dir / "results.json"
    if not results_file.exists():
        print(f"❌ No results.json found in {experiment_dir}")
        return

    with open(results_file) as f:
        results = json.load(f)

    # Overall status
    print("📊 OVERALL STATUS")
    print("-" * 70)
    print(f"Task: {results['task']}")
    print(f"Library: {results['library']['name']} {results['library']['version']}")
    print(f"Commit: {results['library']['commit']}")
    print()

    # Analyze each agent
    for agent_type in ['vanilla', 'walkthrough']:
        agent_data = results[agent_type]
        print(f"\n{'🔵 VANILLA AGENT' if agent_type == 'vanilla' else '🟢 WALKTHROUGH AGENT'}")
        print("-" * 70)

        # Success breakdown
        print(f"Overall Success: {'✅' if agent_data['success'] else '❌'}")
        if 'agent_completed' in agent_data:
            print(f"  Agent Completed: {'✅' if agent_data['agent_completed'] else '❌'}")
            print(f"  Validation Passed: {'✅' if agent_data['validation_passed'] else '❌'}")
        print()

        # Validation details
        if 'validation' in agent_data:
            val = agent_data['validation']
            print("Validation Details:")
            print(f"  Exit Code: {val['exit_code']}")
            print(f"  Duration: {val['duration']:.2f}s" if val['duration'] else "  Duration: N/A")
            if val['output']:
                print(f"  Output:")
                for line in val['output'].split('\n')[:10]:  # First 10 lines
                    print(f"    {line}")
            print()

        # Error message
        if agent_data.get('error_message'):
            print(f"❌ Error: {agent_data['error_message']}")
            print()

        # Performance
        print(f"Performance:")
        print(f"  Duration: {agent_data['duration']:.2f}s")
        print(f"  Tool Calls: {agent_data['tool_calls']}")
        print(f"  Tokens: {agent_data['tokens']['total']:,}")
        print(f"    Input: {agent_data['tokens']['input']}")
        print(f"    Output: {agent_data['tokens']['output']}")
        print(f"    Cache Creation: {agent_data['tokens']['cache_creation']:,}")
        print(f"    Cache Read: {agent_data['tokens']['cache_read']:,}")
        print()

        # Tool errors
        errors = agent_data['errors']
        if errors['total'] > 0:
            print(f"⚠️  Tool Errors: {errors['total']}")
            for tool in ['bash', 'read', 'write', 'edit', 'glob', 'grep']:
                if errors[tool] > 0:
                    print(f"    {tool}: {errors[tool]}")
            print()

    # Files created
    print("\n📁 FILES CREATED")
    print("-" * 70)
    for agent_type in ['vanilla', 'walkthrough']:
        workspace = experiment_dir / f"{agent_type}_workspace"
        if workspace.exists():
            files = list(workspace.glob("*.py"))
            print(f"\n{agent_type.capitalize()} Workspace:")
            for f in files:
                print(f"  ✓ {f.name} ({f.stat().st_size} bytes)")

                # Show first few lines
                try:
                    content = f.read_text()
                    lines = content.split('\n')[:5]
                    for line in lines:
                        print(f"      {line}")
                    total_lines = len(content.split('\n'))
                    if total_lines > 5:
                        print(f"      ... ({total_lines} lines total)")
                except Exception as e:
                    print(f"      (Could not read: {e})")

    # Logs
    print("\n\n📝 LOGS")
    print("-" * 70)
    for agent_type in ['vanilla', 'walkthrough']:
        log_dir = experiment_dir / f"{agent_type}_logs"
        if log_dir.exists():
            print(f"\n{agent_type.capitalize()} Logs:")
            log_files = sorted(log_dir.glob("*.log"))
            for log_file in log_files:
                print(f"  📄 {log_file.name}")

    print("\n" + "="*70)
    print(f"\n💡 TIP: Check validation logs for detailed error messages:")
    print(f"   cat {experiment_dir / 'vanilla_logs/vanilla_validation.log'}")
    print(f"   cat {experiment_dir / 'walkthrough_logs/walkthrough_validation.log'}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_experiment.py <experiment_dir>")
        print("Example: python scripts/analyze_experiment.py experiments/124470d3")
        sys.exit(1)

    experiment_path = Path(sys.argv[1])
    if not experiment_path.exists():
        print(f"❌ Experiment directory not found: {experiment_path}")
        sys.exit(1)

    analyze_experiment(experiment_path)
