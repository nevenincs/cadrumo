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

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from cadrumo.application.aggregation.ledger_filing_snapshot import row_fingerprint
from cadrumo.application.aggregation.ledger_membership import LedgerSourceMembership, query_ledger_membership
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    update_manual_transaction_fields,
)
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from cadrumo.application.modelo.profile_readiness_gate import load_modelo_work_profile
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.application.modelo.verification_repository_ports import VerificationRepositoryBundle
from cadrumo.application.modelo.work_form_models import ModeloWorkForm
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
)
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction
from cadrumo.entrypoints.adapter_composition import (
    build_ledger_evidence_ports,
    build_ledger_membership_ports,
    build_verification_repository_bundle,
)
from cadrumo.entrypoints.tests.profile_persistence.ledger_drift_support import (
    BUCKET_ID,
    TAX_ID,
    calculate_irene_revision,
    workflow_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.tests.env_scope import ready_clave_settings

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
    TransactionCatalogueRepository,
]

_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


@contextmanager
def _ledger_ports(
    objects: SecureObjectRepository,
    tx_repo: TransactionCatalogueRepository,
    event_repo: BucketEventHistoryRepository,
) -> Iterator[LedgerActionPorts]:
    """Yield canonical ledger ports over the isolated repositories."""
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=objects,
        transaction_repository=tx_repo,
        bucket_event_repository=event_repo,
    ) as ports:
        yield ports


