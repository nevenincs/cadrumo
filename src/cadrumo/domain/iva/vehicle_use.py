"""The operator's statement of what a vehicle is used for, as LIVA art. 95.Tres.2.ª sorts it.

Regla 2.ª presumes a passenger car, its trailer, a moped, a motorcycle, a mixed
vehicle or an all-terrain vehicle 50 per cent affected, and six listed uses 100
per cent. A vehicle of any other class falls outside regla 2.ª and under regla
1.ª, at its degree of use. Nothing in a ledger row shows any of this, so it is
stated. What each statement deducts is dated law and lives in the registry.
"""

from __future__ import annotations

from enum import StrEnum

from .errors import IvaValidationError


class IvaVehicleUse(StrEnum):
    """What a row's vehicle is, where that moves it off the general presumption.

    Attributes:
        MIXED_VEHICLE_GOODS_TRANSPORT: Regla 2.ª a), a mixed vehicle carrying goods.
        PAID_PASSENGER_TRANSPORT: Regla 2.ª b), passenger transport for consideration.
        PAID_DRIVER_OR_PILOT_TRAINING: Regla 2.ª c), driver or pilot training for consideration.
        MANUFACTURER_TESTING_OR_PROMOTION: Regla 2.ª d), a manufacturer's tests,
            trials, demonstrations or sales promotion.
        COMMERCIAL_AGENT_TRAVEL: Regla 2.ª e), professional travel of a sales representative or agent.
        SURVEILLANCE: Regla 2.ª f), surveillance services.
        OUTSIDE_PRESUMED_CLASSES: A vehicle of no class regla 2.ª names, such as a lorry.
    """

    MIXED_VEHICLE_GOODS_TRANSPORT = "mixed_vehicle_goods_transport"
    PAID_PASSENGER_TRANSPORT = "paid_passenger_transport"
    PAID_DRIVER_OR_PILOT_TRAINING = "paid_driver_or_pilot_training"
    MANUFACTURER_TESTING_OR_PROMOTION = "manufacturer_testing_or_promotion"
    COMMERCIAL_AGENT_TRAVEL = "commercial_agent_travel"
    SURVEILLANCE = "surveillance"
    OUTSIDE_PRESUMED_CLASSES = "outside_presumed_classes"


def require_iva_vehicle_use(value: object) -> IvaVehicleUse:
    """Return the statement ``value`` names, or refuse it."""
    try:
        return IvaVehicleUse(value)
    except ValueError as exc:
        raise IvaValidationError(f"iva vehicle use {value!r} is not one LIVA art. 95.Tres.2.ª distinguishes") from exc
