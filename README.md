# Vanilla Claude Code vs Walkthrough Claude Code Experiment

Comparing the effectiveness of vanilla Claude Code (given raw documentation) vs walkthrough-powered Claude Code (given structured step-by-step walkthroughs) on software setup tasks.

## Overview

**Hypothesis:** Providing Claude Code with structured, AI-generated walkthroughs improves task completion rates and efficiency compared to providing only documentation.

**Experiment Design:**
```
For each task:
1. Clone repository at specific commit (reproducibility)
2. Generate walkthrough from documentation (using WalkthroughGenerator)
3. Run vanilla agent (docs only) in Docker
4. Run walkthrough agent (docs + walkthrough) in Docker
5. Compare success rates, token usage, and timing
```

**Key Features:**
- ✅ SetupBench-inspired validation (deterministic success criteria)
- ✅ Docker isolation (clean environment per agent)
- ✅ Parallel execution (configurable workers)
- ✅ Progressive difficulty (beginner → intermediate → advanced)
- ✅ Comprehensive metrics (tokens, timing, tool calls, errors)

## Prerequisites

### Required

- **Python 3.10+**
- **Docker** (running)
- **Git**
- **ANTHROPIC_API_KEY** environment variable

### Install Dependencies

```bash
# Option 1: Using pip
pip install -e .

# Option 2: Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Quick Start

### 1. Set API Key

Create a `.env` file:
```bash
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

Or export:
```bash
export ANTHROPIC_API_KEY=your-key-here
```

### 2. Build Docker Image

```bash
docker build -t cc-experiment-runner:latest -f Dockerfile .
```

### 3. Run Single Task (Testing)

```bash
# Run single task with detailed output
python run_full_experiment.py
```

This runs the default task (`fastapi-01-first-steps`) and shows detailed progress.

### 4. Run Batch Experiments

```bash
# Run all 10 tasks with 3 parallel workers (default)
python run_batch_experiment.py

# Run only beginner tasks
python run_batch_experiment.py --difficulty beginner

# Run specific tasks
python run_batch_experiment.py --tasks 1 2 3

# Run with more workers (faster)
python run_batch_experiment.py --workers 5
```

## Project Structure

```
vanilla-cc-walkthrough-cc/
├── src/cc_experiment_runner/          # Main package
│   ├── agents/                        # Agent implementations
│   │   ├── vanilla_agent.py           # Docs-only agent
│   │   └── walkthrough_agent.py       # Walkthrough-guided agent
│   ├── harness/                       # Docker execution
│   │   └── docker_harness.py          # Container lifecycle management
│   ├── repository/                    # Repository management
│   │   └── repository_manager.py      # Clone and manage repos
│   ├── walkthrough/                   # Walkthrough generation
│   │   └── walkthrough_generator.py   # Generate structured walkthroughs
│   ├── hooks/                         # Logging infrastructure
│   │   └── agent_logger.py            # Token/tool call tracking
│   └── schemas/                       # Data models
│       └── experiment_schema.py       # Task, Result schemas
├── tasks/                             # Task definitions
│   ├── fastapi_tasks.json             # 10 FastAPI tasks
│   └── README.md                      # Task creation guide
├── scripts/                           # Utility scripts
│   └── run_agent_in_container.py      # Container entry point
├── experiments/                       # Results directory
│   └── batch_XXXXXXXX/                # Batch experiment results
│       ├── batch_summary.json         # Aggregated metrics
│       ├── shared_repo/               # Cloned repository
│       └── fastapi-XX-*/              # Per-task results
│           ├── results.json
│           ├── walkthroughs/
│           ├── vanilla_workspace/
│           ├── vanilla_logs/
│           ├── walkthrough_workspace/
│           └── walkthrough_logs/
├── docs/                              # Documentation
│   ├── ARCHITECTURE.md                # System design
│   └── plan.md                        # Implementation plan
├── run_full_experiment.py             # Single task runner
├── run_batch_experiment.py            # Batch task runner
├── BATCH_EXPERIMENTS.md               # Batch runner guide
├── Dockerfile                         # Container definition
└── README.md                          # This file
```

## Task Definitions

### Current Tasks (FastAPI)

10 progressive tasks covering FastAPI fundamentals to advanced features:

