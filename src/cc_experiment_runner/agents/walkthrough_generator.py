"""
Walkthrough generator - Creates structured walkthroughs from documentation.
Uses Claude Code agent SDK to generate step-by-step walkthroughs for AI agents.
"""

import json
import time
import asyncio
import re
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
)


# ============================================================================
# DOCUMENT RESOLVERS
# ============================================================================

class MkDocsResolver:
    """Resolves MkDocs PyMdown Extensions snippet references."""

    # Matches: --8<-- "path/to/file.py"
    SNIPPET_PATTERN = re.compile(r'--8<--\s+"([^"]+)"')

    def resolve(
        self,
        content: str,
        doc_path: Path,
        repo_path: Path,
        docs_folder: str
    ) -> Dict[str, Any]:
        """Resolve --8<-- snippet references."""

        # Parse mkdocs.yml for base_path config
        config = self._parse_mkdocs_config(repo_path)
        base_path = config.get('base_path', repo_path / docs_folder)

        snippets_resolved = []
        resolved_content = content

        # Find all snippet references
        for match in self.SNIPPET_PATTERN.finditer(content):
            snippet_ref = match.group(1)
            snippet_path = self._resolve_path(snippet_ref, doc_path, base_path, repo_path)

            if snippet_path and snippet_path.exists():
                try:
                    with open(snippet_path, 'r', encoding='utf-8') as f:
                        snippet_content = f.read()

                    # Replace reference with actual content
                    # Preserve it as a code block
                    replacement = f"\n```\n{snippet_content}\n```\n"
                    resolved_content = resolved_content.replace(
                        match.group(0),
                        replacement
                    )

                    snippets_resolved.append({
                        'reference': snippet_ref,
                        'resolved_path': str(snippet_path.relative_to(repo_path)),
                        'lines': len(snippet_content.splitlines())
                    })
                except Exception as e:
                    # Log but continue if snippet can't be read
                    snippets_resolved.append({
                        'reference': snippet_ref,
                        'error': str(e)
                    })

        return {
            'content': resolved_content,
            'format': 'mkdocs',
            'snippets_resolved': snippets_resolved,
            'resolution_notes': f"Resolved {len([s for s in snippets_resolved if 'error' not in s])} MkDocs snippets"
        }

    def _parse_mkdocs_config(self, repo_path: Path) -> Dict:
        """Parse mkdocs.yml configuration."""
        config_path = repo_path / 'mkdocs.yml'
        if not config_path.exists():
            config_path = repo_path / 'mkdocs.yaml'

        if not config_path.exists():
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Extract pymdownx.snippets settings
            extensions = config.get('markdown_extensions', [])
            for ext in extensions:
                if isinstance(ext, dict) and 'pymdownx.snippets' in ext:
                    return ext['pymdownx.snippets']
        except Exception:
            pass

        return {}

    def _resolve_path(
        self,
        snippet_ref: str,
        doc_path: Path,
        base_path: Path,
        repo_path: Path
    ) -> Optional[Path]:
        """Resolve snippet reference to actual file path."""
        # Try multiple resolution strategies

        # 1. Relative to doc file
        relative_to_doc = doc_path.parent / snippet_ref
        if relative_to_doc.exists():
            return relative_to_doc

        # 2. Relative to base_path
        relative_to_base = base_path / snippet_ref
        if relative_to_base.exists():
            return relative_to_base

        # 3. Relative to repo root
        relative_to_repo = repo_path / snippet_ref
        if relative_to_repo.exists():
            return relative_to_repo

        return None


class DocusaurusResolver:
    """Resolves Docusaurus MDX code imports."""

    # Matches: import CodeExample from '!!raw-loader!./example.js';
    IMPORT_PATTERN = re.compile(r"import\s+(\w+)\s+from\s+['\"]!!raw-loader!([^'\"]+)['\"];?")

    def resolve(
        self,
        content: str,
        doc_path: Path,
        repo_path: Path,
        docs_folder: str
    ) -> Dict[str, Any]:
        """Resolve MDX raw-loader imports."""

        snippets_resolved = []
        resolved_content = content

        # Find all import statements
        for match in self.IMPORT_PATTERN.finditer(content):
            var_name = match.group(1)
            import_path = match.group(2)

            # Resolve relative import
            if import_path.startswith('./') or import_path.startswith('../'):
                snippet_path = (doc_path.parent / import_path).resolve()
            else:
                snippet_path = repo_path / import_path

            if snippet_path.exists():
                try:
                    with open(snippet_path, 'r', encoding='utf-8') as f:
                        snippet_content = f.read()

                    # Find usages like <CodeBlock>{VarName}</CodeBlock>
                    # Replace with actual content
                    usage_pattern = re.compile(
                        rf'<CodeBlock[^>]*>\{{{var_name}\}}</CodeBlock>',
                        re.DOTALL
                    )

                    replacement = f"\n```\n{snippet_content}\n```\n"
                    resolved_content = usage_pattern.sub(replacement, resolved_content)

                    snippets_resolved.append({
                        'reference': import_path,
                        'resolved_path': str(snippet_path.relative_to(repo_path)),
                        'lines': len(snippet_content.splitlines())
                    })
                except Exception as e:
                    snippets_resolved.append({
                        'reference': import_path,
                        'error': str(e)
                    })

        return {
            'content': resolved_content,
            'format': 'docusaurus',
            'snippets_resolved': snippets_resolved,
            'resolution_notes': f"Resolved {len([s for s in snippets_resolved if 'error' not in s])} Docusaurus imports"
        }


