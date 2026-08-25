"""Text-input validation for registry formula evaluation.

Text casilla inputs are canonicalised into
:class:`~core.CasillaId` keys before
:func:`domain.calculations.registry._formula_runtime.calculate_registry_snapshot`
checks that they target text-capable
:class:`~domain.calculations.registry.CasillaDefinition` rows.

See Also:
    :mod:`domain.calculations.registry._formula_runtime`
        Runtime caller that consumes the validated text input mapping.
    :mod:`domain.calculations.registry._formula_runtime_ops`
        Numeric input companion that validates decimal casilla inputs.
    :mod:`domain.calculations.registry._schema`
        Registry schema layer declaring casilla identifiers and data types.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core import CasillaId, validated_casilla_id
from .errors import RegistryValidationError
from .schema_scalars import registry_scalar_value_type, validate_registry_text_scalar
from ._schema_surfaces import CasillaDefinition

__all__ = ["validate_text_input_targets", "validated_text_input_casilla_ids"]


def validated_text_input_casilla_ids[InputKey, InputValue](
    text_inputs: Mapping[InputKey, InputValue],
) -> dict[CasillaId, str]:
    """Canonicalise raw text input keys and strip operator-supplied strings.

    Raw mapping keys become validated
    :class:`~core.CasillaId` values; values must be
    non-empty strings after whitespace trimming so text leaves enter the formula
    runtime in canonical form.
    """
    invalid = tuple(repr(key) for key in text_inputs if not isinstance(key, str))
    if invalid:
        raise RegistryValidationError(
            f"text_input keys must be canonical casilla.id strings: {sorted(invalid)!r}",
            translated_message="errors.calc.unknown_text_input_casillas",
            context={"casilla_ids": ",".join(sorted(invalid))},
        )
    malformed: list[str] = []
    canonical_text_inputs: dict[CasillaId, InputValue] = {}
    for key in text_inputs:
        try:
            canonical_text_inputs[validated_casilla_id(key, surface="text_input casilla.id")] = text_inputs[key]
        except ValueError:
            malformed.append(str(key))
    if malformed:
        raise RegistryValidationError(
            f"text_input keys must be canonical casilla.id strings: {sorted(malformed)!r}",
            translated_message="errors.calc.unknown_text_input_casillas",
            context={"casilla_ids": ",".join(sorted(malformed))},
        )
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
    :class:`~domain.calculations.registry.CasillaDefinition` map so callers
    cannot supply unknown casillas or route text into numeric registry targets.
    """
    text_casilla_ids = {
        casilla_id
        for casilla_id, casilla in casillas_by_id.items()
        if registry_scalar_value_type(casilla.data_type) == "str"
    }
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
        canonical = validate_registry_text_scalar(casilla.data_type, value)
        if casilla.constraints is not None:
            reason = casilla.constraints.violates_text(canonical)
            if reason is not None:
                raise RegistryValidationError(f"text_input {casilla_id!r} {reason}")
        validated[casilla_id] = canonical
    return validated
