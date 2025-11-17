# Architecture Documentation

## Overview

The **vanilla-cc-walkthrough-cc** project compares two approaches to onboarding developers with Claude Code:

1. **Vanilla Agent**: Claude Code with only documentation (README, docs folder)
2. **Walkthrough Agent**: Claude Code with documentation + a structured walkthrough JSON

Both agents run in isolated Docker containers and are validated deterministically to measure onboarding effectiveness.

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST MACHINE                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  run_full_experiment.py (Orchestrator)                     │ │
│  │  - Loads task definition                                   │ │
│  │  - Clones repository                                       │ │
│  │  - Runs vanilla and walkthrough agents                     │ │
│  │  - Collects results and generates report                   │ │
│  └─────────────────┬──────────────────────────────────────────┘ │
│                    │                                             │
│                    ▼                                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  DockerHarness                                             │ │
│  │  - Creates Docker containers                               │ │
│  │  - Mounts workspace, docs, walkthrough                     │ │
│  │  - Passes task JSON with success_command                   │ │
│  │  - Waits for container completion                          │ │
│  │  - Parses results from metrics.json                        │ │
│  └─────────────────┬──────────────────────────────────────────┘ │
│                    │                                             │
└────────────────────┼─────────────────────────────────────────────┘
                     │
                     │ Docker API
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DOCKER CONTAINER                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  run_agent_in_container.py (Entry Point)                   │ │
│  │                                                             │ │
│  │  1. Parse task JSON and extract success_command            │ │
│  │  2. Setup AgentLogger (tools.jsonl, messages.jsonl)        │ │
│  │  3. Run agent (vanilla or walkthrough)                     │ │
│  │  4. Run validation in same container                       │ │
│  │  5. Write results to metrics.json                          │ │
│  │  6. Exit with combined status                              │ │
│  └─────────┬──────────────────────────┬───────────────────────┘ │
│            │                          │                          │
│            ▼                          ▼                          │
│  ┌──────────────────┐      ┌──────────────────────────────────┐ │
│  │  Vanilla Agent   │      │  Walkthrough Agent               │ │
│  │  - Reads docs/   │      │  - Reads docs/                   │ │
│  │  - No walkthrough│      │  - Reads walkthrough.json        │ │
│  │  - Uses Claude   │      │  - Guided by structured steps    │ │
│  └──────────────────┘      └──────────────────────────────────┘ │
│            │                          │                          │
│            └──────────┬───────────────┘                          │
│                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Validation (subprocess.run)                               │ │
│  │  - Runs success_command in /workspace/repo                 │ │
│  │  - Checks for "Setup successful" in output                 │ │
│  │  - Writes validation.log                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│            │                                                     │
│            ▼                                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Results Written to /logs (mounted volume)                 │ │
│  │  - metrics.json (tokens, validation status)                │ │
│  │  - tools.jsonl (tool call logs)                            │ │
│  │  - messages.jsonl (Claude messages)                        │ │
│  │  - validation.log (validation output)                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
                     │
                     │ Volume Mount
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                         HOST MACHINE                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  experiments/<experiment_id>/                              │ │
│  │  ├── vanilla_logs/                                         │ │
│  │  │   ├── metrics.json                                      │ │
│  │  │   ├── tools.jsonl                                       │ │
│  │  │   ├── messages.jsonl                                    │ │
│  │  │   └── validation.log                                    │ │
│  │  ├── walkthrough_logs/                                     │ │
│  │  │   └── (same structure)                                  │ │
│  │  └── results.json (final report)                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Decisions

### 1. **Validation Runs Inside Container (Critical)**

**Why:** Ensures validation runs in the **same environment** as the agent.

**Before (Problematic):**
```
Container: Agent runs → Exits
Host: Reads workspace → Runs validation → Different environment!
```

**After (Correct):**
```
Container: Agent runs → Validation runs → Writes results → Exits
Host: Parses metrics.json
```

