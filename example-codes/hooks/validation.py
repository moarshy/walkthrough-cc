"""
Validation hooks for StackBench agents.

Now uses Pydantic models directly for validation, eliminating manual schema duplication.
The centralized schemas in stackbench.schemas are the single source of truth.
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

# Import centralized schemas and utilities
from stackbench.schemas import (
    DocumentAnalysis,
    DocumentValidationResult,
    APISignatureValidationOutput,
    ClarityValidationOutput,
    APICompletenessOutput
)
from stackbench.utils import validate_with_pydantic


# ============================================================================
# All validation now uses Pydantic models directly from stackbench.schemas
# No need for manual schema dictionaries - they were source of duplication
# ============================================================================


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_field_type(field_name: str, value: Any, expected_types: tuple) -> List[str]:
    """Validate that a field has the correct type."""
    errors = []
    if not isinstance(value, expected_types):
        actual_type = type(value).__name__
        expected_type_names = " or ".join(t.__name__ for t in expected_types if t is not type(None))
        errors.append(f"Field '{field_name}': Expected type {expected_type_names}, got {actual_type}")
    return errors


def validate_nested_list(field_name: str, items: list, schema: dict, path: str = "") -> List[str]:
    """Validate a list of nested objects against a schema."""
    errors = []

    for idx, item in enumerate(items):
        item_path = f"{path}.{field_name}[{idx}]" if path else f"{field_name}[{idx}]"

        if not isinstance(item, dict):
            errors.append(f"{item_path}: Expected dict, got {type(item).__name__}")
            continue

        # Check required fields
        for req_field in schema.get("required_fields", []):
            if req_field not in item:
                errors.append(f"{item_path}: Missing required field '{req_field}'")

        # Check field types
        for field, value in item.items():
            if field in schema.get("field_types", {}):
                expected_type = schema["field_types"][field]
                if not isinstance(expected_type, tuple):
                    expected_type = (expected_type,)

                field_errors = validate_field_type(f"{item_path}.{field}", value, expected_type)
                errors.extend(field_errors)

    return errors


def validate_nested_dict(field_name: str, data: dict, schema: dict, path: str = "") -> List[str]:
    """Validate a nested dictionary against a schema."""
    errors = []
    item_path = f"{path}.{field_name}" if path else field_name

    if not isinstance(data, dict):
        errors.append(f"{item_path}: Expected dict, got {type(data).__name__}")
        return errors

    # Check required fields
    for req_field in schema.get("required_fields", []):
        if req_field not in data:
            errors.append(f"{item_path}: Missing required field '{req_field}'")

    # Check field types
    for field, value in data.items():
        if field in schema.get("field_types", {}):
            expected_type = schema["field_types"][field]
            if not isinstance(expected_type, tuple):
                expected_type = (expected_type,)

            field_errors = validate_field_type(f"{item_path}.{field}", value, expected_type)
            errors.extend(field_errors)

    return errors


def validate_json_structure(data: dict, schema: dict, path: str = "") -> List[str]:
    """
    Validate JSON data against a schema definition.

    Args:
        data: The JSON data to validate
        schema: Schema definition with required_fields, optional_fields, field_types
        path: Current path in the data structure (for error messages)

    Returns:
        List of error messages (empty if validation passes)
    """
    errors = []

    # Check required fields
    for field in schema.get("required_fields", []):
        if field not in data:
            field_path = f"{path}.{field}" if path else field
            errors.append(f"Missing required field: '{field_path}'")

    # Check field types
    for field, value in data.items():
        field_path = f"{path}.{field}" if path else field

        if field in schema.get("field_types", {}):
            expected_type = schema["field_types"][field]

            # Handle union types (e.g., str | None)
            if not isinstance(expected_type, tuple):
                expected_type = (expected_type,)

            # Type check
            field_errors = validate_field_type(field_path, value, expected_type)
            errors.extend(field_errors)

            # Nested validation for dicts
            if isinstance(value, dict) and field in schema.get("nested_schemas", {}):
                nested_schema = schema["nested_schemas"][field]
                nested_errors = validate_nested_dict(field, value, nested_schema, path)
                errors.extend(nested_errors)

            # Nested validation for lists
            elif isinstance(value, list) and field in schema.get("nested_schemas", {}):
                nested_schema = schema["nested_schemas"][field]
                nested_errors = validate_nested_list(field, value, nested_schema, path)
                errors.extend(nested_errors)

    return errors


# ============================================================================
# TRACKING UTILITIES
# ============================================================================

def log_validation_call(
    log_dir: Path,
    hook_type: str,
    filename: str,
    passed: bool,
    errors: Optional[List[str]] = None,
    reason: Optional[str] = None
):
    """
    Log validation hook call to a text file for tracking.

    Args:
        log_dir: Directory to store validation logs
        hook_type: Type of hook (extraction_validation or validation_output)
        filename: Name of file being validated
        passed: Whether validation passed
        errors: List of validation errors (if any)
        reason: Reason for failure (if any)
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{hook_type}_calls.txt"

        timestamp = datetime.now().isoformat()
        status = "✅ PASSED" if passed else "❌ FAILED"

        with open(log_file, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Hook Type: {hook_type}\n")
            f.write(f"File: {filename}\n")
            f.write(f"Status: {status}\n")

            if not passed:
                f.write(f"\nReason: {reason}\n")
                if errors:
                    f.write(f"\nValidation Errors:\n")
                    for error in errors:
                        f.write(f"  - {error}\n")

            f.write(f"{'='*80}\n")

    except Exception as e:
        # Don't let logging errors break the hook
        print(f"⚠️  Failed to log validation call: {e}")


# ============================================================================
# DIRECT VALIDATION HELPERS
# ============================================================================

def validate_extraction_json(
    data: dict,
    filename: str,
    log_dir: Optional[Path] = None
) -> tuple[bool, Optional[List[str]]]:
    """
    Validate extraction JSON data using Pydantic model.

    Args:
        data: The JSON data to validate
        filename: Name of the file being validated
        log_dir: Optional directory to log validation calls

    Returns:
        Tuple of (passed, errors) where passed is bool and errors is list of error messages
    """
    # Validate using Pydantic model directly
    passed, errors = validate_with_pydantic(data, DocumentAnalysis)

    # Log validation call
    if log_dir:
        log_validation_call(
            log_dir,
            "extraction_validation",
            filename,
            passed,
            errors=errors if errors else None,
            reason="Schema validation failed" if errors else None
        )

    return passed, errors if errors else None


def validate_validation_output_json(
    data: dict,
    filename: str,
    log_dir: Optional[Path] = None,
    validation_type: str = "validation_output"
) -> tuple[bool, Optional[List[str]]]:
    """
    Validate API/code/clarity validation JSON data using Pydantic models.

    Args:
        data: The JSON data to validate
        filename: Name of the file being validated
        log_dir: Optional directory to log validation calls
        validation_type: Type of validation (api_signature_validation, code_example_validation, or clarity_validation)

    Returns:
        Tuple of (passed, errors) where passed is bool and errors is list of error messages
    """
    # Select appropriate Pydantic model based on validation type
    if validation_type == "api_signature_validation":
        model = APISignatureValidationOutput
    elif validation_type == "code_example_validation":
        model = DocumentValidationResult
    elif validation_type == "clarity_validation":
        model = ClarityValidationOutput
    else:
        # Default to API model for backward compatibility
        model = APISignatureValidationOutput

    # Validate using Pydantic model directly
    passed, errors = validate_with_pydantic(data, model)

    # Log validation call
    if log_dir:
        log_validation_call(
            log_dir,
            validation_type,
            filename,
            passed,
            errors=errors if errors else None,
            reason="Schema validation failed" if errors else None
        )

    return passed, errors if errors else None


# ============================================================================
# HOOK FACTORIES
# ============================================================================

def create_extraction_validation_hook(output_dir: Optional[Path] = None, log_dir: Optional[Path] = None):
    """
    Create a PreToolUse hook that validates extraction JSON output.

    Args:
        output_dir: Optional expected output directory for location validation
        log_dir: Optional directory to log validation calls

    Returns:
        Async hook function
    """
    async def extraction_validation_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],  # noqa: ARG001 - Required by hook signature
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Validate extraction JSON before writing."""
        try:
            tool_name = input_data.get('tool_name', '')
            tool_input = input_data.get('tool_input', {})
            file_path = tool_input.get('file_path', '')

            # Only validate Write operations on extraction JSON files
            if tool_name != 'Write':
                return {}

            filename = Path(file_path).name
            if not (filename.endswith('_analysis.json') or filename == 'extraction_summary.json'):
                return {}

            # Validate output directory if specified
            if output_dir:
                abs_file_path = Path(file_path).resolve()
                abs_output_dir = output_dir.resolve()
                file_dir = abs_file_path.parent

                if not str(file_dir).startswith(str(abs_output_dir)):
                    reason = f"Files must be created in {abs_output_dir}, not {file_dir}"

                    # Log validation failure
                    if log_dir:
                        log_validation_call(log_dir, "extraction_validation", filename, False, reason=reason)

                    return {
                        'hookSpecificOutput': {
                            'hookEventName': 'PreToolUse',
                            'permissionDecision': 'deny',
                            'permissionDecisionReason': reason
                        }
                    }

            # Validate JSON content
            content = tool_input.get('content', '')
            if not content:
                return {}

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                reason = f"Invalid JSON: {e}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "extraction_validation", filename, False, reason=reason)

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason
                    }
                }

            # Validate using Pydantic
            passed, errors = validate_with_pydantic(data, DocumentAnalysis)

            if not passed:
                error_msg = f"Schema validation failed: {'; '.join(errors[:3]) if errors else 'Unknown error'}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "extraction_validation", filename, False, errors=errors, reason="Schema validation failed")

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': error_msg
                    }
                }

            # Validation passed - log success
            if log_dir:
                log_validation_call(log_dir, "extraction_validation", filename, True)

            return {}  # Validation passed

        except Exception as e:
            # Log error but don't block
            print(f"⚠️  Validation hook error: {e}")
            if log_dir:
                log_validation_call(log_dir, "extraction_validation", filename or "unknown", False, reason=f"Hook error: {e}")
            return {}

    return extraction_validation_hook


def create_validation_output_hook(output_dir: Optional[Path] = None, log_dir: Optional[Path] = None):
    """
    Create a PreToolUse hook that validates API/code validation JSON output.

    Args:
        output_dir: Optional expected output directory for location validation
        log_dir: Optional directory to log validation calls

    Returns:
        Async hook function
    """
    async def validation_output_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],  # noqa: ARG001 - Required by hook signature
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Validate validation JSON before writing."""
        try:
            tool_name = input_data.get('tool_name', '')
            tool_input = input_data.get('tool_input', {})
            file_path = tool_input.get('file_path', '')

            # Only validate Write operations on validation JSON files
            if tool_name != 'Write':
                return {}

            filename = Path(file_path).name
            # Check if this is a validation or clarity file
            if not (filename.endswith('_validation.json') or filename.endswith('_clarity.json')):
                return {}

            # Determine validation type from filename
            if filename.endswith('_clarity.json'):
                validation_type = "clarity_validation"
            elif filename.endswith('_validation.json'):
                # Infer from parent folder or filename pattern
                if 'api' in str(file_path).lower() or 'signature' in filename.lower():
                    validation_type = "api_signature_validation"
                elif 'code' in str(file_path).lower() or 'example' in filename.lower():
                    validation_type = "code_example_validation"
                else:
                    validation_type = "validation_output"  # Generic fallback
            else:
                validation_type = "validation_output"

            # Validate output directory if specified
            if output_dir:
                abs_file_path = Path(file_path).resolve()
                abs_output_dir = output_dir.resolve()
                file_dir = abs_file_path.parent

                if not str(file_dir).startswith(str(abs_output_dir)):
                    reason = f"Files must be created in {abs_output_dir}, not {file_dir}"

                    # Log validation failure
                    if log_dir:
                        log_validation_call(log_dir, validation_type, filename, False, reason=reason)

                    return {
                        'hookSpecificOutput': {
                            'hookEventName': 'PreToolUse',
                            'permissionDecision': 'deny',
                            'permissionDecisionReason': reason
                        }
                    }

            # Validate JSON content
            content = tool_input.get('content', '')
            if not content:
                return {}

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                reason = f"Invalid JSON: {e}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, validation_type, filename, False, reason=reason)

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason
                    }
                }

            # Select Pydantic model based on validation type
            if validation_type == "clarity_validation":
                model = ClarityValidationOutput
            elif validation_type == "api_signature_validation":
                model = APISignatureValidationOutput
            elif validation_type == "code_example_validation":
                model = DocumentValidationResult
            else:
                model = APISignatureValidationOutput  # Default

            # Validate using Pydantic
            passed, errors = validate_with_pydantic(data, model)

            if not passed:
                error_msg = f"Schema validation failed: {'; '.join(errors[:3]) if errors else 'Unknown error'}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, validation_type, filename, False, errors=errors, reason="Schema validation failed")

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': error_msg
                    }
                }

            # Validation passed - log success
            if log_dir:
                log_validation_call(log_dir, validation_type, filename, True)

            return {}  # Validation passed

        except Exception as e:
            # Log error but don't block
            print(f"⚠️  Validation hook error: {e}")
            if log_dir:
                validation_type = "validation_output"  # Default for error cases
                log_validation_call(log_dir, validation_type, filename or "unknown", False, reason=f"Hook error: {e}")
            return {}

    return validation_output_hook


