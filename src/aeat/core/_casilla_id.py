"""Canonical casilla-id primitive shared across architecture layers.

The :data:`CasillaId` alias is the shared key for registry casillas,
CLI ``--casilla`` inputs, parser observations, and calculation payloads.
Use :func:`validated_casilla_id` or :func:`validated_casilla_id_map`
at boundaries so display numbers and labels do not masquerade as
canonical registry identifiers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

_CASILLA_RE = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"

type CasillaId = Annotated[str, Field(min_length=1, max_length=64, pattern=_CASILLA_RE)]

_CASILLA_ID_ADAPTER: TypeAdapter[CasillaId] = TypeAdapter(CasillaId)


def validated_casilla_id(value: object, *, surface: str = "casilla.id") -> CasillaId:
    """Return ``value`` as a canonical :class:`CasillaId`, failing at the declaring surface."""
    if not isinstance(value, str):
        raise ValueError(f"{surface} {value!r} is not a canonical casilla.id")
    try:
        return _CASILLA_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError(f"{surface} {value!r} is not a canonical casilla.id") from exc


def validated_casilla_id_map[T](
    values: Mapping[object, T],
    *,
    surface: str = "casilla.id map",
) -> dict[CasillaId, T]:
    """Return ``values`` keyed by validated :class:`CasillaId` declarations."""
    return {
        validated_casilla_id(key, surface=f"{surface} key"): value
        for key, value in values.items()
    }