**Benefits:**
- ✅ Same tools available (timeout, bash, python versions, etc.)
- ✅ Same environment variables and dependencies
- ✅ True reproducibility across platforms (macOS, Linux, etc.)
- ✅ No host-specific issues (e.g., macOS missing `timeout`)

**Implementation:**
- `run_agent_in_container.py` receives `success_command` in task JSON
- After agent completes, immediately runs validation via `subprocess.run()`
- Writes results to `metrics.json` for host to parse

### 2. **Two-Tier Architecture: Orchestration + Execution**

**Host Tier (Orchestration):**
- `run_full_experiment.py`: Experiment orchestration
- `DockerHarness`: Container lifecycle management
- Result collection and report generation

**Container Tier (Execution):**
- `run_agent_in_container.py`: Agent + validation execution
- `VanillaAgent` / `WalkthroughAgent`: Task completion
- `AgentLogger`: Logging and metrics collection

**Why:** Separates concerns - host manages experiments, container executes tasks in isolation.

### 3. **Volume Mounts for Data Exchange**

**Mounted Volumes:**
```python
volumes = {
    '/workspace/repo': 'rw',      # Repository root (contains library source + agent's project/)
    '/workspace/docs': 'ro',      # Documentation (read-only)
    '/workspace/walkthrough.json': 'ro',  # Walkthrough (walkthrough agent only)
    '/logs': 'rw'                 # Logs and results (written by container)
}
```

**Workspace Structure Inside Container:**
```
/workspace/repo/
├── [library source code]  ← Repository files (read-only for agent)
├── docs/                  ← Documentation (read by agent)
└── project/               ← Agent's isolated workspace (created by agent)
    ├── main.py
    ├── requirements.txt
    └── [other files]
```

**Why:**
- Clean separation between input (docs, walkthrough) and output (logs, workspace changes)
- Agents work in `project/` subdirectory to avoid conflicts with library source code
- Generic approach works for any library/framework

### 4. **Deterministic Validation**

**SetupBench-style validation:**
```bash
success_command = "timeout 300 bash -c 'cd /workspace/repo && source venv/bin/activate && python example.py'"
```

**Success Criteria:** Output contains `"Setup successful"`

**Why:**
- Language-agnostic (works for Python, Node.js, etc.)
- Deterministic (no LLM interpretation)
- Verifiable (can be re-run independently)

---

## Component Deep Dive

### Host Components

#### 1. `run_full_experiment.py`
**Location:** `/Users/arshath/play/naptha/better-onboarding/vanilla-cc-walkthrough-cc/run_full_experiment.py`

**Responsibilities:**
- Load task definition from JSON
- Clone target repository to workspace
- Run vanilla agent via DockerHarness
- Run walkthrough agent via DockerHarness
- Collect results and generate `results.json`
- Create experiment directory with logs

**Key Code:**
```python
task = Task(
    instance_id="fastapi-first-steps",
    repo_url="https://github.com/tiangolo/fastapi",
    branch="master",
    base_commit="d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
    docs_folder="docs/en/docs",
    target_doc="tutorial/first-steps.md",
    problem_statement="Follow the 'First Steps' tutorial...",
    success_command="timeout 300 bash -c '...'",
    timeout_seconds=300
)

harness = DockerHarness(image_name="cc-experiment-runner:latest")
vanilla_result = harness.run_agent(task, "vanilla", repo_path, docs_path, None, vanilla_log_dir)
```

#### 2. `DockerHarness`
**Location:** `src/cc_experiment_runner/harness/docker_harness.py`

**Responsibilities:**
- Create and configure Docker containers
- Mount volumes (workspace, docs, logs)
- Pass task JSON with `success_command` to container
- Wait for container completion
- Parse `metrics.json` for validation results
- Cleanup containers