class SphinxResolver:
    """Resolves Sphinx literalinclude directives."""

    # Matches: .. literalinclude:: path/to/file.py
    LITERAL_PATTERN = re.compile(
        r'\.\.\s+literalinclude::\s+([^\n]+)\n(?:\s+:[^\n]+\n)*',
        re.MULTILINE
    )

    def resolve(
        self,
        content: str,
        doc_path: Path,
        repo_path: Path,
        docs_folder: str
    ) -> Dict[str, Any]:
        """Resolve literalinclude directives."""

        snippets_resolved = []
        resolved_content = content

        for match in self.LITERAL_PATTERN.finditer(content):
            include_path = match.group(1).strip()

            # Resolve relative to doc or repo root
            if include_path.startswith('../') or include_path.startswith('./'):
                snippet_path = (doc_path.parent / include_path).resolve()
            else:
                snippet_path = repo_path / include_path

            if snippet_path.exists():
                try:
                    with open(snippet_path, 'r', encoding='utf-8') as f:
                        snippet_content = f.read()

                    # Replace entire literalinclude directive with code block
                    replacement = f"\n```\n{snippet_content}\n```\n"
                    resolved_content = resolved_content.replace(
                        match.group(0),
                        replacement
                    )

                    snippets_resolved.append({
                        'reference': include_path,
                        'resolved_path': str(snippet_path.relative_to(repo_path)),
                        'lines': len(snippet_content.splitlines())
                    })
                except Exception as e:
                    snippets_resolved.append({
                        'reference': include_path,
                        'error': str(e)
                    })

        return {
            'content': resolved_content,
            'format': 'sphinx',
            'snippets_resolved': snippets_resolved,
            'resolution_notes': f"Resolved {len([s for s in snippets_resolved if 'error' not in s])} Sphinx literalincludes"
        }


