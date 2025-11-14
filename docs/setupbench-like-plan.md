# SetupBench-Style Task Definition Plan

## Overview

This document outlines how to adapt SetupBench's task definition approach for the vanilla vs walkthrough agent benchmark. The goal is to create deterministic, reproducible task definitions with independent validation.

---

## 1. Task Schema Design

### Proposed Task Schema

```python
class Task(BaseModel):
    """SetupBench-inspired task definition."""

    # Core identification
    instance_id: str                     # Unique task ID (e.g., "fastapi-first-steps")

    # Repository details
    repo_url: str                        # GitHub repository URL
    base_commit: str                     # Specific commit hash for reproducibility
    language: str                        # Programming language (e.g., "python")

    # Environment specification
    base_image: str = "ubuntu:22.04"     # Docker base image

    # Task description
    problem_statement: str               # Full task description with constraints
    notes: str                           # Brief task summary for humans

    # Documentation paths (for walkthrough generation)
    docs_folder: str                     # Path to docs within repo (e.g., "docs/en")
    target_doc: str                      # Specific doc file (e.g., "tutorial/first-steps.md")

    # Validation
    success_command: str                 # Command to verify task completion
    timeout_seconds: int = 300           # Validation timeout

    # Ground truth (optional)
    build_commands: Optional[List[str]] = None  # Expected build steps

    # Metadata
    metadata: Optional[Dict[str, Any]] = None
```

### Key Differences from SetupBench

**Removed:**
- `task_type: Literal["reposetup", "dbsetup", "bgsetup", "dependency_resolution"]` - Not needed for our use case
- `license_spdx` - Optional metadata
- `human_actions_bounds` - Not tracking this initially

**Kept:**
- All core identification and validation fields
- Repository and environment specifications
- Documentation paths for walkthrough generation

### Example Task Definition (JSON)

```json
{
  "instance_id": "fastapi-first-steps",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",

  "problem_statement": "You are setting up a FastAPI project following the official First Steps tutorial.\n\nEnvironment: Fresh Ubuntu 22.04 with no preinstalled Python packages.\n\nConstraints:\n- Install all dependencies globally (no virtual environments)\n- Non-interactive setup suitable for headless CI\n- You have root privileges (no need for sudo)\n\nTask: Follow the FastAPI First Steps tutorial to create and run a basic FastAPI application that responds to HTTP requests at the root path.",

  "notes": "Basic FastAPI tutorial - install FastAPI and uvicorn, create main.py with Hello World endpoint.",

  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/first-steps.md",

  "success_command": "timeout 10 bash -c 'uvicorn main:app --host 0.0.0.0 --port 8000 & sleep 3 && curl -s http://localhost:8000 | grep -q \"Hello World\" && killall uvicorn' && echo \"Setup successful\" || echo \"Setup failed\"",

  "timeout_seconds": 300,

  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip curl",
    "pip3 install fastapi uvicorn[standard]",
    "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get(\"/\")\ndef read_root():\n    return {\"Hello\": \"World\"}\nEOF",
    "uvicorn main:app"
  ]
}
```

---

## 2. Validation Harness Design

### Purpose

