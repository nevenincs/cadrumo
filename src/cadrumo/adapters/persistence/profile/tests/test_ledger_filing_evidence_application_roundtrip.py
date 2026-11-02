"""Persistence-backed ledger filing evidence roundtrip.

The encrypted CalculationRevision boundary is exercised at the profile
persistence adapter. Pure evidence projection and coverage policy remain in
the inward application aggregation tests.
"""

from __future__ import annotations

import pytest

from cadrumo.application.aggregation.tests.ledger_filing_evidence_support import (
    FILING_EVIDENCE_NOW,
    filing_evidence_transaction,
)

from .....application.aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from .....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.ledger_filing_snapshot import LedgerFilingEvidence, ManualFactBasisEntry
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from .....domain.transactions.models import TransactionCatalogue
from ...storage.sql.secure_objects import SecureObjectRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from .published_authority_support import published_authority_operation
from .verified_ledger_revision_support import verified_303_ledger_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "13131313-1313-4313-8313-131313131313"
_MANUAL_FACT_CASILLA: CasillaId = validated_casilla_id("00501")
_REVISION_CASILLA: CasillaId = validated_casilla_id("01")
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-2025-form",)


def _seed_parent_work_unit(secure_objects: SecureObjectRepository, *, revision_id: str) -> str:
    """Persist the WorkUnit a saved revision must belong to and return its id."""
    period = Period.from_year_and_code(2025, "1T")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name="303-2025-1T",
        created_at=FILING_EVIDENCE_NOW,
        updated_at=FILING_EVIDENCE_NOW,
    )
    WorkUnitCatalogueRepository(objects=secure_objects).save(
        WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
    )
    return work_unit.work_unit_id


def _revision_with_evidence(
    *,
    evidence: LedgerFilingEvidence,
    tx_id: str,
    operation: PinnedAuthorityOperation,
    secure_objects: SecureObjectRepository,
) -> CalculationRevision:
    period = Period.from_year_and_code(2025, "1T")
    registry_snapshot_ref = published_authority_operation().snapshot("303", filing_year=2025, period="1T").snapshot_ref
    work_unit_id = _seed_parent_work_unit(secure_objects, revision_id=registry_snapshot_ref.revision_id)
    filing_instance_evidence = general_m303_filing_evidence(
        period, reference="test:ledger-filing-evidence", operation=operation
    )
    return verified_303_ledger_revision(
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        filing_instance_evidence=filing_instance_evidence,
        tx_id=tx_id,
        period=period,
        at=FILING_EVIDENCE_NOW,
        ledger_filing_evidence=evidence,
    )


def test_evidence_roundtrips_through_encrypted_revision(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    txn = filing_evidence_transaction()
    catalogue = TransactionCatalogue.from_transactions((txn,))
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        captured_at=FILING_EVIDENCE_NOW,
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=FILING_EVIDENCE_NOW,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        manual_entries=(
            ManualFactBasisEntry(
                casilla_id=_MANUAL_FACT_CASILLA,
                value="140000.00",
                note="resultado contable",
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
    )
    original = _revision_with_evidence(
        evidence=evidence,
        tx_id=txn.transaction_id,
        operation=operation,
        secure_objects=secure_objects,
    )
    repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repo.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    loaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load()
    loaded_revision = loaded.revisions[original.calculation_revision_id]
    # Strict equality across the encrypted boundary: the bundled evidence survives.
    assert loaded_revision == original
    assert loaded_revision.ledger_filing_evidence == evidence
    loaded_evidence = loaded_revision.ledger_filing_evidence
    assert loaded_evidence is not None
    assert loaded_evidence.rows[0].iva_category == "domestic_general"

    # Anti-tautology: a revision with evidence must NOT equal the same revision
    # with its evidence stripped — the field carries real state.
    stripped = original.model_copy(update={"ledger_filing_evidence": None})
    assert stripped != original