# ============================================================================
# WALKTHROUGH VALIDATION SCHEMAS
# ============================================================================

WALKTHROUGH_GENERATION_SCHEMA = {
    "required_fields": [
        "version", "exportedAt", "walkthrough", "steps"
    ],
    "optional_fields": ["metadata"],
    "field_types": {
        "version": str,
        "exportedAt": str,
        "walkthrough": dict,
        "steps": list,
        "metadata": (dict, type(None))
    },
    "nested_schemas": {
        "walkthrough": {
            "required_fields": [
                "title", "description", "type", "status", "createdAt", "updatedAt",
                "estimatedDurationMinutes", "tags"
            ],
            "optional_fields": ["metadata"],
            "field_types": {
                "title": str,
                "description": str,
                "type": str,
                "status": str,
                "createdAt": int,
                "updatedAt": int,
                "estimatedDurationMinutes": int,
                "tags": list,
                "metadata": (dict, type(None))
            }
        },
        "steps": {
            "required_fields": [
                "title", "contentFields", "displayOrder", "createdAt", "updatedAt", "nextStepReference"
            ],
            "optional_fields": ["metadata"],
            "field_types": {
                "title": str,
                "contentFields": dict,
                "displayOrder": int,
                "createdAt": int,
                "updatedAt": int,
                "metadata": (dict, type(None)),
                "nextStepReference": (int, type(None))
            }
        }
    }
}