Create an independent validation harness (like SetupBench's `evaluation_harness.py`) that:
1. Runs **after** the agent completes
2. Executes the `success_command` in a **fresh shell**
3. Checks output for **"Setup successful"** pattern
4. Returns deterministic success/failure

### Implementation

**File:** `src/cc_experiment_runner/validation_harness.py`

```python
"""
Independent validation harness for deterministic task evaluation.
Inspired by SetupBench's evaluation_harness.py.
"""

import subprocess
from pathlib import Path
from typing import Tuple
from .schemas_defs import Task

class ValidationHarness:
    """Validates task completion independently of agent execution."""

    def validate_task(
        self,
        task: Task,
        workspace_dir: Path,
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Run success_command in a fresh shell and validate output.

        Args:
            task: Task definition with success_command
            workspace_dir: Directory where task was executed
            timeout: Optional timeout override (uses task.timeout_seconds if None)

        Returns:
            Tuple of (success: bool, output: str, exit_code: int)
        """
        timeout = timeout or task.timeout_seconds

        try:
            # Run success_command in fresh subprocess
            result = subprocess.run(
                task.success_command,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy()  # Fresh environment
            )

            output = result.stdout + result.stderr
            exit_code = result.returncode

            # Validation logic: Check for "Setup successful" in output
            success = "Setup successful" in output

            return success, output, exit_code

        except subprocess.TimeoutExpired:
            return False, f"Validation command timed out after {timeout}s", -1

        except Exception as e:
            return False, f"Validation failed with error: {e}", -1

    def validate_and_log(
        self,
        task: Task,
        workspace_dir: Path,
        log_path: Path
    ) -> bool:
        """
        Validate task and write detailed log.

        Returns:
            bool: True if validation passed
        """
        success, output, exit_code = self.validate_task(task, workspace_dir)

        # Write validation log
        with open(log_path, 'w') as f:
            f.write(f"Task ID: {task.instance_id}\n")
            f.write(f"Command: {task.success_command}\n")
            f.write(f"Exit Code: {exit_code}\n")
            f.write(f"Success: {success}\n")
            f.write(f"\n--- Output ---\n")
            f.write(output)

        return success
```

### Key Design Decisions

1. **Fresh Shell**: Each validation runs in a new subprocess, ensuring no state leakage from agent execution
2. **Pattern Matching**: Success determined by "Setup successful" string in output (SetupBench convention)
3. **Timeout Handling**: Respects task-specific timeout, prevents hanging validation
4. **Detailed Logging**: Captures full output for debugging failed validations

---

## 3. Integration with Docker Harness

### Current Flow
```
1. Clone repository
2. Run Vanilla Agent (Docker container)
3. Run Walkthrough Agent (Docker container)
4. Compare results based on agent completion
```

### Enhanced Flow with Validation
```
1. Clone repository
2. Run Vanilla Agent (Docker container)
   └─> Agent completes
   └─> ValidationHarness.validate_task()
   └─> Record: agent_completed + validation_passed
3. Run Walkthrough Agent (Docker container)
   └─> Agent completes
   └─> ValidationHarness.validate_task()
   └─> Record: agent_completed + validation_passed
4. Compare results: TRUE success = both agent_completed AND validation_passed
```

### Modified AgentResult Schema

```python
class AgentResult(BaseModel):
    """Extended result with independent validation."""

    # Existing fields
    agent_type: str
    duration: float
    token_usage: TokenUsage
    tool_calls: ToolCallStats

    # Agent execution result
    agent_completed: bool           # Did agent finish without errors?
    agent_error: Optional[str]      # Error if agent failed

    # Independent validation result
    validation_passed: bool         # Did validation command succeed?
    validation_output: str          # Full output from validation command
    validation_exit_code: int       # Exit code from validation command
    validation_duration: float      # Time spent validating

    # Overall success (BOTH must be true)
    success: bool                   # agent_completed AND validation_passed
```

### Key Insight: Two Types of Success

| Scenario | Agent Completed | Validation Passed | Overall Success | Interpretation |
|----------|----------------|-------------------|-----------------|----------------|
| 1 | ✅ | ✅ | ✅ | Perfect - agent did the task correctly |
| 2 | ✅ | ❌ | ❌ | Agent thinks it succeeded but setup is broken |
| 3 | ❌ | N/A | ❌ | Agent crashed/timed out before finishing |
| 4 | ❌ | ✅ | ❌ | Impossible (can't validate if agent didn't run) |

**Scenario 2 is critical**: This exposes cases where agents hallucinate success or miss key setup steps. SetupBench found this happens frequently (see paper section 3.3 on failure modes).

---

## 4. FastAPI Task Examples

### Task 1: Install Dependencies
```json
{
  "instance_id": "fastapi-install-basic",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",

  "problem_statement": "Install FastAPI and uvicorn packages in a fresh Ubuntu 22.04 environment.\n\nConstraints:\n- Install globally (no venv)\n- Include standard extras for uvicorn\n- Verify imports work correctly",

  "notes": "Dependency installation only - test if packages can be imported.",

  "docs_folder": "docs/en/docs",
  "target_doc": "index.md",

  "success_command": "python3 -c 'import fastapi; import uvicorn; print(fastapi.__version__)' && echo 'Setup successful' || echo 'Setup failed'",

  "timeout_seconds": 300,

  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip",
    "pip3 install fastapi 'uvicorn[standard]'"
  ]
}
```

### Task 2: First Steps (Hello World)
```json
{
  "instance_id": "fastapi-first-steps",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",

  "problem_statement": "Follow the FastAPI First Steps tutorial to create a basic API.\n\nTask:\n1. Install FastAPI and uvicorn\n2. Create main.py with a root endpoint that returns {\"Hello\": \"World\"}\n3. Verify the server runs and responds correctly",

  "notes": "Basic FastAPI app with single GET endpoint at root path.",

  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/first-steps.md",

  "success_command": "timeout 10 bash -c 'uvicorn main:app --host 0.0.0.0 --port 8000 & sleep 3 && curl -s http://localhost:8000 | grep -q \"Hello.*World\" && killall -9 uvicorn' && echo 'Setup successful' || echo 'Setup failed'",

  "timeout_seconds": 300,

  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip curl",
    "pip3 install fastapi 'uvicorn[standard]'",
    "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get(\"/\")\ndef read_root():\n    return {\"Hello\": \"World\"}\nEOF"
  ]
}
```

### Task 3: Path Parameters
```json
{
  "instance_id": "fastapi-path-parameters",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",

  "problem_statement": "Follow the FastAPI Path Parameters tutorial.\n\nTask:\n1. Install FastAPI and uvicorn\n2. Create main.py with path parameter endpoint: GET /items/{item_id}\n3. Endpoint should return {\"item_id\": item_id}\n4. Verify server responds with correct path parameter values",

  "notes": "Path parameters tutorial - dynamic URL paths.",

  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/path-params.md",

  "success_command": "timeout 10 bash -c 'uvicorn main:app --host 0.0.0.0 --port 8000 & sleep 3 && curl -s http://localhost:8000/items/42 | grep -q \"\\\"item_id\\\":42\" && killall -9 uvicorn' && echo 'Setup successful' || echo 'Setup failed'",

  "timeout_seconds": 300,

  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip curl",
    "pip3 install fastapi 'uvicorn[standard]'",
    "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get(\"/items/{item_id}\")\ndef read_item(item_id: int):\n    return {\"item_id\": item_id}\nEOF"
  ]
}
```

### Task 4: Query Parameters
```json
{
  "instance_id": "fastapi-query-parameters",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",

  "problem_statement": "Follow the FastAPI Query Parameters tutorial.\n\nTask:\n1. Install FastAPI and uvicorn\n2. Create main.py with query parameter endpoint: GET /items/?skip=0&limit=10\n3. Endpoint should return {\"skip\": skip, \"limit\": limit}\n4. Verify server responds with correct query parameter values",

  "notes": "Query parameters tutorial - URL query strings.",

  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/query-params.md",

  "success_command": "timeout 10 bash -c 'uvicorn main:app --host 0.0.0.0 --port 8000 & sleep 3 && curl -s \"http://localhost:8000/items?skip=5&limit=20\" | grep -q \"\\\"skip\\\":5.*\\\"limit\\\":20\" && killall -9 uvicorn' && echo 'Setup successful' || echo 'Setup failed'",

  "timeout_seconds": 300,

  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip curl",
    "pip3 install fastapi 'uvicorn[standard]'",
    "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get(\"/items\")\ndef read_items(skip: int = 0, limit: int = 10):\n    return {\"skip\": skip, \"limit\": limit}\nEOF"
  ]
}
```

### Task 5: Request Body (POST)
```json
{
  "instance_id": "fastapi-request-body",
  "repo_url": "https://github.com/tiangolo/fastapi",
  "base_commit": "d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d",
  "language": "python",
  "base_image": "ubuntu:22.04",

  "problem_statement": "Follow the FastAPI Request Body tutorial.\n\nTask:\n1. Install FastAPI, uvicorn, and pydantic\n2. Create main.py with POST endpoint that accepts an Item model\n3. Item should have fields: name (str), description (optional str), price (float)\n4. Endpoint should return the received item\n5. Verify server accepts and validates JSON POST requests",

  "notes": "Request body tutorial - POST with Pydantic validation.",

  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/body.md",

  "success_command": "timeout 10 bash -c 'uvicorn main:app --host 0.0.0.0 --port 8000 & sleep 3 && curl -s -X POST http://localhost:8000/items/ -H \"Content-Type: application/json\" -d \"{\\\"name\\\":\\\"Test\\\",\\\"price\\\":42.5}\" | grep -q \"\\\"name\\\":\\\"Test\\\".*\\\"price\\\":42.5\" && killall -9 uvicorn' && echo 'Setup successful' || echo 'Setup failed'",

  "timeout_seconds": 300,

  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip curl",
    "pip3 install fastapi 'uvicorn[standard]' pydantic",
    "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\nfrom pydantic import BaseModel\nfrom typing import Optional\n\napp = FastAPI()\n\nclass Item(BaseModel):\n    name: str\n    description: Optional[str] = None\n    price: float\n\n@app.post(\"/items/\")\ndef create_item(item: Item):\n    return item\nEOF"
  ]
}
```

---

## 5. Success Command Patterns

### Pattern 1: Simple Import Check
```bash
python3 -c 'import fastapi; import uvicorn' && echo 'Setup successful' || echo 'Setup failed'
```

### Pattern 2: Server Response Check
```bash
timeout 10 bash -c 'uvicorn main:app & sleep 3 && curl -s http://localhost:8000 | grep -q "expected_text" && killall uvicorn' && echo 'Setup successful' || echo 'Setup failed'
```

### Pattern 3: CLI Tool Verification
```bash
fastapi --version && echo 'Setup successful' || echo 'Setup failed'
```

### Pattern 4: Database Query Check
```bash
mysql -u root -e "USE test_db; SELECT COUNT(*) FROM users;" | grep -q '[1-9]' && echo 'Setup successful' || echo 'Setup failed'
```

### Key Principles

1. **Always end with `&& echo 'Setup successful' || echo 'Setup failed'`**
2. **Use timeout for server commands** to prevent hanging
3. **Kill background processes** (uvicorn, etc.) to clean up
4. **Use grep -q for pattern matching** (quiet mode, exit code based)
5. **Chain commands with &&** to ensure sequential execution

---

## 6. Task File Structure

### Recommended: Single JSON File

**File:** `tasks/fastapi_tasks.json`

```json
{
  "metadata": {
    "name": "FastAPI Tutorial Tasks",
    "description": "Progressive tasks covering FastAPI tutorial sections",
    "library": "FastAPI",
    "version": "0.100",
    "created": "2025-01-14",
    "total_tasks": 5
  },
  "tasks": [
    {
      "instance_id": "fastapi-install-basic",
      ...
    },
    {
      "instance_id": "fastapi-first-steps",
      ...
    },
    ...
  ]
}
```

### Loading Tasks in Python

```python
from pathlib import Path
import json
from typing import List
from .schemas_defs import Task

def load_tasks_from_json(tasks_file: Path) -> List[Task]:
    """Load tasks from JSON file."""
    with open(tasks_file) as f:
        data = json.load(f)

    return [Task(**task_dict) for task_dict in data["tasks"]]

# Usage in run_full_experiment.py
tasks = load_tasks_from_json(Path("tasks/fastapi_tasks.json"))
for task in tasks:
    run_experiment(task)
```

---

## 7. Comparison: Current vs SetupBench-Style

### Current Approach

**Pros:**
- Simple: Tasks defined in Python code
- Flexible: Easy to modify during development

**Cons:**
- Not deterministic: Success = agent didn't crash
- No independent validation: Trust agent's self-report
- Hard to reproduce: No commit hash pinning

### SetupBench-Style Approach

**Pros:**
- Deterministic: Success verified by independent command
- Reproducible: Specific commit hash and base image
- Debuggable: Clear success command shows what's expected
- Separates concerns: Agent execution vs validation

**Cons:**
- More upfront work: Need to craft success commands
- Requires validation harness: Additional infrastructure

### Migration Path

1. **Phase 1**: Define new Task schema with validation fields
2. **Phase 2**: Create ValidationHarness class
3. **Phase 3**: Integrate harness into Docker execution flow
4. **Phase 4**: Create FastAPI tasks JSON file
5. **Phase 5**: Update run_full_experiment.py to load from JSON
6. **Phase 6**: Run experiments and compare results

---

## 8. Expected Benefits

### 1. Catch Agent Hallucinations
**Example:** Agent says "Successfully started server" but server isn't actually running.
- **Current:** Counts as success (agent completed without error)
- **SetupBench-style:** Counts as failure (validation command finds no server)

### 2. Reproducible Experiments
**Example:** Want to re-run experiment 6 months later.
- **Current:** FastAPI repo has changed, results differ
- **SetupBench-style:** Checkout specific commit hash, exact reproduction

### 3. Clear Success Criteria
**Example:** What does "setup FastAPI" mean exactly?
- **Current:** Implicit, agent decides
- **SetupBench-style:** Explicit success_command defines success

### 4. Better Error Analysis
**Example:** Why did agent fail?
- **Current:** Parse agent logs to understand what went wrong
- **SetupBench-style:** Validation output shows exactly what's missing

### 5. Fair Comparison
**Example:** Comparing vanilla vs walkthrough agents.
- **Current:** Different agents might interpret "success" differently
- **SetupBench-style:** Same validation command for both, objective comparison

---

## 9. Implementation Checklist

- [ ] Update `schemas_defs.py` with new Task schema
- [ ] Create `validation_harness.py` with ValidationHarness class
- [ ] Update `harness_docker.py` to integrate validation
- [ ] Update AgentResult schema with validation fields
- [ ] Create `tasks/fastapi_tasks.json` with 5 tasks
- [ ] Update `run_full_experiment.py` to load tasks from JSON
- [ ] Create helper function to load tasks from JSON
- [ ] Update experiment results to show agent vs validation success
- [ ] Test validation harness independently
- [ ] Run full experiment with both agents
- [ ] Document results comparing agent self-report vs validation

---

## 10. References

- **SetupBench Paper**: arXiv:2507.09063v1 [cs.SE] 11 Jul 2025
- **SetupBench Repo**: https://github.com/microsoft/SetupBench
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Better Onboarding Framework**: Krystal Higgins' structured onboarding approach

---

## Appendix: Validation Command Debugging

### Common Issues

#### 1. Server Doesn't Stop
**Problem:** uvicorn keeps running after validation
**Solution:** Add `killall -9 uvicorn` in success_command

#### 2. Timeout Too Short
**Problem:** Server hasn't fully started before curl
**Solution:** Increase sleep time (sleep 5 instead of sleep 3)

#### 3. Pattern Not Matching
**Problem:** grep -q fails even though output looks correct
**Solution:** Use `curl -v` to see full response, check escaping

#### 4. Port Already in Use
**Problem:** Previous run didn't clean up
**Solution:** Check for existing processes before starting server

### Testing Success Commands

```bash
# Test success command locally
cd /path/to/workspace
bash -c 'YOUR_SUCCESS_COMMAND_HERE'
echo "Exit code: $?"

# Should see:
# - "Setup successful" in output
# - Exit code: 0
```
