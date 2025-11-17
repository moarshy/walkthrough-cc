# Batch Experiment Runner

Run multiple tasks in parallel with configurable workers to efficiently test vanilla vs walkthrough agents across your entire task suite.

## Quick Start

```bash
# Run all 10 FastAPI tasks with 3 parallel workers (default)
python run_batch_experiment.py

# Run with 5 parallel workers
python run_batch_experiment.py --workers 5

# Run specific tasks
python run_batch_experiment.py --tasks 1 2 3

# Run a range of tasks
python run_batch_experiment.py --tasks 1-5

# Run only beginner tasks
python run_batch_experiment.py --difficulty beginner

# Combine options
python run_batch_experiment.py --workers 2 --difficulty intermediate
```

## Features

### ✅ Parallel Execution
- Run multiple tasks concurrently with configurable workers
- Default: 3 workers (good balance for most systems)
- Each task runs vanilla + walkthrough agents in parallel
- Efficient use of compute resources

### ✅ Flexible Filtering
- **By task number**: `--tasks 1 2 3` or `--tasks 1-5`
- **By difficulty**: `--difficulty beginner|intermediate|advanced`
- **Custom task file**: `--task-file path/to/tasks.json`

### ✅ Comprehensive Results
- Per-task results saved in separate directories
- Batch summary with success rates, tokens, timing
- JSON format for easy analysis and visualization

### ✅ Progress Tracking
- Real-time console output for each task
- Clear success/failure indicators
- Token usage and timing metrics

## Command-Line Options

```
usage: run_batch_experiment.py [-h] [--workers W] [--tasks T [T ...]]
                               [--difficulty {beginner,intermediate,advanced}]
                               [--task-file TASK_FILE]

optional arguments:
  -h, --help            show this help message and exit
  --workers W, -w W     Number of parallel workers (default: 3)
  --tasks T [T ...], -t T [T ...]
                        Specific tasks to run (e.g., '1 2 3' or '1-5')
  --difficulty D, -d D  Run only tasks of specific difficulty
  --task-file TASK_FILE
                        Path to tasks JSON file (default: tasks/fastapi_tasks.json)
```

## Examples

### Run All Tasks

```bash
# Default: 3 workers
python run_batch_experiment.py

# With 5 workers (faster, more resource-intensive)
python run_batch_experiment.py --workers 5
```

### Run Specific Tasks

```bash
# Run tasks 1, 2, and 3
python run_batch_experiment.py --tasks 1 2 3

# Run tasks 1 through 5
python run_batch_experiment.py --tasks 1-5

# Run tasks 1-3 and 7-9
python run_batch_experiment.py --tasks 1-3 7-9
```

### Filter by Difficulty

```bash
# Run only beginner tasks (1-3)
python run_batch_experiment.py --difficulty beginner

# Run only intermediate tasks (4-7)
python run_batch_experiment.py --difficulty intermediate

# Run only advanced tasks (8-10)
python run_batch_experiment.py --difficulty advanced
```

### Combine Options

```bash
# Run beginner tasks with 2 workers
python run_batch_experiment.py --workers 2 --difficulty beginner

# Run tasks 1-3 with 5 workers
python run_batch_experiment.py --workers 5 --tasks 1-3

# Run specific intermediate tasks
python run_batch_experiment.py --tasks 4 5 6 --difficulty intermediate
```

## Output Structure

```
experiments/
└── batch_a1b2c3d4/                    # Batch ID (8-char UUID)
    ├── batch_summary.json             # Overall batch results
    ├── fastapi-01-first-steps/        # Task-specific directory
    │   ├── results.json               # Task results
    │   ├── walkthroughs/              # Generated walkthrough
    │   │   └── fastapi-01-first-steps.json
    │   ├── vanilla_workspace/         # Vanilla agent workspace
    │   ├── vanilla_logs/              # Vanilla agent logs
    │   │   ├── vanilla_agent.log
    │   │   ├── vanilla_messages.jsonl
    │   │   └── tools.jsonl
    │   ├── walkthrough_workspace/     # Walkthrough agent workspace
    │   └── walkthrough_logs/          # Walkthrough agent logs
    │       ├── walkthrough_agent.log
    │       ├── walkthrough_messages.jsonl
    │       └── tools.jsonl
    ├── fastapi-02-path-parameters/    # Next task...
    └── repo/                          # Shared cloned repository
```

## Batch Summary JSON

The `batch_summary.json` file contains:

```json
{
  "batch_id": "a1b2c3d4",
  "started_at": "2025-01-17T10:30:00",
  "duration_seconds": 1234.5,
  "workers": 3,
  "total_tasks": 10,
  "filters": {
    "difficulty": null,
    "task_ids": null
  },
  "results": [
    {
      "task_id": "fastapi-01-first-steps",
      "difficulty": "beginner",
      "started_at": "2025-01-17T10:30:01",
      "duration_seconds": 123.4,
      "vanilla": {
        "success": true,
        "agent_completed": true,
        "validation_passed": true,
        "duration": 45.2,
        "tokens": {
          "total": 12500,
          "input": 8000,
          "output": 4500,
          "cache_creation": 5000,
          "cache_read": 3000
        },
        "tool_calls": 25,
        "errors": 0
      },
      "walkthrough": {
        "success": true,
        "agent_completed": true,
        "validation_passed": true,
        "duration": 38.7,
        "tokens": {
          "total": 9800,
          "input": 6500,
          "output": 3300,
          "cache_creation": 4000,
          "cache_read": 2500
        },
        "tool_calls": 18,
        "errors": 0
      }
    }
    // ... more task results
  ],
  "summary": {
    "vanilla_successes": 8,
    "walkthrough_successes": 9,
    "both_successes": 7,
    "vanilla_success_rate": 0.8,
    "walkthrough_success_rate": 0.9,
    "total_vanilla_tokens": 125000,
    "total_walkthrough_tokens": 98000
  }
}
```

## Performance Considerations

### Worker Count

The optimal number of workers depends on your system:

- **Low resources** (4 CPU, 8GB RAM): Use `--workers 1` or `--workers 2`
- **Medium resources** (8 CPU, 16GB RAM): Use `--workers 3` (default)
- **High resources** (16+ CPU, 32+ GB RAM): Use `--workers 5` or more

Each worker runs:
- 1 Docker container for vanilla agent
- 1 Docker container for walkthrough agent
- Repository cloning and walkthrough generation

**Memory estimation**: ~2-3GB per worker

### Parallel vs Sequential

**Parallel benefits:**
- Much faster overall execution
- Better resource utilization
- Runs independent tasks concurrently

**Sequential benefits (workers=1):**
- Lower memory usage
- Easier debugging (clearer logs)
- More stable on resource-constrained systems

## Tips

### 1. Start Small

Test with a few tasks first:
```bash
python run_batch_experiment.py --tasks 1 2 3 --workers 2
```

### 2. Monitor Resources

Watch CPU, memory, and Docker containers:
```bash
docker stats
htop  # or top
```

### 3. Debug Individual Tasks

If a task fails, run it individually with the original script:
```bash
# Edit run_full_experiment.py to use the specific task
python run_full_experiment.py
```

### 4. Incremental Testing

Test by difficulty level:
```bash
# Test beginner first
python run_batch_experiment.py --difficulty beginner

# Then intermediate
python run_batch_experiment.py --difficulty intermediate

# Finally advanced
python run_batch_experiment.py --difficulty advanced
```

### 5. Analyze Results

Use `jq` to analyze batch summary:
```bash
# Overall success rate
jq '.summary' experiments/batch_*/batch_summary.json

# Task-level results
jq '.results[] | select(.vanilla.success == false)' experiments/batch_*/batch_summary.json

# Token comparison
jq '.results[] | {task: .task_id, vanilla_tokens: .vanilla.tokens.total, walkthrough_tokens: .walkthrough.tokens.total}' experiments/batch_*/batch_summary.json
```

## Troubleshooting

### Error: "Docker daemon not running"
```bash
# Start Docker
# macOS: Open Docker Desktop
# Linux: sudo systemctl start docker
```

### Error: "Out of memory"
```bash
# Reduce workers
python run_batch_experiment.py --workers 1

# Or increase Docker memory limit in Docker Desktop settings
```

### Error: "Port already in use"
```bash
# Clean up lingering containers
docker ps -a | grep cc-agent | awk '{print $1}' | xargs docker rm -f

# Clean up processes on port 8000
lsof -ti:8000 | xargs kill -9
```

### Tasks hanging
```bash
# Check Docker containers
docker ps

# Check logs of running container
docker logs <container_id>

# Force stop all containers
docker ps -q | xargs docker stop
```

## Next Steps

After running batch experiments:

1. **Analyze results**: Check `batch_summary.json` for success rates
2. **Review failures**: Examine logs in task directories
3. **Compare approaches**: Look at token usage, timing, error patterns
4. **Iterate**: Improve prompts, walkthroughs, or validation based on findings

## Related Documentation

- **Task Creation**: See `tasks/README.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Single Task**: Use `run_full_experiment.py` for detailed debugging