**Beginner (1-3):**
1. `fastapi-01-first-steps` - Basic GET endpoint
2. `fastapi-02-path-parameters` - Dynamic URL paths
3. `fastapi-03-query-parameters` - Query string handling

**Intermediate (4-7):**
4. `fastapi-04-request-body` - POST with Pydantic validation
5. `fastapi-05-nested-models` - Complex nested models
6. `fastapi-06-response-model` - Response filtering
7. `fastapi-07-error-handling` - HTTP exceptions

**Advanced (8-10):**
8. `fastapi-08-dependencies` - Dependency injection
9. `fastapi-09-background-tasks` - Async processing
10. `fastapi-10-sql-database` - SQLAlchemy CRUD API

### Task Format

Tasks follow the **SetupBench** structure:

```json
{
  "instance_id": "fastapi-01-first-steps",
  "difficulty": "beginner",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "branch": "master",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",
  "problem_statement": "Follow the FastAPI First Steps tutorial...",
  "notes": "Basic FastAPI app with single GET endpoint",
  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/first-steps.md",
  "success_command": "timeout 10 bash -c '...' && echo 'Setup successful'",
  "timeout_seconds": 300
}
```

See `tasks/README.md` for complete task creation guide.

## Usage

### Batch Experiments (Recommended)

Run multiple tasks in parallel for efficient testing:

```bash
# Run all tasks (default: 3 workers)
python run_batch_experiment.py

# Run beginner tasks only
python run_batch_experiment.py --difficulty beginner

# Run first 5 tasks with 2 workers
python run_batch_experiment.py --tasks 1-5 --workers 2

# Run specific tasks
python run_batch_experiment.py --tasks 1 3 5 7 9

# Run with more workers (faster, more resources)
python run_batch_experiment.py --workers 5
```

**Output:** Results saved to `experiments/batch_XXXXXXXX/`

See `BATCH_EXPERIMENTS.md` for complete guide.

### Single Task (Debugging)

Run one task with detailed output:

```bash
# Edit run_full_experiment.py to configure task
python run_full_experiment.py
```

**Output:** Results saved to `experiments/XXXXXXXX/`

### Results Structure

```
experiments/batch_a1b2c3d4/
├── batch_summary.json              # Overall metrics
│   ├── summary.vanilla_successes   # Vanilla success count
│   ├── summary.walkthrough_successes
│   ├── summary.total_vanilla_tokens
│   └── summary.total_walkthrough_tokens
├── shared_repo/                    # Cloned repository (shared)
└── fastapi-01-first-steps/         # Task results
    ├── results.json                # Task-specific metrics
    ├── walkthroughs/
    │   └── fastapi-01-first-steps.json
    ├── vanilla_workspace/          # Vanilla agent workspace
    ├── vanilla_logs/
    │   ├── vanilla_agent.log
    │   ├── vanilla_messages.jsonl
    │   ├── vanilla_container.log
    │   ├── vanilla_validation.log
    │   ├── tools.jsonl
    │   └── metrics.json
    ├── walkthrough_workspace/      # Walkthrough agent workspace
    └── walkthrough_logs/
        ├── walkthrough_agent.log
        ├── walkthrough_messages.jsonl
        ├── walkthrough_container.log
        ├── walkthrough_validation.log
        ├── tools.jsonl
        └── metrics.json
```

## How It Works

### 1. Walkthrough Generation

Uses a specialized Claude Code agent to generate structured walkthroughs:

```python
generator = WalkthroughGenerator(api_key=API_KEY)
walkthrough = generator.generate_from_file(
    doc_path="docs/tutorial/first-steps.md",
    library_name="FastAPI",
    task_description="Set up FastAPI application",
    repo_path="/path/to/fastapi"
)
```

**Output:** Structured JSON with:
- `contentForUser` - User-facing instructions (markdown)
- `contextForAgent` - Background knowledge (what to expect)
- `operationsForAgent` - Specific commands to execute
- `introductionForAgent` - Purpose and goals

### 2. Vanilla Agent

**System Prompt:** SetupBench-inspired benchmark prompt
- Environment: Fresh Ubuntu 22.04, minimal tools
- Constraints: Global installs, no venvs, non-interactive
- Task: Full problem statement with validation criteria

**Input:**
- Repository code at `/testbed`
- Documentation at `/workspace/docs`
- Target doc path