**Key Code:**
```python
def run_agent(self, task, agent_type, repo_path, docs_path, walkthrough_path, log_dir):
    # Prepare task JSON (includes success_command)
    task_json = json.dumps({
        'instance_id': task.instance_id,
        'success_command': task.success_command,  # ← Critical
        # ... other fields
    })

    # Create container
    container = self.docker_client.containers.run(
        image=self.image_name,
        command=['python3', '/app/run_agent_in_container.py', agent_type, task_json, self.api_key],
        volumes=volumes,
        detach=True
    )

    # Wait and parse results
    exit_code = self._wait_for_container(container, self.timeout_seconds)

    # Parse validation results from metrics.json
    metrics_file = log_dir / "metrics.json"
    validation_passed = metrics.get('validation_passed', False)
```

**Note:** Validation was previously handled by a separate `ValidationHarness` component, but has been moved into the container for better reproducibility. See `run_agent_in_container.py` for the current implementation.

### Container Components

#### 1. `run_agent_in_container.py`
**Location:** `scripts/run_agent_in_container.py`

**Responsibilities (Critical Entry Point):**
1. Parse task JSON from command-line arguments
2. Extract `success_command` from task JSON
3. Setup `AgentLogger` for logging
4. Run appropriate agent (vanilla or walkthrough)
5. **Run validation in same container**
6. Write results to `metrics.json`
7. Exit with combined status (agent + validation)

**Key Code:**
```python
# Parse task JSON to get success_command
task_data = json.loads(task_json)
success_command = task_data.get('success_command', '')

# Run agent
result = asyncio.run(run_vanilla_agent(logger) if agent_type == "vanilla" else run_walkthrough_agent(logger))
agent_completed = not result.get('error')

# ========== RUN VALIDATION IN SAME CONTAINER ==========
if agent_completed and success_command:
    validation_result = subprocess.run(
        success_command,
        shell=True,
        cwd="/workspace/repo",
        capture_output=True,
        text=True,
        timeout=300
    )
    validation_output = validation_result.stdout + validation_result.stderr
    validation_passed = "Setup successful" in validation_output

# Save results
stats['validation_passed'] = validation_passed
stats['overall_success'] = agent_completed and validation_passed
json.dump(stats, f)

# Exit with success only if BOTH pass
exit_code = 0 if (agent_completed and validation_passed) else 1
sys.exit(exit_code)
```

#### 2. `VanillaAgent`
**Location:** `src/cc_experiment_runner/agents/vanilla_agent.py`

**Responsibilities:**
- Run Claude Code with **only documentation** (no walkthrough)
- Read problem statement and target doc
- Attempt to complete task using docs as reference
- Log all tool calls and messages

**Prompt Structure:**
```
You are helping a developer learn {library_name}.

Task: {problem_statement}

Available Documentation: docs/{target_doc}

Please complete the task by following the documentation.
```

#### 3. `WalkthroughAgent`
**Location:** `src/cc_experiment_runner/agents/walkthrough_agent.py`

**Responsibilities:**
- Run Claude Code with **documentation + structured walkthrough**
- Read problem statement, target doc, and walkthrough JSON
- Follow step-by-step instructions from walkthrough
- Log all tool calls and messages

**Prompt Structure:**
```
You are helping a developer learn {library_name}.

Task: {problem_statement}

You have access to:
1. Documentation: docs/{target_doc}
2. Structured Walkthrough: walkthrough.json

Follow the walkthrough steps to complete the task.
```

**Walkthrough Structure:**
```json
{
  "walkthrough": {
    "library_name": "fastapi",
    "library_version": "0.100.0",
    "target_doc": "tutorial/first-steps.md"
  },
  "steps": [
    {
      "step_number": 1,
      "title": "Create main.py",
      "description": "Create the main FastAPI application file",
      "expected_outcome": "File main.py created with FastAPI import",
      "validation_hint": "Check that 'from fastapi import FastAPI' is in main.py"
    }
  ]
}
```

#### 4. `AgentLogger`
**Location:** `src/cc_experiment_runner/hooks/logging.py`

**Responsibilities:**
- Hook into Claude Code's Pre-tool and Post-tool events
- Log all tool calls to `tools.jsonl`
- Log all messages to `messages.jsonl`
- Track token usage and statistics
- Provide `get_stats()` for metrics collection

