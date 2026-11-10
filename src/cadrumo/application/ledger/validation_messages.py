"""Bounded, field-located refusal messages for ledger validation failures."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import ValidationError

from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import CadrumoError

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


def _registered_cause(item: Mapping[str, object]) -> CadrumoError | None:
    """Find the registered refusal a Pydantic entry was raised from, if any.

    A domain rule that crosses Pydantic's validator protocol is re-raised as a
    builtin ``ValueError`` with the registered failure as its cause, so the
    entry's context holds the exception the rule actually raised. Only that
    exception object is read: the rest of the context can repeat the input, and
    it never leaves this function.
    """
    context = item.get("ctx")
    if not isinstance(context, Mapping):
        return None
    found: object = cast("Mapping[str, object]", context).get("error")
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


def _located(item: Mapping[str, object]) -> str:
    """One Pydantic entry as its dotted field location and its own sentence."""
    location = item.get("loc", ())
    parts: tuple[object, ...] = cast("tuple[object, ...]", location) if isinstance(location, tuple) else ()
    field_path = ".".join(str(part) for part in parts if part != "__root__")
    message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
    return f"{field_path}: {message}" if field_path and message else message


def ledger_refusal_messages(error: Exception, *, limit: int, fallback: str) -> tuple[str, ...]:
    """Return at most ``limit`` refusals said in the operator's language.

    A registered refusal is rendered through its own translation, whichever
    layer raised it and whether or not Pydantic wrapped it on the way out. Only
    an unregistered failure keeps its author's sentence, and nothing carries
    Pydantic's documentation URL, input value or context into a result a person
    reads.
    """
    if isinstance(error, CadrumoError):
        return (resolve_error_message(error)[:_MAX_MESSAGE_LENGTH],)
    if isinstance(error, ValidationError):
        messages: list[str] = []
        for item in error.errors(include_input=False, include_url=False):
            registered = _registered_cause(item)
            said = resolve_error_message(registered) if registered is not None else _located(item)
            if said:
                messages.append(said[:_MAX_MESSAGE_LENGTH])
            if len(messages) >= limit:
                break
        if messages:
            return tuple(messages)
    return bounded_validation_messages(error, limit=limit, fallback=fallback)


def ledger_refusal_sentence(error: Exception, *, fallback: str) -> str:
    """Return the one sentence a per-row refusal carries, in the operator's language."""
    return ledger_refusal_messages(error, limit=1, fallback=fallback)[0]


__all__ = [
    "bounded_validation_messages",
    "ledger_refusal_messages",
    "ledger_refusal_sentence",
    "registered_refusal_causes",
]
