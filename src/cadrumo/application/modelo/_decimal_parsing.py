"""Shared finite-Decimal parser for borrador-sourced modelo bindings.

This module is a parsing helper, not a binding:
:func:`decimal_from_string` coerces a finite raw string or
:class:`~decimal.Decimal` into a :class:`~decimal.Decimal` for a registry
binding identifier. It is named for what it does (parsing) rather than the
pipeline that consumes it, so "binding" stays reserved for the
registry-data-input concept.

The borrador-binding path accepts live snapshot values as either
:class:`~decimal.Decimal` or :class:`str`. Its resolver keeps that boundary
local and delegates the canonical finite coercion here. Profile-sourced bindings
use typed profile facts directly and keep their Decimal-channel refusal in the
profile resolver instead of reusing this helper.

See Also:
    :func:`cadrumo.application.modelo.borrador_binding.resolve_modelo_100_borrador_bindings`
        Consumes this helper after registry eligibility and caller-precedence
        checks decide that a borrador snapshot may supply the value.
    :func:`cadrumo.application.modelo.profile_binding.resolve_profile_sourced_bindings`
        Resolves the same registry binding channels from typed profile facts,
        without raw string parsing.

The caller supplies the pipeline-specific error factory so the operator-facing
refusal keeps the boundary context of the surface that found the bad value.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ...core.decimal.coercion import coerce_finite_european_decimal
from ...domain.calculations.registry.ids import BindingId


def decimal_from_string(
    binding_id: BindingId,
    value: Decimal | str,
    *,
    error_factory: Callable[[str], Exception],
    pipeline_label: str = "value",
) -> Decimal:
    """Parse a finite decimal value or raise the pipeline-specific error.

    Args:
        binding_id: Registry binding identifier being resolved; appears in the
            error message so the operator can locate the offending value.
        value: Decimal or free string from a source pipeline such as a live
            borrador snapshot. Strings use the canonical finite European
            decimal contract, and Decimal instances must also be finite.
        error_factory: Callable invoked with the formatted message when the
            value does not resolve to a finite decimal. Each pipeline supplies its own boundary
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
        :func:`cadrumo.application.modelo.borrador_binding.resolve_modelo_100_borrador_bindings`
            Resolver that validates the borrador snapshot and calls this helper
            for Decimal-channel snapshot values.
    """
    parsed = coerce_finite_european_decimal(value)
    if parsed is not None:
        return parsed
    raise error_factory(
        f"{pipeline_label} for numeric binding {binding_id!r} must be a finite decimal; got {value!r}",
    )


__all__ = ["decimal_from_string"]