**Logged Data:**
```jsonl
// tools.jsonl
{"timestamp": "2024-01-15T10:30:45", "tool": "Write", "tool_use_id": "abc123", "input": {...}, "error": null}

// messages.jsonl
{"timestamp": "2024-01-15T10:30:45", "role": "assistant", "content": [...], "usage": {...}}
```

---

## Data Schemas

### Task Schema
**Location:** `src/cc_experiment_runner/schemas/experiment_schema.py`

```python
class Task(BaseModel):
    instance_id: str           # Unique task identifier
    repo_url: str             # GitHub repository URL
    branch: str = "main"      # Branch to clone
    base_commit: str          # Specific commit hash
    docs_folder: str          # Path to docs in repo
    target_doc: str           # Specific doc to follow
    problem_statement: str    # Task description for agent
    notes: Optional[str]      # Optional hints
    success_command: str      # Validation command
    timeout_seconds: int = 300
```

### AgentResult Schema

```python
class AgentResult(BaseModel):
    agent_type: str                    # "vanilla" or "walkthrough"
    task_id: str                       # instance_id from task
    agent_completed: bool              # Did agent finish?
    validation_passed: bool            # Did validation pass?
    validation_output: str             # Validation command output
    validation_exit_code: int          # Exit code from validation
    validation_duration: float         # Validation time (seconds)
    success: bool                      # agent_completed AND validation_passed
    duration_seconds: float            # Total agent time
    exit_code: int                     # Container exit code
    error_message: Optional[str]       # Error if failed
    error_type: Optional[str]          # Error classification
    token_usage: TokenUsage            # Token statistics
    tool_calls: ToolCallStats          # Tool call statistics
    started_at: str                    # ISO timestamp
    completed_at: str                  # ISO timestamp
    log_dir: Path                      # Path to logs
    messages_file: Optional[Path]      # messages.jsonl path
    tools_file: Optional[Path]         # tools.jsonl path
```

### Walkthrough Schema
**Location:** `src/cc_experiment_runner/schemas/walkthrough_schema.py`

```python
class WalkthroughStep(BaseModel):
    step_number: int
    title: str
    description: str
    code_snippet: Optional[str]
    expected_outcome: str
    validation_hint: Optional[str]
    common_errors: Optional[List[str]]

class Walkthrough(BaseModel):
    walkthrough: WalkthroughMetadata  # library_name, version, etc.
    steps: List[WalkthroughStep]
```

---

## Execution Flow

### Full Experiment Execution

```
1. run_full_experiment.py starts
   ├─ Load task from JSON
   ├─ Create experiment directory: experiments/<experiment_id>/
   ├─ Clone repo to vanilla_workspace/ and walkthrough_workspace/
   │
   ├─ 2. Run Vanilla Agent
   │   ├─ DockerHarness.run_agent("vanilla")
   │   ├─ Create container with volumes:
   │   │   - vanilla_workspace → /workspace/repo
   │   │   - docs/ → /workspace/docs
   │   │   - vanilla_logs/ → /logs
   │   ├─ Container runs run_agent_in_container.py vanilla
   │   │   ├─ VanillaAgent executes (reads docs only)
   │   │   ├─ Validation runs in container
   │   │   └─ Writes metrics.json, tools.jsonl, messages.jsonl
   │   ├─ Container exits
   │   └─ Host parses metrics.json → AgentResult
   │
   ├─ 3. Run Walkthrough Agent
   │   ├─ DockerHarness.run_agent("walkthrough")
   │   ├─ Create container with volumes:
   │   │   - walkthrough_workspace → /workspace/repo
   │   │   - docs/ → /workspace/docs
   │   │   - walkthrough.json → /workspace/walkthrough.json
   │   │   - walkthrough_logs/ → /logs
   │   ├─ Container runs run_agent_in_container.py walkthrough
   │   │   ├─ WalkthroughAgent executes (reads docs + walkthrough)
   │   │   ├─ Validation runs in container
   │   │   └─ Writes metrics.json, tools.jsonl, messages.jsonl
   │   ├─ Container exits
   │   └─ Host parses metrics.json → AgentResult
   │
   └─ 4. Generate Results
       ├─ Compare vanilla vs walkthrough results
       ├─ Write results.json
       └─ Print summary report
```

