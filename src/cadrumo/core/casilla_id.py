"""Canonical casilla-id primitive shared across architecture layers.

The :data:`CasillaId` alias is the shared key for registry casillas,
CLI ``--casilla`` inputs, parser observations, and calculation payloads.
Its public home is :mod:`cadrumo.core`; it anchors
:class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition`,
:class:`~domain.calculations.registry.schema_surfaces.CalculationCompletenessCasilla`,
and filing snapshot facts such as
:class:`~domain.modelos.ledger_filing_snapshot.ManualFactBasisEntry`.

Use :func:`validated_casilla_id` or :func:`validated_casilla_id_map`
at boundaries so display numbers, labels, and export metadata do not
masquerade as canonical registry identifiers. Registry membership helpers
such as :func:`~domain.calculations.registry.casilla_membership.casillas_by_id` and
:func:`~domain.calculations.registry.casilla_membership.declared_casilla_ids` then compare
only declared ``casilla.id`` values.

The alias is a structural token, not a registry lookup. It can prove that a
string is shaped like a canonical ``casilla.id``; only a selected
:class:`~domain.calculations.registry.schema.ModeloRevision` can prove that the id
is declared for a filing context.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Annotated, Final

from pydantic import Field

_CASILLA_RE = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_CASILLA_MAX_LENGTH: Final = 64

type CasillaId = Annotated[str, Field(min_length=1, max_length=_CASILLA_MAX_LENGTH, pattern=_CASILLA_RE)]

# The same token rule as ``CasillaId``, checked without a validator call: a
# calculation identity hashes tens of thousands of ids on every catalogue read.
_CASILLA_TOKEN: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


def validated_casilla_id(value: object, *, surface: str = "casilla.id") -> CasillaId:
    """Return ``value`` as a canonical :data:`CasillaId`, failing at the declaring surface.

    This validates the token shape only. Callers that need revision membership
    must also compare against
    :func:`~domain.calculations.registry.casilla_membership.declared_casilla_ids` or
    :func:`~domain.calculations.registry.casilla_membership.undeclared_casilla_ids`.

    Args:
        value: Candidate boundary value.
        surface: Human-readable source used in the failure message.

    Raises:
        ValueError: When ``value`` is not a string or fails the canonical
            ``casilla.id`` shape.
    """
    if not isinstance(value, str) or len(value) > _CASILLA_MAX_LENGTH or _CASILLA_TOKEN.fullmatch(value) is None:
        raise ValueError(f"{surface} {value!r} is not a canonical casilla.id")
    return str.__str__(value)


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
    against the selected :class:`~domain.calculations.registry.schema.ModeloRevision`.
    """
    return {validated_casilla_id(key, surface=f"{surface} key"): value for key, value in values.items()}
