"""Read-only reciprocity checks between IRPF assets and the separate IVA register."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.bienes_inversion.register import BienInversionIvaRecord
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision


class ActivityAssetIvaLinkage(BaseModel):
    """Verified cross-register edge; neither source record owns the other."""

    model_config = STRICT_FROZEN_CONFIG

    irpf_asset_id: str = Field(min_length=1, max_length=128)
    irpf_asset_revision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    iva_record_id: str = Field(min_length=1, max_length=128)
    canonical_transaction_id: str = Field(pattern=r"^[0-9a-f]{64}$")


def verify_optional_iva_linkage(
    *,
    asset: ActivityAssetRevision,
    iva_record: BienInversionIvaRecord | None,
    transaction_replacements: dict[str, str],
) -> ActivityAssetIvaLinkage | None:
    """Verify optional IVA reciprocity against canonical transaction lineage.

    ``None`` is a valid result: an IRPF activity asset need not carry deductible
    IVA or qualify for the separate bienes-de-inversión register.  When an IVA
    record is supplied, its existing ``acquisition_ledger_id`` must name the
    current canonical transaction.  A corrected acquisition therefore makes
    stale asset evidence visible and requires a new immutable asset revision.
    """
    canonical_transaction_id = asset.acquisition.resolve_current_transaction_id(transaction_replacements)
    if canonical_transaction_id != asset.acquisition.observed_transaction_id:
        raise ActividadAssetValidationError(
            "activity asset acquisition evidence is stale after a canonical transaction correction",
        )
    if iva_record is None:
        return None
    if iva_record.acquisition_ledger_id != canonical_transaction_id:
        raise ActividadAssetValidationError(
            "IRPF asset and IVA investment record do not reference the same canonical acquisition transaction",
        )
    if iva_record.acquisition_year != asset.in_service_date.year:
        raise ActividadAssetValidationError(
            "IRPF asset service year and IVA investment-record acquisition year differ",
        )
    return ActivityAssetIvaLinkage(
        irpf_asset_id=asset.asset_id,
        irpf_asset_revision_id=asset.revision_id,
        iva_record_id=iva_record.identifier,
        canonical_transaction_id=canonical_transaction_id,
    )


__all__ = ["ActivityAssetIvaLinkage", "verify_optional_iva_linkage"]
