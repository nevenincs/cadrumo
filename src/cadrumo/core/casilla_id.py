"""Canonical casilla-id primitive shared across architecture layers.

The :data:`CasillaId` alias is the shared key for registry casillas,
CLI ``--casilla`` inputs, parser observations, and calculation payloads.
Its public home is :mod:`cadrumo.core`; it anchors
:class:`~domain.calculations.registry.CasillaDefinition`,
:class:`~domain.calculations.registry.CalculationCompletenessCasilla`,
and filing snapshot facts such as
:class:`~domain.modelos.ledger_filing_snapshot.ManualFactBasisEntry`.

Use :func:`validated_casilla_id` or :func:`validated_casilla_id_map`
at boundaries so display numbers, labels, and export metadata do not
masquerade as canonical registry identifiers. Registry membership helpers
such as :func:`~domain.calculations.registry.casillas_by_id` and
:func:`~domain.calculations.registry.declared_casilla_ids` then compare
only declared ``casilla.id`` values.

The alias is a structural token, not a registry lookup. It can prove that a
string is shaped like a canonical ``casilla.id``; only a selected
:class:`~domain.calculations.registry.ModeloRevision` can prove that the id
is declared for a filing context.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

_CASILLA_RE = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"

type CasillaId = Annotated[str, Field(min_length=1, max_length=64, pattern=_CASILLA_RE)]

_CASILLA_ID_ADAPTER: TypeAdapter[CasillaId] = TypeAdapter(CasillaId)


def validated_casilla_id(value: object, *, surface: str = "casilla.id") -> CasillaId:
    """Return ``value`` as a canonical :data:`CasillaId`, failing at the declaring surface.

    This validates the token shape only. Callers that need revision membership
    must also compare against
    :func:`~domain.calculations.registry.declared_casilla_ids` or
    :func:`~domain.calculations.registry.undeclared_casilla_ids`.

    Args:
        value: Candidate boundary value.
        surface: Human-readable source used in the failure message.

    Raises:
        ValueError: When ``value`` is not a string or fails the canonical
            ``casilla.id`` shape.
    """
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
    """Return ``values`` keyed by validated :data:`CasillaId` declarations.

    Mapping validators feed registry and filing surfaces that accept
    ``dict[CasillaId, T]`` inputs, including calculation-revision snapshots and
    registry filing test helpers. Like :func:`validated_casilla_id`, this checks
    key shape only; the caller remains responsible for validating membership
    against the selected :class:`~domain.calculations.registry.ModeloRevision`.
    """
    return {validated_casilla_id(key, surface=f"{surface} key"): value for key, value in values.items()}
