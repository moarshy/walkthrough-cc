# Vanilla CC vs Walkthrough CC Experiment Plan

**Goal:** Compare the effectiveness of vanilla Claude Code (given just docs) vs walkthrough-powered Claude Code (given docs + generated walkthroughs) on repository setup tasks.

**Date:** November 13, 2025
**Status:** Planning

---

## Overview

This experiment tests the hypothesis that providing Claude Code with structured walkthroughs improves task completion rates and efficiency compared to providing only documentation.

### Existing Infrastructure ✅

**Good News:** Most core components already exist in `example-codes/`:
- ✅ **RepositoryManager**: Clones repos, manages directory structure
- ✅ **WalkthroughGenerator**: Generates walkthroughs from docs using Claude Code
- ✅ **Logging Hooks**: Comprehensive message and tool call logging
- ✅ **Schemas**: WalkthroughExport, ContentFields, AuditResult, etc.

**What We Need to Build:**
- ⚠️ **Experiment Runner**: Orchestrates vanilla vs walkthrough comparison
- ⚠️ **Docker Harness**: Runs agents in isolated containers (similar to setupbench-cc)
- ⚠️ **Agent Wrappers**: VanillaAgent and WalkthroughAgent configurations
- ⚠️ **Comparison Metrics**: Calculate success rate, efficiency, cost differences

### Experimental Setup

```
Input: GitHub repo + branch + docs folder + specific doc file
       ↓
Step 1: Download repository locally (✅ RepositoryManager)
       ↓
Step 2: Generate walkthrough from doc (✅ WalkthroughGenerator)
       ↓
Step 3: Run two Docker agents in parallel (⚠️ Docker harness needed):
       - Vanilla CC: docs only
       - Walkthrough CC: docs + walkthrough
       ↓
Step 4: Compare results (⚠️ Comparison metrics needed)
```

### Agent Input Comparison

| Input | Walkthrough Generator | Vanilla Agent | Walkthrough Agent |
|-------|----------------------|---------------|-------------------|
| **Environment** | `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| **Repository** | ❌ No | ✅ `/workspace/repo/` | ✅ `/workspace/repo/` |
| **Documentation** | ✅ Single doc content (string) | ✅ `/workspace/docs/` (all docs) | ✅ `/workspace/docs/` (all docs) |
| **Target Doc** | ❌ N/A | ✅ Specific file path | ✅ Specific file path |
| **Walkthrough JSON** | ❌ No (generates it!) | ❌ No | ✅ `/workspace/walkthrough.json` |
| **System Prompt** | "Expert technical writer creating structured walkthroughs" | "Software dev assistant following documentation" | "Software dev assistant with structured walkthrough" |
| **User Prompt** | "Create walkthrough from this doc" | "Set up project following {doc}" | "Follow walkthrough.json step-by-step" |
| **Key Input** | Documentation markdown text | Documentation file path + repo | Documentation + **structured steps** |
| **Output** | WalkthroughExport JSON file | Setup result (success/fail) | Setup result (success/fail) |

**Key Difference:**
- **Vanilla Agent**: Must interpret raw documentation markdown → figure out steps → execute
- **Walkthrough Agent**: Gets pre-processed structured steps with:
  - `introductionForAgent`: Purpose of step
  - `contextForAgent`: Background knowledge
  - `operationsForAgent`: **Exact commands to run**
  - `contentForUser`: User-facing instructions

---

## System Architecture

### Directory Structure

```
/Users/arshath/play/naptha/better-onboarding/vanilla-cc-walkthrough-cc/
├── docs/                           # Documentation (this file)
│   └── plan.md
├── example-codes/                  # Reference implementation
│   ├── walkthrough_generate_agent.py
│   ├── walkthrough_audit_agent.py
│   ├── schemas.py
│   └── hooks/
├── src/                           # NEW: Main implementation
│   ├── repo_manager.py           # Download and manage repos
│   ├── walkthrough_generator.py  # Generate walkthroughs
│   ├── vanilla_agent.py          # Vanilla CC agent
│   ├── walkthrough_agent.py      # Walkthrough CC agent
│   ├── harness_docker.py         # Docker execution harness
│   ├── runner.py                 # Main orchestrator
│   └── schemas.py                # Data models
├── hooks/                         # NEW: Agent hooks
│   ├── logging.py                # Message/tool logging
│   ├── logging_manager.py        # Log organization
│   └── validation.py             # Output validation
├── experiments/                   # NEW: Experiment definitions
│   ├── tasks.json                # Task definitions (repo+doc pairs)
│   └── configs/                  # Agent configurations
├── results/                       # NEW: Experiment results
│   └── [timestamp]/
│       ├── vanilla/              # Vanilla CC results
│       ├── walkthrough/          # Walkthrough CC results
│       ├── walkthroughs/         # Generated walkthroughs
│       ├── logs/                 # All agent logs
│       └── comparison.json       # Comparison metrics
└── scripts/                       # NEW: Utility scripts
    ├── run_experiment.py         # Run full experiment
    ├── generate_walkthroughs_only.py
    └── analyze_results.py
