"""Evidence attachment survives the finalized-modelo write guard.

The documented remedy for an export evidence refusal is ``aeat app ledger
evidence add`` followed by ``aeat app ledger attach``. Because ``verify`` has
already moved the revision to ``VERIFICADO_COMPLETO`` by the time ``export``
raises, the finalized-modelo write guard used to refuse that attach outright,
leaving the operator with no way forward but a destructive whole-unit discard.

These tests pin the narrowed guard: an evidence-only attachment proceeds and
reports the cited revisions as stale, while every value-affecting update — and
any update that smuggles a value change alongside an attachment — still meets
the guard. Real adapters only: real evidence service, real encrypted repository,
real revision fixtures (``aeat-quality-gates``, ``aeat-quality-gates``).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.aggregation import row_fingerprint
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import BucketTransactionRef, derive_transaction_id
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    update_manual_transaction_fields,
)
from ..evidence import PurchaseInvoiceEvidenceService
from ..models import (
    LedgerRemovalBlocker,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ._remove_draft_revision_support import _seed_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "32323232-3232-4232-8232-323232323232"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as runtime:
        yield runtime


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "supplier-invoice.pdf"
    path.write_bytes(b"%PDF-1.4 supplier invoice")
    return path


def _transactions(profile: TestRuntimeProfile) -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)


def _events(profile: TestRuntimeProfile) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=profile.repository)


def _work_units(profile: TestRuntimeProfile) -> WorkUnitCatalogueRepository:
    return WorkUnitCatalogueRepository(objects=profile.repository)


def _revisions(profile: TestRuntimeProfile) -> CalculationRevisionCatalogueRepository:
    return CalculationRevisionCatalogueRepository(objects=profile.repository)


def _mint_evidence_id(profile: TestRuntimeProfile, pdf_file: Path) -> str:
    """Register a PDF through the real evidence service and return its evidence id."""
    service = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=_events(profile),
    )
    return service.add(bucket_id=_BUCKET, source_path=pdf_file).record.evidence_id


def _deductible_expense_row(profile: TestRuntimeProfile, *, idempotency_key: str) -> str:
    """Create the shape the export evidence gate refuses: deductible input IVA, no proof."""
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET,
            booked_date=date(2026, 2, 11),
            amount=Decimal("605.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="material_oficina",
            taxable_base=Decimal("500.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("105.00"),
            idempotency_key=idempotency_key,
        ),
        transaction_repository=_transactions(profile),
        bucket_event_repository=_events(profile),
        occurred_at=datetime(2026, 2, 11, 8, 0, tzinfo=UTC),
    )
    return created.ref.transaction_id


def _finalize_revision_citing(profile: TestRuntimeProfile, transaction_id: str) -> str:
    return _seed_revision_citing_transaction(
        profile.repository,
        transaction_id=transaction_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        period_code="1T",
        bucket_id=_BUCKET,
    )


def test_attach_evidence_proceeds_under_finalized_revision(
    profile: TestRuntimeProfile,
    pdf_file: Path,
) -> None:
    # The dead end itself: verify has finalized the revision, export refused for
    # missing evidence, and the documented remedy must now be reachable.
    transaction_id = _deductible_expense_row(profile, idempotency_key="attach-under-finalized")
    revision_id = _finalize_revision_citing(profile, transaction_id)
    evidence_id = _mint_evidence_id(profile, pdf_file)

    attached = attach_manual_transaction_evidence(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=evidence_id,
        actor="operator-A",
        transaction_repository=_transactions(profile),
        bucket_event_repository=_events(profile),
        work_unit_repository=_work_units(profile),
        calculation_repository=_revisions(profile),
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert attached.transaction.purchase_invoice_evidence_id == evidence_id
    # The citation still resolves: an evidence-only edit re-derives the same id.
    assert attached.transaction.transaction_id == transaction_id
    persisted = _transactions(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id == evidence_id
    # The operator is told which finalized revision now predates its evidence.
    assert [blocker.calculation_revision_id for blocker in attached.stale_finalized_revisions] == [revision_id]
    assert attached.stale_finalized_revisions[0].revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value


def test_attach_leaves_the_finalized_revision_untouched(
    profile: TestRuntimeProfile,
    pdf_file: Path,
) -> None:
    # The guard's subject — the finalized revision — must survive the attach
    # byte-for-byte: casilla values, cited ids, and state are frozen snapshots.
    transaction_id = _deductible_expense_row(profile, idempotency_key="attach-revision-frozen")
    revision_id = _finalize_revision_citing(profile, transaction_id)
    before = _revisions(profile).load().revisions[revision_id]

    attach_manual_transaction_evidence(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=_mint_evidence_id(profile, pdf_file),
        actor="operator-A",
        transaction_repository=_transactions(profile),
        bucket_event_repository=_events(profile),
        work_unit_repository=_work_units(profile),
        calculation_repository=_revisions(profile),
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert _revisions(profile).load().revisions[revision_id] == before


def test_value_affecting_update_still_refuses_under_finalized_revision(
    profile: TestRuntimeProfile,
) -> None:
    # The guard is narrowed, not removed: a classification change to a row a
    # finalized revision cites is still refused.
    transaction_id = _deductible_expense_row(profile, idempotency_key="classify-under-finalized")
    _finalize_revision_citing(profile, transaction_id)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        update_manual_transaction_fields(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
            actor="operator-A",
            source_command="aeat app ledger classify",
            transaction_repository=_transactions(profile),
            bucket_event_repository=_events(profile),
            work_unit_repository=_work_units(profile),
            calculation_repository=_revisions(profile),
        )

    persisted = _transactions(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.business_classification is BusinessClassification.BUSINESS


def test_evidence_attachment_bundled_with_a_value_change_still_refuses(
    profile: TestRuntimeProfile,
    pdf_file: Path,
) -> None:
    # The exemption must not become a bypass: a patch carrying an evidence field
    # AND a value field is a value-affecting update and meets the guard.
    transaction_id = _deductible_expense_row(profile, idempotency_key="attach-plus-value")
    _finalize_revision_citing(profile, transaction_id)
    evidence_id = _mint_evidence_id(profile, pdf_file)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        update_manual_transaction_fields(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(
                purchase_invoice_evidence_id=evidence_id,
                taxable_base=Decimal("400.00"),
            ),
            actor="operator-A",
            source_command="aeat app ledger attach",
            transaction_repository=_transactions(profile),
            bucket_event_repository=_events(profile),
            work_unit_repository=_work_units(profile),
            calculation_repository=_revisions(profile),
            _evidence_authority=True,
        )

    persisted = _transactions(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id is None
    assert persisted.taxable_base == Decimal("500.00")


def test_attach_without_a_finalized_revision_reports_no_stale_revisions(
    profile: TestRuntimeProfile,
    pdf_file: Path,
) -> None:
    # Anti-tautology guard for the advisory: the stale-revision channel is empty
    # when nothing finalized cites the row, so a populated channel in the tests
    # above is a real signal rather than a constant.
    transaction_id = _deductible_expense_row(profile, idempotency_key="attach-no-revision")

    attached = attach_manual_transaction_evidence(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=_mint_evidence_id(profile, pdf_file),
        actor="operator-A",
        transaction_repository=_transactions(profile),
        bucket_event_repository=_events(profile),
        work_unit_repository=_work_units(profile),
        calculation_repository=_revisions(profile),
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert attached.stale_finalized_revisions == ()


def test_stale_revision_advisory_names_no_harmful_recovery_verb(profile: TestRuntimeProfile) -> None:
    # Both plausible recovery verbs were MEASURED against a real stuck profile and
    # both fail: `work calculate` re-derives the same content-addressed revision id
    # and returns the finalized revision untouched, and `work discard` marks the
    # work unit descartado while `work create` re-derives the SAME work-unit id and
    # returns the discarded unit, stranding the target permanently. The advisory
    # must therefore never point at either. Asserted on the notice's structured
    # suggestion, not on localized prose.
    from ....entrypoints.cli.ledger_lifecycle_cli import _stale_finalized_revision_notices

    blocker = LedgerRemovalBlocker(
        work_unit_id="ab" * 32,
        calculation_revision_id="cd" * 32,
        revision_state=CalculationRevisionState.VERIFICADO_COMPLETO.value,
        modelo="130",
        filing_year=2026,
        period="1T",
    )
    transaction_id = _deductible_expense_row(profile, idempotency_key="advisory-shape")
    stored = _transactions(profile).load().get(transaction_id)
    assert stored is not None
    result = ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id=_BUCKET, transaction_id=transaction_id),
        transaction=stored,
        stale_finalized_revisions=(blocker,),
    )

    notices = _stale_finalized_revision_notices(result)
    assert len(notices) == 1
    message = notices[0].message
    assert "work discard" not in message
    assert "work create" not in message
    # `work calculate` may only appear as the thing to link BEFORE, never as the
    # action to run now, so the message must not open with it.
    assert not message.lstrip().startswith("aeat app modelo work calculate")
    # Neither candidate verb works here, so the advisory must carry no executable
    # action at all and must say so in its context rather than leave the absence
    # indistinguishable from an action nobody got round to attaching.
    assert notices[0].action is None
    assert notices[0].context is not None
    assert notices[0].context["reason"] == "finalized_revision_predates_evidence"
    assert notices[0].context["actionability"] == "finalized_revision_has_no_safe_recovery_action"


def test_evidence_fields_are_not_transaction_identity_or_tax_facts(
    profile: TestRuntimeProfile,
    pdf_file: Path,
) -> None:
    # The invariant the exemption rests on, pinned directly against the two
    # canonical contracts. If a future change makes evidence part of the id or of
    # the filing fingerprint, the exemption is no longer sound and this fails.
    transaction_id = _deductible_expense_row(profile, idempotency_key="evidence-not-identity")
    before = _transactions(profile).load().get(transaction_id)
    assert before is not None

    attach_manual_transaction_evidence(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=_mint_evidence_id(profile, pdf_file),
        actor="operator-A",
        transaction_repository=_transactions(profile),
        bucket_event_repository=_events(profile),
        work_unit_repository=_work_units(profile),
        calculation_repository=_revisions(profile),
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )
    after = _transactions(profile).load().get(transaction_id)
    assert after is not None
    assert after.purchase_invoice_evidence_id is not None

    assert derive_transaction_id(after.raw) == derive_transaction_id(before.raw)
    assert row_fingerprint(after) == row_fingerprint(before)

    # Anti-tautology: a genuine tax fact DOES move the fingerprint, so the
    # equality above is a real property of evidence rather than of the helper.
    reclassified = after.model_copy(update={"taxable_base": Decimal("400.00")})
    assert row_fingerprint(reclassified) != row_fingerprint(after)
