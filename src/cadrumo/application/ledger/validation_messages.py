"""Bounded, field-located refusal messages for ledger validation failures."""

from __future__ import annotations

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ...core.errors.error_codes import get_registered_error_code, resolve_error_message
from ...core.errors.hierarchy import CadrumoError

_MAX_MESSAGE_LENGTH = 2048
_MAX_DIAGNOSTIC_ENTRIES = 8
_MAX_DIAGNOSTIC_LENGTH = 768


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
            message = item.get("msg", "").removeprefix("Value error, ").strip()
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


def _registered_cause(item: ErrorDetails) -> CadrumoError | None:
    """Find the registered refusal a Pydantic entry was raised from, if any.

    A domain rule that crosses Pydantic's validator protocol is re-raised as a
    builtin ``ValueError`` with the registered failure as its cause, so the
    entry's context holds the exception the rule actually raised. Only that
    exception object is read: the rest of the context can repeat the input, and
    it never leaves this function.
    """
    context = item.get("ctx")
    if context is None:
        return None
    found: object = context.get("error")
    while isinstance(found, BaseException):
        if isinstance(found, CadrumoError):
            return found
        found = found.__cause__
    return None


def registered_refusal_causes(error: Exception) -> tuple[CadrumoError, ...]:
    """Return the registered refusals ``error`` is, or wraps one entry at a time.

    This is how a reader learns which typed refusal a Pydantic report carries
    without reading its sentence.
    """
    if isinstance(error, CadrumoError):
        return (error,)
    if not isinstance(error, ValidationError):
        return ()
    found = (_registered_cause(item) for item in error.errors(include_input=False, include_url=False))
    return tuple(cause for cause in found if cause is not None)


def _located(item: ErrorDetails) -> str:
    """One Pydantic entry as its dotted field location and its own sentence."""
    field_path = ".".join(str(part) for part in item["loc"] if part != "__root__")
    message = item["msg"].removeprefix("Value error, ").strip()
    return f"{field_path}: {message}" if field_path and message else message


def ledger_refusal_messages(
    error: Exception, *, limit: int, fallback: str, locale: str | None = None
) -> tuple[str, ...]:
    """Return at most ``limit`` refusals said in the operator's language.

    ``locale`` names the language a registered refusal is said in; without it the
    process language speaks, as for a caller that has no request to answer.

    A registered refusal is rendered through its own translation, whichever
    layer raised it and whether or not Pydantic wrapped it on the way out. Only
    an unregistered failure keeps its author's sentence, and nothing carries
    Pydantic's documentation URL, input value or context into a result a person
    reads.
    """
    if isinstance(error, CadrumoError):
        return (resolve_error_message(error, locale=locale)[:_MAX_MESSAGE_LENGTH],)
    if isinstance(error, ValidationError):
        messages: list[str] = []
        for item in error.errors(include_input=False, include_url=False):
            registered = _registered_cause(item)
            said = resolve_error_message(registered, locale=locale) if registered is not None else _located(item)
            if said:
                messages.append(said[:_MAX_MESSAGE_LENGTH])
            if len(messages) >= limit:
                break
        if messages:
            return tuple(messages)
    return bounded_validation_messages(error, limit=limit, fallback=fallback)


def ledger_refusal_diagnostic(error: Exception) -> str:
    """Name which rule refused, for a log line, without any figure or person's text.

    The line carries only closed tokens: the exception type, each registered
    refusal's error code and catalogue key, and the model field locations
    Pydantic reports. It never carries a message, an input value or a context.
    """
    tokens = [f"type={type(error).__name__}"]
    causes = [
        f"{get_registered_error_code(cause).code}:{getattr(cause, 'translated_message', None) or '-'}"
        for cause in registered_refusal_causes(error)[:_MAX_DIAGNOSTIC_ENTRIES]
    ]
    if causes:
        tokens.append(f"causes={','.join(causes)}")
    if isinstance(error, ValidationError):
        locations = [
            ".".join(str(part) for part in item["loc"] if part != "__root__") or "-"
            for item in error.errors(include_input=False, include_context=False, include_url=False)[
                :_MAX_DIAGNOSTIC_ENTRIES
            ]
        ]
        tokens.append(f"fields={','.join(locations)}")
    return " ".join(tokens)[:_MAX_DIAGNOSTIC_LENGTH]


def ledger_refusal_sentence(error: Exception, *, fallback: str) -> str:
    """Return the one sentence a per-row refusal carries, in the operator's language."""
    return ledger_refusal_messages(error, limit=1, fallback=fallback)[0]


__all__ = [
    "bounded_validation_messages",
    "ledger_refusal_diagnostic",
    "ledger_refusal_messages",
    "ledger_refusal_sentence",
    "registered_refusal_causes",
]
