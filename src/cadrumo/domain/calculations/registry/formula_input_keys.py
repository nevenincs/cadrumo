"""Shared key-shape validation for numeric and text formula inputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from ....core.casilla_id import CasillaId, validated_casilla_id
from .errors import RegistryValidationError

type FormulaInputSurface = Literal["input", "text_input"]


def canonicalize_formula_input_keys[InputKey, InputValue](
    values: Mapping[InputKey, InputValue],
    *,
    surface: FormulaInputSurface,
) -> dict[CasillaId, InputValue]:
    """Validate key shape only; callers retain membership and value policy."""
    if surface == "input":
        translated_message = "errors.calc.unknown_input_casillas"
    elif surface == "text_input":
        translated_message = "errors.calc.unknown_text_input_casillas"
    else:
        raise ValueError(f"unsupported formula input surface {surface!r}")

    invalid = tuple(repr(key) for key in values if not isinstance(key, str))
    if invalid:
        sorted_invalid = sorted(invalid)
        raise RegistryValidationError(
            f"{surface} keys must be canonical casilla.id strings: {sorted_invalid!r}",
            translated_message=translated_message,
            context={"casilla_ids": ",".join(sorted_invalid)},
        )

    malformed: list[str] = []
    canonical: dict[CasillaId, InputValue] = {}
    for key in values:
        try:
            canonical[validated_casilla_id(key, surface=f"{surface} casilla.id")] = values[key]
        except ValueError:
            malformed.append(str(key))
    if malformed:
        sorted_malformed = sorted(malformed)
        raise RegistryValidationError(
            f"{surface} keys must be canonical casilla.id strings: {sorted_malformed!r}",
            translated_message=translated_message,
            context={"casilla_ids": ",".join(sorted_malformed)},
        )
    return canonical
