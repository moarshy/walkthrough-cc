"""
Walkthrough generator - Creates structured walkthroughs from documentation.
Uses Claude Code agent SDK to generate step-by-step walkthroughs for AI agents.
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
)


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

5. **Output Format**: You MUST use the Write tool to save valid JSON to the specified output file

You are thorough and precise. Create walkthroughs that enable successful execution by AI agents.
"""

GENERATION_PROMPT_TEMPLATE = """Analyze the following documentation and create a structured walkthrough.

Library: {library_name}
Version: {library_version}
Task: {task_description}

Documentation content:
```markdown
{content}
```

Create a walkthrough with the following structure and **USE THE WRITE TOOL** to save it to `{output_file}`:

```json
{{
  "version": "1.0",
  "exportedAt": "{timestamp}",
  "walkthrough": {{
    "title": "Getting Started with {library_name}",
    "description": "Step-by-step guide...",
    "type": "quickstart",
    "status": "published",
    "createdAt": {created_at},
    "updatedAt": {updated_at},
    "estimatedDurationMinutes": 30,
    "tags": ["{library_name}", "quickstart"],
    "metadata": null
  }},
  "steps": [
    {{
      "title": "Step Title",
      "contentFields": {{
        "version": "v1",
        "contentForUser": "# Step Title\\n\\nExplanation...\\n\\n```bash\\ncommand\\n```",
        "contextForAgent": "Background info about this step...",
        "operationsForAgent": "1. Run: command\\n2. Check output...\\n3. Verify...",
        "introductionForAgent": "This step accomplishes..."
      }},
      "displayOrder": 0,
      "createdAt": {step_created_at},
      "updatedAt": {step_updated_at},
      "metadata": {{"imported": true}},
      "nextStepReference": 1
    }}
  ],
  "metadata": {{
    "originalDocPath": "docs/{library_name}",
    "generatedBy": "cc-experiment-walkthrough-generator"
  }}
}}
```

IMPORTANT:
- The last step should have `nextStepReference: null`
- All other steps should reference the next step's displayOrder
- Use actual timestamps (Unix milliseconds)
- Be comprehensive - don't skip steps from the documentation
- Make operations concrete and executable
- **YOU MUST USE THE WRITE TOOL** to save the JSON to `{output_file}` - do not just return it as text
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

    def generate_from_doc(
        self,
        doc_content: str,
        library_name: str,
        task_description: str,
        output_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate walkthrough from documentation content.

        Args:
            doc_content: The documentation text
            library_name: Name of the library/framework
            task_description: What the user is trying to accomplish
            output_file: Path to save the walkthrough JSON (optional)

        Returns:
            Structured walkthrough JSON dict
        """
        return asyncio.run(self._generate_async(
            doc_content, library_name, task_description, output_file
        ))

    async def _generate_async(
        self,
        doc_content: str,
        library_name: str,
        task_description: str,
        output_file: Optional[Path]
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

        # Create Claude SDK client
        options = ClaudeAgentOptions(
            system_prompt=GENERATION_SYSTEM_PROMPT,
            allowed_tools=["Write"],  # Agent uses Write to save JSON
            permission_mode="acceptEdits",
            cwd=str(output_file.parent),
        )

        async with ClaudeSDKClient(options=options) as client:
            # Generate walkthrough using agent
            prompt = GENERATION_PROMPT_TEMPLATE.format(
                library_name=library_name,
                library_version="latest",
                task_description=task_description,
                content=doc_content,
                timestamp=now_iso,
                created_at=now_ms,
                updated_at=now_ms,
                step_created_at=now_ms,
                step_updated_at=now_ms,
                output_file=str(output_file)
            )

            await client.query(prompt)

            # Wait for agent to complete (it will use Write tool)
            async for message in client.receive_response():
                pass  # Agent will write the file

        # Load the generated file
        if not output_file.exists():
            raise ValueError(f"Agent did not create output file: {output_file}")

        with open(output_file, 'r', encoding='utf-8') as f:
            walkthrough_data = json.load(f)

        return walkthrough_data

    def generate_from_file(
        self,
        doc_path: Path,
        library_name: str,
        task_description: str,
        output_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate walkthrough from a documentation file.

        Args:
            doc_path: Path to the markdown documentation file
            library_name: Name of the library/framework
            task_description: What the user is trying to accomplish
            output_file: Path to save the walkthrough JSON (optional)

        Returns:
            Structured walkthrough JSON dict
        """
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return self.generate_from_doc(content, library_name, task_description, output_file)