**Process:**
1. Read documentation
2. Interpret setup steps
3. Install dependencies globally
4. Create application files
5. Validate with success command

### 3. Walkthrough Agent

**System Prompt:** Same benchmark structure + walkthrough guidance

**Input:**
- Repository code at `/testbed`
- Documentation at `/workspace/docs`
- Structured walkthrough at `/workspace/walkthrough.json`

**Process:**
1. Load walkthrough JSON
2. For each step (by displayOrder):
   - Read `contextForAgent` (understand WHY)
   - Read `operationsForAgent` (know WHAT to do)
   - Execute operations
   - Validate success
3. Report completion

### 4. Docker Isolation

Each agent runs in an isolated Docker container:

```python
harness = DockerHarness()
result = harness.run_agent(
    task=task,
    agent_type="vanilla",  # or "walkthrough"
    repo_path=workspace_dir,
    docs_path=docs_dir,
    walkthrough_path=walkthrough_file,  # walkthrough only
    log_dir=log_dir
)
```

**Benefits:**
- Clean environment (no state leakage)
- Consistent validation (same environment)
- Resource limits (memory, CPU)
- Easy cleanup

### 5. Validation

**SetupBench-style validation:**
- Runs inside same container as agent
- Uses `success_command` from task definition
- Checks for "Setup successful" string
- Deterministic (no flakiness)

**Example:**
```bash
timeout 10 bash -c '
  uvicorn main:app --host 0.0.0.0 --port 8000 &
  SERVER_PID=$!
  sleep 3
  curl -s http://localhost:8000 | grep -q "Hello World"
  RESULT=$?
  kill -9 $SERVER_PID
  exit $RESULT
' && echo "Setup successful" || echo "Setup failed"
```

## Results Format

### Batch Summary

`experiments/batch_XXXXXXXX/batch_summary.json`:

```json
{
  "batch_id": "a1b2c3d4",
  "started_at": "2025-01-17T10:30:00",
  "duration_seconds": 1234.5,
  "workers": 3,
  "total_tasks": 10,
  "results": [ /* per-task results */ ],
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

### Task Results

`experiments/batch_XXXXXXXX/fastapi-01-first-steps/results.json`:

```json
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
```

## Analysis

### Analyzing Results with jq

```bash
# Overall success rate
jq '.summary' experiments/batch_*/batch_summary.json

# Failed tasks
jq '.results[] | select(.vanilla.success == false)' \
  experiments/batch_*/batch_summary.json

# Token comparison
jq '.results[] | {
  task: .task_id,
  vanilla_tokens: .vanilla.tokens.total,
  walkthrough_tokens: .walkthrough.tokens.total,
  difference: (.walkthrough.tokens.total - .vanilla.tokens.total)
}' experiments/batch_*/batch_summary.json

# Success rate by difficulty
jq '.results | group_by(.difficulty) | map({
  difficulty: .[0].difficulty,
  total: length,
  vanilla_successes: map(select(.vanilla.success)) | length,
  walkthrough_successes: map(select(.walkthrough.success)) | length
})' experiments/batch_*/batch_summary.json
```

### Analyzing Results with Python

```python
import json
from pathlib import Path

# Load batch summary
batch_dir = Path("experiments/batch_a1b2c3d4")
summary = json.loads((batch_dir / "batch_summary.json").read_text())

# Calculate metrics
total_tasks = summary["total_tasks"]
vanilla_rate = summary["summary"]["vanilla_success_rate"]
walkthrough_rate = summary["summary"]["walkthrough_success_rate"]
improvement = (walkthrough_rate - vanilla_rate) / vanilla_rate if vanilla_rate > 0 else 0

print(f"Vanilla success rate: {vanilla_rate:.1%}")
print(f"Walkthrough success rate: {walkthrough_rate:.1%}")
print(f"Improvement: {improvement:+.1%}")

# Token efficiency
vanilla_tokens = summary["summary"]["total_vanilla_tokens"]
walkthrough_tokens = summary["summary"]["total_walkthrough_tokens"]
token_ratio = walkthrough_tokens / vanilla_tokens if vanilla_tokens > 0 else 0

