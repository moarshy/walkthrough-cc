# Vanilla Claude Code vs Walkthrough Claude Code Experiment

Comparing the effectiveness of vanilla Claude Code (given raw documentation) vs walkthrough-powered Claude Code (given structured step-by-step walkthroughs) on repository setup tasks.

## Overview

**Hypothesis:** Providing Claude Code with structured walkthroughs improves task completion rates and efficiency compared to providing only documentation.

**Experiment Design:**
```
For each task:
1. Clone repository
2. Generate walkthrough from documentation (using Claude Code)
3. Run vanilla agent: docs only
4. Run walkthrough agent: docs + structured walkthrough
5. Compare success rates, efficiency, and cost
```

## Prerequisites

### Required

- **Python 3.10+**
- **Docker** (running)
- **ANTHROPIC_API_KEY** environment variable
- **Git**

### Python Dependencies (using uv)

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

Or with pip:
```bash
pip install -e .
```

### Claude Code CLI

The Docker container will install Claude Code CLI automatically. No need to install locally.

## Quick Start

### 1. Build Docker Image

```bash
cd /Users/arshath/play/naptha/better-onboarding/vanilla-cc-walkthrough-cc
docker build -t cc-experiment:latest .
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY=your-key-here
```

### 3. Run Experiment

```bash
# Run all 5 tasks sequentially
python run_experiment.py

# Run specific tasks
python run_experiment.py --task-ids nextjs-getting-started react-tutorial

# Run with 3 parallel workers
python run_experiment.py --parallel 3
```

## Project Structure

```
vanilla-cc-walkthrough-cc/
├── docs/                   # Documentation
│   └── plan.md            # Detailed implementation plan
├── example-codes/          # Existing infrastructure (reused)
│   ├── repository/        # RepositoryManager
│   ├── hooks/             # Logging hooks
│   ├── schemas.py         # Walkthrough schemas
│   └── walkthrough_generate_agent.py
├── src/                    # Main implementation
│   ├── schemas.py         # Experiment schemas
│   ├── harness_docker.py  # Docker container management
│   ├── agent_wrapper.py   # Agent runner (runs inside container)
│   └── runner.py          # Experiment orchestrator
├── experiments/
│   ├── tasks.json         # Task definitions
│   └── configs/           # Agent configurations
├── results/                # Experiment outputs
│   └── exp_TIMESTAMP/
│       ├── walkthroughs/  # Generated walkthroughs
│       ├── logs/          # Agent logs
│       └── *_results.json # Results and metrics
├── Dockerfile              # Container image definition
└── run_experiment.py       # Main entry point
```

## Task Definitions

Tasks are defined in `experiments/tasks.json`:

```json
{
  "id": "nextjs-getting-started",
  "library_name": "Next.js",
  "library_version": "14.0",
  "repo_url": "https://github.com/vercel/next.js",
  "branch": "canary",
  "docs_folder": "docs",
  "target_doc": "01-getting-started/01-installation.mdx",
  "validation": {
    "type": "server",
    "command": "npm run dev",
    "port": 3000,
    "timeout": 60
  }
}
```

**Included Tasks:**
1. **Next.js** - Getting started guide
2. **React** - Tic-tac-toe tutorial
3. **Express.js** - Installation guide
4. **Vue.js** - Quick start
5. **FastAPI** - First steps tutorial

## Usage

### Basic Usage

```bash
# Run all tasks
python run_experiment.py

# Estimated time: 60-150 minutes (sequential)
# Estimated tokens: ~1,250,000 tokens
```

### Advanced Options

```bash
# Run specific tasks
python run_experiment.py --task-ids nextjs-getting-started react-tutorial

# Parallel execution (3 workers)
python run_experiment.py --parallel 3

# Custom output directory
python run_experiment.py --output results/my_experiment

# Custom timeout (1 hour per agent)
python run_experiment.py --timeout 3600

# Skip prerequisite checks
python run_experiment.py --skip-checks
```

### Output

Results are saved to `results/exp_TIMESTAMP/`:

```
results/exp_20251113_143022/
├── exp_20251113_143022_results.json  # Complete results
├── walkthroughs/
│   ├── nextjs-getting-started.json
│   └── ...
└── logs/
    ├── nextjs-getting-started/
    │   ├── vanilla/
    │   │   ├── messages.jsonl
    │   │   ├── tools.jsonl
    │   │   └── agent.log
    │   └── walkthrough/
    │       ├── messages.jsonl
    │       ├── tools.jsonl
    │       └── agent.log
    └── ...
```

## Results Format

The results JSON contains:

```json
{
  "experiment_id": "exp_20251113_143022",
  "summary": {
    "total_tasks": 5,
    "vanilla_success_rate": 0.60,
    "walkthrough_success_rate": 0.80,
    "success_rate_improvement": 0.33,
    "avg_vanilla_duration_seconds": 450.2,
    "avg_walkthrough_duration_seconds": 380.5,
    "time_reduction": 0.155,
    "token_increase": 0.18
  },
  "tasks": [ /* detailed results per task */ ]
}
```