### Container Execution Flow (Detailed)

```
Container starts: python3 /app/run_agent_in_container.py walkthrough '<task_json>' '<api_key>'
│
├─ 1. Parse Arguments
│   ├─ agent_type = "walkthrough"
│   ├─ task_json = {..., "success_command": "timeout 300 bash -c '...'"}
│   └─ api_key = "sk-ant-..."
│
├─ 2. Setup Environment
│   ├─ os.environ['ANTHROPIC_API_KEY'] = api_key
│   ├─ Create AgentLogger(tools.jsonl, messages.jsonl)
│   └─ Parse success_command from task_json
│
├─ 3. Run Agent
│   ├─ WalkthroughAgent.run()
│   │   ├─ Load walkthrough.json
│   │   ├─ Load target doc from docs/
│   │   ├─ Execute task with Claude Code
│   │   │   ├─ Tool calls logged to tools.jsonl
│   │   │   ├─ Messages logged to messages.jsonl
│   │   │   └─ Token usage tracked
│   │   └─ Return result dict
│   ├─ agent_completed = not result.get('error')
│   └─ agent_exit_code = 0 if agent_completed else 1
│
├─ 4. Run Validation (IN SAME CONTAINER)
│   ├─ if agent_completed and success_command:
│   │   ├─ subprocess.run(success_command, cwd="/workspace/repo")
│   │   ├─ validation_output = stdout + stderr
│   │   ├─ validation_passed = "Setup successful" in validation_output
│   │   └─ validation_exit_code = returncode
│   └─ Write validation.log
│
├─ 5. Write Results
│   ├─ metrics.json:
│   │   {
│   │     "agent_type": "walkthrough",
│   │     "agent_completed": true,
│   │     "validation_passed": true,
│   │     "validation_exit_code": 0,
│   │     "overall_success": true,
│   │     "input_tokens": 12500,
│   │     "output_tokens": 3200,
│   │     ...
│   │   }
│   └─ validation.log: Full validation output
│
└─ 6. Exit
    └─ exit_code = 0 if (agent_completed AND validation_passed) else 1
```

---

## Hook System

### Purpose
Hooks intercept Claude Code tool calls for:
1. **Logging**: Track all tool usage for analysis
2. **Validation**: Enforce constraints (e.g., walkthrough output path)
3. **Metrics**: Collect performance data

### Hook Types

#### Pre-tool Hooks
Run **before** tool execution. Can block tool calls.

**Example: Output Path Validation**
```python
async def validate_output_path_hook(input_data, tool_use_id, context):
    """Ensure walkthrough files are written to walkthroughs/ directory."""
    if input_data.get('tool_name') == 'Write':
        file_path = input_data.get('tool_input', {}).get('file_path', '')
        if not file_path.startswith('walkthroughs/'):
            return {
                'hookSpecificOutput': {
                    'permissionDecision': 'deny',
                    'denialReason': 'Walkthroughs must be saved in walkthroughs/ directory'
                }
            }
    return {}
```

#### Post-tool Hooks
Run **after** tool execution. Can validate outputs.

**Example: JSON Schema Validation**
```python
async def validate_walkthrough_json_hook(input_data, tool_use_id, context):
    """Validate walkthrough JSON against schema."""
    if input_data.get('tool_name') == 'Write':
        content = input_data.get('tool_input', {}).get('content', '')
        try:
            data = json.loads(content)
            walkthrough = Walkthrough(**data)  # Pydantic validation
            return {'hookSpecificOutput': {'validationPassed': True}}
        except Exception as e:
            return {'hookSpecificOutput': {'validationError': str(e)}}
```

#### Logging Hooks
**Pre-tool and Post-tool** for comprehensive logging.

