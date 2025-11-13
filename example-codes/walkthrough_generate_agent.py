"""
Walkthrough Generation Agent

This agent analyzes documentation (tutorials, quickstarts, guides) and generates
structured walkthrough JSON files. It breaks down documentation into discrete steps
with proper content fields for both users and agents.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    HookMatcher,
)

from .schemas import (
    ContentFields,
    WalkthroughStep,
    WalkthroughMetadata,
    Walkthrough,
    WalkthroughExport,
)

from stackbench.hooks.validation import create_walkthrough_generation_validation_hook
from stackbench.hooks.logging import create_logging_hooks, AgentLogger

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

GENERATION_SYSTEM_PROMPT = """You are an expert technical writer and documentation analyst specializing in creating interactive walkthroughs from documentation.

Your task is to analyze tutorial/quickstart documentation and convert it into a structured step-by-step walkthrough that a Claude Code agent can execute.

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

3. **Be Specific in Operations**:
   - Use exact commands (e.g., "Run: npm install", not "Install dependencies")
   - Include error handling guidance
   - Note when to wait for user confirmation
   - Specify what success looks like

4. **Maintain Context**:
   - Each step should make sense standalone
   - Reference prerequisites from earlier steps
   - Note dependencies between steps

5. **Output Format**: Return valid JSON matching the WalkthroughExport schema

You are thorough and precise. Create walkthroughs that enable successful execution by AI agents.
"""

GENERATION_PROMPT_TEMPLATE = """Analyze the following documentation and create a structured walkthrough.

Documentation file: {doc_path}
Library: {library_name}
Version: {library_version}

Documentation content:
```markdown
{content}
```

Create a walkthrough with the following:

1. **Metadata**: Title, description, estimated duration, tags
2. **Steps**: Break down into logical steps (typically 5-15 steps for a quickstart)

For each step, provide:
- **title**: Clear, action-oriented title (e.g., "Install Dependencies", "Create First Component")
- **contentForUser**: The user-facing content (markdown with code blocks)
- **contextForAgent**: Background context and what to know
- **operationsForAgent**: Exact commands and actions to execute
- **introductionForAgent**: Purpose and goals of this step

**IMPORTANT**: You must use the Write tool to save the walkthrough JSON to `{output_file}`.

The JSON object should match this schema:
```json
{{
  "version": "1.0",
  "exportedAt": "{timestamp}",
  "walkthrough": {{
    "title": "Getting Started with ExampleLib",
    "description": "A comprehensive guide to...",
    "type": "quickstart",
    "status": "published",
    "createdAt": {created_at},
    "updatedAt": {updated_at},
    "estimatedDurationMinutes": 30,
    "tags": ["tag1", "tag2"],
    "metadata": null
  }},
  "steps": [
    {{
      "title": "Step Title",
      "contentFields": {{
        "version": "v1",
        "contentForUser": "# Step Title\\n\\nExplanation...\\n\\n```bash\\ncommand\\n```",
        "contextForAgent": "Background info...",
        "operationsForAgent": "1. Run: command\\n2. Check output...\\n3. Verify...",
        "introductionForAgent": "This step accomplishes..."
      }},
      "displayOrder": 1,
      "createdAt": {step_created_at},
      "updatedAt": {step_updated_at},
      "metadata": {{"imported": true}},
      "nextStepReference": 1
    }}
  ],
  "metadata": {{
    "originalDocPath": "{doc_path}",
    "generatedBy": "stackbench-walkthrough-generator"
  }}
}}
```

