"""Bounded, field-located refusal messages for ledger validation failures."""

from __future__ import annotations

from pydantic import ValidationError

_MAX_MESSAGE_LENGTH = 2048


def bounded_validation_messages(error: Exception, *, limit: int, fallback: str) -> tuple[str, ...]:
    """Return at most ``limit`` user-actionable messages, or ``fallback`` when none survive.

    A Pydantic refusal keeps each entry's dotted field location and message,
    never its input, context or documentation URL. Any other error keeps its own
    sentence. Every message is truncated to a fixed length.
    """
    messages: list[str] = []
    if isinstance(error, ValidationError):
        for item in error.errors(include_input=False, include_context=False, include_url=False)[:limit]:
            location = item.get("loc", ())
            field_path = ".".join(str(part) for part in location if part != "__root__")
            message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
            detail = f"{field_path}: {message}" if field_path else message
            if detail:
                messages.append(detail[:_MAX_MESSAGE_LENGTH])
    else:
        detail = str(error).strip()
        if detail:
            messages.append(detail[:_MAX_MESSAGE_LENGTH])
    if not messages:
        messages.append(fallback)
    return tuple(messages[:limit])
