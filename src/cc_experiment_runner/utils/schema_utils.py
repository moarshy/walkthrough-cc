"""
Schema utility functions.

Provides helpers for generating examples and documentation from Pydantic schemas.
"""

import json
from typing import Dict, Any


def generate_walkthrough_example(
    library_name: str = "{library_name}",
    library_version: str = "{library_version}",
    created_at: int = None,
    updated_at: int = None,
    output_file: str = "{output_file}"
) -> str:
    """
    Generate a walkthrough JSON example with proper structure.

    This function creates an example that follows the Walkthrough schema
    defined in schemas/walkthrough_schema.py, ensuring consistency between
    the prompt example and the actual validation schema.

    Args:
        library_name: Name of the library/project
        library_version: Version of the library
        created_at: Unix timestamp (milliseconds) for creation
        updated_at: Unix timestamp (milliseconds) for update
        output_file: Output file path

    Returns:
        JSON string with formatted walkthrough example
    """
    import time
    if created_at is None:
        created_at = int(time.time() * 1000)
    if updated_at is None:
        updated_at = created_at

    step_created_at = created_at
    step_updated_at = updated_at

    example = {
        "walkthrough": {
            "title": f"Getting Started with {library_name}",
            "description": "Step-by-step guide for setting up and using the project",
            "library": library_name,
            "version": library_version,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "originalDocPath": "docs/path/to/doc.md",
            "generatedBy": "cc-experiment-walkthrough-generator"
        },
        "steps": [
            {
                "displayOrder": 1,
                "contentForUser": "# Step Title\n\nExplanation for the user with markdown formatting...\n\n```bash\ncommand\n```\n\nMore details...",
                "contextForAgent": "Background info about this step, explaining why it's needed, what it accomplishes, and any important context the agent should understand.",
                "operationsForAgent": "1. Run: command\n2. Check output for success indicators\n3. Verify that X was created\n4. If error Y occurs, do Z",
                "introductionForAgent": "This step accomplishes [goal]. The agent should [key action].",
                "nextStepReference": 2,
                "createdAt": step_created_at,
                "updatedAt": step_updated_at
            },
            {
                "displayOrder": 2,
                "contentForUser": "# Another Step\n\nMore instructions...",
                "contextForAgent": "Context for step 2...",
                "operationsForAgent": "Operations for step 2...",
                "introductionForAgent": "Purpose of step 2...",
                "nextStepReference": None,
                "createdAt": step_created_at,
                "updatedAt": step_updated_at
            }
        ]
    }

    return json.dumps(example, indent=2)


def get_schema_reference() -> str:
    """
    Get a reference to the schema file location.

    Returns:
        String with schema file reference
    """
    return """
The walkthrough structure is defined by the Pydantic schema in:
`src/cc_experiment_runner/schemas/walkthrough_schema.py`

Key models:
- Walkthrough: Root object containing metadata and steps
- WalkthroughMetadata: Metadata about the walkthrough
- WalkthroughStep: Individual step with content for user and agent

Each step MUST have these fields:
- displayOrder (int): Step number (starting from 1)
- contentForUser (str): Markdown content for users
- contextForAgent (str): Background knowledge for AI agents
- operationsForAgent (str): Executable operations/commands
- introductionForAgent (str): Purpose and goals of the step
- nextStepReference (int | null): Next step's displayOrder or null for last step
- createdAt (int): Unix timestamp in milliseconds
- updatedAt (int): Unix timestamp in milliseconds
"""