## How It Works

### 1. Walkthrough Generation

```python
# Agent reads documentation
doc_content = read("docs/getting-started.md")

# Agent generates structured walkthrough
walkthrough = {
  "steps": [
    {
      "title": "Install Dependencies",
      "contentForUser": "Run: npm install",
      "contextForAgent": "This installs project dependencies...",
      "operationsForAgent": "1. Run: npm install\n2. Verify: node_modules/ exists",
      "introductionForAgent": "This step sets up the project environment"
    }
  ]
}
```

### 2. Vanilla Agent

**Input:**
- Repository code: `/workspace/repo`
- Documentation: `/workspace/docs`
- Target doc path

**Prompt:**
> "Read /workspace/docs/getting-started.md and follow the instructions to set up the project."

**Process:**
- Agent reads documentation
- Agent interprets steps
- Agent executes commands
- Agent validates success

### 3. Walkthrough Agent

**Input:**
- Repository code: `/workspace/repo`
- Documentation: `/workspace/docs`
- Walkthrough JSON: `/workspace/walkthrough.json`

**Prompt:**
> "Follow the structured walkthrough in /workspace/walkthrough.json step-by-step."

**Process:**
- Agent loads walkthrough JSON
- For each step:
  - Read `contextForAgent` (background)
  - Read `operationsForAgent` (exact commands)
  - Execute operations
  - Validate success
- Report overall result

### 4. Comparison

Metrics calculated:
- **Success rate improvement**: (walkthrough_rate - vanilla_rate) / vanilla_rate
- **Time efficiency**: (vanilla_time - walkthrough_time) / vanilla_time
- **Cost increase**: (walkthrough_tokens - vanilla_tokens) / vanilla_tokens

## Adding New Tasks

1. Edit `experiments/tasks.json`:

```json
{
  "id": "my-new-task",
  "library_name": "MyLibrary",
  "library_version": "1.0",
  "repo_url": "https://github.com/org/repo",
  "branch": "main",
  "docs_folder": "docs",
  "target_doc": "quickstart.md",
  "validation": {
    "type": "server",
    "command": "npm start",
    "port": 3000,
    "timeout": 60
  }
}
```

2. Run:

```bash
python run_experiment.py --task-ids my-new-task
```

## Troubleshooting

### Docker Image Not Found

```bash
docker build -t cc-experiment:latest .
```

### API Key Not Set

```bash
export ANTHROPIC_API_KEY=your-key-here
```

### Container Crashes (OOM)

Increase Docker memory limit:
- **Docker Desktop**: Settings → Resources → Memory → 8GB+
- **Linux**: Edit `/etc/docker/daemon.json`

### Timeout Issues

Increase timeout:

```bash
python run_experiment.py --timeout 3600  # 1 hour
```

### Python Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist:

```bash
pip install pydantic gitpython docker python-dotenv
```

## Development

### Run Tests

```bash
# Test existing components
python scripts/test_existing_components.py
```

### Modify Agent Prompts

Edit prompts in `src/agent_wrapper.py`:
- `VANILLA_SYSTEM_PROMPT`
- `WALKTHROUGH_SYSTEM_PROMPT`

### Rebuild Docker Image

```bash
docker build -t cc-experiment:latest .
```

### View Logs

```bash
# Agent logs
cat results/exp_TIMESTAMP/logs/task-id/vanilla/agent.log

# Container logs
cat results/exp_TIMESTAMP/logs/task-id/vanilla/vanilla_container.log

# Messages (JSONL)
cat results/exp_TIMESTAMP/logs/task-id/vanilla/messages.jsonl
```

## Architecture

### Docker Harness (`src/harness_docker.py`)

- Creates isolated containers for each agent
- Mounts volumes (repo, docs, walkthrough)
- Passes environment variables (API key)
- Monitors execution with timeout
- Collects logs and metrics
- Cleans up containers

### Agent Wrapper (`src/agent_wrapper.py`)

- Runs inside Docker container
- Receives agent type (vanilla/walkthrough)
- Sets up appropriate system prompt
- Runs Claude Code agent
- Logs messages and tool calls
- Exits with proper status code

### Experiment Runner (`src/runner.py`)

- Loads task definitions
- Clones repositories
- Generates walkthroughs
- Runs both agents per task
- Collects and compares results
- Generates summary report

## Cost Estimation

**Per Task (Estimated):**
- Walkthrough generation: ~50,000 tokens
- Vanilla agent: ~100,000 tokens
- Walkthrough agent: ~100,000 tokens
- **Total: ~250,000 tokens/task**

**For 5 tasks:**
- ~1,250,000 tokens total
- At $3/MTok input + $15/MTok output (Claude Sonnet 4.5)
- Estimated cost: ~$10-20

## References

- **SetupBench Paper**: arXiv:2507.09063
- **Better Onboarding Framework**: Krystal Higgins
- **Claude Code CLI**: https://docs.claude.com/claude-code

## License

MIT