WALKTHROUGH_AUDIT_SCHEMA = {
    "required_fields": [
        "walkthrough_id", "walkthrough_title", "library_name", "library_version",
        "started_at", "completed_at", "duration_seconds", "total_steps",
        "completed_steps", "failed_steps", "success", "gaps"
    ],
    "optional_fields": [
        "clarity_gaps", "prerequisite_gaps", "logical_flow_gaps",
        "execution_gaps", "completeness_gaps", "cross_reference_gaps",
        "critical_gaps", "warning_gaps", "info_gaps",
        "execution_log", "agent_log_path"
    ],
    "field_types": {
        "walkthrough_id": str,
        "walkthrough_title": str,
        "library_name": str,
        "library_version": str,
        "started_at": str,
        "completed_at": str,
        "duration_seconds": (int, float),
        "total_steps": int,
        "completed_steps": int,
        "failed_steps": int,
        "success": bool,
        "gaps": list,
        "clarity_gaps": int,
        "prerequisite_gaps": int,
        "logical_flow_gaps": int,
        "execution_gaps": int,
        "completeness_gaps": int,
        "cross_reference_gaps": int,
        "critical_gaps": int,
        "warning_gaps": int,
        "info_gaps": int,
        "execution_log": (str, type(None)),
        "agent_log_path": (str, type(None))
    },
    "nested_schemas": {
        "gaps": {
            "required_fields": [
                "step_number", "step_title", "gap_type", "severity", "description", "timestamp"
            ],
            "optional_fields": ["suggested_fix", "context"],
            "field_types": {
                "step_number": int,
                "step_title": str,
                "gap_type": str,
                "severity": str,
                "description": str,
                "suggested_fix": (str, type(None)),
                "context": (str, type(None)),
                "timestamp": str
            }
        }
    }
}