class DocumentResolver:
    """Detects documentation format and resolves external code snippets."""

    FORMATS = {
        'mkdocs': ['mkdocs.yml', 'mkdocs.yaml'],
        'docusaurus': ['docusaurus.config.js', 'docusaurus.config.ts', 'sidebars.js'],
        'sphinx': ['conf.py', 'source/conf.py'],
        'hugo': ['config.toml', 'config.yaml', 'hugo.toml'],
        'vuepress': ['.vuepress/config.js', '.vuepress/config.ts']
    }

    def detect_format(self, repo_path: Path) -> str:
        """Detect documentation format by config files."""
        for format_name, config_files in self.FORMATS.items():
            for config_file in config_files:
                if (repo_path / config_file).exists():
                    return format_name
        return 'unknown'

    def resolve_content(
        self,
        doc_path: Path,
        repo_path: Path,
        docs_folder: str
    ) -> Dict[str, Any]:
        """Resolve all external code snippet references in documentation."""

        doc_format = self.detect_format(repo_path)

        with open(doc_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        resolver = self._get_resolver(doc_format)
        if resolver is None:
            # No resolution needed
            return {
                'content': original_content,
                'format': doc_format,
                'snippets_resolved': [],
                'resolution_notes': 'No external snippets detected or resolver available'
            }

        resolved = resolver.resolve(
            content=original_content,
            doc_path=doc_path,
            repo_path=repo_path,
            docs_folder=docs_folder
        )

        return resolved

    def _get_resolver(self, doc_format: str):
        """Get appropriate resolver for doc format."""
        resolvers = {
            'mkdocs': MkDocsResolver(),
            'docusaurus': DocusaurusResolver(),
            'sphinx': SphinxResolver(),
        }
        return resolvers.get(doc_format)


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

GENERATION_SYSTEM_PROMPT = """You are an expert technical writer and documentation analyst specializing in creating interactive walkthroughs from documentation.

Your task is to analyze tutorial/quickstart documentation and convert it into a structured step-by-step walkthrough that a Claude Code agent can execute.

**DOCUMENTATION FORMAT AWARENESS:**
You may receive documentation from various generators (MkDocs, Docusaurus, Sphinx, etc.). External code snippet references have been RESOLVED and inlined for you. If you see resolution metadata, it means code snippets were imported from separate files and are now embedded in the content you're analyzing.

CRITICAL REQUIREMENTS:

1. **Identify Logical Steps**: Break the tutorial into discrete, actionable steps
   - Each step should have a clear objective
   - Steps should follow a logical progression
   - Don't combine unrelated actions into one step

2. **Extract Four Content Types** for each step:
   - **contentForUser**: The markdown content the user sees (can include code blocks, explanations)
   - **contextForAgent**: Background knowledge the agent needs (how things work, what to expect)
   - **operationsForAgent**: Specific commands/actions to execute (be explicit and concrete)
   - **introductionForAgent**: Purpose and goals of the step

3. **Handle Code Snippets Properly**:
   - Code blocks may have been imported from external files (check resolution metadata)
   - Preserve all code examples exactly as provided
   - Note file paths if specified in resolution metadata
   - Include setup/prerequisites for code execution

4. **Be Specific in Operations**:
   - Use exact commands (e.g., "Run: npm install", not "Install dependencies")
   - Include error handling guidance
   - Note when to wait for user confirmation
   - Specify what success looks like

5. **Maintain Context**:
   - Each step should make sense standalone
   - Reference prerequisites from earlier steps
   - Note dependencies between steps

6. **Output Format**: You MUST use the Write tool to save valid JSON to the specified output file

You are thorough and precise. Create walkthroughs that enable successful execution by AI agents.
"""

GENERATION_PROMPT_TEMPLATE = """Analyze the following documentation and create a structured walkthrough.

Library: {library_name}
Version: {library_version}
Task: {task_description}
Documentation Path: {doc_location_info}
Documentation Content Info: {doc_content_info}

Documentation content:
```markdown
{content}
```

Create a walkthrough with the following structure and **USE THE WRITE TOOL** to save it to `{output_file}`:

```json
{{
  "walkthrough": {{
    "title": "Getting Started with {library_name}",
    "description": "Step-by-step guide...",
    "library": "{library_name}",
    "version": "{library_version}",
    "createdAt": {created_at},
    "updatedAt": {updated_at},
    "originalDocPath": "docs/path/to/doc.md",
    "generatedBy": "cc-experiment-walkthrough-generator"
  }},
  "steps": [
    {{
      "displayOrder": 1,
      "contentForUser": "# Step Title\\n\\nExplanation for the user with markdown formatting...\\n\\n```bash\\ncommand\\n```\\n\\nMore details...",
      "contextForAgent": "Background info about this step, explaining why it's needed, what it accomplishes, and any important context the agent should understand.",
      "operationsForAgent": "1. Run: command\\n2. Check output for success indicators\\n3. Verify that X was created\\n4. If error Y occurs, do Z",
      "introductionForAgent": "This step accomplishes [goal]. The agent should [key action].",
      "nextStepReference": 2,
      "createdAt": {step_created_at},
      "updatedAt": {step_updated_at}
    }},
    {{
      "displayOrder": 2,
      "contentForUser": "# Another Step\\n\\nMore instructions...",
      "contextForAgent": "Context for step 2...",
      "operationsForAgent": "Operations for step 2...",
      "introductionForAgent": "Purpose of step 2...",
      "nextStepReference": null,
      "createdAt": {step_created_at},
      "updatedAt": {step_updated_at}
    }}
  ]
}}
```

IMPORTANT:
- The last step should have `nextStepReference: null`
- All other steps should reference the next step's displayOrder
- Use actual timestamps (Unix milliseconds)
- Be comprehensive - don't skip steps from the documentation
- Make operations concrete and executable
- **YOU MUST USE THE WRITE TOOL** to save the JSON
- **CRITICAL**: Use the RELATIVE path: `{output_file}` (NOT an absolute path)
- This path is relative to your working directory
"""


# ============================================================================
# WALKTHROUGH GENERATOR
# ============================================================================

class WalkthroughGenerator:
    """Generates structured walkthroughs from documentation using Claude Code agent."""

    def __init__(self, api_key: str):
        """
        Initialize the walkthrough generator.

        Args:
            api_key: Anthropic API key (set via ANTHROPIC_API_KEY env var for SDK)
        """
        # SDK uses ANTHROPIC_API_KEY from environment
        import os
        os.environ['ANTHROPIC_API_KEY'] = api_key
        self.resolver = DocumentResolver()

    def generate_from_doc(
        self,
        doc_content: str,
        library_name: str,
        task_description: str,
        output_file: Optional[Path] = None,
        resolution_metadata: Optional[Dict[str, Any]] = None,
        doc_path: Optional[Path] = None,
        repo_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate walkthrough from documentation content.

        Args:
            doc_content: The documentation text
            library_name: Name of the library/framework
            task_description: What the user is trying to accomplish
            output_file: Path to save the walkthrough JSON (optional)
            resolution_metadata: Metadata about resolved code snippets (optional)
            doc_path: Path to the original doc file (optional, for context)
            repo_path: Path to the repository root (optional, for context)

        Returns:
            Structured walkthrough JSON dict
        """
        return asyncio.run(self._generate_async(
            doc_content, library_name, task_description, output_file,
            resolution_metadata, doc_path, repo_path
        ))

    async def _generate_async(
        self,
        doc_content: str,
        library_name: str,
        task_description: str,
        output_file: Optional[Path],
        resolution_metadata: Optional[Dict[str, Any]] = None,
        doc_path: Optional[Path] = None,
        repo_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Async implementation of walkthrough generation."""

        # Prepare timestamps
        now_ms = int(time.time() * 1000)
        now_iso = datetime.now().isoformat() + "Z"

        # Create temp output file if not specified
        if output_file is None:
            output_file = Path(f"/tmp/walkthrough_{library_name}_{now_ms}.json")
        else:
            output_file = Path(output_file)

        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Setup logging (similar to agent logging)
        log_dir = output_file.parent / "generation_logs"
        log_dir.mkdir(exist_ok=True)

        from ..agent_hooks import AgentLogger
        logger = AgentLogger(
            log_file=log_dir / "generator.log",
            tools_log_file=log_dir / "tools.jsonl",
            messages_log_file=log_dir / "messages.jsonl"
        )

        logger.log_message(f"Starting walkthrough generation for {library_name}")
        logger.log_message(f"Output file: {output_file}")

        # Prepare doc location info
        doc_location_info = ""
        if doc_path and repo_path:
            relative_path = doc_path.relative_to(repo_path)
            doc_location_info = str(relative_path)
        elif doc_path:
            doc_location_info = str(doc_path)

        # Prepare doc content info for prompt
        doc_content_info = ""
        if resolution_metadata and resolution_metadata.get('snippets_resolved'):
            doc_content_info = f"""Format: {resolution_metadata.get('format', 'unknown')}
Snippets Resolved: {len(resolution_metadata['snippets_resolved'])}
Resolution Notes: {resolution_metadata.get('resolution_notes', 'N/A')}

External code snippets have been automatically resolved and inlined:
```json
{json.dumps(resolution_metadata['snippets_resolved'], indent=2)}
```"""
        else:
            doc_content_info = "Format: plain markdown, no external snippets detected"

        # Create Claude SDK client with logging + validation hooks
        from ..agent_hooks import create_logging_hooks
        from ..hooks import create_walkthrough_generation_hooks

        # Combine logging hooks with validation hooks
        logging_hooks = create_logging_hooks(logger)
        validation_hooks = create_walkthrough_generation_hooks()

        # Merge hooks (validation hooks take precedence)
        combined_hooks = {**logging_hooks}
        for event, matchers in validation_hooks.items():
            if event in combined_hooks:
                combined_hooks[event].extend(matchers)
            else:
                combined_hooks[event] = matchers

        # Set working directory to experiment root (not walkthroughs subdirectory)
        # This ensures relative paths work correctly
        experiment_root = output_file.parent.parent if output_file.parent.name == 'walkthroughs' else output_file.parent

        # Set environment variable for hooks to know where to write logs
        import os
        hooks_log_dir = experiment_root / "walkthroughs" / "hooks_logs"
        os.environ['WALKTHROUGH_HOOKS_LOG_DIR'] = str(hooks_log_dir)

        options = ClaudeAgentOptions(
            system_prompt=GENERATION_SYSTEM_PROMPT,
            allowed_tools=["Write"],  # Agent uses Write to save JSON
            permission_mode="acceptEdits",
            cwd=str(experiment_root),
            hooks=combined_hooks
        )

        logger.log_message("Initializing Claude SDK client")
        logger.log_message(f"Hooks logs will be written to: {hooks_log_dir}")

        async with ClaudeSDKClient(options=options) as client:
            # Generate walkthrough using agent
            # Use relative path from experiment root
            relative_output = output_file.relative_to(experiment_root) if output_file.is_relative_to(experiment_root) else f"walkthroughs/{output_file.name}"

            prompt = GENERATION_PROMPT_TEMPLATE.format(
                library_name=library_name,
                library_version="latest",
                task_description=task_description,
                doc_location_info=doc_location_info,
                doc_content_info=doc_content_info,
                content=doc_content,
                timestamp=now_iso,
                created_at=now_ms,
                updated_at=now_ms,
                step_created_at=now_ms,
                step_updated_at=now_ms,
                output_file=str(relative_output)
            )

            logger.log_message(f"Sending prompt (length: {len(prompt)} chars)")
            logger.log_conversation_message("user", prompt)

            await client.query(prompt)

            # Wait for agent to complete (it will use Write tool)
            logger.log_message("Waiting for agent response...")
            message_count = 0
            async for message in client.receive_response():
                message_count += 1
                logger.log_message(f"Received message {message_count}: {type(message).__name__}")

                # Log all messages to messages.jsonl
                from claude_agent_sdk import ResultMessage, UserMessage, SystemMessage

                if isinstance(message, AssistantMessage):
                    # Log assistant message to messages.jsonl
                    content_for_log = []
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            content_for_log.append({"type": "text", "text": block.text})
                            logger.log_message(f"Assistant text: {block.text[:200]}...")
                        elif isinstance(block, ToolUseBlock):
                            content_for_log.append({"type": "tool_use", "name": block.name, "id": block.id})

                    logger.log_conversation_message("assistant", content_for_log)

                elif isinstance(message, UserMessage):
                    # Log user message (tool results)
                    logger.log_conversation_message("user", str(message.content)[:500])

                elif isinstance(message, SystemMessage):
                    # Log system message - SystemMessage has different structure
                    logger.log_conversation_message("system", str(message)[:500])

                # Track token usage
                if isinstance(message, ResultMessage) and message.usage:
                    usage = message.usage
                    logger.track_tokens(
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
                        cache_read_input_tokens=usage.get("cache_read_input_tokens", 0)
                    )

            logger.log_message(f"Agent finished after {message_count} messages")

        # Load the generated file
        logger.log_message(f"Checking if output file exists: {output_file}")
        if not output_file.exists():
            logger.log_message(f"ERROR: Output file not created!", level="ERROR")
            logger.log_message(f"Working directory was: {output_file.parent}", level="ERROR")
            logger.log_message(f"Files in directory: {list(output_file.parent.glob('*'))}", level="ERROR")
            raise ValueError(f"Agent did not create output file: {output_file}")

        logger.log_message("Output file exists! Loading walkthrough data...")
        with open(output_file, 'r', encoding='utf-8') as f:
            walkthrough_data = json.load(f)

        logger.log_message(f"✅ Successfully loaded walkthrough with {len(walkthrough_data.get('steps', []))} steps")
        logger.log_message(f"Total tokens used: {logger.get_stats()['total_tokens']}")

        return walkthrough_data

    def generate_from_file(
        self,
        doc_path: Path,
        library_name: str,
        task_description: str,
        output_file: Optional[Path] = None,
        repo_path: Optional[Path] = None,
        docs_folder: str = "docs"
    ) -> Dict[str, Any]:
        """
        Generate walkthrough from a documentation file.

        Args:
            doc_path: Path to the markdown documentation file
            library_name: Name of the library/framework
            task_description: What the user is trying to accomplish
            output_file: Path to save the walkthrough JSON (optional)
            repo_path: Path to repository root for resolving external snippets (optional)
            docs_folder: Name of docs folder within repo (default: "docs")

        Returns:
            Structured walkthrough JSON dict
        """
        # Resolve external snippets if repo_path provided
        if repo_path:
            resolved = self.resolver.resolve_content(
                doc_path=doc_path,
                repo_path=repo_path,
                docs_folder=docs_folder
            )
            content = resolved['content']
            metadata = {
                'doc_format': resolved['format'],
                'snippets_resolved': resolved['snippets_resolved'],
                'resolution_notes': resolved['resolution_notes']
            }
        else:
            # Fallback: just read file
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            metadata = None

        return self.generate_from_doc(
            content,
            library_name,
            task_description,
            output_file,
            resolution_metadata=metadata,
            doc_path=doc_path,
            repo_path=repo_path
        )
