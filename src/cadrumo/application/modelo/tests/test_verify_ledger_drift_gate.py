"""Real-behavior tests for the verify-time ledger-drift gate on BORRADOR drafts.

The defect these gate: verify targets the work unit's current calculation
revision, and the deductible-evidence gate reads the LIVE ledger while the
casilla values come from the STORED revision. So an operator who hits the
blocking deductible-evidence finding, reclassifies the row to drop the
deduction, and re-runs verify WITHOUT recalculating is verifying a stale draft.
The evidence gate sees the row is no longer deductible and raises nothing; the
grant then freezes an evidence bundle over casilla values that still assert the
deduction. That is an over-declaration, and the wrong order was never refused.

The gate's anchor is the ledger row fingerprint, and its whole viability rests
on one discrimination it must make: a reclassify moves the fingerprint and an
evidence attach does not. That is not assumed here, it is measured through the
real ledger paths, because catching an attach would break the recovery path the
deductible-evidence promotion depends on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.aggregation import row_fingerprint
from ....domain.modelos.verification_report import ModeloVerificationFindingSeverity, VerificationCompletenessStatus, VerificationReport
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import Transaction
from ....tests.env_scope import ready_clave_settings
from ....tests.secure_sql import isolated_runtime_profile
from ...ledger.actions_manual import attach_manual_transaction_evidence, update_manual_transaction_fields
from ...ledger.evidence import PurchaseInvoiceEvidenceService
from ...ledger.models import ManualLedgerTransactionPatch
from .._verification_actions import verify_modelo_revision
from .test_modelo_303_deductible_evidence_gate import (
    _BUCKET_ID,
    _TAX_ID,
    _calculate_irene_revision,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
    TransactionCatalogueRepository,
]

_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def _row(tx_repo: TransactionCatalogueRepository, transaction_id: str) -> Transaction:
    """Return one live ledger row, refusing the optional the catalogue returns."""
    row = tx_repo.load().get(transaction_id)
    assert row is not None
    return row


def _write_invoice(tmp_path: Path) -> Path:
    invoice = tmp_path / "supplier-invoice.pdf"
    invoice.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
    return invoice


def test_attaching_evidence_does_not_move_the_row_fingerprint(tmp_path: Path) -> None:
    """Attach is value-neutral, measured rather than assumed.

    The drift gate anchors on this fingerprint, so if an attach moved it the
    gate would refuse the very recovery the deductible-evidence promotion tells
    the operator to perform. The fingerprint covers tax facts only, but
    ``lifecycle_state`` IS one of them, so whether the real attach path
    transitions it is a behavioural question that reading the field list cannot
    settle. This drives the production attach path end to end.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _revision, _sale, purchase, _wu, _cr, _fr, _vr, event_repo, tx_repo = _calculate_irene_revision(
            profile.repository,
        )
        before = row_fingerprint(_row(tx_repo, purchase.transaction_id))

        evidence = PurchaseInvoiceEvidenceService(
            settings=profile.settings,
            bucket_event_repository=event_repo,
        ).add(bucket_id=_BUCKET_ID, source_path=_write_invoice(tmp_path))
        attach_manual_transaction_evidence(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            purchase_invoice_evidence_id=evidence.record.evidence_id,
            actor="operator",
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            occurred_at=_AT,
        )

        attached = tx_repo.load().get(purchase.transaction_id)
        assert attached is not None
        # The attach really happened; the fingerprint is unmoved anyway.
        assert attached.purchase_invoice_evidence_id == evidence.record.evidence_id
        assert row_fingerprint(attached) == before


