"""Shared string-to-Decimal parser for borrador-sourced modelo bindings.

This module is a parsing helper, not a binding: :func:`decimal_from_string`
coerces a raw string into a :class:`~decimal.Decimal` for a registry binding
identifier. It is named for what it does (parsing) rather than the pipeline that
consumes it, so "binding" stays reserved for the registry-data-input concept.

The borrador-binding path accepts live snapshot values as either
:class:`~decimal.Decimal` or :class:`str`. Its resolver keeps that boundary
local and delegates only the string coercion here. Profile-sourced bindings use
typed profile facts directly and keep their Decimal-channel refusal in the
profile resolver instead of reusing this raw-string helper.

See Also:
    :func:`aeat.application.modelo._borrador_binding.resolve_modelo_100_borrador_bindings`
        Consumes this helper after registry eligibility and caller-precedence
        checks decide that a borrador snapshot may supply the value.
    :func:`aeat.application.modelo._profile_binding.resolve_profile_sourced_bindings`
        Resolves the same registry binding channels from typed profile facts,
        without raw string parsing.

The caller supplies the pipeline-specific error factory so the operator-facing
refusal keeps the boundary context of the surface that found the bad value.
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
        binding_id: Registry binding identifier being resolved; appears in the
            error message so the operator can locate the offending value.
        value: Free string from a source pipeline such as a live borrador
            snapshot.
        error_factory: Callable invoked with the formatted message when
            the string does not parse. Each pipeline supplies its own boundary
            error class so refusals carry the right context; the factory may
            use the message directly or translate it into structured context.
        pipeline_label: Operator-facing label that prefixes the refusal
            message (for example, ``"borrador value"``); defaults to the
            generic ``"value"``.

    Returns:
        The parsed :class:`~decimal.Decimal`.

    Raises:
        Exception: Whatever ``error_factory`` produced.

    See Also:
        :func:`aeat.application.modelo._borrador_binding.resolve_modelo_100_borrador_bindings`
            Resolver that validates the borrador snapshot and calls this helper
            for Decimal-channel snapshot strings.
    """
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise error_factory(
            f"{pipeline_label} for numeric binding {binding_id!r} must be decimal-compatible; got {value!r}",
        ) from exc


__all__ = ["decimal_from_string"]