print(f"\nVanilla tokens: {vanilla_tokens:,}")
print(f"Walkthrough tokens: {walkthrough_tokens:,}")
print(f"Token ratio: {token_ratio:.2f}x")
```

## Adding New Tasks

See `tasks/README.md` for complete guide.

**Quick steps:**

1. Add task to `tasks/fastapi_tasks.json`:
```json
{
  "instance_id": "fastapi-11-my-task",
  "difficulty": "intermediate",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "...",
  "language": "python",
  "base_image": "ubuntu:22.04",
  "problem_statement": "...",
  "notes": "Brief description",
  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/my-topic.md",
  "success_command": "...",
  "timeout_seconds": 300
}
```

2. Test:
```bash
python run_batch_experiment.py --tasks 11
```

## Troubleshooting

### Docker Issues

**Image not found:**
```bash
docker build -t cc-experiment-runner:latest -f Dockerfile .
```

**Out of memory:**
- Increase Docker memory: Docker Desktop → Settings → Resources → Memory → 8GB+
- Reduce workers: `--workers 1`

**Port conflicts:**
```bash
# Kill processes on port 8000
lsof -ti:8000 | xargs kill -9

# Clean up containers
docker ps -a | grep cc-agent | awk '{print $1}' | xargs docker rm -f
```

### API Key Issues

**Not set:**
```bash
export ANTHROPIC_API_KEY=your-key-here
```

**Not loaded:**
- Check `.env` file exists
- Verify format: `ANTHROPIC_API_KEY=sk-ant-...`

### Validation Issues

**Tasks timing out:**
- Check container logs: `docker logs <container_id>`
- Increase timeout: edit `timeout_seconds` in task definition
- Check background processes: see `ARCHITECTURE.md` for cleanup details

**"Setup failed" but looks correct:**
- Verify `success_command` is deterministic
- Check for background processes not cleaned up
- Review validation logs in `*_validation.log`

## Performance Tips

### Worker Count

- **Low resources** (4 CPU, 8GB RAM): `--workers 1-2`
- **Medium resources** (8 CPU, 16GB RAM): `--workers 3` (default)
- **High resources** (16+ CPU, 32+ GB RAM): `--workers 5+`

**Memory estimate:** ~2-3GB per worker

### Incremental Testing

Test progressively:
```bash
# Start with one task
python run_batch_experiment.py --tasks 1

# Then beginner tasks
python run_batch_experiment.py --difficulty beginner

# Then all tasks
python run_batch_experiment.py
```

## Cost Estimation

**Per Task (Actual from experiments):**
- Walkthrough generation: ~50,000-100,000 tokens
- Vanilla agent: ~300,000-600,000 tokens
- Walkthrough agent: ~600,000-1,200,000 tokens
- **Total: ~470,000 tokens/task**

**For 10 tasks:**
- ~4,700,000 tokens total (vanilla)
- ~9,250,000 tokens total (walkthrough)
- **Combined: ~13,950,000 tokens**

**Cost (Claude Sonnet 4.5):**
- Input: $3/MTok
- Output: $15/MTok
- Cache write: $3.75/MTok
- Cache read: $0.30/MTok
- **Estimated: $50-100 for full batch** (with caching)

## Architecture

See `docs/ARCHITECTURE.md` for detailed design documentation.

**Key components:**

- **DockerHarness** - Container lifecycle, resource limits, logging
- **RepositoryManager** - Clone repos, checkout commits, manage state
- **WalkthroughGenerator** - Generate structured walkthroughs from docs
- **Vanilla/Walkthrough Agents** - Execute tasks with different inputs
- **AgentLogger** - Track tokens, tool calls, errors, timing
- **Task schemas** - SetupBench-inspired deterministic validation

## References

- **SetupBench**: arXiv:2507.09063 - Benchmark for evaluating LLM agents on software setup tasks
- **Better Onboarding Framework**: Krystal Higgins - Structured onboarding methodology
- **Claude Code**: https://docs.anthropic.com/claude-code - AI pair programmer
- **FastAPI**: https://fastapi.tiangolo.com/ - Modern Python web framework

## License

MIT

## Contributing

Contributions welcome! Areas of interest:

1. **New task libraries** - Add tasks for Django, Express, React, Vue, etc.
2. **Analysis tools** - Visualizations, statistical comparisons
3. **Performance improvements** - Faster cloning, parallel generation
4. **Documentation** - More examples, better guides

See `tasks/README.md` for task creation guidelines.
