"""Reciprocal IRPF/IVA acquisition-linkage acceptance cases."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....domain.bienes_inversion.register import BienInversionIvaRecord
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ..iva_linkage import verify_optional_iva_linkage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TRANSACTION_ID = "a" * 64


@pytest.fixture(scope="module", autouse=True)
def _governed_fact_scope() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _asset(*, transaction_id: str = _TRANSACTION_ID) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="irpf-computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=transaction_id,
            invoice_evidence_id="purchase-invoice-computer",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000.00"),
            prior_allocation_provenance="canonical ledger allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
    )


def _iva_record(*, transaction_id: str = _TRANSACTION_ID) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier="iva-computer",
        description="Computer",
        acquisition_year=2025,
        cuota_soportada=Decimal("420.00"),
        prorrata_inicial_pct=Decimal("100"),
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id=transaction_id,
    )


def test_distinct_irpf_and_iva_records_share_only_canonical_acquisition_lineage() -> None:
    asset = _asset()
    iva_record = _iva_record()

    link = verify_optional_iva_linkage(
        asset=asset,
        iva_record=iva_record,
        transaction_replacements={},
    )

    assert link is not None
    assert link.irpf_asset_id == "irpf-computer"
    assert link.iva_record_id == "iva-computer"
    assert link.irpf_asset_revision_id == asset.revision_id
    assert link.canonical_transaction_id == _TRANSACTION_ID
    assert not hasattr(asset, "iva_record_id")
    assert not hasattr(iva_record, "irpf_asset_id")


def test_non_iva_irpf_acquisition_is_supported_without_fabricating_a_register_record() -> None:
    assert (
        verify_optional_iva_linkage(
            asset=_asset(),
            iva_record=None,
            transaction_replacements={},
        )
        is None
    )


def test_linkage_refuses_stale_irpf_evidence_after_transaction_correction() -> None:
    replacement_id = "c" * 64

    with pytest.raises(ActividadAssetValidationError, match="stale"):
        verify_optional_iva_linkage(
            asset=_asset(),
            iva_record=_iva_record(transaction_id=replacement_id),
            transaction_replacements={_TRANSACTION_ID: replacement_id},
        )


def test_linkage_refuses_unrelated_iva_record_without_mutating_either_store() -> None:
    asset = _asset()
    iva_record = _iva_record(transaction_id="d" * 64)

    with pytest.raises(ActividadAssetValidationError, match="same canonical acquisition"):
        verify_optional_iva_linkage(
            asset=asset,
            iva_record=iva_record,
            transaction_replacements={},
        )
    assert asset.acquisition.observed_transaction_id == _TRANSACTION_ID
    assert iva_record.acquisition_ledger_id == "d" * 64
