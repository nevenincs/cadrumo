"""Export evidence gate coverage for ledger-derived calculation revisions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import IVARegime
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._ledger_filing_snapshot import LedgerFilingSnapshot
from ....domain.modelos._work_unit import derive_work_unit_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .._export import (
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
    _raise_if_ledger_export_evidence_missing,
    export_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)
_TX_ID = "a" * 64


@pytest.fixture
def active_profile(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span("operator"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def _revision(
    *,
    source_transaction_ids: tuple[str, ...],
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-operator",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="gate",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"base": "100.00"},
        binding_overrides={},
        casilla_values={"cuota": Decimal("21.00")},
        source_transaction_ids=source_transaction_ids,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot={"base": "100.00"},
        casilla_values={"cuota": Decimal("21.00")},
        source_transaction_ids=source_transaction_ids,
        ledger_filing_snapshot=ledger_filing_snapshot,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
    )


def test_export_refuses_ledger_revision_without_bundled_evidence_or_reference() -> None:
    revision = _revision(source_transaction_ids=(_TX_ID,))

    with pytest.raises(ModeloExportEvidenceMissingError, match=r"ledger_filing_evidence|ledger_filing_snapshot"):
        _raise_if_ledger_export_evidence_missing(revision)


def test_export_service_refuses_ledger_revision_without_evidence_reference(
    active_profile: None,
    tmp_path: Path,
) -> None:
    revision = _revision(source_transaction_ids=(_TX_ID,))
    repository = CalculationRevisionCatalogueRepository()
    repository.save(upsert_calculation_revision(repository.load(), revision))
    output_path = tmp_path / "modelo-303.txt"

    with pytest.raises(ModeloExportEvidenceMissingError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=TaxpayerProfile(tax_id="taxpayerdefault", iva_regime=IVARegime.GENERAL),
            calculation_repository=repository,
        )

    assert not output_path.exists()


def test_export_allows_non_ledger_revision_without_evidence() -> None:
    revision = _revision(source_transaction_ids=())

    _raise_if_ledger_export_evidence_missing(revision)


def test_export_allows_ledger_revision_with_snapshot_reference() -> None:
    revision = _revision(
        source_transaction_ids=(_TX_ID,),
        ledger_filing_snapshot=LedgerFilingSnapshot(
            snapshot_fingerprint="f" * 64,
            captured_at=_NOW,
        ),
    )

    _raise_if_ledger_export_evidence_missing(revision)
