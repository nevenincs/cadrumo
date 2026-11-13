"""Typed ``--json`` payload schemas for the ``config profile posicion`` family.

A row projects the facts the profile stores for it, keyed by their schema leaf and
rendered in the one canonical text form. A leaf the row does not state is absent,
never a default. ``row`` is the stable key a ledger row names: the position of the
row in its profile section, which is never reused.
"""

from __future__ import annotations

from pydantic import NonNegativeInt

from ...core.json_contract import OutputSchema


class ProfilePosicionRowPayload(OutputSchema):
    """One stored position row."""

    row: NonNegativeInt
    facts: dict[str, str]


class ConfigProfilePosicionAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile posicion add``."""

    profile: str
    row: NonNegativeInt
    total: NonNegativeInt


class ConfigProfilePosicionEditResult(OutputSchema):
    """JSON envelope for ``aeat config profile posicion edit``."""

    profile: str
    row: NonNegativeInt
    changed: bool


class ConfigProfilePosicionListResult(OutputSchema):
    """JSON envelope for ``aeat config profile posicion list``."""

    profile: str
    total: NonNegativeInt
    posiciones: list[ProfilePosicionRowPayload] = []


class ConfigProfilePosicionRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile posicion remove``."""

    profile: str
    removed_row: NonNegativeInt
    total: NonNegativeInt
