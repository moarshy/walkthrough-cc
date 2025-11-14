# SetupBench-Style Implementation Summary

## ✅ Completed Implementation

We have successfully implemented the SetupBench-style task definition system with deterministic validation for the vanilla vs walkthrough agent benchmark.

---

## What Was Implemented

### 1. ✅ Updated Task Schema (`src/cc_experiment_runner/schemas_defs.py`)

**Removed old schema:**
- `TaskValidation` class (replaced with inline validation fields)
- Old `Task` class with `library_name`, `library_version`, `branch` fields

**New SetupBench-style schema:**
```python
class Task(BaseModel):
    # Core identification
    instance_id: str

    # Repository details
    repo_url: str
    base_commit: str  # Specific commit hash
    language: str
    base_image: str = "ubuntu:22.04"

    # Task description
    problem_statement: str
    notes: str

    # Documentation (for walkthrough generation)
    docs_folder: str
    target_doc: str

    # Validation
    success_command: str
    timeout_seconds: int = 300

    # Ground truth (optional)
    build_commands: Optional[List[str]] = None
```

**Enhanced AgentResult schema:**
```python
class AgentResult(BaseModel):
    # Agent execution
    agent_completed: bool  # Did agent finish?

    # Independent validation
    validation_passed: bool  # Did validation succeed?
    validation_output: str
    validation_exit_code: int
    validation_duration: float

    # Overall success (BOTH must be true)
    success: bool  # agent_completed AND validation_passed
```

### 2. ✅ Created Validation Harness (`src/cc_experiment_runner/validation_harness.py`)

**Features:**
- `ValidationHarness` class with `validate_task()` method
- Runs `success_command` in fresh subprocess
- Checks for "Setup successful" pattern (SetupBench convention)
- Returns `(success: bool, output: str, exit_code: int)`
- Handles timeouts and errors gracefully
- Includes `validate_and_log()` for detailed logging

**Key method:**
```python
def validate_task(
    self,
    task: Task,
    workspace_dir: Path,
    timeout: Optional[int] = None
) -> Tuple[bool, str, int]:
    """Run success_command in fresh shell and validate output."""
```

### 3. ✅ Created Task Loader (`src/cc_experiment_runner/task_loader.py`)

**Functions:**
- `load_tasks_from_json(tasks_file: Path) -> List[Task]` - Load all tasks from JSON
- `load_single_task(task_dict: Dict) -> Task` - Load one task from dictionary
- `load_task_by_id(tasks_file: Path, instance_id: str) -> Task` - Load specific task
- `validate_tasks_file(tasks_file: Path) -> Dict` - Validate JSON file structure

**Error handling:**
- Custom `TaskLoadError` exception
- Detailed validation error messages
- Pydantic schema validation

### 4. ✅ Created FastAPI Tasks (`tasks/fastapi_tasks.json`)

**5 progressive tasks:**

1. **fastapi-install-basic** - Install dependencies only
   - Validates: `python3 -c 'import fastapi; import uvicorn'`

2. **fastapi-first-steps** - Hello World API
   - Validates: Server responds to GET / with {"Hello": "World"}

3. **fastapi-path-parameters** - Dynamic URL paths
   - Validates: GET /items/42 returns {"item_id": 42}

4. **fastapi-query-parameters** - Query string handling
   - Validates: GET /items?skip=5&limit=20 returns correct values

5. **fastapi-request-body** - POST with Pydantic validation
   - Validates: POST /items/ with JSON body works correctly

**Each task includes:**
- Complete problem_statement with constraints
- Specific commit hash (d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d)
- Deterministic success_command
- Expected build_commands for reference
- Documentation paths for walkthrough generation

### 5. ✅ Updated Docker Harness (`src/cc_experiment_runner/harness_docker.py`)

**Key changes:**

1. **Added validation import:**
   ```python
   from .validation_harness import ValidationHarness
   ```

