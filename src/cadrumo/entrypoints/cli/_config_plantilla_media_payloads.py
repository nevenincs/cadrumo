"""Typed ``--json`` payload schemas for the ``config profile plantilla-media`` family."""

from __future__ import annotations

from decimal import Decimal

from ...core.json_contract import OutputSchema
from ...domain.user_profile.plantilla_media import PlantillaMediaState


class ProfilePlantillaMediaYearPayload(OutputSchema):
    """One declared calendar year of average total workforce."""

    year: int
    average_workforce: Decimal
    state: PlantillaMediaState


class ConfigProfilePlantillaMediaResult(OutputSchema):
    """Every declared year after a set, list or remove, in year order."""

    years: list[ProfilePlantillaMediaYearPayload]


__all__ = ["ConfigProfilePlantillaMediaResult", "ProfilePlantillaMediaYearPayload"]