def _verification_ports(repos: _Repos) -> VerificationRepositoryBundle:
    """Compose the complete verification bundle over the isolated repositories."""
    wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = repos
    return replace(
        build_verification_repository_bundle(BUCKET_ID),
        work_unit=wu_repo,
        calculation=cr_repo,
        filing=filing_repo,
        verification=vr_repo,
        bucket_event=event_repo,
        transaction=tx_repo,
        ledger_membership_ports=build_ledger_membership_ports(bucket_id=BUCKET_ID, transaction_repository=tx_repo),
    )


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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            _revision, _sale, purchase, _wu, _cr, _fr, _vr, event_repo, tx_repo = calculate_irene_revision(
                profile.repository, operation=operation
            )
        before = row_fingerprint(_row(tx_repo, purchase.transaction_id))

        evidence = PurchaseInvoiceEvidenceService(
            ports=build_ledger_evidence_ports(bucket_id=BUCKET_ID),
        ).add(bucket_id=BUCKET_ID, source_path=_write_invoice(tmp_path))
        with _ledger_ports(profile.repository, tx_repo, event_repo) as ports:
            attach_manual_transaction_evidence(
                bucket_id=BUCKET_ID,
                transaction_id=purchase.transaction_id,
                purchase_invoice_evidence_id=evidence.record.evidence_id,
                actor="operator",
                ports=ports,
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            _revision, _sale, purchase, _wu, _cr, _fr, _vr, event_repo, tx_repo = calculate_irene_revision(
                profile.repository, operation=operation
            )
        before = row_fingerprint(_row(tx_repo, purchase.transaction_id))

        with _ledger_ports(profile.repository, tx_repo, event_repo) as ports:
            update_manual_transaction_fields(
                bucket_id=BUCKET_ID,
                transaction_id=purchase.transaction_id,
                patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
                actor="operator",
                source_command="test",
                ports=ports,
                occurred_at=_AT,
            )

        reclassified = tx_repo.load().get(purchase.transaction_id)
        assert reclassified is not None
        assert row_fingerprint(reclassified) != before


def _form(repos: _Repos) -> ModeloWorkForm:
    """The declaration's editor form, read from the same storage the check wrote to."""
    work_units, calculations, _filings, reports, _events, _transactions = repos
    (unit,) = work_units.load().values()
    with bundled_indexed_authority().operation() as operation:
        return load_modelo_work_form(
            unit.bucket_id,
            unit.modelo,
            unit.filing_year,
            unit.period,
            operation=operation,
            work_unit_repository=work_units,
            calculation_repository=calculations,
            verification_repository=reports,
            admission=None,
            language=OutputLanguage.EN,
        ).form


def _verify(
    revision_id: str,
    repos: _Repos,
    *,
    verification_ports: VerificationRepositoryBundle | None = None,
) -> VerificationReport:
    with bundled_indexed_authority().operation() as operation:
        return verify_modelo_revision(
            revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(TAX_ID),
            verification_repositories=verification_ports or _verification_ports(repos),
            clock=_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
                calculate_irene_revision(profile.repository, operation=operation)
            )
        repos: _Repos = (wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo)

        blocked = _verify(revision.calculation_revision_id, repos)
        assert blocked.granted_verificado_completo is False

        with _ledger_ports(profile.repository, tx_repo, event_repo) as ports:
            update_manual_transaction_fields(
                bucket_id=BUCKET_ID,
                transaction_id=purchase.transaction_id,
                patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
                actor="operator",
                source_command="test",
                ports=ports,
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
        drift = next(finding for finding in blocking if finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION)
        # Only entries changed, so the sentence names only them.
        assert drift.message_locale_key == "application.modelo.findings.ledger_snapshot_drift_changed"
        assert dict(drift.message_facts) == {
            "anchored": True,
            "changed_count": 1,
            "filing_year": 2026,
            "modelo": "303",
            "period": "1T",
            "removed_count": 0,
            "added_count": 0,
            "membership_available": True,
        }
        assert "next_action" not in drift.model_dump(mode="json")
        assert "ley-37-1992:art-164" in drift.legal_refs

        # Nothing was frozen: the draft is still a draft, with no evidence bundle.
        settled = cr_repo.load().get(revision.calculation_revision_id)
        assert settled is not None
        assert settled.state is CalculationRevisionState.BORRADOR
        assert settled.ledger_filing_evidence is None
        # The editor form reads the same check: the calculation is out of date until calculated again.
        assert _form(repos).calculation_out_of_date is True


def test_an_untouched_draft_still_verifies_cleanly(tmp_path: Path) -> None:
    """The gate does not fire when nothing drifted.

    Guards the obvious over-block: if the anchor were recorded wrongly, or the
    comparison were against the wrong rows, every ledger-derived verify would
    refuse. Here the invoice is attached and nothing else moves, so the verify
    must reach its grant exactly as it did before the gate existed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
                calculate_irene_revision(profile.repository, operation=operation)
            )
        repos: _Repos = (wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo)

        evidence = PurchaseInvoiceEvidenceService(
            ports=build_ledger_evidence_ports(bucket_id=BUCKET_ID),
        ).add(bucket_id=BUCKET_ID, source_path=_write_invoice(tmp_path))
        with _ledger_ports(profile.repository, tx_repo, event_repo) as ports:
            attach_manual_transaction_evidence(
                bucket_id=BUCKET_ID,
                transaction_id=purchase.transaction_id,
                purchase_invoice_evidence_id=evidence.record.evidence_id,
                actor="operator",
                ports=ports,
                occurred_at=_AT,
            )

        granted = _verify(revision.calculation_revision_id, repos)

        assert granted.granted_verificado_completo is True
        assert granted.completeness_status is VerificationCompletenessStatus.COMPLETE
        assert _form(repos).calculation_out_of_date is False


def test_a_ledger_derived_draft_carries_the_anchor_the_gate_compares(tmp_path: Path) -> None:
    """Calculate pins the ledger state its values came from.

    Without this the gate has nothing to compare for a draft, because the
    snapshot is otherwise captured only on a granted verify — precisely the
    drafts that need guarding.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            revision, sale, purchase, _wu, _cr, _fr, _vr, _ev, tx_repo = calculate_irene_revision(
                profile.repository, operation=operation
            )

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

    from cadrumo.domain.modelos.calculation_revision import derive_calculation_revision_id

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


def _add_transaction(
    objects: SecureObjectRepository,
    repos: _Repos,
    *,
    booked_date: date = date(2026, 3, 25),
    business: BusinessClassification = BusinessClassification.BUSINESS,
    direction: TransactionDirection = TransactionDirection.INCOMING,
    currency: str = "EUR",
) -> Transaction:
    """Add through the real ledger action after the persisted calculation."""
    with _ledger_ports(objects, repos[-1], repos[-2]) as ports:
        return create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=BUCKET_ID,
                booked_date=booked_date,
                amount=Decimal("363.00"),
                currency=currency,
                direction=direction,
                description="New transaction after calculation",
                counterparty="New customer or supplier",
                business_classification=business,
                taxable_base=Decimal("300.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("63.00"),
                actor="operator",
            ),
            ports=ports,
            occurred_at=_AT,
        ).transaction


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("held_back", [False, True])
def test_added_declarable_sale_or_held_back_purchase_refuses_saved_calculation(
    tmp_path: Path,
    empty: bool,
    held_back: bool,
) -> None:
    """New admitted and unclassified-deduction rows cannot disappear into old values."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            result = calculate_irene_revision(
                profile.repository,
                operation=operation,
                empty=empty,
            )
        revision = result[0]
        repos: _Repos = result[3:]
        original = revision.model_dump(mode="json")
        added = _add_transaction(
            profile.repository,
            repos,
            direction=TransactionDirection.OUTGOING if held_back else TransactionDirection.INCOMING,
        )
        report = _verify(revision.calculation_revision_id, repos)
        drift = next(
            finding for finding in report.findings if finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
        )
        assert report.granted_verificado_completo is False
        assert drift.message_locale_key == "application.modelo.findings.ledger_snapshot_drift_added"
        assert drift.message_facts["added_count"] == 1
        assert drift.message_facts["changed_count"] == drift.message_facts["removed_count"] == 0
        assert drift.message_facts["anchored"] is (not empty)
        assert added.transaction_id not in revision.source_transaction_ids
        saved = repos[1].load().get(revision.calculation_revision_id)
        assert saved is not None
        assert saved.model_dump(mode="json") == original
        assert _form(repos).calculation_out_of_date is True


@pytest.mark.parametrize(
    ("booked_date", "business", "currency"),
    [
        (date(2026, 4, 25), BusinessClassification.BUSINESS, "EUR"),
        (date(2026, 3, 25), BusinessClassification.PERSONAL, "EUR"),
        (date(2026, 3, 25), BusinessClassification.PERSONAL, "USD"),
        (date(2026, 3, 25), BusinessClassification.REVIEWED_EXCLUDED, "EUR"),
    ],
)
def test_added_rows_outside_selected_admission_do_not_stale_the_calculation(
    tmp_path: Path,
    booked_date: date,
    business: BusinessClassification,
    currency: str,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            result = calculate_irene_revision(
                profile.repository,
                operation=operation,
            )
        revision = result[0]
        repos: _Repos = result[3:]
        _add_transaction(profile.repository, repos, booked_date=booked_date, business=business, currency=currency)
        report = _verify(revision.calculation_revision_id, repos)
        assert not any(finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION for finding in report.findings)


def test_recorded_held_back_transaction_is_not_reported_as_a_new_row(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            result = calculate_irene_revision(
                profile.repository,
                operation=operation,
                held_back_purchase=True,
            )
        revision = result[0]
        repos: _Repos = result[3:]
        purchase = result[2]
        assert purchase.transaction_id not in revision.source_transaction_ids
        assert any(issue.source_ref == f"transaction:{purchase.transaction_id}" for issue in revision.source_issues)
        report = _verify(revision.calculation_revision_id, repos)
        assert not any(finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION for finding in report.findings)
        assert report.granted_verificado_completo is False


def test_unavailable_membership_refuses_even_an_empty_draft(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            result = calculate_irene_revision(
                profile.repository,
                operation=operation,
                empty=True,
            )
        revision = result[0]
        repos: _Repos = result[3:]
        ports = _verification_ports(repos)
        wrong_bucket = TransactionCatalogueRepository(
            bucket_id="11111111-1111-4111-8111-111111111111",
            objects=profile.repository,
        )
        ports = replace(
            ports,
            ledger_membership_ports=replace(
                ports.ledger_membership_ports,
                transaction_repository=wrong_bucket,
            ),
        )
        report = _verify(revision.calculation_revision_id, repos, verification_ports=ports)
        drift = next(
            finding for finding in report.findings if finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
        )
        assert report.granted_verificado_completo is False
        assert drift.message_facts["membership_available"] is False


def test_non_ledger_binding_revision_does_not_borrow_bucket_transactions(tmp_path: Path) -> None:
    """Actual published non-ledger bindings never request unrelated source replay."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as runtime:
        with bundled_indexed_authority().operation() as operation:
            result = calculate_irene_revision(
                runtime.repository,
                operation=operation,
                empty=True,
            )
            revision = result[0]
            repos: _Repos = result[3:]
            (unit,) = repos[0].load().values()
            _add_transaction(runtime.repository, repos)
            profile = load_modelo_work_profile(
                bucket_id=BUCKET_ID,
                profile_decode_context=operation.profile_decode_context(),
            )
            assert profile is not None
            non_ledger_revision = operation.snapshot("111", filing_year=2026, period="1T").revision
            membership = query_ledger_membership(
                target=revision,
                work_unit=unit,
                revision=non_ledger_revision,
                profile=profile,
                ports=build_ledger_membership_ports(bucket_id=BUCKET_ID, transaction_repository=repos[-1]),
                operation=operation,
            )
        assert membership == LedgerSourceMembership()


def test_an_added_sale_in_a_different_encrypted_bucket_does_not_stale_the_draft(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path, primary_bucket_id=BUCKET_ID) as runtime:
        with bundled_indexed_authority().operation() as operation:
            result = calculate_irene_revision(runtime.primary.repository, operation=operation)
        revision = result[0]
        repos: _Repos = result[3:]
        with (
            runtime.switch_to_secondary(),
            ledger_ports_for_test(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            ) as ports,
        ):
            added = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=runtime.secondary.bucket_id,
                    booked_date=date(2026, 3, 25),
                    amount=Decimal("363.00"),
                    direction=TransactionDirection.INCOMING,
                    description="Other taxpayer's sale",
                    business_classification=BusinessClassification.BUSINESS,
                    taxable_base=Decimal("300.00"),
                    iva_rate=Decimal("0.21"),
                    iva_amount=Decimal("63.00"),
                ),
                ports=ports,
                occurred_at=_AT,
            ).transaction
            assert ports.transaction_repository.load().get(added.transaction_id) is not None
        assert repos[-1].load().get(added.transaction_id) is None
        report = _verify(revision.calculation_revision_id, repos)
        assert not any(finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION for finding in report.findings)
