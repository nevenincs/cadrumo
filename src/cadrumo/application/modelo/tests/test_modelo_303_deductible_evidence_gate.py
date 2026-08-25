"""Modelo 303 filing-grade gate for deductible IVA evidence gaps."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import (
    CasillaId,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
    validated_casilla_id,
)
from ....core.resources import resources
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva import InvoiceKind, IvaDeductionClassificationProvenance
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests import general_m303_filing_evidence
from ....tests.env_scope import ready_clave_settings
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from ...calculations import IvaWalletDecisionRepository
from ...invoices import build_catalogue_invoice, create_catalogue_invoice
from ...ledger.actions_manual import attach_manual_transaction_evidence, link_manual_transaction_invoice
from ...ledger.evidence import PurchaseInvoiceEvidenceService
from .. import (
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    file_modelo_revision,
    verify_modelo_revision,
    verify_modelo_revision_with_preconditions,
)
from .._export import ModeloExportCommand, ModeloExportEvidenceMissingError, export_modelo_revision
from .._filing_actions import ModeloFilingEvidenceMissingError
from .._verification_actions import _missing_evidence_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30300000-0000-4000-8000-000000000303"
_TAX_ID = "12345678Z"
_YEAR = 2026
_PERIOD = "1T"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CALCULATED_AT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)
_VERIFIED_AT = datetime(2026, 4, 6, 10, 0, tzinfo=UTC)
_IVA_RATE = Decimal("0.21")


_DEVENGADA_TOTAL: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE_TOTAL: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_RESULTADO: CasillaId = validated_casilla_id("iva.resultado-regimen-general")


def _store_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Irene"),
                UserProfileFact(path="identity.surnames", value="Evidence"),
                UserProfileFact(path="activities.description", value="consulting"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 1, 1),
    )


def _wallet_decision() -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAX_ID,
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, _PERIOD),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="first_period_zero_aeat_wallet",
        wallet_captured_at=_CALCULATED_AT,
        decided_at=_CALCULATED_AT,
    )


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"M303 evidence gate {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    booked_date = date(_YEAR, 2, 15)
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                amount=taxable_base + iva_amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            # The deduction CLASSIFICATION axis, not the attached document. Input
            # IVA without an exact kind and provenance is dropped by the
            # aggregation gate before it can reach a casilla, which would leave
            # the deducible total at zero and make this module measure the wrong
            # thing. The scenario under test is untouched: no purchase-invoice
            # evidence record is attached, so the verify gate still has nothing
            # to resolve and still blocks.
            "deduction_fact_kind": (
                IvaDeductionFactKind.DOMESTIC_CURRENT if direction is TransactionDirection.OUTGOING else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _repositories(
    objects: SecureObjectRepository,
) -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
    TransactionCatalogueRepository,
]:
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        ModeloRecordCatalogueRepository(objects=objects),
        VerificationReportCatalogueRepository(objects=objects),
        BucketEventHistoryRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
    )


def _calculate_irene_revision(
    objects: SecureObjectRepository,
) -> tuple[
    CalculationRevision,
    Transaction,
    Transaction,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
    TransactionCatalogueRepository,
]:
    _store_profile(objects)
    wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _repositories(objects)
    sale = _iva_transaction(
        "irene-sale-no-evidence",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
    )
    purchase = _iva_transaction(
        "irene-purchase-no-evidence",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((sale, purchase)))
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        bucket_event_repository=event_repo,
        clock=_T0,
    )
    decision = _wallet_decision()
    IvaWalletDecisionRepository(objects=objects).save_decision(decision)
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="operator",
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_CALCULATED_AT,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period, reference="test:m303-deductible-evidence-gate"
        ),
    )
    return revision, sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo


def _persist_legacy_verified_revision(
    revision: CalculationRevision,
    *,
    cr_repo: CalculationRevisionCatalogueRepository,
    tx_repo: TransactionCatalogueRepository,
) -> CalculationRevision:
    catalogue = tx_repo.load()
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=revision.source_transaction_ids,
        catalogue=catalogue,
        captured_at=_VERIFIED_AT,
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=revision.source_transaction_ids,
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_VERIFIED_AT,
        legal_refs=tuple(dict.fromkeys(str(ref) for obs in revision.observations for ref in obs.legal_refs)),
        source_refs=tuple(dict.fromkeys(str(ref) for obs in revision.observations for ref in obs.source_refs)),
    )
    legacy = revision.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": _VERIFIED_AT,
            "verified_by": "legacy-operator",
            "ledger_filing_snapshot": snapshot,
            "ledger_filing_evidence": evidence,
            "updated_at": _VERIFIED_AT,
        },
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), legacy))
    return legacy


def test_modelo_303_verify_blocks_on_deductible_gap_and_only_warns_on_the_output_gap(
    secure_objects: SecureObjectRepository,
) -> None:
    """A deductible gap refuses the grant; an output gap stays advisory.

    This inverts the previous expectation deliberately. The condition used to be
    advisory here and a hard refusal at export and local filing, so verify froze
    a gap-carrying bundle onto a revision that could then never be exported and,
    because the revision id is content-addressed over tax facts that an evidence
    attach does not change, could never be superseded either. Blocking at verify
    is what makes that state unreachable instead of merely unexportable.

    The output side is NOT promoted, and the asymmetry is the point: deducting
    input IVA requires the factura, while no CLI path mints issued-invoice
    evidence, so blocking output IVA would refuse a taxpayer who cannot comply.
    """
    revision, sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )

    assert revision.casilla_values[_DEVENGADA_TOTAL] == sale.iva_amount
    assert revision.casilla_values[_DEDUCIBLE_TOTAL] == purchase.iva_amount
    assert sale.iva_amount is not None
    assert purchase.iva_amount is not None
    assert revision.casilla_values[_RESULTADO] == sale.iva_amount - purchase.iva_amount

    verification = verify_modelo_revision_with_preconditions(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings(_TAX_ID),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        verification_repository=vr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_VERIFIED_AT,
    )
    report = verification.report

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    blocking = [
        finding for finding in report.findings if finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    ]
    warning = [finding for finding in report.findings if finding.severity is ModeloVerificationFindingSeverity.WARNING]
    assert blocking != []
    assert warning != []
    expected_source_refs = tuple(dict.fromkeys(ref for obs in revision.observations for ref in obs.source_refs))
    evidence_findings = [
        finding
        for finding in report.findings
        if finding.source_refs == expected_source_refs
        and finding.kind in {ModeloVerificationFindingKind.BLOCKING_RULE, ModeloVerificationFindingKind.ADVISORY}
    ]
    assert evidence_findings
    assert all(finding.source_refs == expected_source_refs for finding in evidence_findings)
    assert all("deductible_iva_evidence" not in finding.source_refs for finding in evidence_findings)
    assert all("output_iva_evidence" not in finding.source_refs for finding in evidence_findings)
    assert all(
        "_" not in source_ref and "-" in source_ref
        for finding in evidence_findings
        for source_ref in finding.source_refs
    )
    # The deductible finding is BLOCKING while the output side stays an
    # ADVISORY; each remains factual and has no persisted recovery prose.
    assert any(finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE for finding in evidence_findings)
    assert any(finding.kind is ModeloVerificationFindingKind.ADVISORY for finding in evidence_findings)
    assert all("next_action" not in finding.model_dump(mode="json") for finding in evidence_findings)
    evidence_projections = tuple(
        projection for projection in verification.finding_preconditions if projection.finding in evidence_findings
    )
    assert len(evidence_projections) == len(evidence_findings)
    assert all(
        projection.precondition_failure is not None
        and projection.precondition_failure.scenario_id == "modelo.work.verify.deductible_iva_evidence.missing"
        and projection.precondition_failure.verdict.action is None
        and projection.precondition_failure.verdict.no_recovery_outcome is not None
        for projection in evidence_projections
        if projection.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    )
    assert all(
        projection.precondition_failure is None
        for projection in evidence_projections
        if projection.finding.severity is ModeloVerificationFindingSeverity.WARNING
    )
    # The load-bearing half: a blocked verify must leave NO frozen bundle and a
    # still-open draft. If either moved, the operator would be locked out of the
    # target exactly as before, and the promotion would have changed the message
    # rather than the outcome.
    stored = cr_repo.load().get(revision.calculation_revision_id)
    assert stored is not None
    assert stored.state is CalculationRevisionState.BORRADOR
    assert stored.ledger_filing_evidence is None


def test_modelo_303_verify_uses_attached_purchase_invoice_evidence(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
            _calculate_irene_revision(profile.repository)
        )
        invoice = tmp_path / "supplier-invoice.pdf"
        invoice.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
        evidence = PurchaseInvoiceEvidenceService(
            settings=profile.settings,
            bucket_event_repository=event_repo,
        ).add(bucket_id=_BUCKET_ID, source_path=invoice)

        attached = attach_manual_transaction_evidence(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            purchase_invoice_evidence_id=evidence.record.evidence_id,
            actor="operator",
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            occurred_at=_VERIFIED_AT,
        )

        assert attached.transaction.purchase_invoice_evidence_id == evidence.record.evidence_id
        reloaded = tx_repo.load().get(purchase.transaction_id)
        assert reloaded is not None
        assert reloaded.purchase_invoice_evidence_id == evidence.record.evidence_id

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            settings=ready_clave_settings(_TAX_ID),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=vr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_VERIFIED_AT,
        )

        assert report.granted_verificado_completo is True
        assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
        assert not any(
            finding.message_locale_key == "application.modelo.findings.transaction_evidence_missing_deductible"
            for finding in report.findings
        )
        stored = cr_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.ledger_filing_evidence is not None
        purchase_rows = [
            row for row in stored.ledger_filing_evidence.rows if row.transaction_id == purchase.transaction_id
        ]
        assert len(purchase_rows) == 1
        assert purchase_rows[0].purchase_invoice_evidence_id == evidence.record.evidence_id


def test_modelo_303_verify_and_file_credit_a_linked_validated_invoice(
    tmp_path: Path,
) -> None:
    """A row bound to a real, validated ``Invoice`` passes verify AND survives filing.

    This is the real path, not the model boundary: the invoice is minted
    through :func:`create_catalogue_invoice` -- the sanctioned catalogue
    writer that runs RD 1619/2012 art. 6 content validation -- and bound to
    the transaction through :func:`link_manual_transaction_invoice`, the sole
    invoice-linkage writer. Neither is a mock; both are the production
    functions an operator's ``aeat app ledger link`` command calls.

    Before the fix this test defends, ``_row_has_deduction_grade_evidence``
    read only ``purchase_invoice_evidence_id`` and never ``invoice_id``, so a
    row linked to a fully-validated ``Invoice`` still blocked verification --
    a validated invoice was treated as no evidence at all. This test fails on
    that code, and the sibling
    ``test_advisory_still_fires_when_neither_invoice_id_nor_evidence_id_is_set``
    in ``test_evidence_advisory.py`` proves the widening did not also silence
    a row with neither carrier set.

    The ``file_modelo_revision`` step at the end defends the SECOND grading
    surface this discovery uncovered: ``LedgerEvidenceRow`` (the bundle
    ``verify`` freezes) never carried ``invoice_id``, so a row credited only
    through a linked invoice at verify time bundled with
    ``purchase_invoice_evidence_id`` and ``attachment_ids`` both empty --
    and ``raise_if_deductible_iva_evidence_missing``
    (``_ledger_evidence_gate.py``) then blocked local filing on a revision
    ``verify`` had JUST granted. That is not a hypothetical: it reproduced
    against the first version of this fix, and is exactly the "permanent dead
    end" failure class the surrounding campaign was built to close -- a
    revision that is VERIFICADO_COMPLETO and content-addressed cannot be
    re-verified or recalculated into a different id, so a fix that only
    closes the verify-time gate while leaving the bundle-time gate blind
    would strand the taxpayer worse than before the fix.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
            _calculate_irene_revision(profile.repository)
        )

        invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        created = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Proveedor Ejemplo SL",
                counterparty_tax_id="B12345674",
                counterparty_country="ES",
                invoice_number="F2026-0042",
                issued_at=date(_YEAR, 2, 15),
                taxable_base=Decimal("200.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
            ),
            repository=invoice_repo,
        )

        linked = link_manual_transaction_invoice(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            invoice_id=created.invoice.invoice_id,
            actor="operator",
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            bucket_event_repository=event_repo,
            occurred_at=_VERIFIED_AT,
        )

        linked_transaction = linked.transactions.get(purchase.transaction_id)
        assert linked_transaction is not None
        assert linked_transaction.invoice_id == created.invoice.invoice_id
        assert linked_transaction.purchase_invoice_evidence_id is None
        reloaded = tx_repo.load().get(purchase.transaction_id)
        assert reloaded is not None
        assert reloaded.invoice_id == created.invoice.invoice_id

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            settings=ready_clave_settings(_TAX_ID),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=vr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_VERIFIED_AT,
        )

        assert report.granted_verificado_completo is True
        assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
        assert not any(
            finding.message_locale_key == "application.modelo.findings.transaction_evidence_missing_deductible"
            for finding in report.findings
        )

        stored = cr_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.ledger_filing_evidence is not None
        purchase_rows = [
            row for row in stored.ledger_filing_evidence.rows if row.transaction_id == purchase.transaction_id
        ]
        assert len(purchase_rows) == 1
        assert purchase_rows[0].invoice_id == created.invoice.invoice_id
        assert purchase_rows[0].purchase_invoice_evidence_id is None

        # The load-bearing half of this test: filing a VERIFICADO_COMPLETO
        # revision whose only deductible evidence is a linked invoice must
        # NOT dead-end. Before the LedgerEvidenceRow.invoice_id fix, this
        # raised ModeloFilingEvidenceMissingError even though verify had just
        # granted the same revision.
        filed = file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=vr_repo,
            bucket_event_repository=event_repo,
            clock=_VERIFIED_AT,
        )
        assert filed is not None
        assert tuple(filing_repo.load().values()) != ()