```python
async def pre_tool_hook(input_data, tool_use_id, context):
    """Log tool call before execution."""
    self.tools_log.append({
        'timestamp': datetime.now().isoformat(),
        'tool': input_data.get('tool_name'),
        'tool_use_id': tool_use_id,
        'input': input_data.get('tool_input')
    })

async def post_tool_hook(input_data, tool_use_id, context):
    """Log tool result after execution."""
    # Update logged entry with result/error
```

### Hook Registration

Hooks are registered in the agent's `onboarding_settings`:

```python
onboarding_settings = {
    "hooks": {
        "pre_tool": {
            "main": logging_hook.pre_tool_hook,
            "validation": validate_output_path_hook
        },
        "post_tool": {
            "main": logging_hook.post_tool_hook,
            "schema_check": validate_walkthrough_json_hook
        }
    }
}
```

---

## Results and Analysis

### Results Structure

```json
{
  "experiment_id": "a1b2c3d4",
  "task": "fastapi-first-steps",
  "timestamp": "2024-01-15T10:30:45",
  "library": {
    "name": "fastapi",
    "version": "0.100.0",
    "commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d"
  },
  "vanilla": {
    "success": false,
    "agent_completed": true,
    "validation_passed": false,
    "validation": {
      "exit_code": 1,
      "output": "ModuleNotFoundError: No module named 'fastapi'",
      "duration": 2.5
    },
    "duration": 45.3,
    "tokens": {
      "total": 15700,
      "input": 12500,
      "output": 3200
    },
    "tool_calls": 12,
    "errors": {"total": 2, "bash": 1, "edit": 1}
  },
  "walkthrough": {
    "success": true,
    "agent_completed": true,
    "validation_passed": true,
    "validation": {
      "exit_code": 0,
      "output": "Setup successful\nFastAPI app running on port 8000",
      "duration": 3.1
    },
    "duration": 38.7,
    "tokens": {
      "total": 18200,
      "input": 14000,
      "output": 4200
    },
    "tool_calls": 15,
    "errors": {"total": 0}
  }
}
```

### Analysis Tools

#### 1. `analyze_experiment.py`
**Location:** `scripts/analyze_experiment.py`

**Usage:**
```bash
python scripts/analyze_experiment.py experiments/a1b2c3d4
```

**Output:**
- Overall status comparison
- Validation details for both agents
- Performance metrics (duration, tokens, tool calls)
- Tool errors breakdown
- Files created in workspaces
- Log file locations

#### 2. Direct Log Inspection

```bash
# View validation logs
cat experiments/a1b2c3d4/vanilla_logs/vanilla_validation.log
cat experiments/a1b2c3d4/walkthrough_logs/walkthrough_validation.log

# View tool calls
cat experiments/a1b2c3d4/vanilla_logs/tools.jsonl | jq .

# View messages
cat experiments/a1b2c3d4/vanilla_logs/messages.jsonl | jq .

# View metrics
cat experiments/a1b2c3d4/vanilla_logs/metrics.json | jq .
```

---

## Docker Image

### Base Image
**Dockerfile Location:** `Dockerfile`

**Base:** `python:3.11-slim`

**Installed Tools:**
- Python 3.11 + pip
- Node.js 20.x + npm
- bash, git, curl, timeout
- Common development tools

**Application Setup:**
```dockerfile
# Copy application code
COPY src/ /app/
COPY scripts/ /app/

# Install Python dependencies
RUN pip install anthropic pydantic docker

# Set working directory
WORKDIR /workspace/repo

# Entry point
CMD ["python3", "/app/run_agent_in_container.py"]
```

### Building and Running

```bash
# Build image
docker build -t cc-experiment-runner:latest .

# Test container manually
docker run -it \
  -v $(pwd)/test_workspace:/workspace/repo \
  -v $(pwd)/docs:/workspace/docs \
  -v $(pwd)/logs:/logs \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  cc-experiment-runner:latest \
  python3 /app/run_agent_in_container.py vanilla '<task_json>' "$ANTHROPIC_API_KEY"
```

