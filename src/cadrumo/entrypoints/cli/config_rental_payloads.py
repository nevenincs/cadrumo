"""Typed ``--json`` payload schemas for the ``config profile inmueble`` and ``arrendamiento`` families.

A row projects the facts the profile stores for it, keyed by their schema leaf and
rendered in the one canonical text form. A leaf the row does not state is absent,
never a default. ``row`` is the stable key a lease and a ledger row name: the
position of the row in its profile section, which is never reused.
"""

from __future__ import annotations

from pydantic import NonNegativeInt

from ...core.json_contract import OutputSchema


class ProfileRentalRowPayload(OutputSchema):
    """One stored property or lease row."""

    row: NonNegativeInt
    facts: dict[str, str]


class ConfigProfileInmuebleAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile inmueble add``."""

    profile: str
    row: NonNegativeInt
    total: NonNegativeInt


class ConfigProfileInmuebleEditResult(OutputSchema):
    """JSON envelope for ``aeat config profile inmueble edit``."""

    profile: str
    row: NonNegativeInt
    changed: bool


class ConfigProfileInmuebleListResult(OutputSchema):
    """JSON envelope for ``aeat config profile inmueble list``."""

    profile: str
    total: NonNegativeInt
    inmuebles: list[ProfileRentalRowPayload] = []


class ConfigProfileInmuebleRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile inmueble remove``."""

    profile: str
    removed_row: NonNegativeInt
    total: NonNegativeInt


class ConfigProfileArrendamientoAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile arrendamiento add``."""

    profile: str
    row: NonNegativeInt
    total: NonNegativeInt


class ConfigProfileArrendamientoEditResult(OutputSchema):
    """JSON envelope for ``aeat config profile arrendamiento edit``."""

    profile: str
    row: NonNegativeInt
    changed: bool


class ConfigProfileArrendamientoEndResult(OutputSchema):
    """JSON envelope for ``aeat config profile arrendamiento end``."""

    profile: str
    row: NonNegativeInt
    fecha_fin: str
    changed: bool


class ConfigProfileArrendamientoListResult(OutputSchema):
    """JSON envelope for ``aeat config profile arrendamiento list``."""

    profile: str
    total: NonNegativeInt
    arrendamientos: list[ProfileRentalRowPayload] = []


class ConfigProfileArrendamientoRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile arrendamiento remove``."""

    profile: str
    removed_row: NonNegativeInt
    total: NonNegativeInt
