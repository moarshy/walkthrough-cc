# StackBench Hooks

This directory contains programmatic hooks for StackBench agents. Hooks provide deterministic control over agent behavior by executing at specific points in the agent lifecycle.

## Overview

StackBench uses [Claude Code hooks](https://docs.claude.com/en/docs/claude-code/hooks) to validate outputs and log execution details. All hooks are implemented as **programmatic Python hooks** using the Claude Agent SDK, providing better type safety, debugging, and integration compared to shell-based hooks.

## Hook Types

### 1. Validation Hooks (`validation.py`)

**Purpose**: Validate JSON output files against Pydantic schemas before they are written to disk.

**Event**: `PreToolUse` (runs before Write tool execution)

**Hooks**:

#### `create_extraction_validation_hook(output_dir)`
- **Validates**: Extraction agent outputs (`*_analysis.json`, `extraction_summary.json`)
- **Schema**: `DocumentAnalysis` - Validates API signatures and code examples structure
- **Checks**:
  - Required fields: `page`, `library`, `language`, `signatures`, `examples`, etc.
  - Field types: Ensures correct types for all fields
  - Nested validation: Validates signature and example objects
  - Output directory: Ensures files are written to the correct location
- **Behavior**: Blocks invalid JSON from being written (returns `permissionDecision: deny`)

#### `create_validation_output_hook(output_dir)`
- **Validates**: API/Code validation agent outputs (`*_validation.json`)
- **Schema**: `ValidationOutput` - Validates validation result structure
- **Checks**:
  - Required fields: `validation_id`, `validated_at`, `summary`, `validations`, etc.
  - Summary structure: `total_signatures_checked`, `valid`, `invalid`, `not_found`, `accuracy_score`
  - Environment info: Library versions, Python version
  - Validation results: Per-signature validation status and issues
- **Behavior**: Blocks invalid JSON from being written (returns `permissionDecision: deny`)

**Usage Example**:
```python
from stackbench.hooks import create_extraction_validation_hook

validation_hook = create_extraction_validation_hook(output_dir=Path("/path/to/output"))
```

---

### 2. Logging Hooks (`logging.py`)

**Purpose**: Capture all tool calls and their results for debugging and auditing.

**Events**: `PreToolUse` (before tool execution) + `PostToolUse` (after tool execution)

**Components**:

#### `AgentLogger`
A logger class that writes to two files:
- **Agent log** (`<doc>_agent.log`): Human-readable log of events with timestamps
- **Tools log** (`<doc>_tools.jsonl`): Machine-readable JSONL log of all tool calls

**Methods**:
- `log_message(message, level)`: Write a message to the agent log
- `log_tool_call(entry)`: Write a tool call entry to the JSONL log
- `get_stats()`: Get logging statistics (tool calls, messages, errors)

#### `create_logging_hooks(logger)`
Creates PreToolUse and PostToolUse hooks that:
- Log every tool call with input parameters
- Log every tool result with output data
- Track tool execution errors
- Maintain statistics on tool usage

**JSONL Format**:
```json
{
  "timestamp": "2025-10-15T10:30:00",
  "event_type": "pre_tool",
  "tool_name": "Read",
  "tool_input": {"file_path": "/path/to/file"},
  "tool_use_id": "toolu_123"
}
{
  "timestamp": "2025-10-15T10:30:01",
  "event_type": "post_tool",
  "tool_name": "Read",
  "tool_input": {"file_path": "/path/to/file"},
  "tool_output": {"content": "..."},
  "tool_use_id": "toolu_123",
  "error": null
}
```

**Usage Example**:
```python
from stackbench.hooks import AgentLogger, create_logging_hooks

logger = AgentLogger(
    log_file=Path("logs/doc_agent.log"),
    tools_log_file=Path("logs/doc_tools.jsonl")
)

hooks = create_logging_hooks(logger)
```

---

### 3. Hook Manager (`manager.py`)

**Purpose**: Combine validation and logging hooks into a unified configuration.

**Classes**:

#### `HookManager`
Manages all hooks for an agent type. Combines:
- Validation hooks (specific to agent type)
- Logging hooks (if logger provided)

**Methods**:
- `create_hooks()`: Returns combined hook configuration

#### `create_agent_hooks(agent_type, logger, output_dir)`
Convenience function to create hooks for an agent.

**Parameters**:
- `agent_type`: One of `"extraction"`, `"api_validation"`, `"code_validation"`
- `logger`: Optional `AgentLogger` for logging hooks
- `output_dir`: Optional output directory for validation hooks

**Returns**: Dictionary with `PreToolUse` and `PostToolUse` hook configurations

**Usage Example**:
```python
from stackbench.hooks import create_agent_hooks, AgentLogger
from pathlib import Path

# Create logger
logger = AgentLogger(
    log_file=Path("logs/extraction/doc_agent.log"),
    tools_log_file=Path("logs/extraction/doc_tools.jsonl")
)

# Create combined hooks
hooks = create_agent_hooks(
    agent_type="extraction",
    logger=logger,
    output_dir=Path("data/run_123/results/extraction")
)

# Use with ClaudeAgentOptions
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write"],
    permission_mode="acceptEdits",
    hooks=hooks  # Pass combined hooks
)
```

---

## Hook Execution Flow

### Extraction Agent

```
┌─────────────────────────────────────────────────────┐
│ 1. Agent starts processing document                 │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 2. PreToolUse Hook: Log tool call (Read)           │
│    - Write to tools.jsonl                           │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 3. Tool executes (Read markdown file)               │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 4. PostToolUse Hook: Log tool result               │
│    - Write to tools.jsonl                           │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 5. PreToolUse Hook: Validate extraction JSON        │
│    - Check schema against DocumentAnalysis          │
│    - Check output directory location                │
│    - BLOCK if validation fails                      │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 6. PreToolUse Hook: Log tool call (Write)          │
│    - Write to tools.jsonl                           │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 7. Tool executes (Write analysis.json)              │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 8. PostToolUse Hook: Log tool result               │
│    - Write to tools.jsonl                           │
└─────────────────────────────────────────────────────┘
```

### API Validation Agent

Similar flow, but uses `create_validation_output_hook()` for validating `*_validation.json` files.

### Code Validation Agent

Similar flow, uses validation hooks for code validation outputs.

---

## Integration with Agents

Each agent should:

1. **Accept a logger parameter** (optional):
   ```python
   def __init__(self, ..., logger: Optional[AgentLogger] = None):
       self.logger = logger
   ```

2. **Create per-document loggers**:
   ```python
   doc_logger = AgentLogger(
       log_file=log_dir / f"{doc_name}_agent.log",
       tools_log_file=log_dir / f"{doc_name}_tools.jsonl"
   )
   ```

3. **Create hooks with hook manager**:
   ```python
   from stackbench.hooks import create_agent_hooks

   hooks = create_agent_hooks(
       agent_type="extraction",
       logger=doc_logger,
       output_dir=self.output_folder
   )
   ```

4. **Pass hooks to ClaudeAgentOptions**:
   ```python
   options = ClaudeAgentOptions(
       system_prompt=SYSTEM_PROMPT,
       allowed_tools=["Read", "Write"],
       permission_mode="acceptEdits",
       hooks=hooks  # ← Add hooks here
   )
   ```

---

## Log Directory Structure

When integrated with the pipeline, logs are organized as:

```
data/
└── <run_id>/
    ├── repo/                      # Cloned repository
    ├── results/                   # Agent outputs
    │   ├── extraction/
    │   ├── api_validation/
    │   └── code_validation/
    └── logs/                      # Agent execution logs
        ├── extraction/
        │   ├── quickstart_agent.log
        │   ├── quickstart_tools.jsonl
        │   ├── api_reference_agent.log
        │   ├── api_reference_tools.jsonl
        │   └── summary.json
        ├── api_validation/
        │   └── ...
        └── code_validation/
            └── ...
```

---

## Benefits of Programmatic Hooks

### vs. Shell-based Hooks (`.claude/settings.json`)

| Feature | Programmatic Hooks | Shell-based Hooks |
|---------|-------------------|-------------------|
| **Type Safety** | ✅ Python types | ❌ JSON strings |
| **Debugging** | ✅ Python debugger | ❌ Subprocess debugging |
| **Error Handling** | ✅ Try/catch blocks | ❌ Exit codes only |
| **Integration** | ✅ Direct API access | ❌ File I/O only |
| **Testing** | ✅ Unit testable | ❌ Integration tests only |
| **Dependencies** | ✅ Python stdlib | ❌ Requires jq, shell utils |
| **Platform** | ✅ Cross-platform | ⚠️ Shell-dependent |

---

## Schema Definitions

### DocumentAnalysis Schema (Extraction)

```python
{
    "required_fields": [
        "page", "library", "language", "signatures", "examples",
        "processed_at", "total_signatures", "total_examples", "warnings"
    ],
    "nested_schemas": {
        "signatures": {
            "required_fields": [
                "library", "function", "params", "param_types",
                "defaults", "imports", "line", "context"
            ]
        },
        "examples": {
            "required_fields": [
                "library", "language", "code", "has_main",
                "is_executable", "line", "context", "dependencies"
            ]
        }
    }
}
```

### ValidationOutput Schema (API/Code Validation)

```python
{
    "required_fields": [
        "validation_id", "validated_at", "source_file",
        "library", "version", "language", "summary",
        "validations", "environment", "processing", "warnings"
    ],
    "nested_schemas": {
        "summary": {
            "required_fields": [
                "total_signatures_checked", "valid", "invalid",
                "not_found", "accuracy_score"
            ]
        },
        "validations": {
            "required_fields": [
                "signature_id", "function", "library",
                "status", "documented", "issues"
            ]
        }
    }
}
```

---

## Future Enhancements

Potential additions to the hooks system:

1. **Performance Hooks**: Track execution time per tool call
2. **Cost Hooks**: Track API costs per agent run
3. **Retry Hooks**: Automatic retry on specific failures
4. **Notification Hooks**: Alert on errors or completion
5. **Metrics Hooks**: Export metrics to monitoring systems

---

## Related Documentation

- [Claude Code Hooks Reference](https://docs.claude.com/en/docs/claude-code/hooks)
- [Claude Agent SDK Documentation](https://docs.claude.com/en/docs/claude-code/agent-sdk)
- StackBench Pipeline: `stackbench/pipeline/runner.py`
- StackBench Agents: `stackbench/agents/`

---

## Troubleshooting

### Hook not executing

1. Check that hooks are passed to `ClaudeAgentOptions`
2. Verify hook matcher (tool name) is correct
3. Enable debug logging: `logger.log_message("Debug info")`

### Validation blocking valid output

1. Check schema definitions in `validation.py`
2. Verify JSON structure matches Pydantic models
3. Review validation errors in agent output

### Log files not created

1. Check logger initialization with correct paths
2. Ensure parent directories exist
3. Verify file permissions

---

## Contributing

When adding new hooks:

1. Add hook function to appropriate module (`validation.py` or `logging.py`)
2. Update `HookManager.create_hooks()` to include the new hook
3. Document the hook in this README
4. Add tests for the hook behavior
5. Update integration examples