---

## Performance Considerations

### Resource Limits

```python
DockerHarness(
    mem_limit="8g",           # 8GB memory limit
    cpu_count=4,              # 4 CPU cores
    timeout_seconds=7200      # 2 hour timeout
)
```

**Why:**
- Prevent runaway containers
- Fair resource allocation
- Deterministic performance

### Caching

**Prompt Caching:**
- Documentation is cached by Claude API
- Reduces token costs on repeated tool calls
- Tracked separately in token usage

**Docker Layer Caching:**
- Base image layers cached
- Application code in separate layers
- Faster rebuilds during development

---

## Reproducibility

### Deterministic Factors

1. **Docker Environment**: Same OS, tools, dependencies
2. **Commit Pinning**: Exact repository commit (`base_commit`)
3. **Validation Command**: Deterministic success criteria
4. **Resource Limits**: Consistent memory and CPU
5. **In-Container Validation**: Validation runs in same environment as agent

### Non-Deterministic Factors

1. **Claude Model Output**: LLM responses vary
2. **Network Conditions**: Affects API latency
3. **Random Seeds**: Not controlled in agent logic

### Best Practices for Reproducibility

```python
# ✅ Good: Pinned commit
task = Task(
    repo_url="https://github.com/tiangolo/fastapi",
    base_commit="d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d"
)

# ❌ Bad: Latest commit (changes over time)
task = Task(
    repo_url="https://github.com/tiangolo/fastapi",
    base_commit="HEAD"
)

# ✅ Good: Validation runs in Docker
# (Automatically done by run_agent_in_container.py)

# ❌ Bad: Validation runs on host
# (Old architecture - now fixed)
```

---

## Debugging Guide

### Container Won't Start

```bash
# Check Docker daemon
docker info

# Verify image exists
docker images | grep cc-experiment-runner

# Check for port conflicts
docker ps -a

# View Docker logs
docker logs <container_id>
```

### Agent Fails

```bash
# Check agent logs
cat experiments/<experiment_id>/vanilla_logs/vanilla_agent.log

# Check tool errors
cat experiments/<experiment_id>/vanilla_logs/tools.jsonl | jq 'select(.error != null)'

# Check messages
cat experiments/<experiment_id>/vanilla_logs/messages.jsonl | jq .
```

### Validation Fails

```bash
# Check validation log
cat experiments/<experiment_id>/vanilla_logs/vanilla_validation.log

# Check validation command
cat experiments/<experiment_id>/vanilla_logs/metrics.json | jq '.validation_exit_code'

# Manually run validation
cd experiments/<experiment_id>/vanilla_workspace
timeout 300 bash -c 'source venv/bin/activate && python example.py'
```

### API Issues

```bash
# Verify API key
echo $ANTHROPIC_API_KEY

# Check API connectivity
curl -H "x-api-key: $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages

# Check rate limits in logs
grep -i "rate limit" experiments/<experiment_id>/*/container.log
```

---

## Extension Points

### Adding New Tasks

1. Create task JSON in `tasks/`
2. Define `problem_statement` and `success_command`
3. Ensure `success_command` outputs "Setup successful" on success
4. Run experiment: `python run_full_experiment.py --task tasks/new_task.json`

### Adding New Agents

1. Create agent file in `src/cc_experiment_runner/agents/`
2. Implement agent logic following `VanillaAgent` pattern
3. Register in `run_agent_in_container.py`
4. Update `DockerHarness` to support new agent type

### Custom Validation Logic

Currently: Success = "Setup successful" in output

To customize:
1. Modify `run_agent_in_container.py` line 94:
   ```python
   validation_passed = custom_validation_function(validation_output)
   ```
2. Or: Modify `success_command` in task definition to use custom script

### Adding Hooks

1. Create hook file in `src/cc_experiment_runner/hooks/`
2. Implement async hook function
3. Register in agent's `onboarding_settings`
4. Test with experiment run

