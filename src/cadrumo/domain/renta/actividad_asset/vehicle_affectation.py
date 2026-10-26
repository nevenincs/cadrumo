"""Whether a vehicle is an affected activity asset (LIRPF art. 29; RIRPF art. 22).

A vehicle is indivisible, so it is either wholly affected or not affected; no
business-use share exists.  The regulation excludes an element used for both
the activity and private needs unless the private use is accessory (personal
use on non-working time), denies even that allowance to passenger cars and
similar vehicles outside five listed uses, and excludes an element missing
from the activity's books.  The product cannot observe use, so it records the
taxpayer's typed declaration with its evidence and refuses anything short of
an admitted one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import ActividadAssetUnsupportedError


class VehicleCategory(StrEnum):
    """Traffic-law category of a vehicle, as RIRPF art. 22.4 classifies it."""

    PASSENGER_CAR = "passenger_car"
    ALL_TERRAIN = "all_terrain"
    MIXED_VEHICLE = "mixed_vehicle"
    TRAILER = "trailer"
    MOPED = "moped"
    MOTORCYCLE = "motorcycle"
    AIRCRAFT = "aircraft"
    LEISURE_BOAT = "leisure_boat"
    OTHER_VEHICLE = "other_vehicle"


RESTRICTED_VEHICLE_CATEGORIES: frozenset[VehicleCategory] = frozenset(
    {
        VehicleCategory.PASSENGER_CAR,
        VehicleCategory.ALL_TERRAIN,
        VehicleCategory.MIXED_VEHICLE,
        VehicleCategory.TRAILER,
        VehicleCategory.MOPED,
        VehicleCategory.MOTORCYCLE,
        VehicleCategory.AIRCRAFT,
        VehicleCategory.LEISURE_BOAT,
    },
)
"""Categories RIRPF art. 22.4 denies the accessory private-use allowance.

All-terrain vehicles and mixed vehicles count as passenger cars for this
purpose (art. 22.4, final paragraph).
"""


class VehiclePrivateUse(StrEnum):
    """How the vehicle is used for the taxpayer's private needs."""

    NONE = "none"
    ACCESSORY_NON_WORKING_TIME = "accessory_non_working_time"
    SHARED = "shared"


class VehicleListedUse(StrEnum):
    """The uses RIRPF art. 22.4 (a)-(e) exempt from the passenger-car restriction."""

    MIXED_VEHICLE_GOODS_TRANSPORT = "mixed_vehicle_goods_transport"
    PAID_PASSENGER_TRANSPORT = "paid_passenger_transport"
    PAID_DRIVING_OR_PILOT_INSTRUCTION = "paid_driving_or_pilot_instruction"
    COMMERCIAL_REPRESENTATIVE_TRAVEL = "commercial_representative_travel"
    HABITUAL_ONEROUS_HIRE = "habitual_onerous_hire"


class ElectricPropulsion(StrEnum):
    """Annex II Reglamento General de Vehículos types LIS DA 18a.1 admits."""

    FCV = "fcv"
    FCHV = "fchv"
    BEV = "bev"
    REEV = "reev"
    PHEV = "phev"


class VehicleAffectation(BaseModel):
    """The taxpayer's declaration of how a vehicle serves the activity."""

    model_config = STRICT_FROZEN_CONFIG

    category: VehicleCategory
    private_use: VehiclePrivateUse
    listed_use: VehicleListedUse | None = None
    recorded_in_activity_books: bool
    evidence_reference: str = Field(min_length=1, max_length=512)
    electric_propulsion: ElectricPropulsion | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_listed_use(self) -> Self:
        if (
            self.listed_use is VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT
            and self.category is not VehicleCategory.MIXED_VEHICLE
        ):
            raise ValueError("the goods-transport listed use applies only to a mixed vehicle")
        return self


def require_vehicle_affected(affectation: VehicleAffectation) -> None:
    """Refuse a vehicle the declaration does not prove to be an affected asset."""
    if not affectation.recorded_in_activity_books:
        raise ActividadAssetUnsupportedError(
            "a vehicle missing from the activity's books is not an affected asset (RIRPF art. 22.2.2º)",
        )
    if affectation.private_use is VehiclePrivateUse.SHARED:
        raise ActividadAssetUnsupportedError(
            "a vehicle shared between the activity and private needs is not an affected asset, and a vehicle "
            "cannot be partially affected (RIRPF art. 22.2.1º and 22.3; LIRPF art. 29.2)",
        )
    if (
        affectation.private_use is VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME
        and affectation.category in RESTRICTED_VEHICLE_CATEGORIES
        and affectation.listed_use is None
    ):
        raise ActividadAssetUnsupportedError(
            f"a {affectation.category.value} with any private use is affected only under one of the uses RIRPF "
            "art. 22.4 (a)-(e) lists; otherwise it must be used exclusively for the activity",
        )


__all__ = [
    "RESTRICTED_VEHICLE_CATEGORIES",
    "ElectricPropulsion",
    "VehicleAffectation",
    "VehicleCategory",
    "VehicleListedUse",
    "VehiclePrivateUse",
    "require_vehicle_affected",
]