IMPORTANT:
- The last step should have `nextStepReference: null`
- All other steps should reference the next step's displayOrder
- Use actual timestamps (Unix milliseconds)
- Be comprehensive - don't skip steps
- Make operations concrete and executable
- **Use the Write tool to save the JSON** - do not just return it in text
"""


# ============================================================================
# GENERATE AGENT
# ============================================================================

class WalkthroughGenerateAgent:
    """Agent that generates walkthroughs from documentation."""

    def __init__(
        self,
        output_folder: Path,
        library_name: str,
        library_version: str,
    ):
        """
        Initialize the generate agent.

        Args:
            output_folder: Path to save generated walkthroughs
            library_name: Name of the library being documented
            library_version: Version of the library
        """
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.library_name = library_name
        self.library_version = library_version

        print(f"📝 Walkthrough Generate Agent initialized")
        print(f"   Library: {library_name} v{library_version}")
        print(f"   Output: {output_folder}")

    def extract_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from Claude's response, handling markdown code blocks."""
        try:
            # Try to find JSON in markdown code blocks
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
                return json.loads(json_text)
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
                return json.loads(json_text)
            else:
                # Try parsing the whole response
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing error: {e}")
            print(f"   Response preview: {response_text[:300]}...")
            return None

    async def get_claude_response(self, client: ClaudeSDKClient, prompt: str) -> str:
        """Send prompt to Claude and get text response."""
        await client.query(prompt)

        response_text = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text

    async def generate_walkthrough(
        self,
        doc_path: Path,
        walkthrough_id: Optional[str] = None
    ) -> WalkthroughExport:
        """
        Generate a walkthrough from a documentation file.

        Args:
            doc_path: Path to the markdown documentation file
            walkthrough_id: Optional ID for the walkthrough (default: doc filename stem)

        Returns:
            WalkthroughExport containing the generated walkthrough

        Raises:
            ValueError: If generation fails or produces invalid output
        """
        print(f"\n🔄 Generating walkthrough from: {doc_path.name}")

        # Read documentation
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Prepare timestamps
        now_ms = int(time.time() * 1000)
        now_iso = datetime.now().isoformat() + "Z"

        # Setup hooks
        log_dir = self.output_folder / "agent_logs"
        logger = AgentLogger(
            log_file=log_dir / "generate.log",
            tools_log_file=log_dir / "generate_tools.jsonl"
        )
        logging_hooks = create_logging_hooks(logger)

        validation_hook = create_walkthrough_generation_validation_hook(
            output_dir=self.output_folder,
            log_dir=self.output_folder / "validation_logs"
        )

        hooks = {
            'PreToolUse': [
                HookMatcher(matcher="Write", hooks=[validation_hook])
            ] + logging_hooks['PreToolUse'],
            'PostToolUse': logging_hooks['PostToolUse']
        }

        # Create Claude SDK client
        options = ClaudeAgentOptions(
            system_prompt=GENERATION_SYSTEM_PROMPT,
            allowed_tools=["Read", "Write"],  # Allow reading files and writing JSON
            permission_mode="acceptEdits",
            cwd=str(Path.cwd()),
            hooks=hooks
        )

        # Use provided walkthrough_id or default to doc filename
        if not walkthrough_id:
            walkthrough_id = f"wt_{doc_path.stem}"

        # Save to output folder
        output_file = self.output_folder / f"{walkthrough_id}.json"

        async with ClaudeSDKClient(options=options) as client:
            # Generate walkthrough
            prompt = GENERATION_PROMPT_TEMPLATE.format(
                doc_path=str(doc_path),
                library_name=self.library_name,
                library_version=self.library_version,
                content=content,
                timestamp=now_iso,
                created_at=now_ms,
                updated_at=now_ms,
                step_created_at=now_ms,
                step_updated_at=now_ms,
                output_file=str(output_file)
            )

            await client.query(prompt)

            # Wait for agent to complete
            async for message in client.receive_response():
                pass  # Agent will use Write tool, hooks will validate

        # Load the generated file
        if not output_file.exists():
            raise ValueError(f"Agent did not create output file: {output_file}")

        with open(output_file, 'r', encoding='utf-8') as f:
            walkthrough_data = json.load(f)

        # Validate and create WalkthroughExport
        try:
            walkthrough_export = WalkthroughExport(**walkthrough_data)
        except Exception as e:
            print(f"❌ Validation error: {e}")
            raise ValueError(f"Generated walkthrough does not match schema: {e}")

        print(f"✅ Walkthrough generated: {output_file.name}")
        print(f"   Title: {walkthrough_export.walkthrough.title}")
        print(f"   Steps: {len(walkthrough_export.steps)}")
        print(f"   Duration: ~{walkthrough_export.walkthrough.estimatedDurationMinutes} minutes")

        return walkthrough_export

    async def generate_from_multiple_docs(
        self,
        doc_paths: List[Path],
        walkthrough_prefix: Optional[str] = None
    ) -> List[WalkthroughExport]:
        """
        Generate walkthroughs from multiple documentation files.

        Args:
            doc_paths: List of paths to markdown documentation files
            walkthrough_prefix: Optional prefix for walkthrough IDs

        Returns:
            List of WalkthroughExport objects
        """
        print(f"\n📚 Generating walkthroughs from {len(doc_paths)} documents...")

        results = []
        for i, doc_path in enumerate(doc_paths, 1):
            print(f"\n[{i}/{len(doc_paths)}] Processing: {doc_path.name}")

            walkthrough_id = None
            if walkthrough_prefix:
                walkthrough_id = f"wt_{walkthrough_prefix}_{doc_path.stem}"

            try:
                walkthrough = await self.generate_walkthrough(doc_path, walkthrough_id)
                results.append(walkthrough)
            except Exception as e:
                print(f"❌ Failed to generate walkthrough for {doc_path.name}: {e}")
                continue

        print(f"\n✨ Generated {len(results)}/{len(doc_paths)} walkthroughs")
        return results