def create_walkthrough_generation_validation_hook(output_dir: Optional[Path] = None, log_dir: Optional[Path] = None):
    """
    Create a PreToolUse hook that validates walkthrough generation JSON output.

    Args:
        output_dir: Optional expected output directory for location validation
        log_dir: Optional directory to log validation calls

    Returns:
        Async hook function
    """
    async def walkthrough_generation_validation_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],  # noqa: ARG001 - Required by hook signature
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Validate walkthrough generation JSON before writing."""
        try:
            tool_name = input_data.get('tool_name', '')
            tool_input = input_data.get('tool_input', {})
            file_path = tool_input.get('file_path', '')

            # Only validate Write operations on walkthrough JSON files
            if tool_name != 'Write':
                return {}

            filename = Path(file_path).name
            if not filename.endswith('.json'):
                return {}

            # Validate output directory if specified
            if output_dir:
                abs_file_path = Path(file_path).resolve()
                abs_output_dir = output_dir.resolve()
                file_dir = abs_file_path.parent

                if not str(file_dir).startswith(str(abs_output_dir)):
                    reason = f"Files must be created in {abs_output_dir}, not {file_dir}"

                    # Log validation failure
                    if log_dir:
                        log_validation_call(log_dir, "walkthrough_generation_validation", filename, False, reason=reason)

                    return {
                        'hookSpecificOutput': {
                            'hookEventName': 'PreToolUse',
                            'permissionDecision': 'deny',
                            'permissionDecisionReason': reason
                        }
                    }

            # Validate JSON content
            content = tool_input.get('content', '')
            if not content:
                return {}

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                reason = f"Invalid JSON: {e}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "walkthrough_generation_validation", filename, False, reason=reason)

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason
                    }
                }

            # Validate structure
            errors = validate_json_structure(data, WALKTHROUGH_GENERATION_SCHEMA)

            if errors:
                error_msg = f"Schema validation failed: {'; '.join(errors[:3])}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "walkthrough_generation_validation", filename, False, errors=errors, reason="Schema validation failed")

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': error_msg
                    }
                }

            # Validation passed - log success
            if log_dir:
                log_validation_call(log_dir, "walkthrough_generation_validation", filename, True)

            return {}  # Validation passed

        except Exception as e:
            # Log error but don't block
            print(f"⚠️  Validation hook error: {e}")
            if log_dir:
                log_validation_call(log_dir, "walkthrough_generation_validation", filename or "unknown", False, reason=f"Hook error: {e}")
            return {}

    return walkthrough_generation_validation_hook


def create_walkthrough_audit_validation_hook(output_dir: Optional[Path] = None, log_dir: Optional[Path] = None):
    """
    Create a PreToolUse hook that validates walkthrough audit JSON output.

    Args:
        output_dir: Optional expected output directory for location validation
        log_dir: Optional directory to log validation calls

    Returns:
        Async hook function
    """
    async def walkthrough_audit_validation_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],  # noqa: ARG001 - Required by hook signature
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Validate walkthrough audit JSON before writing."""
        try:
            tool_name = input_data.get('tool_name', '')
            tool_input = input_data.get('tool_input', {})
            file_path = tool_input.get('file_path', '')

            # Only validate Write operations on audit result files
            if tool_name != 'Write':
                return {}

            filename = Path(file_path).name
            if not filename.endswith('_audit.json'):
                return {}

            # Validate output directory if specified
            if output_dir:
                abs_file_path = Path(file_path).resolve()
                abs_output_dir = output_dir.resolve()
                file_dir = abs_file_path.parent

                if not str(file_dir).startswith(str(abs_output_dir)):
                    reason = f"Files must be created in {abs_output_dir}, not {file_dir}"

                    # Log validation failure
                    if log_dir:
                        log_validation_call(log_dir, "walkthrough_audit_validation", filename, False, reason=reason)

                    return {
                        'hookSpecificOutput': {
                            'hookEventName': 'PreToolUse',
                            'permissionDecision': 'deny',
                            'permissionDecisionReason': reason
                        }
                    }

            # Validate JSON content
            content = tool_input.get('content', '')
            if not content:
                return {}

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                reason = f"Invalid JSON: {e}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "walkthrough_audit_validation", filename, False, reason=reason)

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason
                    }
                }

            # Validate structure
            errors = validate_json_structure(data, WALKTHROUGH_AUDIT_SCHEMA)

            if errors:
                error_msg = f"Schema validation failed: {'; '.join(errors[:3])}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "walkthrough_audit_validation", filename, False, errors=errors, reason="Schema validation failed")

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': error_msg
                    }
                }

            # Validation passed - log success
            if log_dir:
                log_validation_call(log_dir, "walkthrough_audit_validation", filename, True)

            return {}  # Validation passed

        except Exception as e:
            # Log error but don't block
            print(f"⚠️  Validation hook error: {e}")
            if log_dir:
                log_validation_call(log_dir, "walkthrough_audit_validation", filename or "unknown", False, reason=f"Hook error: {e}")
            return {}

    return walkthrough_audit_validation_hook


