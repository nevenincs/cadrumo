"""Bounded schema diagnostics without caller-supplied values or field names."""

from pydantic import ValidationError

from cadrumo.application.operations.frontend_requests import OperationObservationRequestV1


def request_faults(tool: str, error: ValidationError) -> list[dict[str, str]]:
    """Expose known observation fields; redact all unrecognized locations."""
    fields = OperationObservationRequestV1.model_fields if tool == "observe" else {}
    faults: list[dict[str, str]] = []
    for issue in error.errors(include_input=False, include_context=False, include_url=False)[:8]:
        location = issue["loc"]
        field = location[0] if len(location) == 1 and location[0] in fields else "request"
        # Validator messages and custom type strings can contain caller data.
        kind = issue["type"]
        reason = (
            kind
            if kind
            in {
                "missing",
                "extra_forbidden",
                "greater_than",
                "greater_than_equal",
                "less_than_equal",
                "int_type",
                "string_type",
                "literal_error",
            }
            else "invalid_value"
        )
        faults.append({"field": str(field), "reason": reason})
    return faults