```

---

## Component Design

### 1. Repository Manager (✅ **ALREADY EXISTS**)

**Location:** `example-codes/repository/manager.py`

**Purpose:** Download and manage GitHub repositories for testing.

**Key Classes:**
```python
class RepositoryManager:
    def clone_repository(
        repo_url: str,
        branch: str,
        library_name: str,
        library_version: str,
        commit: Optional[str],
        docs_path: Optional[str],
        include_folders: Optional[List[str]]
    ) -> RunContext:
        """Clone repo and set up directory structure."""

    def find_markdown_files(
        context: RunContext,
        include_folders: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Find markdown docs (with API reference filtering)."""

    def cleanup_run(run_id: str):
        """Clean up repository and run directory."""

class RunContext:
    """Manages run directory structure: repo/, results/, cache/"""
```

**Features:**
- ✅ Clones repos with branch/commit support
- ✅ Resolves commit hashes automatically
- ✅ Filters API reference pages
- ✅ Creates organized directory structure
- ✅ Saves metadata.json for tracking

**Usage:** We can reuse this directly, just adapt the directory structure for our experiment needs.

---

### 2. Walkthrough Generator (✅ **ALREADY EXISTS**)

**Location:** `example-codes/walkthrough_generate_agent.py`

**Purpose:** Generate walkthroughs from documentation files using Claude Code.

**Input to Generator Agent:**

```python
# What the agent receives:
{
    "doc_path": "docs/getting-started.md",
    "library_name": "Next.js",
    "library_version": "14.0",
    "content": """
# Getting Started with Next.js

## Installation
First, install Next.js:
```bash
npx create-next-app@latest
```

## Create Your First Page
...
""",
    "output_file": "walkthroughs/nextjs-getting-started.json"
}
```

**System Prompt:**
```
You are an expert technical writer and documentation analyst specializing in
creating interactive walkthroughs from documentation.

Your task is to analyze tutorial/quickstart documentation and convert it into
a structured step-by-step walkthrough that a Claude Code agent can execute.

CRITICAL REQUIREMENTS:
1. Identify Logical Steps: Break the tutorial into discrete, actionable steps
2. Extract Four Content Types for each step:
   - contentForUser: The markdown content the user sees
   - contextForAgent: Background knowledge the agent needs
   - operationsForAgent: Specific commands/actions to execute
   - introductionForAgent: Purpose and goals of the step
3. Be Specific in Operations: Use exact commands, include error handling
4. Output Format: Return valid JSON matching the WalkthroughExport schema
```

**User Prompt Template:**
```
Analyze the following documentation and create a structured walkthrough.

Documentation file: {doc_path}
Library: {library_name}
Version: {library_version}

Documentation content:
```markdown
{content}
```

Create a walkthrough with:
1. Metadata: Title, description, estimated duration, tags
2. Steps: Break down into logical steps (typically 5-15 steps)

For each step, provide:
- title: Clear, action-oriented title
- contentForUser: User-facing content (markdown with code blocks)
- contextForAgent: Background context and what to know
- operationsForAgent: Exact commands and actions to execute
- introductionForAgent: Purpose and goals of this step

**IMPORTANT**: Use the Write tool to save the walkthrough JSON to {output_file}
```

**Output:** WalkthroughExport JSON file with structured steps

**Improvements Needed:**
- Add timeout handling (prevent infinite generation)
- Add retry logic for failed generations
- Track token usage for generation
- Log generation time

---

### 3. Docker Harness (`src/harness_docker.py`)

**Purpose:** Execute agents in isolated Docker containers (similar to setupbench-cc).

**Key Functions:**
```python
class DockerHarness:
    def setup_container(
        task_id: str,
        repo_path: Path,
        docs_path: Path,
        agent_type: str  # "vanilla" or "walkthrough"
    ) -> Container:
        """Create and configure Docker container."""

    async def run_agent(
        container: Container,
        task: Task,
        timeout: int = 7200
    ) -> AgentResult:
        """Run agent in container with timeout."""

    def cleanup_container(container: Container):
        """Stop and remove container."""
```

**Container Specs:**
- Base image: `ubuntu:22.04`
- Pre-installed: Python 3.10, Node.js 18, git, curl
- Claude Code CLI installed
- Resource limits: 8GB RAM, 4 CPUs

**Logging:**
- Stream container logs to file
- Monitor resource usage (CPU, memory)
- Capture stdout/stderr

---

### 4. Vanilla Agent (`src/vanilla_agent.py`)

**Purpose:** Execute setup tasks with only documentation (no walkthrough).

**Input to Vanilla Agent:**

```python
# Environment:
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Required!

# Workspace (Docker volumes):
/workspace/
├── repo/              # Cloned repository
│   ├── src/
│   ├── package.json
│   └── ...
├── docs/              # Documentation folder
│   ├── getting-started.md  # ← Target doc
│   ├── installation.md
│   └── ...
└── logs/              # Agent logs output
```

**System Prompt:**
```
You are a software development assistant helping to set up a project based on
its documentation.

CONTEXT:
- Repository code: /workspace/repo
- Documentation: /workspace/docs
- Target doc: {target_doc_name}

YOUR TASK:
1. Read the target documentation file: /workspace/docs/{target_doc_name}
2. Follow the instructions step-by-step to set up the project
3. Execute all necessary commands (install dependencies, build, run tests, start server)
4. Verify the setup works correctly
5. Report success or failure with details

GUIDELINES:
- Be thorough: Don't skip steps from the documentation
- Be careful: Check for errors after each command
- Be adaptive: If something fails, try alternative approaches
- Be validating: Confirm the project actually works (server responds, tests pass, etc.)

AVAILABLE TOOLS:
- Read: Read files in the workspace
- Write: Create new files
- Edit: Modify existing files
- Bash: Run shell commands
- Glob: Find files by pattern
- Grep: Search file contents

SUCCESS CRITERIA:
- All installation steps completed
- Project builds successfully (if applicable)
- Server starts and responds (if applicable)
- Tests pass (if applicable)
```

**Initial User Prompt:**
```
Please set up the project following the documentation in /workspace/docs/{target_doc_name}.

Read the documentation carefully and execute all steps to get the project running.
When you're done, verify that everything works and report the results.
```

**Execution Flow:**
1. Agent reads `/workspace/docs/{target_doc_name}`
2. Agent follows steps autonomously
3. Agent validates setup (server running, tests passing, etc.)
4. Agent reports success/failure
5. Harness captures exit code and logs

**Example Interaction:**
```
User: Please set up the project following /workspace/docs/getting-started.md

Agent: I'll read the documentation and set up the project.
[Reads docs/getting-started.md]

Agent: The documentation shows I need to:
1. Install dependencies: npm install
2. Build the project: npm run build
3. Start the dev server: npm run dev

Let me start...
[Runs: npm install]
[Runs: npm run build]
[Runs: npm run dev &]
[Waits for server]
[Curls http://localhost:3000]

Agent: ✅ Setup complete! Server is running on port 3000.
```

---

### 5. Walkthrough Agent (`src/walkthrough_agent.py`)

**Purpose:** Execute setup tasks with documentation + structured walkthrough.

**Input to Walkthrough Agent:**

```python
# Environment:
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Required!

# Workspace (Docker volumes):
/workspace/
├── repo/              # Cloned repository
│   ├── src/
│   ├── package.json
│   └── ...
├── docs/              # Documentation folder
│   ├── getting-started.md
│   └── ...
├── walkthrough.json   # ← Generated walkthrough!
└── logs/              # Agent logs output
```

**What's in walkthrough.json:**
```json
{
  "version": "1.0",
  "walkthrough": {
    "title": "Getting Started with Next.js",
    "description": "Set up a Next.js project from scratch",
    "estimatedDurationMinutes": 15
  },
  "steps": [
    {
      "title": "Install Dependencies",
      "displayOrder": 1,
      "contentFields": {
        "contentForUser": "# Install Dependencies\n\nRun:\n```bash\nnpx create-next-app@latest\n```",
        "contextForAgent": "Next.js uses npx to bootstrap projects. This command will prompt for project configuration.",
        "operationsForAgent": "1. Run: npx create-next-app@latest my-app\n2. Answer prompts: TypeScript=Yes, ESLint=Yes, App Router=Yes\n3. Wait for installation to complete\n4. Verify: Check that my-app/ directory was created",
        "introductionForAgent": "This step installs Next.js and creates the project scaffold."
      },
      "nextStepReference": 2
    },
    {
      "title": "Start Development Server",
      "displayOrder": 2,
      "contentFields": {
        "contentForUser": "# Start the Server\n\n```bash\ncd my-app\nnpm run dev\n```",
        "contextForAgent": "The dev server runs on port 3000 by default and supports hot reload.",
        "operationsForAgent": "1. Change directory: cd my-app\n2. Run: npm run dev &\n3. Wait 10 seconds for server to start\n4. Verify: curl http://localhost:3000 should return HTML\n5. Check logs for 'Ready on http://localhost:3000'",
        "introductionForAgent": "This step starts the development server and verifies it's running."
      },
      "nextStepReference": null
    }
  ]
}
```

**System Prompt:**
```
You are a software development assistant with access to a structured walkthrough
for setting up a project.

CONTEXT:
- Repository code: /workspace/repo
- Documentation: /workspace/docs
- Structured walkthrough: /workspace/walkthrough.json

The walkthrough provides step-by-step guidance with:
- contentForUser: User-facing instructions (markdown)
- contextForAgent: Background knowledge (what to expect, how things work)
- operationsForAgent: Specific commands and actions to execute
- introductionForAgent: Purpose and goals of each step

YOUR TASK:
1. Read and parse /workspace/walkthrough.json
2. Execute each step in order (by displayOrder)
3. For each step:
   - Read the contextForAgent to understand what you're doing
   - Read the operationsForAgent for specific commands
   - Execute the operations carefully
   - Verify success before moving to next step
4. Report overall success or failure with details

GUIDELINES:
- Follow the walkthrough structure: It's been validated and designed for agents
- Use operationsForAgent as your primary guide
- contextForAgent helps you understand WHY you're doing each step
- If a step fails, try to diagnose and fix before giving up
- Validate after each step (check files exist, servers respond, etc.)

AVAILABLE TOOLS:
- Read: Read files in the workspace
- Write: Create new files
- Edit: Modify existing files
- Bash: Run shell commands
- Glob: Find files by pattern
- Grep: Search file contents

SUCCESS CRITERIA:
- All steps completed successfully
- All validations pass
- Final project is functional (server running, tests passing, etc.)
```

**Initial User Prompt:**
```
Please set up the project by following the structured walkthrough in /workspace/walkthrough.json.

The walkthrough contains step-by-step instructions designed for AI agents.
Execute each step carefully, validate your work, and report the results.
```

**Execution Flow:**
1. Agent reads `/workspace/walkthrough.json`
2. Agent parses steps (sorted by displayOrder)
3. For each step:
   - Reads introductionForAgent (understand purpose)
   - Reads contextForAgent (understand background)
   - Reads operationsForAgent (get specific commands)
   - Executes operations
   - Validates success
   - Moves to nextStepReference
4. Agent reports final success/failure
5. Harness captures exit code and logs

**Example Interaction:**
```
User: Please follow the walkthrough in /workspace/walkthrough.json

Agent: I'll execute the walkthrough step-by-step.
[Reads walkthrough.json]

Agent: Found 2 steps:
1. Install Dependencies
2. Start Development Server

Starting Step 1: Install Dependencies
[Reads contextForAgent: "Next.js uses npx to bootstrap projects..."]
[Reads operationsForAgent: "1. Run: npx create-next-app@latest my-app..."]
[Runs: npx create-next-app@latest my-app]
[Answers prompts: TypeScript=Yes, ESLint=Yes, App Router=Yes]
[Waits for installation]
[Verifies: ls my-app/]
✅ Step 1 complete: my-app/ directory created

Starting Step 2: Start Development Server
[Reads contextForAgent: "The dev server runs on port 3000..."]
[Reads operationsForAgent: "1. cd my-app 2. Run: npm run dev &..."]
[Runs: cd my-app && npm run dev &]
[Waits 10 seconds]
[Runs: curl http://localhost:3000]
[Checks logs for "Ready on http://localhost:3000"]
✅ Step 2 complete: Server is running

Agent: ✅ All steps completed successfully! Server running on port 3000.
```

**Key Difference from Vanilla:**
- **Vanilla Agent**: Interprets documentation directly, must figure out steps
- **Walkthrough Agent**: Gets pre-processed, structured steps with explicit operations
  - `contextForAgent`: Why this step matters
  - `operationsForAgent`: Exactly what to do
  - `introductionForAgent`: Purpose of the step

---

### 6. Runner (`src/runner.py`)

**Purpose:** Orchestrate the full experiment.

**Key Functions:**
```python
class ExperimentRunner:
    def __init__(
        tasks: List[Task],
        output_dir: Path,
        parallel: bool = False
    ):
        """Initialize experiment runner."""

    async def run_experiment(self) -> ExperimentResults:
        """Run full experiment for all tasks."""

    async def run_single_task(
        task: Task,
        task_dir: Path
    ) -> TaskResult:
        """Run vanilla + walkthrough for one task."""
```

**Workflow:**
```
For each task:
    1. Download repo
    2. Generate walkthrough
    3. Run vanilla agent (Docker)
    4. Run walkthrough agent (Docker)
    5. Collect results
    6. Clean up
```

---

## Task Definition Schema

### `experiments/tasks.json`

```json
{
  "tasks": [
    {
      "id": "nextjs-quickstart",
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
    },
    {
      "id": "react-tutorial",
      "library_name": "React",
      "library_version": "18.3",
      "repo_url": "https://github.com/facebook/react",
      "branch": "main",
      "docs_folder": "docs",
      "target_doc": "learn/tutorial-tic-tac-toe.md",
      "validation": {
        "type": "build",
        "command": "npm run build",
        "success_pattern": "Compiled successfully"
      }
    }
  ]
}
```

**Fields:**
- `id`: Unique task identifier
- `library_name`: Name of library/framework
- `library_version`: Version being tested
- `repo_url`: GitHub repository URL
- `branch`: Git branch to checkout
- `docs_folder`: Path to docs within repo
- `target_doc`: Specific doc file to use
- `validation`: How to verify success

---

## Hooks and Logging

### Based on `setupbench-cc` architecture

**Logging Hooks** (`hooks/logging.py`):
```python
class AgentLogger:
    - Log all messages (user/assistant)
    - Log all tool calls (tool name, args, results)
    - Track token usage
    - Track timing for each operation

create_logging_hooks() -> Dict[str, List[Hook]]:
    - PreToolUse: Log tool call before execution
    - PostToolUse: Log result after execution
```

**Log Files:**
```
results/[timestamp]/logs/[task_id]/
├── vanilla/
│   ├── messages.jsonl           # All messages
│   ├── tools.jsonl              # Tool calls
│   └── agent.log                # Human-readable log
└── walkthrough/
    ├── messages.jsonl
    ├── tools.jsonl
    └── agent.log
```

**Logging Manager** (`hooks/logging_manager.py`):
- Organize log directories
- Create summary files
- Handle log rotation if needed

---

## Metrics to Track

### Per-Task Metrics

**Completion:**
- `success`: Boolean (did task complete successfully?)
- `duration_seconds`: Time to completion
- `exit_code`: Agent exit code

**Token Usage:**
- `total_tokens`: Total tokens used
- `input_tokens`: Prompt tokens
- `output_tokens`: Completion tokens
- `cache_read_tokens`: Cached tokens reused
- `cache_creation_tokens`: New cache tokens

**Actions:**
- `total_messages`: Number of messages exchanged
- `tool_calls_total`: Total tool calls
- `tool_calls_by_type`: Breakdown by tool (Bash, Read, etc.)
- `bash_commands_count`: Number of Bash commands
- `file_operations_count`: Read/Write/Edit operations

**Errors:**
- `error_count`: Number of errors encountered
- `error_types`: Types of errors
- `recovery_attempts`: Retries after errors

### Comparison Metrics

**Success Rate:**
```
vanilla_success_rate = vanilla_successes / total_tasks
walkthrough_success_rate = walkthrough_successes / total_tasks
improvement = (walkthrough_success_rate - vanilla_success_rate) / vanilla_success_rate
```

**Efficiency:**
```
avg_vanilla_time = mean(vanilla_durations)
avg_walkthrough_time = mean(walkthrough_durations)
time_reduction = (avg_vanilla_time - avg_walkthrough_time) / avg_vanilla_time
```

**Cost:**
```
vanilla_cost = sum(vanilla_tokens * price_per_token)
walkthrough_cost = sum((generation_tokens + execution_tokens) * price_per_token)
cost_comparison = walkthrough_cost / vanilla_cost
```

---

## Results Schema

### `results/[timestamp]/comparison.json`

```json
{
  "experiment_id": "exp_20251113_143022",
  "started_at": "2025-11-13T14:30:22Z",
  "completed_at": "2025-11-13T16:45:10Z",
  "duration_seconds": 8088,

  "summary": {
    "total_tasks": 10,
    "vanilla": {
      "successes": 6,
      "failures": 4,
      "success_rate": 0.60,
      "avg_duration_seconds": 450.2,
      "total_tokens": 1250000,
      "avg_tokens_per_task": 125000
    },
    "walkthrough": {
      "successes": 9,
      "failures": 1,
      "success_rate": 0.90,
      "avg_duration_seconds": 380.5,
      "total_tokens": 1450000,
      "avg_tokens_per_task": 145000,
      "generation_tokens": 250000
    },
    "comparison": {
      "success_rate_improvement": 0.50,
      "time_reduction": 0.155,
      "token_increase": 0.16,
      "cost_increase": 0.18
    }
  },

  "tasks": [
    {
      "task_id": "nextjs-quickstart",
      "vanilla_result": { /* TaskResult */ },
      "walkthrough_result": { /* TaskResult */ },
      "walkthrough_path": "walkthroughs/nextjs-quickstart.json"
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Tasks:**
1. ✅ Create directory structure
2. ✅ **REUSE** `RepositoryManager` from example-codes/repository/
3. ✅ **REUSE** `WalkthroughGenerator` from example-codes/walkthrough_generate_agent.py
4. ✅ **REUSE** schemas from example-codes/schemas.py
5. ✅ **REUSE** logging hooks from example-codes/hooks/
6. ⚠️ Adapt for experiment structure (2 agents instead of 3-stage pipeline)

**Deliverables:**
- Can download repos (using existing manager)
- Can generate walkthroughs (using existing agent)
- Can log agent activity (using existing hooks)
- Adapted directory structure for vanilla vs walkthrough comparison

---

### Phase 2: Docker Harness (Week 2)

**Tasks:**
1. ✅ Create Dockerfile for agent environment
2. ✅ Implement `DockerHarness` (container lifecycle)
3. ✅ Add resource monitoring (CPU, memory)
4. ✅ Add timeout handling
5. ✅ Test with simple tasks

**Deliverables:**
- Can run agents in Docker
- Can monitor resource usage
- Can handle crashes/timeouts

---

### Phase 3: Agent Implementation (Week 2)

**Tasks:**
1. ✅ Implement `VanillaAgent` (docs only)
2. ✅ Implement `WalkthroughAgent` (docs + walkthrough)
3. ✅ Add validation logic
4. ✅ Add error handling
5. ✅ Test both agents

**Deliverables:**
- Both agents can execute tasks
- Agents produce consistent logs
- Agents validate success/failure

---

### Phase 4: Orchestration (Week 3)

**Tasks:**
1. ✅ Implement `ExperimentRunner`
2. ✅ Add parallel task execution
3. ✅ Add progress reporting
4. ✅ Generate comparison metrics
5. ✅ Create summary reports

**Deliverables:**
- Can run full experiments
- Can compare results
- Can generate reports

---

### Phase 5: Testing and Refinement (Week 4)

**Tasks:**
1. ✅ Create test task set (5-10 tasks)
2. ✅ Run pilot experiment
3. ✅ Analyze results
4. ✅ Fix issues
5. ✅ Re-run with improvements

**Deliverables:**
- Validated experiment pipeline
- Initial results data
- Bug fixes applied

---

## Docker Configuration

### Dockerfile

```dockerfile
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    nodejs \
    npm \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Setup workspace
RUN mkdir -p /workspace/repo \
    && mkdir -p /workspace/docs \
    && mkdir -p /workspace/walkthroughs

WORKDIR /workspace

# Set environment
ENV ANTHROPIC_API_KEY=""
ENV NODE_PATH=/usr/local/lib/node_modules

# Default command
CMD ["/bin/bash"]
```

### Container Execution

```python
import os

# CRITICAL: API Key must be available!
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set!")

# Mount volumes:
volumes = {
    repo_path: {'bind': '/workspace/repo', 'mode': 'rw'},
    docs_path: {'bind': '/workspace/docs', 'mode': 'ro'},
    # Walkthrough agent only:
    walkthrough_path: {'bind': '/workspace/walkthrough.json', 'mode': 'ro'},
}

# Set resource limits:
mem_limit = '8g'    # 8GB RAM (generous for building projects)
cpu_count = 4       # 4 CPU cores

# Environment variables:
environment = {
    # REQUIRED: API key for Claude Code CLI
    'ANTHROPIC_API_KEY': api_key,

    # Task metadata:
    'TASK_ID': task.id,
    'AGENT_TYPE': agent_type,  # 'vanilla' or 'walkthrough'
    'TARGET_DOC': task.target_doc,

    # Runtime config:
    'NODE_PATH': '/usr/local/lib/node_modules',
    'PYTHONUNBUFFERED': '1',  # Unbuffered logs
}

# Run container:
container = docker_client.containers.run(
    image='cc-experiment:latest',
    command=['python3', '-m', 'agent_wrapper', agent_type],
    volumes=volumes,
    environment=environment,
    mem_limit=mem_limit,
    cpu_count=cpu_count,
    detach=True,
    network_mode='bridge',
    name=f'cc-agent-{task.id}-{agent_type}'
)
```

**Important Notes:**
- `ANTHROPIC_API_KEY` **must** be set in the host environment before running experiments
- The key is passed into the Docker container as an environment variable
- Claude Code CLI inside the container reads `ANTHROPIC_API_KEY` automatically
- Without the key, the agent cannot authenticate with the Claude API

---

## Experiment Workflow

### Command: `python scripts/run_experiment.py`

```bash
# Run full experiment with default tasks
python scripts/run_experiment.py \
  --tasks experiments/tasks.json \
  --output results/

# Run specific tasks
python scripts/run_experiment.py \
  --tasks experiments/tasks.json \
  --task-ids nextjs-quickstart react-tutorial \
  --output results/

# Run in parallel
python scripts/run_experiment.py \
  --tasks experiments/tasks.json \
  --parallel 3 \
  --output results/
```

### Execution Steps

For each task:

```
1. Download Repository
   - Clone repo_url to temp directory
   - Checkout specified branch
   - Verify docs folder exists

2. Generate Walkthrough
   - Run WalkthroughGenerator on target_doc
   - Save to results/[timestamp]/walkthroughs/[task_id].json
   - Log generation time and tokens

3. Run Vanilla Agent
   - Create Docker container
   - Mount repo + docs
   - Run VanillaAgent with target_doc
   - Collect logs and results
   - Validate success
   - Cleanup container

4. Run Walkthrough Agent
   - Create Docker container
   - Mount repo + docs + walkthrough.json
   - Run WalkthroughAgent
   - Collect logs and results
   - Validate success
   - Cleanup container

5. Compare Results
   - Calculate metrics
   - Save comparison data
   - Update summary

6. Cleanup
   - Remove repo directory
   - Archive logs
```

---

## Analysis Scripts

### `scripts/analyze_results.py`

**Generate:**
1. Success rate comparison table
2. Time efficiency graphs
3. Token usage breakdown
4. Error analysis
5. Cost comparison

**Output:**
- `analysis_report.md`: Human-readable analysis
- `plots/`: Visualizations (matplotlib)
- `detailed_comparison.csv`: Detailed metrics

---

## Monitoring and Debugging

### During Experiment

**Monitor Docker:**
```bash
# Terminal 1: Run experiment
python scripts/run_experiment.py --tasks experiments/tasks.json

# Terminal 2: Monitor containers
watch -n 2 'docker stats --no-stream | grep cc-agent'

# Terminal 3: Check logs
tail -f results/[timestamp]/logs/[task_id]/vanilla/agent.log
```

**Progress Indicators:**
- Task completion percentage
- Current task being executed
- Estimated time remaining
- Resource usage warnings

### After Experiment

**Check Results:**
```bash
# View summary
python scripts/analyze_results.py results/[timestamp]

# Compare specific tasks
python scripts/compare_task.py \
  --task nextjs-quickstart \
  --results results/[timestamp]

# Generate report
python scripts/generate_report.py results/[timestamp]
```

---

## Expected Challenges

### 1. Walkthrough Generation Failures

**Issue:** Claude Code may generate invalid JSON or incomplete walkthroughs.

**Mitigation:**
- Strict JSON schema validation
- Retry logic (up to 3 attempts)
- Fallback to manual walkthrough if available
- Log generation failures for analysis

### 2. Docker Container Crashes

**Issue:** Agents may crash due to OOM or resource exhaustion.

**Mitigation:**
- 8GB memory limit (generous)
- 2-hour timeout per task
- Monitor memory usage
- Sequential execution option if parallel fails

### 3. Task Validation Ambiguity

**Issue:** Hard to determine if setup "succeeded" without clear validation.

**Mitigation:**
- Define explicit validation for each task (server start, build success, test pass)
- Use exit codes + pattern matching
- Manual review of ambiguous results

### 4. Token Cost

**Issue:** Running 2 agents per task + walkthrough generation is expensive.

**Mitigation:**
- Start with small task set (5-10 tasks)
- Use prompt caching aggressively
- Monitor costs in real-time
- Stop if budget exceeded

---

## Success Criteria

### Experiment is successful if:

1. ✅ Can generate walkthroughs for at least 80% of tasks
2. ✅ Both agents complete at least 70% of tasks
3. ✅ Walkthrough agent shows improvement in success rate OR efficiency
4. ✅ Results are reproducible
5. ✅ Logs capture enough detail for analysis

### Comparison is valid if:

1. ✅ Tasks are identical for both agents
2. ✅ Environment is identical (same Docker image)
3. ✅ Validation criteria are consistent
4. ✅ No manual intervention during execution
5. ✅ Sufficient sample size (≥10 tasks)

---

## Next Steps

### Immediate (This Week)

1. **Create initial task set** (5 tasks)
   - Choose diverse repos (Next.js, React, Vue, Express, Flask)
   - Define validation criteria
   - Test manual setup to verify tasks are feasible

2. **Verify existing infrastructure** ✅ **ALREADY EXISTS**
   - ✅ RepositoryManager: `example-codes/repository/manager.py`
   - ✅ WalkthroughGenerator: `example-codes/walkthrough_generate_agent.py`
   - ✅ Logging hooks: `example-codes/hooks/`
   - ✅ Schemas: `example-codes/schemas.py`

3. **Adapt for experiment structure**
   - Modify directory layout for 2-agent comparison
   - Create `src/experiment_runner.py` that uses existing components
   - Define new schemas: `Task`, `ExperimentResult` (build on existing)

4. **Test existing components**
   - Clone a test repo using RepositoryManager
   - Generate walkthrough for sample doc
   - Verify logging works

### Short Term (Next Week)

5. **Implement Docker harness**
   - Create Dockerfile
   - Test container creation
   - Test agent execution in container

6. **Implement agents**
   - VanillaAgent
   - WalkthroughAgent
   - Test both with simple task

7. **Create runner script**
   - Run single task end-to-end
   - Generate comparison metrics
   - Test on 1-2 tasks

### Medium Term (Week 3-4)

8. **Run pilot experiment**
   - 5-10 tasks
   - Analyze results
   - Iterate on prompts/configuration

9. **Refine and scale**
   - Fix issues from pilot
   - Expand to 20-30 tasks
   - Generate comprehensive report

---

## Open Questions

1. **Task Selection:**
   - Which repos/docs should we test?
   - Should we focus on one ecosystem (e.g., only Node.js)?
   - Or test across ecosystems (Node, Python, Rust)?

2. **Validation Strategy:**
   - Is "server starts" sufficient validation?
   - Should we run actual tests?
   - How to handle tasks without clear validation?

3. **Walkthrough Quality:**
   - How to ensure generated walkthroughs are high quality?
   - Should we manually review/edit generated walkthroughs?
   - Or accept whatever Claude generates?

4. **Agent Autonomy:**
   - Should agents be fully autonomous?
   - Or allow manual intervention for debugging?

5. **Cost Budget:**
   - What's the budget for this experiment?
   - How many tasks can we afford?

---

## References

- SetupBench paper: arXiv:2507.09063
- Better Onboarding framework: Krystal Higgins
- setupbench-cc implementation: /Users/arshath/play/naptha/better-onboarding/setupbench-cc
- Example codes: /Users/arshath/play/naptha/better-onboarding/vanilla-cc-walkthrough-cc/example-codes
