from __future__ import annotations


def one_line_error_message(exc: Exception) -> str:
    """Return the first non-empty exception line or its type name."""
    for line in str(exc).splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return exc.__class__.__name__


def binding_source_value(source: object) -> str:
    """Normalize a typed or plain registry binding source for projection output."""
    value = getattr(source, "value", source)
    return str(value)


def readiness_binding_input_channel(
    binding_id: str,
    *,
    enum_consumed: set[str],
    date_consumed: set[str],
) -> str:
    """Return the operator input channel declared for one missing binding."""
    if binding_id in date_consumed:
        return "date"
    if binding_id in enum_consumed:
        return "enum"
    return "decimal"
