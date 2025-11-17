# Task Definition Guide

This directory contains task definitions for the vanilla vs walkthrough agent comparison framework. Tasks follow the **SetupBench** structure and philosophy, providing deterministic, reproducible benchmarks for evaluating agent performance on software setup tasks.

## Table of Contents

- [Overview](#overview)
- [Task Structure](#task-structure)
- [Field Reference](#field-reference)
- [Creating New Tasks](#creating-new-tasks)
- [Best Practices](#best-practices)
- [Task Categories](#task-categories)
- [Validation Commands](#validation-commands)
- [Examples](#examples)

---

## Overview

### What is a Task?

A **task** is a self-contained setup challenge that tests an agent's ability to:
- Read and interpret documentation
- Install dependencies in a minimal environment
- Configure software correctly
- Validate that the setup works

### Task Format

Tasks are defined in **JSON files** with this structure:

```json
{
  "metadata": {
    "name": "Task Collection Name",
    "description": "Brief description",
    "library": "Library Name",
    "version": "1.0",
    "created": "2025-01-14",
    "total_tasks": 5
  },
  "tasks": [
    { /* task 1 */ },
    { /* task 2 */ },
    { /* task 3 */ }
  ]
}
```

Each file can contain multiple related tasks (e.g., progressive difficulty, tutorial sections).

---

## Task Structure

### Required Fields

Every task **must** include these fields:

| Field | Type | Description |
|-------|------|-------------|
| `instance_id` | string | Unique identifier (e.g., `"fastapi-first-steps"`) |
| `repo_url` | string | GitHub repository URL |
| `base_commit` | string | Specific commit hash for reproducibility |
| `language` | string | Programming language (`"python"`, `"javascript"`, `"ruby"`, etc.) |
| `base_image` | string | Docker base image (usually `"ubuntu:22.04"`) |
| `problem_statement` | string | Full task description with constraints |
| `notes` | string | Brief human-readable summary |
| `docs_folder` | string | Path to docs within repo (e.g., `"docs/en"`) |
| `target_doc` | string | Specific doc file (e.g., `"tutorial/first-steps.md"`) |
| `success_command` | string | Shell command to validate completion |
| `timeout_seconds` | number | Maximum time allowed for agent execution |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `branch` | string | Git branch to clone (default: `"main"`) |
| `build_commands` | array | Reference implementation steps (not used by agents) |
| `metadata` | object | Additional custom metadata |

---

## Field Reference

### `instance_id`

**Format:** `library-topic-variant`

**Examples:**
- `fastapi-first-steps`
- `fastapi-query-parameters`
- `django-admin-setup`
- `react-create-app`

**Guidelines:**
- Use lowercase with hyphens
- Include library name prefix
- Be descriptive but concise
- Must be unique across all tasks

### `repo_url`

**Format:** Full GitHub repository URL

**Example:** `https://github.com/tiangolo/fastapi`

**Guidelines:**
- Must be a public GitHub repository
- Should point to official/canonical repository
- Will be cloned into `/testbed` during execution

### `base_commit`

**Format:** Full 40-character Git commit SHA

**Example:** `d78b5e872c8a9e5f6ccf21932e3e4e0a2b5f4c3d`

**Guidelines:**
- Pin to a specific commit for reproducibility
- Use a stable, well-tested commit
- Document commit date in task metadata if helpful

### `language`

**Examples:** `python`, `javascript`, `ruby`, `go`, `rust`, `java`

**Guidelines:**
- Use lowercase
- Single word (no "Node.js", just "javascript")
- Helps categorize tasks

### `base_image`

**Standard:** `ubuntu:22.04`

**Guidelines:**
- Use `ubuntu:22.04` unless specific requirements demand otherwise
- Matches SetupBench standard
- Minimal environment (no preinstalled dev tools)

### `problem_statement`

**Structure:** Follow SetupBench's format exactly:

```
Follow the [Library] [Topic] tutorial to [goal].

Environment: Fresh Ubuntu 22.04 with no preinstalled [language] packages.

Constraints:
- Install all dependencies globally (no virtual environments)
- Non-interactive setup suitable for headless CI
- You have root privileges

Task:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Validation: [Brief explanation of what will be tested]
```

**Example:**

```
Follow the FastAPI First Steps tutorial to create a basic API application.

Environment: Fresh Ubuntu 22.04 with no preinstalled Python packages.

Constraints:
- Install all dependencies globally (no virtual environments)
- Non-interactive setup suitable for headless CI
- You have root privileges

Task:
1. Install FastAPI and uvicorn
2. Create a file named main.py with a FastAPI application
3. The application should have a root endpoint (GET /) that returns {"Hello": "World"}
4. The server must start and respond correctly to HTTP requests

Validation: The server will be started, tested with curl, and then stopped.
```

### `notes`

**Purpose:** One-sentence summary for humans

**Examples:**
- `"Basic FastAPI app with single GET endpoint at root path"`
- `"Path parameters tutorial - dynamic URL paths with type validation"`
- `"Install PostgreSQL, create database, and run schema/seed files"`

**Guidelines:**
- Keep under 80 characters
- Focus on what makes this task unique
- Not read by agents

### `docs_folder` and `target_doc`

**Purpose:** Guide agents to relevant documentation

**Examples:**
```json
{
  "docs_folder": "docs/en/docs",
  "target_doc": "tutorial/first-steps.md"
}
```

**Guidelines:**
- `docs_folder`: Path from repo root to documentation directory
- `target_doc`: Relative path within docs_folder to specific file
- Combined, they point to documentation agent should read
- For vanilla agent: primary reference material
- For walkthrough agent: source material for walkthrough generation

### `success_command`

**Purpose:** Deterministic validation that proves the setup worked

**Structure:**
```bash
[test command] && echo 'Setup successful' || echo 'Setup failed'
```

**Important:** Must end with `echo 'Setup successful'` on success. The validation harness checks for this exact string.

**Examples:**

**Simple import test:**
```bash
python3 -c 'import fastapi; import uvicorn; print(f"FastAPI {fastapi.__version__}")' && echo 'Setup successful' || echo 'Setup failed'
```

**Server test:**
```bash
timeout 10 bash -c 'uvicorn main:app --host 0.0.0.0 --port 8000 & sleep 3 && curl -s http://localhost:8000 | grep -q "Hello.*World" && killall -9 uvicorn' && echo 'Setup successful' || echo 'Setup failed'
```

**Database test:**
```bash
PGPASSWORD=mypass psql -U myuser -d mydb -c "SELECT COUNT(*) FROM users;" | grep -q '[1-9]' && echo "Setup successful" || echo "Setup failed"
```

**Guidelines:**
- Must be non-interactive (no user input)
- Must complete quickly (< 30 seconds typical)
- Must be deterministic (same result every time)
- Must clean up background processes
- Must return exit code 0 on success
- Must print "Setup successful" on success

### `timeout_seconds`

**Typical Values:**
- Simple tasks (install only): 300 (5 minutes)
- Medium tasks (install + setup): 600 (10 minutes)
- Complex tasks (build from source): 1800 (30 minutes)

**Guidelines:**
- Allow enough time for slow networks
- Account for apt updates and package installs
- Consider compilation time for native code
- Default: 300 seconds

### `build_commands`

**Purpose:** Reference implementation for task creators (not used by agents)

**Example:**
```json
{
  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip",
    "pip3 install fastapi 'uvicorn[standard]'",
    "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\napp = FastAPI()\n@app.get(\"/\")\ndef read_root():\n    return {\"Hello\": \"World\"}\nEOF"
  ]
}
```

**Guidelines:**
- Document the "golden path" solution
- Helps verify task is actually solvable
- Useful for debugging task definitions
- Not provided to agents

---

## Creating New Tasks

### Step 1: Choose a Library and Topic

**Criteria:**
- Library has good documentation
- Setup process is well-defined
- Validation is straightforward
- Task is educational/representative

**Good Examples:**
- Web frameworks (FastAPI, Flask, Express, Rails)
- Databases (PostgreSQL, MySQL, MongoDB, Redis)
- Build tools (Webpack, Vite, Cargo, Maven)
- CLI tools (Click, Commander, Cobra)

### Step 2: Define Learning Objectives

What should the agent learn/demonstrate?

**Examples:**
- Basic installation and import verification
- Creating and running a simple application
- Configuration and environment setup
- Database schema and data management
- Testing and validation

### Step 3: Write the Problem Statement

Follow the SetupBench template:

1. **Opening:** "Follow the [Library] [Topic] tutorial to [goal]."
2. **Environment:** "Fresh Ubuntu 22.04 with no preinstalled [language] packages."
3. **Constraints:** List the standard constraints (global installs, non-interactive, root privileges)
4. **Task:** Numbered steps describing what to do
5. **Validation:** Brief note about how success will be tested

### Step 4: Design the Success Command

**Checklist:**
- ✅ Tests the actual functionality (not just file existence)
- ✅ Runs in < 30 seconds
- ✅ Cleans up background processes
- ✅ Ends with `&& echo 'Setup successful' || echo 'Setup failed'`
- ✅ Works in a fresh shell (no environment dependencies)
- ✅ Is deterministic (no flakiness)

**Test your success command:**
```bash
docker run --rm -it ubuntu:22.04 bash
# ... do the setup manually ...
# ... run your success command ...
```

### Step 5: Identify Documentation

**Find:**
- Repository URL
- Stable commit hash
- Documentation folder path
- Specific tutorial/guide file

**Verify:**
- Documentation is clear and complete
- Documentation matches your task requirements
- Documentation is at the pinned commit

### Step 6: Write Build Commands (Optional but Recommended)

Document the reference solution:

```json
"build_commands": [
  "# Install system dependencies",
  "apt-get update && apt-get install -y python3 python3-pip curl",

  "# Install application dependencies",
  "pip3 install fastapi 'uvicorn[standard]'",

  "# Create application file",
  "cat > main.py << 'EOF'\nfrom fastapi import FastAPI\napp = FastAPI()\n@app.get(\"/\")\ndef read_root():\n    return {\"Hello\": \"World\"}\nEOF"
]
```

### Step 7: Test the Task

**Manual Testing:**
```bash
# 1. Clone the repo at the specified commit
git clone <repo_url> /testbed
cd /testbed
git checkout <base_commit>

# 2. Follow your problem_statement instructions

# 3. Run your success_command
<success_command>
```

**Automated Testing:**
```bash
# Use the experiment runner
python run_full_experiment.py
```

### Step 8: Add to Task Collection

Add your task to an existing collection JSON file or create a new one:

```json
{
  "metadata": {
    "name": "My Library Tasks",
    "description": "Progressive tasks for My Library",
    "library": "MyLibrary",
    "version": "2.0",
    "created": "2025-01-17",
    "total_tasks": 1
  },
  "tasks": [
    {
      "instance_id": "mylibrary-hello-world",
      "repo_url": "https://github.com/example/mylibrary",
      // ... rest of task definition
    }
  ]
}
```

---

## Best Practices

### ✅ DO

- **Pin to specific commits** - Ensures reproducibility
- **Test success commands thoroughly** - Avoid flaky validation
- **Use standard base image** - `ubuntu:22.04` unless requirements dictate otherwise
- **Write clear problem statements** - Follow SetupBench template
- **Clean up background processes** - Kill servers, daemons, etc.
- **Make validation fast** - Target < 10 seconds for success_command
- **Document reference solutions** - Use `build_commands` field
- **Use realistic scenarios** - Tasks should reflect real-world usage
- **Progressive difficulty** - Group related tasks by increasing complexity

### ❌ DON'T

- **Don't assume preinstalled tools** - Not even curl, git, or build-essential
- **Don't use virtual environments** - Agent must install globally
- **Don't require user interaction** - Must work in headless CI
- **Don't create brittle validation** - Avoid timing-dependent tests
- **Don't leave processes running** - Clean up after success_command
- **Don't use floating versions** - Pin commits, not branches
- **Don't write vague problem statements** - Be specific and structured
- **Don't forget to test** - Verify tasks work end-to-end

---

## Task Categories

Tasks generally fall into these categories (aligned with SetupBench):

### 1. **Dependency Resolution**
Installing packages and resolving dependency conflicts.

**Example:** `fastapi-install-basic`
```json
{
  "instance_id": "fastapi-install-basic",
  "problem_statement": "Install FastAPI and uvicorn packages...",
  "success_command": "python3 -c 'import fastapi; import uvicorn' && echo 'Setup successful' || echo 'Setup failed'"
}
```

### 2. **Repository Setup**
Cloning, configuring, and running a complete application.

**Example:** `fastapi-first-steps`
```json
{
  "instance_id": "fastapi-first-steps",
  "problem_statement": "Create a FastAPI application with a single GET endpoint...",
  "success_command": "timeout 10 bash -c 'uvicorn main:app & sleep 3 && curl -s http://localhost:8000 | grep -q \"Hello\"' && echo 'Setup successful' || echo 'Setup failed'"
}
```

### 3. **Database Setup**
Installing, configuring, and initializing databases.

**Example:** `postgresql-basic`
```json
{
  "instance_id": "postgresql-basic",
  "problem_statement": "Install PostgreSQL, create a database and user, run schema files...",
  "success_command": "PGPASSWORD=pass psql -U user -d db -c 'SELECT 1' && echo 'Setup successful' || echo 'Setup failed'"
}
```

### 4. **Background Service Setup**
Setting up long-running services (servers, workers, daemons).

**Example:** `redis-celery-worker`
```json
{
  "instance_id": "redis-celery-worker",
  "problem_statement": "Install Redis and Celery, configure worker as background service...",
  "success_command": "redis-cli GET health | grep -q 'ok' && echo 'Setup successful' || echo 'Setup failed'"
}
```

---

## Validation Commands

### Testing Imports

**Python:**
```bash
python3 -c 'import module_name; print(module_name.__version__)' && echo 'Setup successful' || echo 'Setup failed'
```

**Node.js:**
```bash
node -e "require('module-name'); console.log('ok')" && echo 'Setup successful' || echo 'Setup failed'
```

**Ruby:**
```bash
ruby -e "require 'gem_name'; puts 'ok'" && echo 'Setup successful' || echo 'Setup failed'
```

### Testing Servers

**Web Server (with cleanup):**
```bash
timeout 10 bash -c '
  uvicorn main:app --host 0.0.0.0 --port 8000 </dev/null &>/dev/null &
  SERVER_PID=$!
  sleep 3
  curl -s http://localhost:8000 | grep -q "expected-content"
  RESULT=$?
  kill -9 $SERVER_PID 2>/dev/null || true
  exit $RESULT
' && echo 'Setup successful' || echo 'Setup failed'
```

**Notes:**
- Use `timeout` to prevent hangs
- Capture server PID to kill it specifically
- `</dev/null &>/dev/null` prevents terminal attachment
- Always clean up with `kill -9` after test

### Testing Databases

**PostgreSQL:**
```bash
PGPASSWORD=mypass psql -U myuser -d mydb -c "SELECT COUNT(*) FROM table_name;" | grep -q '[1-9]' && echo "Setup successful" || echo "Setup failed"
```

**MySQL:**
```bash
mysql -u root -ppassword -e "USE mydb; SHOW TABLES;" | grep -q 'expected_table' && echo "Setup successful" || echo "Setup failed"
```

**MongoDB:**
```bash
mongosh mydb --eval "db.collection.countDocuments({})" | grep -q '[1-9]' && echo "Setup successful" || echo "Setup failed"
```

**Redis:**
```bash
redis-cli GET my_key | grep -q "expected_value" && echo "Setup successful" || echo "Setup failed"
```

**SQLite:**
```bash
sqlite3 /path/to/db.sqlite "SELECT COUNT(*) FROM items;" | grep -q '[1-9]' && echo "Setup successful" || echo "Setup failed"
```

### Testing Files

**File existence:**
```bash
test -f /path/to/file && echo "Setup successful" || echo "Setup failed"
```

**File content:**
```bash
grep -q "expected-content" /path/to/file && echo "Setup successful" || echo "Setup failed"
```

**Configuration validity:**
```bash
python3 -m json.tool config.json >/dev/null 2>&1 && echo "Setup successful" || echo "Setup failed"
```

---

## Examples

### Example 1: Simple Installation Task

```json
{
  "instance_id": "requests-install",
  "repo_url": "https://github.com/psf/requests",
  "base_commit": "6c5e6b2e12a8c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
  "language": "python",
  "base_image": "ubuntu:22.04",
  "problem_statement": "Install the Python requests library.\n\nEnvironment: Fresh Ubuntu 22.04 with no preinstalled Python packages.\n\nConstraints:\n- Install all dependencies globally (no virtual environments)\n- Non-interactive setup suitable for headless CI\n- You have root privileges\n\nTask:\nInstall the requests library and verify it can be imported successfully.\n\nValidation: Python import test will verify installation.",
  "notes": "Simple installation - verify requests can be imported",
  "docs_folder": "docs",
  "target_doc": "user/install.md",
  "success_command": "python3 -c 'import requests; print(f\"Requests {requests.__version__}\")' && echo 'Setup successful' || echo 'Setup failed'",
  "timeout_seconds": 300,
  "build_commands": [
    "apt-get update && apt-get install -y python3 python3-pip",
    "pip3 install requests"
  ]
}
```

### Example 2: Web Server Task

```json
{
  "instance_id": "express-hello-world",
  "repo_url": "https://github.com/expressjs/express",
  "base_commit": "7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6",
  "language": "javascript",
  "base_image": "ubuntu:22.04",
  "problem_statement": "Create a basic Express.js web server.\n\nEnvironment: Fresh Ubuntu 22.04 with no preinstalled Node.js.\n\nConstraints:\n- Install all dependencies globally (no local node_modules)\n- Non-interactive setup suitable for headless CI\n- You have root privileges\n\nTask:\n1. Install Node.js and npm\n2. Install Express.js globally\n3. Create a file named server.js with an Express server\n4. The server should listen on port 3000\n5. The root endpoint (GET /) should return \"Hello World\"\n\nValidation: Server will be started, tested with curl, and stopped.",
  "notes": "Basic Express server with Hello World endpoint",
  "docs_folder": "docs",
  "target_doc": "getting-started.md",
  "success_command": "timeout 10 bash -c 'node server.js </dev/null &>/dev/null & SERVER_PID=$!; sleep 3; curl -s http://localhost:3000 | grep -q \"Hello World\"; RESULT=$?; kill -9 $SERVER_PID 2>/dev/null || true; exit $RESULT' && echo 'Setup successful' || echo 'Setup failed'",
  "timeout_seconds": 300,
  "build_commands": [
    "apt-get update && apt-get install -y curl",
    "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
    "apt-get install -y nodejs",
    "npm install -g express",
    "cat > server.js << 'EOF'\nconst express = require('express');\nconst app = express();\napp.get('/', (req, res) => res.send('Hello World'));\napp.listen(3000);\nEOF"
  ]
}
```

### Example 3: Database Setup Task

```json
{
  "instance_id": "postgresql-users-table",
  "repo_url": "https://github.com/postgres/postgres",
  "base_commit": "1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0",
  "language": "sql",
  "base_image": "ubuntu:22.04",
  "problem_statement": "Set up PostgreSQL with a users table.\n\nEnvironment: Fresh Ubuntu 22.04 with no preinstalled database software.\n\nConstraints:\n- Install all dependencies globally\n- Non-interactive setup suitable for headless CI\n- You have root privileges\n\nTask:\n1. Install PostgreSQL\n2. Create a database named 'appdb'\n3. Create a user named 'appuser' with password 'apppass'\n4. Create a 'users' table with columns: id (serial primary key), name (varchar), email (varchar)\n5. Insert at least one test record\n\nValidation: Query will verify table exists and contains data.",
  "notes": "PostgreSQL installation with database, user, and table creation",
  "docs_folder": "doc/src/sgml",
  "target_doc": "tutorial.sgml",
  "success_command": "PGPASSWORD=apppass psql -U appuser -d appdb -c \"SELECT COUNT(*) FROM users;\" | grep -q '[1-9]' && echo 'Setup successful' || echo 'Setup failed'",
  "timeout_seconds": 600,
  "build_commands": [
    "apt-get update && apt-get install -y postgresql postgresql-contrib",
    "service postgresql start",
    "sudo -u postgres psql -c \"CREATE DATABASE appdb;\"",
    "sudo -u postgres psql -c \"CREATE USER appuser WITH PASSWORD 'apppass';\"",
    "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;\"",
    "sudo -u postgres psql appdb -c \"CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(100), email VARCHAR(100));\"",
    "sudo -u postgres psql appdb -c \"INSERT INTO users (name, email) VALUES ('Test User', 'test@example.com');\""
  ]
}
```

---

## Integration with Experiment Runner

Tasks defined here are used by:

1. **run_full_experiment.py** - Main orchestrator
   - Loads task definitions
   - Clones repository at specified commit
   - Generates walkthrough (walkthrough agent)
   - Runs both agents in Docker containers
   - Validates results
   - Compares metrics

2. **WalkthroughGenerator** - Creates structured walkthroughs
   - Uses `target_doc` as source material
   - Generates step-by-step guidance
   - Resolves code snippets from repo

3. **DockerHarness** - Executes agents
   - Mounts repo at `/testbed`
   - Provides docs at `/workspace/docs`
   - Runs `success_command` for validation

---

## Questions?

For more details on:
- **Task execution**: See `/docs/ARCHITECTURE.md`
- **Agent prompts**: See `/src/cc_experiment_runner/agents/`
- **SetupBench reference**: See `/SetupBench/` repository

Happy task creation! 🚀