def test_a_blocked_verify_is_recoverable_by_attaching_and_verifying_again(
    tmp_path: Path,
) -> None:
    """The recovery the whole promotion rests on: block, attach, re-verify, grant.

    The sibling test above attaches BEFORE the first verify, which was the only
    ordering that ever worked. This one drives the ordering an operator actually
    reaches: verify first, hit the refusal, then fix it. It is the case that was
    a permanent dead end before the promotion, because verify granted over the
    gap and froze a bundle onto a revision whose content-addressed id an evidence
    attach cannot change.

    It also pins that the idempotent re-verify guard does not fire here. That
    guard keys on a non-BORRADOR state, so a blocked revision must stay BORRADOR
    for the second verify to do real work rather than return the first report.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        revision, _sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = (
            _calculate_irene_revision(profile.repository)
        )

        def _verify() -> VerificationReport:
            return verify_modelo_revision(
                revision.calculation_revision_id,
                actor="operator",
                workflow_profile=_workflow_profile(),
                settings=ready_clave_settings(_TAX_ID),
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                filing_repository=filing_repo,
                verification_repository=vr_repo,
                bucket_event_repository=event_repo,
                transaction_repository=tx_repo,
                clock=_VERIFIED_AT,
            )

        blocked = _verify()
        assert blocked.granted_verificado_completo is False
        assert blocked.completeness_status is VerificationCompletenessStatus.BLOCKED
        after_block = cr_repo.load().get(revision.calculation_revision_id)
        assert after_block is not None
        assert after_block.state is CalculationRevisionState.BORRADOR
        assert after_block.ledger_filing_evidence is None

        invoice = tmp_path / "supplier-invoice.pdf"
        invoice.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
        evidence = PurchaseInvoiceEvidenceService(
            settings=profile.settings,
            bucket_event_repository=event_repo,
        ).add(bucket_id=_BUCKET_ID, source_path=invoice)
        attach_manual_transaction_evidence(
            bucket_id=_BUCKET_ID,
            transaction_id=purchase.transaction_id,
            purchase_invoice_evidence_id=evidence.record.evidence_id,
            actor="operator",
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            occurred_at=_VERIFIED_AT,
        )

        granted = _verify()
        assert granted.granted_verificado_completo is True
        assert granted.completeness_status is VerificationCompletenessStatus.COMPLETE
        assert granted.verification_report_id != blocked.verification_report_id

        settled = cr_repo.load().get(revision.calculation_revision_id)
        assert settled is not None
        assert settled.state is CalculationRevisionState.VERIFICADO_COMPLETO
        assert settled.ledger_filing_evidence is not None
        purchase_rows = [
            row for row in settled.ledger_filing_evidence.rows if row.transaction_id == purchase.transaction_id
        ]
        assert len(purchase_rows) == 1
        assert purchase_rows[0].purchase_invoice_evidence_id == evidence.record.evidence_id
        # The revision id never moved. That is the point of ruling against
        # folding evidence into identity: no calculation differs, so no new
        # revision was needed to carry the fix.
        assert settled.calculation_revision_id == revision.calculation_revision_id


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_YEAR, _PERIOD)
    revision_id = "2026-y-siguientes"
    modelo = ModeloCode("303")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_YEAR,
        period=period,
        revision_id=revision_id,
        name="303 evidence gate",
        created_at=_T0,
        updated_at=_T0,
    )


def test_output_iva_evidence_hint_is_advisory_and_names_current_cli_limit(
    secure_objects: SecureObjectRepository,
) -> None:
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    sale = _iva_transaction(
        "irene-sale-no-evidence",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((sale,)))
    work_unit = _work_unit()
    filing_instance_evidence = general_m303_filing_evidence(work_unit.period, reference="test:m303-deductible-evidence")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        relation_overrides={},
        casilla_values={},
        source_transaction_ids=(sale.transaction_id,),
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        source_transaction_ids=(sale.transaction_id,),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )

    findings = _missing_evidence_findings(
        target=revision,
        work_unit=work_unit,
        transaction_repository=tx_repo,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert "next_action" not in finding.model_dump(mode="json")


def test_modelo_303_export_refuses_legacy_verified_deductible_iva_missing_evidence(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    revision, _sale, _purchase, _wu_repo, cr_repo, _filing_repo, _vr_repo, _event_repo, tx_repo = (
        _calculate_irene_revision(secure_objects)
    )
    legacy = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)
    output_path = tmp_path / "modelo-303.txt"

    with pytest.raises(ModeloExportEvidenceMissingError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=legacy.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=_workflow_profile(),
            calculation_repository=cr_repo,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "deductible_iva_evidence_missing"
    failure = exc_info.value.precondition_failure
    assert failure is not None
    assert failure.identity == (
        "modelo.export",
        "modelo.export.deductible_iva_evidence.present",
        "modelo.export.deductible_iva_evidence.missing",
    )
    assert failure.verdict.no_recovery_outcome is not None
    assert not output_path.exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_modelo_303_internal_file_refuses_legacy_verified_deductible_iva_missing_evidence(
    secure_objects: SecureObjectRepository,
) -> None:
    revision, _sale, _purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )
    legacy = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)

    with pytest.raises(ModeloFilingEvidenceMissingError) as exc_info:
        file_modelo_revision(
            legacy.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=vr_repo,
            bucket_event_repository=event_repo,
            clock=_VERIFIED_AT,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "deductible_iva_evidence_missing"
    failure = exc_info.value.precondition_failure
    assert failure is not None
    assert failure.identity == (
        "modelo.work.file",
        "modelo.work.file.deductible_iva_evidence.present",
        "modelo.work.file.deductible_iva_evidence.missing",
    )
    assert failure.verdict.no_recovery_outcome is not None
    assert tuple(filing_repo.load().values()) == ()