2. **Integrated validation after agent completes:**
   ```python
   if agent_completed:
       validator = ValidationHarness()
       validation_passed, validation_output, validation_exit_code = validator.validate_and_log(
           task=task,
           workspace_dir=repo_path,
           log_path=log_dir / f"{agent_type}_validation.log"
       )
   ```

3. **Updated success logic:**
   ```python
   # Overall success = BOTH agent completed AND validation passed
   success = agent_completed and validation_passed
   ```

4. **Updated field names:**
   - `task.id` → `task.instance_id`
   - `task.branch` → `task.base_commit`
   - Removed `library_name`, `library_version` (not in new schema)

5. **Enhanced AgentResult creation:**
   - Includes all new validation fields
   - Distinguishes agent completion from validation success
   - Logs validation results separately

---

## How It Works

### Execution Flow

```
1. Load Task from JSON
   └─> TaskLoader reads tasks/fastapi_tasks.json
   └─> Validates against Task schema

2. Clone Repository
   └─> Checkout specific commit (base_commit)
   └─> Extract docs folder

3. Generate Walkthrough (if needed)
   └─> WalkthroughGenerator reads target_doc
   └─> Produces structured JSON

4. Run Vanilla Agent (Docker container)
   └─> Agent executes setup following raw docs
   └─> Container exits with code 0 or non-zero
   └─> ValidationHarness runs success_command
   └─> Record: agent_completed + validation_passed

5. Run Walkthrough Agent (Docker container)
   └─> Agent executes setup following walkthrough JSON
   └─> Container exits with code 0 or non-zero
   └─> ValidationHarness runs success_command
   └─> Record: agent_completed + validation_passed

6. Compare Results
   └─> Analyze success rates (agent vs validation)
   └─> Identify cases where agent "hallucinates" success
```

### Validation Logic

**SetupBench-style deterministic validation:**

```python
# Success determined by pattern matching in output
success = "Setup successful" in output
```

**Example success_command:**
```bash
timeout 10 bash -c 'uvicorn main:app & sleep 3 && curl -s http://localhost:8000 | grep -q "Hello" && killall uvicorn' && echo 'Setup successful' || echo 'Setup failed'
```

**Key principle:**
- Always ends with `&& echo 'Setup successful' || echo 'Setup failed'`
- Independent of agent's self-report
- Runs in fresh shell to avoid state leakage

### Success Scenarios

| Agent Completed | Validation Passed | Overall Success | Interpretation |
|----------------|-------------------|-----------------|----------------|
| ✅ | ✅ | ✅ | Perfect - setup works correctly |
| ✅ | ❌ | ❌ | Agent hallucination - thinks it succeeded but didn't |
| ❌ | N/A | ❌ | Agent crashed/timed out |

---

## What Still Needs to Be Done

### 1. ⏳ Update `run_full_experiment.py`

**Required changes:**
- Import `task_loader`
- Load tasks from JSON instead of hardcoding
- Update to work with new Task schema fields
- Handle `base_commit` instead of `branch` for git operations

**Example:**
```python
from cc_experiment_runner.task_loader import load_tasks_from_json

# Load tasks
tasks = load_tasks_from_json(Path("tasks/fastapi_tasks.json"))

# For each task
for task in tasks:
    # Clone at specific commit
    subprocess.run(["git", "clone", task.repo_url, repo_dir])
    subprocess.run(["git", "checkout", task.base_commit], cwd=repo_dir)

    # Run experiment
    ...
```

### 2. ⏳ Update Agent System Prompts (if needed)

**Files to check:**
- `src/cc_experiment_runner/agents/vanilla_agent.py`
- `src/cc_experiment_runner/agents/walkthrough_agent.py`

**Potential updates:**
- Reference `problem_statement` instead of implicit task description
- Use `instance_id` instead of `id`
- Update to work with new task JSON structure passed to container

### 3. ⏳ Test with Single Task