def create_api_completeness_validation_hook(output_dir: Optional[Path] = None, log_dir: Optional[Path] = None):
    """
    Create a PreToolUse hook that validates API completeness analysis JSON output.

    Args:
        output_dir: Optional expected output directory for location validation
        log_dir: Optional directory to log validation calls

    Returns:
        Async hook function
    """
    async def api_completeness_validation_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],  # noqa: ARG001 - Required by hook signature
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Validate API completeness JSON before writing."""
        try:
            tool_name = input_data.get('tool_name', '')
            tool_input = input_data.get('tool_input', {})
            file_path = tool_input.get('file_path', '')

            # Only validate Write operations on completeness analysis files
            if tool_name != 'Write':
                return {}

            filename = Path(file_path).name
            if filename != 'completeness_analysis.json':
                return {}

            # Validate output directory if specified
            if output_dir:
                abs_file_path = Path(file_path).resolve()
                abs_output_dir = output_dir.resolve()
                file_dir = abs_file_path.parent

                if not str(file_dir).startswith(str(abs_output_dir)):
                    reason = f"Files must be created in {abs_output_dir}, not {file_dir}"

                    # Log validation failure
                    if log_dir:
                        log_validation_call(log_dir, "api_completeness_validation", filename, False, reason=reason)

                    return {
                        'hookSpecificOutput': {
                            'hookEventName': 'PreToolUse',
                            'permissionDecision': 'deny',
                            'permissionDecisionReason': reason
                        }
                    }

            # Validate JSON content
            content = tool_input.get('content', '')
            if not content:
                return {}

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                reason = f"Invalid JSON: {e}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "api_completeness_validation", filename, False, reason=reason)

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason
                    }
                }

            # Validate using Pydantic
            passed, errors = validate_with_pydantic(data, APICompletenessOutput)

            if not passed:
                error_msg = f"Schema validation failed: {'; '.join(errors[:3]) if errors else 'Unknown error'}"

                # Log validation failure
                if log_dir:
                    log_validation_call(log_dir, "api_completeness_validation", filename, False, errors=errors, reason="Schema validation failed")

                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': error_msg
                    }
                }

            # Validation passed - log success
            if log_dir:
                log_validation_call(log_dir, "api_completeness_validation", filename, True)

            return {}  # Validation passed

        except Exception as e:
            # Log error but don't block
            print(f"⚠️  Validation hook error: {e}")
            if log_dir:
                log_validation_call(log_dir, "api_completeness_validation", filename or "unknown", False, reason=f"Hook error: {e}")
            return {}

    return api_completeness_validation_hook
