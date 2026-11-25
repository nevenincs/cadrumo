"""The verify-time drift gate refuses a draft whose contributor changed a V3 admission fact.

``investment_asset_id`` and ``counterparty_identification_state`` decide whether a
row is admitted (the bienes de inversion reconciliation and the intra-community
identification check) without moving any amount. A BORRADOR row stays editable,
so an edit to either after calculation must block verify, or the draft is sealed
on values computed under the old admission outcome. A draft anchored under
field-set version 2 keeps being compared under version 2.

The operator-stated accrual date is the V7 fact: an anchor older than version 7
cannot see a date nothing could write when it was sealed, so the gate reports
an anchored row that now carries one, while the field-set comparison itself
keeps its old answer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import EUMemberState
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    row_fingerprint,
)
from ...aggregation.ledger_membership import LedgerSourceMembership
from ...aggregation.tests.ledger_source_mesh_support import InMemoryTransactionCatalogueRepository
from ..ledger_drift_gate import ledger_drift_findings, undetermined_mixed_use_contributor_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "31313131-3131-4131-8131-313131313131"
_YEAR = filing_year_envelope().horizon
_AT = datetime(_YEAR, 4, 20, 12, 0, tzinfo=UTC)
_DRIFT_KEY = "application.modelo.findings.ledger_snapshot_drift_changed"


def _purchase() -> Transaction:
    booked = date(_YEAR, 2, 10)
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="admission-facts-probe",
                booked_date=booked,
                value_date=booked,
                amount=Decimal("242.00"),
                currency="EUR",
                counterparty="Proveedor sintetico",
                description="admission facts probe",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=_AT,
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "material_oficina",
            "taxable_base": Decimal("200.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("42.00"),
            "classified_at": _AT,
            "classified_by": "manual",
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator="invoice:admission-facts-probe",
                evidence_digest="a" * 64,
            ),
        },
    )


def _draft(contributor: Transaction, anchor: LedgerFilingSnapshot) -> tuple[WorkUnit, CalculationRevision]:
    snapshot = published_snapshot("303", filing_year=_YEAR, period="1T")
    period = Period.from_year_and_code(_YEAR, "1T")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET,
            modelo="303",
            filing_year=_YEAR,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("303"),
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"303-{_YEAR}-1T",
        created_at=_AT,
        updated_at=_AT,
    )
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
            source_transaction_ids=(contributor.transaction_id,),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=_AT,
        updated_at=_AT,
        filing_instance_evidence=None,
        source_provenance=(),
        source_transaction_ids=(contributor.transaction_id,),
        ledger_filing_snapshot=anchor,
    )
    return work_unit, revision


def _current_anchor(contributor: Transaction) -> LedgerFilingSnapshot:
    return compute_ledger_filing_snapshot(
        source_transaction_ids=[contributor.transaction_id],
        catalogue=TransactionCatalogue.from_transactions([contributor]),
        captured_at=_AT,
    )


def _anchor_sealed_under_v2(contributor: Transaction) -> LedgerFilingSnapshot:
    live = _current_anchor(contributor)
    return live.model_copy(
        update={
            "fingerprint_field_set_version": 2,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(contributor, field_set_version=2)})
                for row in live.rows
            ),
        },
    )


def _anchor_sealed_under(contributor: Transaction, version: int) -> LedgerFilingSnapshot:
    live = _current_anchor(contributor)
    return live.model_copy(
        update={
            "fingerprint_field_set_version": version,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(contributor, field_set_version=version)})
                for row in live.rows
            ),
        },
    )


def _gate(draft: tuple[WorkUnit, CalculationRevision], live: Transaction) -> list[ModeloVerificationFinding]:
    work_unit, revision = draft
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(TransactionCatalogue.from_transactions([live]))
    return ledger_drift_findings(
        target=revision,
        work_unit=work_unit,
        transaction_repository=repository,
        current_membership=LedgerSourceMembership(observed_transaction_ids=(live.transaction_id,)),
    )


_ADMISSION_EDITS = pytest.mark.parametrize(
    "update",
    [
        {"investment_asset_id": "bien-inversion-0001"},
        {"counterparty_identification_state": EUMemberState.from_registry("FR")},
    ],
    ids=["investment_asset_id", "counterparty_identification_state"],
)


def test_an_unedited_contributor_leaves_the_draft_current() -> None:
    purchase = _purchase()
    assert _gate(_draft(purchase, _current_anchor(purchase)), purchase) == []


@_ADMISSION_EDITS
def test_an_admission_fact_edit_after_calculation_blocks_a_v3_anchored_draft(update: dict[str, object]) -> None:
    before = _purchase()
    after = before.model_copy(update=update)

    (finding,) = _gate(_draft(before, _current_anchor(before)), after)

    assert finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert finding.message_locale_key == _DRIFT_KEY
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["anchored"] is True
    assert finding.message_facts["changed_count"] == 1
    assert finding.message_facts["removed_count"] == 0
    assert finding.message_facts["added_count"] == 0


@_ADMISSION_EDITS
def test_a_v2_anchored_draft_is_still_compared_under_v2(update: dict[str, object]) -> None:
    """No rehash and no false drift: the V2 anchor cannot see the V3 facts, by design."""
    before = _purchase()
    after = before.model_copy(update=update)
    assert _gate(_draft(before, _anchor_sealed_under_v2(before)), after) == []


_STATED_ACCRUAL = date(_YEAR, 3, 30)


@pytest.mark.parametrize("version", [2, 5, 6])
def test_an_accrual_date_written_after_an_older_anchor_is_reported_by_the_gate_only(version: int) -> None:
    """The older field set stays quiet on its own; the gate names the row it could not see."""
    before = _purchase()
    after = before.model_copy(update={"accrual_date": _STATED_ACCRUAL})
    anchor = _anchor_sealed_under(before, version)

    assert evaluate_ledger_filing_staleness(anchor, TransactionCatalogue.from_transactions([after])).is_stale is False

    (finding,) = _gate(_draft(before, anchor), after)
    assert finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert finding.message_locale_key == _DRIFT_KEY
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["changed_count"] == 1


def test_a_v6_anchored_row_without_an_accrual_date_stays_current() -> None:
    before = _purchase()
    assert _gate(_draft(before, _anchor_sealed_under(before, 6)), before) == []


def test_an_accrual_date_stated_before_a_current_anchor_is_not_drift_and_a_change_is() -> None:
    stated = _purchase().model_copy(update={"accrual_date": _STATED_ACCRUAL})
    draft = _draft(stated, _current_anchor(stated))
    assert _gate(draft, stated) == []

    (finding,) = _gate(draft, stated.model_copy(update={"accrual_date": date(_YEAR, 4, 2)}))
    assert finding.message_facts["changed_count"] == 1


def _undetermined_finding(
    draft: tuple[WorkUnit, CalculationRevision], live: Transaction, operation: PinnedAuthorityOperation
) -> ModeloVerificationFinding | None:
    work_unit, revision = draft
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(TransactionCatalogue.from_transactions([live]))
    return undetermined_mixed_use_contributor_finding(
        target=revision,
        work_unit=work_unit,
        transaction_repository=repository,
        operation=operation,
    )


def _uncategorized_mixed(purchase: Transaction) -> Transaction:
    return purchase.model_copy(
        update={
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.50"),
            "category_id": None,
        },
    )


def test_a_stored_draft_that_counted_an_uncategorized_mixed_row_warns_and_stays_as_stored(
    *, operation: PinnedAuthorityOperation
) -> None:
    row = _uncategorized_mixed(_purchase())
    draft = _draft(row, _current_anchor(row))
    assert _gate(draft, row) == []
    finding = _undetermined_finding(draft, row, operation)
    assert finding is not None
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.message_facts["rows"] == 1
    assert draft[1].casilla_values == {}


@pytest.mark.parametrize(
    "update",
    [{"category_id": "vehiculo_combustible"}, {"direction": TransactionDirection.INCOMING}],
    ids=["categorized", "income"],
)
def test_a_contributor_whose_treatment_is_known_does_not_warn(
    update: dict[str, object], *, operation: PinnedAuthorityOperation
) -> None:
    row = _uncategorized_mixed(_purchase()).model_copy(update=update)
    assert _undetermined_finding(_draft(row, _current_anchor(row)), row, operation) is None


def test_a_row_that_is_not_a_contributor_does_not_warn(*, operation: PinnedAuthorityOperation) -> None:
    row = _uncategorized_mixed(_purchase())
    work_unit, revision = _draft(row, _current_anchor(row))
    elsewhere = revision.model_copy(update={"source_transaction_ids": ("a" * 64,)})
    assert _undetermined_finding((work_unit, elsewhere), row, operation) is None
