"""Text-input validation for registry formula evaluation."""

from __future__ import annotations

from collections.abc import Mapping

from ._errors import RegistryValidationError
from ._ids import CasillaId, validated_casilla_id
from ._schema_surfaces import CasillaDefinition

__all__ = ["validate_text_input_targets", "validated_text_input_casilla_ids"]


def validated_text_input_casilla_ids[InputKey, InputValue](
    text_inputs: Mapping[InputKey, InputValue],
) -> dict[CasillaId, str]:
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
        if not isinstance(value, str) or not value:
            raise RegistryValidationError(f"text_input {key!r} must be a non-empty string")
        resolved_text_inputs[key] = value
    return resolved_text_inputs


def validate_text_input_targets(
    text_inputs: Mapping[CasillaId, str],
    *,
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> None:
    text_casilla_ids = {casilla_id for casilla_id, casilla in casillas_by_id.items() if casilla.data_type == "text"}
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
