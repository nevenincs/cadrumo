"""IVA wallet values from calculation revisions and profile projections."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_PENDING_PRIOR_CASILLA,
)
from ...domain.modelos.calculation_revision import CalculationRevision
from ..user_profile.projections import profile_path_values_for_bucket as _profile_path_values_for_bucket

_M303_PRIOR_COMPENSATION_CASILLA_ID = M303_COMPENSATION_PENDING_PRIOR_CASILLA
_M303_PRIOR_COMPENSATION_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"


def revision_iva_compensation_amount(revision: CalculationRevision) -> Decimal | None:
    """Return the Modelo 303 prior-compensation amount carried by a revision.

    Reads the :class:`~CalculationRevision` casilla values
    first, then binding overrides, matching the persisted calculation payload.
    """
    casilla_value = dict(revision.casilla_values).get(_M303_PRIOR_COMPENSATION_CASILLA_ID)
    if casilla_value is not None:
        return Decimal(casilla_value)
    binding_value = dict(revision.binding_overrides).get(_M303_PRIOR_COMPENSATION_BINDING_ID)
    if binding_value is not None:
        return Decimal(binding_value)
    return None


def taxpayer_nif_for_bucket(bucket_id: str) -> str | None:
    """Load the profile tax id for a bucket, or ``None`` when absent."""
    return taxpayer_nif_from_path_values(_profile_path_values_for_bucket(bucket_id))


def taxpayer_nif_from_path_values(values: Mapping[str, str] | None) -> str | None:
    """Return the tax id from an already-loaded profile projection, or ``None`` when absent."""
    if values is None:
        return None
    value = values.get("identity.tax_id")
    if value is None or not value.strip():
        return None
    return value.strip()
