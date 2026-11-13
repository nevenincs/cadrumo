"""Typed ``--json`` payload schemas for the ``config profile ascendiente`` family.

Each row projects what the ascendants operation stores for one person: the stored
NIF or NIE, the date of birth, the date of death, the number of descendants the
ascendant lives with, whether it lived with the filer at least half the period, its
annual rentas, whether it files its own return, its disability grade, whether it needs
assistance of third persons or has reduced mobility and whether a judicial resolution
declares its incapacity. A leaf the row does not state is ``None``, never a default.

``state`` is the backend's own reading of the group: ``rows``, ``incomplete``,
``none_declared`` (the profile states that there are none) or ``unknown`` (nothing
was stated). An empty ``ascendientes`` list means no row is stored; only ``state``
says whether that is an answer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import NonNegativeInt

from ...application.user_profile.family_rows import ProfileFamilyGroupState
from ...core.json_contract import OutputSchema


class ProfileAscendientePayload(OutputSchema):
    """One stored ascendant row, addressed by the 0-based index ``ascendiente remove`` takes."""

    index: NonNegativeInt
    nif: str | None = None
    apellidos_nombre: str | None = None
    birth_date: date
    death_date: date | None = None
    convivientes: NonNegativeInt | None = None
    rentas_anuales: Decimal | None = None
    declaracion_propia: bool | None = None
    discapacidad: NonNegativeInt | None = None
    convivencia_mitad_periodo: bool | None = None
    discapacidad_asistencia: bool | None = None
    incapacidad_judicial: bool | None = None


class ConfigProfileAscendienteAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile ascendiente add``."""

    profile: str
    added: NonNegativeInt
    total: NonNegativeInt
    none_declared: bool = False


class ConfigProfileAscendienteListResult(OutputSchema):
    """JSON envelope for ``aeat config profile ascendiente list``."""

    profile: str
    total: NonNegativeInt
    state: ProfileFamilyGroupState
    stated_count: str | None = None
    ascendientes: list[ProfileAscendientePayload] = []


class ConfigProfileAscendienteEditResult(OutputSchema):
    """JSON envelope for ``aeat config profile ascendiente edit``; ``changed`` is false when nothing differed."""

    profile: str
    index: NonNegativeInt
    changed: bool
    total: NonNegativeInt


class ConfigProfileAscendienteRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile ascendiente remove``."""

    profile: str
    removed_index: NonNegativeInt
    total: NonNegativeInt