**Testing steps:**
1. Load `fastapi-install-basic` task
2. Run vanilla agent
3. Check validation log
4. Run walkthrough agent
5. Check validation log
6. Compare results

### 4. ⏳ Update Repository Manager

**File:** `src/cc_experiment_runner/repository_manager.py` (or similar)

**Updates needed:**
- Use `base_commit` instead of `branch`
- Ensure git checkout works with commit hash

---

## Files Modified/Created

### Created:
- ✅ `src/cc_experiment_runner/validation_harness.py` - Independent validation
- ✅ `src/cc_experiment_runner/task_loader.py` - JSON task loading
- ✅ `tasks/fastapi_tasks.json` - 5 FastAPI benchmark tasks
- ✅ `docs/setupbench-like-plan.md` - Detailed planning document
- ✅ `docs/implementation-summary.md` - This file

### Modified:
- ✅ `src/cc_experiment_runner/schemas_defs.py` - New Task and AgentResult schemas
- ✅ `src/cc_experiment_runner/harness_docker.py` - Integrated validation

### Still Need to Modify:
- ⏳ `run_full_experiment.py` - Update to load from JSON
- ⏳ `src/cc_experiment_runner/agents/vanilla_agent.py` - Check if updates needed
- ⏳ `src/cc_experiment_runner/agents/walkthrough_agent.py` - Check if updates needed
- ⏳ `src/cc_experiment_runner/repository_manager.py` - Use base_commit

---

## Key Benefits Achieved

### 1. ✅ Deterministic Validation
**Before:** Success = agent didn't crash
**After:** Success = independent validation command passes

### 2. ✅ Reproducible Experiments
**Before:** Uses branch name (moving target)
**After:** Uses specific commit hash (fixed point)

### 3. ✅ Clear Success Criteria
**Before:** Implicit (agent decides)
**After:** Explicit (success_command defines success)

### 4. ✅ Catch Agent Hallucinations
**Before:** Can't detect when agent thinks it succeeded but didn't
**After:** Validation shows if setup actually works

### 5. ✅ Structured Task Definitions
**Before:** Hardcoded in Python
**After:** JSON files that are easy to extend and version

---

## Next Steps

1. **Update `run_full_experiment.py`** to load tasks from JSON
2. **Test with a single task** (fastapi-install-basic)
3. **Run full experiment** with all 5 tasks
4. **Analyze results** comparing agent_completed vs validation_passed rates
5. **Create more tasks** for other libraries/frameworks

---

## Usage Example

```python
from pathlib import Path
from cc_experiment_runner.task_loader import load_tasks_from_json
from cc_experiment_runner.validation_harness import ValidationHarness

# Load tasks
tasks = load_tasks_from_json(Path("tasks/fastapi_tasks.json"))
print(f"Loaded {len(tasks)} tasks")

# Run validation on a completed setup
task = tasks[0]  # fastapi-install-basic
validator = ValidationHarness()
success, output, exit_code = validator.validate_task(
    task,
    workspace_dir=Path("/workspace/repo")
)

print(f"Validation: {'PASSED' if success else 'FAILED'}")
print(f"Output: {output}")
```

---

## Success Metrics to Track

When running experiments, track these metrics:

1. **Agent Completion Rate** - % of agents that finish without errors
2. **Validation Pass Rate** - % of completed setups that pass validation
3. **Overall Success Rate** - % that pass BOTH agent completion AND validation
4. **Hallucination Rate** - % where agent completes but validation fails
5. **Comparison** - Vanilla vs Walkthrough across all metrics

Expected finding: Walkthrough agents should have:
- Higher agent completion rate
- Similar or better validation pass rate
- Lower hallucination rate
- Overall better success rate

---

## References

- **SetupBench Paper**: arXiv:2507.09063v1 [cs.SE] 11 Jul 2025
- **SetupBench Repo**: https://github.com/microsoft/SetupBench
- **Plan Document**: `docs/setupbench-like-plan.md`