def test_reclassifying_a_row_moves_the_row_fingerprint(tmp_path: Path) -> None:
    """Reclassify is value-changing, measured through the real update path.

    The counterpart to the test above: the anchor is only useful if it moves
    for the change that invalidates the stored casilla values. Together the two
    establish the discrimination the gate needs — catch the reclassify, ignore
    the attach.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _revision, _sale, purchase, _wu, _cr, _fr, _vr, event_repo, tx_repo = _calculate_irene_revision(
            profile.repository,
        )
        before = row_fingerprint(_row(tx_repo, purchase.transaction_id))

        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
            actor="operator",
            source_command="test",
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            occurred_at=_AT,
        )

        reclassified = tx_repo.load().get(purchase.transaction_id)
        assert reclassified is not None
        assert row_fingerprint(reclassified) != before


def _verify(revision_id: str, repos: _Repos) -> VerificationReport:
    wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = repos
    return verify_modelo_revision(
        revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings(_TAX_ID),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        verification_repository=vr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_AT,
    )


def test_reclassifying_then_verifying_the_stale_draft_is_refused(tmp_path: Path) -> None:
    """The exact operator path the defect made reachable.

    Hit the blocking deductible-evidence finding, reclassify the row to drop
    the deduction rather than attaching an invoice, then re-verify WITHOUT
    recalculating. Before the gate this granted: the evidence gate reads the
    live ledger and saw nothing deductible left to complain about, while the
    casilla values still asserted the deduction, so the grant froze an evidence
    bundle over an over-declaration.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
            _calculate_irene_revision(profile.repository)
        )
        repos: _Repos = (wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo)

        blocked = _verify(revision.calculation_revision_id, repos)
        assert blocked.granted_verificado_completo is False

        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
            actor="operator",
            source_command="test",
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            occurred_at=_AT,
        )

        after_reclassify = _verify(revision.calculation_revision_id, repos)

        assert after_reclassify.granted_verificado_completo is False
        assert after_reclassify.completeness_status is VerificationCompletenessStatus.BLOCKED
        # The refusal is the drift gate, not a leftover evidence finding: the
        # deductible gap is gone from the live ledger now.
        blocking = [
            finding
            for finding in after_reclassify.findings
            if finding.severity is ModeloVerificationFindingSeverity.BLOCKING
        ]
        assert blocking, "a reclassified-away deduction must not leave the stale draft grantable"
        # The refusal resolves the operator's position instead of restating it.
        drift = next(
            finding
            for finding in blocking
            if finding.message_locale_key == "application.modelo.findings.ledger_snapshot_drift"
        )
        assert dict(drift.message_facts) == {
            "anchored": True,
            "changed_count": 1,
            "filing_year": 2026,
            "modelo": "303",
            "period": "1T",
            "removed_count": 0,
        }
        assert "next_action" not in drift.model_dump(mode="json")
        assert "ley-37-1992:art-164" in drift.legal_refs

        # Nothing was frozen: the draft is still a draft, with no evidence bundle.
        settled = cr_repo.load().get(revision.calculation_revision_id)
        assert settled is not None
        assert settled.state is CalculationRevisionState.BORRADOR
        assert settled.ledger_filing_evidence is None


def test_an_untouched_draft_still_verifies_cleanly(tmp_path: Path) -> None:
    """The gate does not fire when nothing drifted.

    Guards the obvious over-block: if the anchor were recorded wrongly, or the
    comparison were against the wrong rows, every ledger-derived verify would
    refuse. Here the invoice is attached and nothing else moves, so the verify
    must reach its grant exactly as it did before the gate existed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
            _calculate_irene_revision(profile.repository)
        )
        repos: _Repos = (wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo)

        evidence = PurchaseInvoiceEvidenceService(
            settings=profile.settings,
            bucket_event_repository=event_repo,
        ).add(bucket_id=_BUCKET_ID, source_path=_write_invoice(tmp_path))
        attach_manual_transaction_evidence(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            purchase_invoice_evidence_id=evidence.record.evidence_id,
            actor="operator",
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            occurred_at=_AT,
        )

        granted = _verify(revision.calculation_revision_id, repos)

        assert granted.granted_verificado_completo is True
        assert granted.completeness_status is VerificationCompletenessStatus.COMPLETE


def test_a_ledger_derived_draft_carries_the_anchor_the_gate_compares(tmp_path: Path) -> None:
    """Calculate pins the ledger state its values came from.

    Without this the gate has nothing to compare for a draft, because the
    snapshot is otherwise captured only on a granted verify — precisely the
    drafts that need guarding.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        revision, sale, purchase, _wu, _cr, _fr, _vr, _ev, tx_repo = _calculate_irene_revision(profile.repository)

        anchor = revision.ledger_filing_snapshot
        assert anchor is not None
        assert {row.transaction_id for row in anchor.rows} == {sale.transaction_id, purchase.transaction_id}
        assert {row.fingerprint for row in anchor.rows} == {
            row_fingerprint(_row(tx_repo, sale.transaction_id)),
            row_fingerprint(_row(tx_repo, purchase.transaction_id)),
        }


def test_the_drift_anchor_does_not_move_any_revision_id() -> None:
    """The anchor is excluded from the content-addressed revision identity.

    Writing a field onto every ledger-derived draft is one refactor away from
    being a repository-wide identity event: if the anchor participated in
    ``derive_calculation_revision_id``, every revision id would move. It does
    not, and this pins that as an assertion rather than an inherited belief —
    two ids derived from identical inputs must be equal, and the deriver must
    not accept the anchor at all.
    """
    import inspect

    from ....domain.modelos.calculation_revision import derive_calculation_revision_id

    parameters = inspect.signature(derive_calculation_revision_id).parameters
    assert "ledger_filing_snapshot" not in parameters

    # The runtime enforcement is the model's own self-validation: constructing a
    # CalculationRevision whose id differs from the derived id raises. The
    # sibling export test builds one that carries no anchor and validates, and
    # the drift-gate tests build drafts that DO carry one and validate equally —
    # which is the property holding in practice, not just in the signature.
    assert derive_calculation_revision_id(
        work_unit_id="a1b2c3d4" * 8,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=("beef1234" * 8,),
        filing_instance_evidence=None,
        source_provenance=(),
    ) == derive_calculation_revision_id(
        work_unit_id="a1b2c3d4" * 8,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=("beef1234" * 8,),
        filing_instance_evidence=None,
        source_provenance=(),
    )
