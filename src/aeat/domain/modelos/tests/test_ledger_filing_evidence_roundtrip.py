"""Encrypted roundtrip coverage for ledger filing evidence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests.secure_sql import isolated_runtime_profile
from .._calculation_repository import CalculationRevisionCatalogueRepository
from .._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .._ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry
from .._work_unit import derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 6, 3, 14, 0, tzinfo=UTC)
_TX_ID = "c" * 64


@pytest.fixture
def objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile.repository


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
                iva_category="domestic_general_21",
                category_id="office-supplies",
                irpf_category="professional-services",
                counterparty_eu_member_state="DE",
                fx_rate=Decimal("1.08"),
                value_in_eur=Decimal("112.04"),
                lifecycle_state="active",
                counterparty="Proveedor SL",
                description="Compra material oficina",
                purchase_invoice_evidence_id="purchase-evidence-1",
                attachment_ids=("attachment-1",),
                document_link_ids=("drive-doc-1",),
                legal_refs=("liva-art-99",),
                source_refs=("boe-a-2026-1",),
            ),
        ),
        manual_entries=(
            ManualFactBasisEntry(
                casilla="00501",
                value="140000.00",
                kind="casilla_input",
                note="resultado contable",
            ),
        ),
        captured_at=_NOW,
    )


def _revision(evidence: LedgerFilingEvidence | None) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-a",
        modelo="303",
        filing_year=2026,
        period="1T",
        revision_id="2009-y-siguientes",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"00501": "140000.00"},
        binding_overrides={},
        casilla_values={"00501": Decimal("140000.00")},
        source_transaction_ids=(_TX_ID,),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot={"00501": "140000.00"},
        source_transaction_ids=(_TX_ID,),
        casilla_values={"00501": Decimal("140000.00")},
        ledger_filing_evidence=evidence,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
    )


def test_ledger_filing_evidence_roundtrips_through_encrypted_revision(objects: SecureObjectRepository) -> None:
    evidence = _evidence()
    original = _revision(evidence)
    repository = CalculationRevisionCatalogueRepository(objects=objects)

    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    loaded = CalculationRevisionCatalogueRepository(objects=objects).load().get(original.calculation_revision_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.ledger_filing_evidence == evidence
    # Narrow ledger_filing_evidence to non-None for safe attribute access.
    assert loaded.ledger_filing_evidence is not None
    assert loaded.ledger_filing_evidence.rows[0].document_link_ids == ("drive-doc-1",)
    assert loaded.ledger_filing_evidence.manual_entries[0].note == "resultado contable"

    stripped = original.model_copy(update={"ledger_filing_evidence": None})
    assert stripped != original


def test_ledger_evidence_negative_amount_payload_rejected_at_load(objects: SecureObjectRepository) -> None:
    """Anti-tautology proof: a persisted evidence row with a negative amount is refused.

    Persist a valid non-negative-magnitude evidence row, then surgically rewrite
    the on-disk ``amount`` to a negative value and re-save the encrypted record.
    The load path MUST reject the mutated payload because
    :class:`LedgerEvidenceRow` enforces the non-negative gate on rehydration. If
    the load silently admitted the negative amount, the magnitude gate would be
    tautological and every evidence roundtrip in the suite would be suspect.
    """

    import json as _json

    from pydantic import ValidationError

    from ....adapters.persistence.storage import SensitivityClass
    from .._calculation_repository import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
    )

    original = _revision(_evidence())
    repository = CalculationRevisionCatalogueRepository(objects=objects)
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    record = objects.load(
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
    objects.save(
        namespace=_CALCULATION_NAMESPACE,
        object_key=_CALCULATION_OBJECT_KEY,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=_json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(ValidationError):
        CalculationRevisionCatalogueRepository(objects=objects).load()