---

## Security Considerations

### API Key Handling

- ✅ API key passed as command argument (not in environment)
- ✅ Not logged to files
- ✅ Not persisted in container
- ❌ Visible in `docker ps` (use secrets in production)

### Container Isolation

- ✅ Network: bridge mode (limited external access)
- ✅ Filesystem: Only mounted volumes accessible
- ✅ Resources: Memory and CPU limits enforced
- ⚠️ No user namespacing (runs as root in container)

### Input Validation

- ✅ Task JSON validated against Pydantic schemas
- ✅ Walkthrough JSON validated before use
- ✅ File paths validated by hooks
- ⚠️ `success_command` runs with shell=True (injection risk if user input)

---

## Future Improvements

### Potential Enhancements

1. **Parallel Execution**: Run vanilla and walkthrough agents concurrently
2. **Result Database**: Store results in PostgreSQL for analysis
3. **Web Dashboard**: Visualize experiment results over time
4. **A/B Testing**: Compare multiple walkthrough variations
5. **Cost Tracking**: Track API costs per experiment
6. **Replay Mode**: Re-run experiments from saved logs
7. **Multi-Model Support**: Test with GPT-4, Claude 2, etc.
8. **Benchmark Suite**: Predefined set of tasks for comparison

### Known Limitations

1. **Single Task Per Run**: Must run experiments sequentially
2. **No Incremental Checkpoints**: Agent can't resume from failure
3. **Limited Error Recovery**: No automatic retry logic
4. **Fixed Timeout**: Same timeout for all tasks
5. **No Human-in-Loop**: Can't intervene during agent execution

---

## References

### Related Projects

- **SetupBench**: Inspiration for validation harness and task definition
- **SWE-bench**: Similar approach for software engineering tasks
- **Claude Code**: Underlying agent framework

### Documentation

- [Claude Code Docs](https://code.claude.com/docs)
- [Docker Python SDK](https://docker-py.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

## Changelog

### v2.0 (Current) - Validation-in-Container Architecture
- ✅ Validation now runs inside the same Docker container as agent
- ✅ Fixed macOS compatibility (timeout command issue)
- ✅ True reproducibility across platforms
- ✅ Simplified architecture (no separate validation containers)
- ✅ Combined exit code (agent + validation)

### v1.0 - Initial Architecture
- ❌ Validation ran on host machine
- ❌ Environment mismatch between agent and validation
- ❌ Platform-specific issues (macOS vs Linux)

---

## Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `run_full_experiment.py` | Experiment orchestrator (host) |
| `src/cc_experiment_runner/harness/docker_harness.py` | Container lifecycle manager |
| `scripts/run_agent_in_container.py` | Container entry point (agent + validation) |
| `src/cc_experiment_runner/agents/vanilla_agent.py` | Vanilla agent implementation |
| `src/cc_experiment_runner/agents/walkthrough_agent.py` | Walkthrough agent implementation |
| `src/cc_experiment_runner/hooks/logging.py` | Agent logging hooks |
| `src/cc_experiment_runner/schemas/experiment_schema.py` | Task and result schemas |
| `scripts/analyze_experiment.py` | Result analysis tool |

### Key Commands

```bash
# Run experiment
python run_full_experiment.py

# Analyze results
python scripts/analyze_experiment.py experiments/<experiment_id>

# Build Docker image
docker build -t cc-experiment-runner:latest .

# View logs
cat experiments/<experiment_id>/vanilla_logs/vanilla_validation.log
cat experiments/<experiment_id>/vanilla_logs/metrics.json | jq .
```

### Key Concepts

- **Two-Tier Architecture**: Host orchestrates, Docker executes
- **In-Container Validation**: Validation runs in same environment as agent
- **Deterministic Validation**: "Setup successful" in output = success
- **Hook System**: Pre-tool and Post-tool hooks for logging and validation
- **Volume Mounts**: Clean separation of inputs and outputs
- **Combined Exit Code**: Container exits 0 only if agent AND validation pass
