"""Text-input validation for registry formula evaluation.

Text casilla inputs are canonicalised into
:class:`~core.casilla_id.CasillaId` keys before
:func:`domain.calculations.registry.formula_runtime.calculate_registry_snapshot`
checks that they target text-capable
:class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition` rows.

See Also:
    :mod:`domain.calculations.registry.formula_runtime`
        Runtime caller that consumes the validated text input mapping.
    :mod:`domain.calculations.registry.formula_runtime_ops`
        Numeric input companion that validates decimal casilla inputs.
    :mod:`domain.calculations.registry.schema`
        Registry schema layer declaring casilla identifiers and data types.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.casilla_id import CasillaId
from .casilla_membership import text_family_casilla_ids
from .errors import RegistryValidationError
from .formula_input_keys import canonicalize_formula_input_keys
from .schema_scalars import validate_registry_text_scalar
from .schema_surfaces import CasillaDefinition
from .tax_id_format import runtime_tax_id_format

__all__ = ["validate_text_input_targets", "validated_text_input_casilla_ids"]


def validated_text_input_casilla_ids[InputKey, InputValue](
    text_inputs: Mapping[InputKey, InputValue],
) -> dict[CasillaId, str]:
    """Canonicalise raw text input keys and strip operator-supplied strings.

    Raw mapping keys become validated
    :class:`~core.casilla_id.CasillaId` values; values must be
    non-empty strings after whitespace trimming so text leaves enter the formula
    runtime in canonical form.
    """
    canonical_text_inputs = canonicalize_formula_input_keys(text_inputs, surface="text_input")
    resolved_text_inputs: dict[CasillaId, str] = {}
    for key, value in canonical_text_inputs.items():
        if not isinstance(value, str):
            raise RegistryValidationError(f"text_input {key!r} must be a non-empty string")
        stripped = value.strip()
        if not stripped:
            raise RegistryValidationError(f"text_input {key!r} must be a non-empty string")
        resolved_text_inputs[key] = stripped
    return resolved_text_inputs


def validate_text_input_targets(
    text_inputs: Mapping[CasillaId, str],
    *,
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> dict[CasillaId, str]:
    """Validate and canonicalise text-family inputs against declared casillas.

    The runtime passes the revision's
    :class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition` map so callers
    cannot supply unknown casillas or route text into numeric registry targets.
    """
    text_casilla_ids = text_family_casilla_ids(casillas_by_id.values())
    unknown_text_inputs = sorted(set(text_inputs).difference(casillas_by_id))
    if unknown_text_inputs:
        raise RegistryValidationError(
            f"unknown text_input casilla ids: {unknown_text_inputs!r}",
            translated_message="errors.calc.unknown_text_input_casillas",
            context={"casilla_ids": ",".join(unknown_text_inputs)},
        )
    mistyped_text_inputs = sorted(set(text_inputs).difference(text_casilla_ids))
    if mistyped_text_inputs:
        raise RegistryValidationError(
            f"text_input supplied for non-text casilla ids: {mistyped_text_inputs!r}",
            translated_message="errors.calc.text_input_non_text_casillas",
            context={"casilla_ids": ",".join(mistyped_text_inputs)},
        )
    validated: dict[CasillaId, str] = {}
    for casilla_id, value in text_inputs.items():
        casilla = casillas_by_id[casilla_id]
        canonical = validate_registry_text_scalar(
            casilla.data_type,
            value,
            tax_id_format=runtime_tax_id_format() if casilla.data_type == "nif" else None,
        )
        if casilla.constraints is not None:
            reason = casilla.constraints.violates_text(canonical)
            if reason is not None:
                raise RegistryValidationError(f"text_input {casilla_id!r} {reason}")
        validated[casilla_id] = canonical
    return validated
