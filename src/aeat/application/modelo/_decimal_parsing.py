"""Shared str→Decimal parser for modelo binding pipelines.

This module is a parsing helper, not a binding: ``decimal_from_string`` coerces a
raw string into a :class:`~decimal.Decimal`. It is named for what it does
(parsing) rather than the pipelines that consume it, so "binding" stays reserved
for the registry-data-input concept.

The borrador-binding and profile-binding pipelines each shipped a near-duplicate ``_decimal_value``
helper. They diverged on:

- accepted input shapes: the profile-binding variant accepts
  :class:`bool` / :class:`int` / :class:`Decimal` / :class:`str`; the
  borrador-binding variant accepts only :class:`Decimal` / :class:`str`
- error class: each raised a pipeline-specific error so the operator
  refusal carried the right boundary context (Modelo100BorradorBindingError
  vs ProfilePreflightError)

This module owns the shared str→Decimal coercion that both helpers
delegate to. The per-pipeline helpers stay (they keep the error-class
boundary the surface needs), but the string parsing now lives in one
place; bool-sentinel handling on the profile-binding side wraps this
helper rather than re-implementing the parse.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from ...domain.calculations.registry import BindingId


def decimal_from_string(
    binding_id: BindingId,
    value: str,
    *,
    error_factory: Callable[[str], Exception],
    pipeline_label: str = "value",
) -> Decimal:
    """Parse a stripped string as a Decimal or raise the pipeline-specific error.

    Args:
        binding_id: Identifier of the binding being resolved; appears in
            the error message so the operator can locate the offending
            value.
        value: Free string from the registry / profile fact.
        error_factory: Callable invoked with the formatted message when
            the string does not parse. Each pipeline supplies its own
            boundary error class so refusals carry the right context
            (borrador vs profile-binding vs another future pipeline).
        pipeline_label: Operator-facing label that prefixes the refusal
            message ("borrador value" / "profile fact" / ...); defaults
            to the generic "value".

    Returns:
        The parsed :class:`Decimal`.

    Raises:
        Exception: Whatever ``error_factory`` produced.
    """
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise error_factory(
            f"{pipeline_label} for numeric binding {binding_id!r} must be decimal-compatible; got {value!r}",
        ) from exc


__all__ = ["decimal_from_string"]
