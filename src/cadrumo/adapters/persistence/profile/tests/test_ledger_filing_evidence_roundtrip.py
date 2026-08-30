"""Encrypted roundtrip coverage for ledger filing evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.period import Period
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry
from .....domain.modelos.work_unit import derive_work_unit_id
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....tests import general_m303_filing_evidence
from .....tests.secure_objects_fixture import secure_objects
from ...storage.sql import SecureObjectRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 6, 3, 14, 0, tzinfo=UTC)
_BUCKET_ID = "30330300-0000-4000-8000-000000000501"
_TX_ID = "c" * 64


_EVIDENCE_CASILLA: CasillaId = validated_casilla_id("00501")
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-2025-form",)

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _evidence() -> LedgerFilingEvidence:
    return LedgerFilingEvidence(
        snapshot_fingerprint="b" * 64,
        rows=(
            LedgerEvidenceRow(
                transaction_id=_TX_ID,
                fingerprint="a" * 64,
                booked_date="2026-01-31",
                value_date="2026-02-01",
                amount=Decimal("121.00"),
                currency="EUR",
                direction="outgoing",
                business_classification="mixed",
                business_pct=Decimal("0.75"),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
                iva_category="domestic_general",
                category_id="office-supplies",
                irpf_category="professional-services",
                counterparty_country="DE",
                fx_rate=Decimal("1.08"),
                value_in_eur=Decimal("112.04"),
                lifecycle_state="active",
                counterparty="Proveedor SL",
                description="Compra material oficina",
                purchase_invoice_evidence_id="purchase-evidence-1",
                invoice_id="invoice-1",
                attachment_ids=("attachment-1",),
                document_link_ids=("drive-doc-1",),
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        manual_entries=(
            ManualFactBasisEntry(
                casilla_id=_EVIDENCE_CASILLA,
                value="140000.00",
                kind="casilla_input",
                note="resultado contable",
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        captured_at=_NOW,
    )


def _revision(evidence: LedgerFilingEvidence | None) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2022",
    )
    filing_instance_evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "1T"), reference="test:ledger-filing-evidence-roundtrip"
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_EVIDENCE_CASILLA: "140000.00"},
        binding_overrides={},
        casilla_values={_EVIDENCE_CASILLA: Decimal("140000.00")},
        source_transaction_ids=(_TX_ID,),
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_EVIDENCE_CASILLA: "140000.00"},
        source_transaction_ids=(_TX_ID,),
        casilla_values={_EVIDENCE_CASILLA: Decimal("140000.00")},
        observations=(
            CasillaObservation(
                casilla_id=_EVIDENCE_CASILLA,
                value=Decimal("140000.00"),
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        ledger_filing_evidence=evidence,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def test_ledger_filing_evidence_roundtrips_through_encrypted_revision(secure_objects: SecureObjectRepository) -> None:
    evidence = _evidence()
    original = _revision(evidence)
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)

    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    loaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(original.calculation_revision_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.ledger_filing_evidence == evidence
    # Narrow ledger_filing_evidence to non-None for safe attribute access.
    assert loaded.ledger_filing_evidence is not None
    assert loaded.ledger_filing_evidence.rows[0].document_link_ids == ("drive-doc-1",)
    assert loaded.ledger_filing_evidence.manual_entries[0].note == "resultado contable"

    stripped = original.model_copy(update={"ledger_filing_evidence": None})
    assert stripped != original


def test_ledger_evidence_negative_amount_payload_rejected_at_load(secure_objects: SecureObjectRepository) -> None:
    """Anti-tautology proof: a persisted evidence row with a negative amount is refused.

    Persist a valid non-negative-magnitude evidence row, then surgically rewrite
    the on-disk ``amount`` to a negative value and re-save the encrypted record.
    The load path MUST reject the mutated payload because
    :class:`LedgerEvidenceRow` enforces the non-negative gate on rehydration. If
    the load silently admitted the negative amount, the magnitude gate would be
    tautological and every evidence roundtrip in the suite would be suspect.
    """

    import json as _json

    from ...storage import SensitivityClass
    from ..modelos_calculation import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
    )

    original = _revision(_evidence())
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    record = secure_objects.load(
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_CALCULATION_CATALOGUE_VERSION,
    )
    assert record is not None
    envelope = _json.loads(record.payload.decode("utf-8"))
    revision_dict = envelope["payload"]["revisions"][original.calculation_revision_id]
    row = revision_dict["ledger_filing_evidence"]["rows"][0]
    assert row["amount"] == "121.00", "fixture must serialise the magnitude for this proof to be meaningful"
    row["amount"] = "-121.00"
    secure_objects.save(
        namespace=_CALCULATION_NAMESPACE,
        object_key=_CALCULATION_OBJECT_KEY,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=_json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(ValidationError):
        CalculationRevisionCatalogueRepository(objects=secure_objects).load()


def test_ledger_evidence_malformed_identity_payload_rejected_at_load(secure_objects: SecureObjectRepository) -> None:
    """Persisted evidence cannot rehydrate a non-canonical contributor identity."""
    import json as _json

    from ...storage import SensitivityClass
    from ..modelos_calculation import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
    )

    original = _revision(_evidence())
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    record = secure_objects.load(
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_CALCULATION_CATALOGUE_VERSION,
    )
    assert record is not None
    envelope = _json.loads(record.payload.decode("utf-8"))
    row = envelope["payload"]["revisions"][original.calculation_revision_id]["ledger_filing_evidence"]["rows"][0]
    row["transaction_id"] = "not-a-content-address"
    secure_objects.save(
        namespace=_CALCULATION_NAMESPACE,
        object_key=_CALCULATION_OBJECT_KEY,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=_json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(ValidationError, match="transaction_id"):
        CalculationRevisionCatalogueRepository(objects=secure_objects).load()
