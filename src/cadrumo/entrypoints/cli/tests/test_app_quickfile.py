"""Real-behavior CLI tests for ``aeat app quickfile``.

Drives the one-command filing chain through the real ``cadrumo`` CLI against an
isolated real-session backend (real KEK/DEK, real encrypted SQLite) — no mocks,
no seeded revisions. Each test runs the actual
readiness -> create -> calculate -> verify -> export services in sequence.

Coverage:
- a calculable modelo (115, fed one invoice-backed retención) reaches granted
  verification before honestly refusing its unavailable export layout;
- a modelo whose ``previous_filing`` source is absent (130 without an observed
  prior-year Modelo 100 filing) calculates using the caller-supplied override
  but halts at ``verify``, where the cross-period clean-state gate catches the
  same absent source and refuses verificado-completo.

The chain is build + export only: no live AEAT submission path is exercised or
reachable (``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.calculations.tests.filing_evidence import regimen_simplificado_filing_evidence
from ....application.state_projection import ProjectionModeloReadiness
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource, published_snapshot
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence, M303FilingInstanceEvidence
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .cli_runner import invoke_cached_cli

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Signatures of a concurrent-registry-write race: a concurrent process may be
# editing the registry TOML tree while these tests load it, producing a
# transient mid-edit validation/fingerprint error. Re-run rather than triage
# as a regression; ``_invoke`` encodes that as a bounded retry keyed strictly
# on these transient markers so a real failure (a genuine refusal, a wrong
# value) is never masked.
_TRANSIENT_REGISTRY_RACE_MARKERS = (
    "registry directory changed during cache fingerprinting",
    "required-role gate",
    "duplicate catalogue ids",
    "references unknown source id",
)
_IVA_WALLET_DECIDED_AT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)


def _invoke(args: Sequence[str], *, attempts: int = 8) -> Result:
    """Invoke the CLI, re-running only on the transient registry-write race."""
    result = invoke_cached_cli(list(args))
    tries = 1
    while (
        tries < attempts
        and result.exit_code != 0
        and any(marker in result.output for marker in _TRANSIENT_REGISTRY_RACE_MARKERS)
    ):
        time.sleep(2)
        dispose_engine()
        result = invoke_cached_cli(list(args))
        tries += 1
    return result


def _create_profile(*, activity_start_date: str = "2026-01-01", complete: bool = True) -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Quickfile",
            "activities.description": "design",
            "censo.activity_start_date": activity_start_date,
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
            "tax_residence.ccaa": "madrid",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
        complete=complete,
        log_in=False,
    )


def _capture_m115_invoice_withholding() -> None:
    """Capture one received urban-rent invoice's retención as Modelo 115 2025 1T evidence.

    Modelo 115 aggregates its cuota from persisted retención evidence; with one
    captured allocation the calculate stage resolves and the chain runs to
    completion. The evidence enters through the public path only: ``ledger
    invoice add`` mints a received rent invoice (2700.00 base, 19% retención =
    513.00), then ``modelo aggregate --received-invoice-retencion`` records its
    single paid allocation with the property detail Modelo 180 requires. The
    settlement is the invoice grand total (2700.00 + 21% IVA = 3267.00) less
    the retención: 2754.00.
    """
    paid_on = date(2025, 3, 15)
    created = _invoke(
        [
            "--format", "json",
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-name", "Arrendador Ejemplo SL",
            "--counterparty-nif", "B12345674",
            "--invoice-number", "M115-RENT-2025-001",
            "--invoice-date", paid_on.isoformat(),
            "--country-code", "ES",
            "--taxable-base", "2700.00", "--iva-rate", "21",
            "--retention-rate", "0.19", "--retention-amount", "513.00",
            "--iva-category", "domestic_general",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    invoice_id = _payload(created.output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, created.output

    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice_id,
        income_kind=WithholdingIncomeKind.URBAN_RENT,
        scheme="arrendamiento_urbano",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="m115-rent-payment-2025-03-15",
        payment_occurred_on=paid_on,
        allocation_id="m115-rent-allocation-1",
        allocated_base=Decimal("2700.00"),
        allocated_withholding=Decimal("513.00"),
        allocated_settlement=Decimal("2754.00"),
        idempotency_key="m115-rent-allocation-1",
        modelo_180_property=Modelo180PropertyEvidence(
            property_key="quickfile-rent-property",
            situation="1",
            cadastral_reference="1234567VK4713C0001XY",
            address=Modelo180StructuredAddress(
                province_code="28",
                municipality_code="079",
                municipality="Madrid",
                locality="Madrid",
                postal_code="28001",
                street_type="CL",
                street_name="Ejemplo",
                number_type="NUM",
                house_number="1",
            ),
            recipient_province_code="28",
            modality="1",
            accrual_year=2025,
            withholding_percentage=Decimal("19.00"),
        ),
    )
    captured = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "115", "--year", "2025", "--period", "1T",
            "--received-invoice-retencion", request.model_dump_json(),
        ],
    )  # fmt: skip
    assert captured.exit_code == 0, captured.output


def _active_bucket_id() -> str:
    from ....core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "profile create must install an active-profile pointer"
    return bucket_id


def _write_m303_filing_evidence(path: Path, *, operation: PinnedAuthorityOperation) -> None:
    period = Period.from_year_and_code(2026, "1T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=m303_regime_composition_simplified_scope("general", authority=PublishedGovernedFactSource()),
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=published_snapshot(
            "303",
            filing_year=period.filing_year,
            period=period.code,
        ),
        scope_decision=scope,
    )
    evidence = FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            annual_volume_nonzero=None,
            insolvency=None,
            exonerado_390=None,
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=snapshot,
                dana_eligibility=None,
                operation=operation,
            ),
        ),
    )
    path.write_text(evidence.model_dump_json(), encoding="utf-8")


def _raw_m303_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"M303 quickfile {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="7" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_IVA_WALLET_DECIDED_AT,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _m303_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
    iva_amount: Decimal,
    purchase_invoice_evidence_id: str | None = None,
    invoice_id: str | None = None,
) -> Transaction:
    booked_date = date(2026, 2, 15)
    payload: dict[str, object] = {
        "raw": _raw_m303_transaction(
            provider_id,
            booked_date=booked_date,
            amount=taxable_base + iva_amount,
        ),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "category_id": "material_oficina",
        "taxable_base": taxable_base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": iva_amount,
        "classified_at": _IVA_WALLET_DECIDED_AT,
        "classified_by": "manual",
    }
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
        payload["deduction_fact_kind"] = IvaDeductionFactKind.from_registry("domestic_current")
        payload["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{purchase_invoice_evidence_id}",
            evidence_digest=purchase_invoice_evidence_id,
        )
    if invoice_id is not None:
        payload["invoice_id"] = invoice_id
    return Transaction.model_validate(payload)


def _seed_m303_ledger_and_wallet(bucket_id: str) -> None:
    from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
    from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ....application.invoices.catalogue_creation import build_catalogue_invoice
    from ....domain.invoices.service import link_transaction
    from ....domain.iva.classification import InvoiceKind

    purchase_invoice = build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Quickfile SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="REC-2026-1T",
        issued_at=date(2026, 2, 15),
        taxable_base=Decimal("200.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=recorded_ecb_rate_provider(),
    )
    sale = _m303_transaction(
        "quickfile-sale-general",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    purchase = _m303_transaction(
        "quickfile-purchase-general",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        purchase_invoice_evidence_id=purchase_invoice.invoice_id,
        invoice_id=purchase_invoice.invoice_id,
    )
    invoice_catalogue = link_transaction(
        build_invoice_catalogue((purchase_invoice,)),
        purchase_invoice.invoice_id,
        purchase.transaction_id,
    )
    with open_test_profile_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((sale, purchase)),
        )
        InvoiceCatalogueRepository(bucket_id=bucket_id).save(invoice_catalogue)
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=2026,
                target_period=Period.from_year_and_code(2026, "1T"),
                target_registry_snapshot_ref=published_snapshot("303", filing_year=2026, period="1T").snapshot_ref,
                source_registry_snapshot_refs=(),
                selected_authority="aeat_wallet",
                selected_amount=Decimal("0.00"),
                wallet_amount=Decimal("0.00"),
                local_recurrence_amount=None,
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason_identity="first_period_zero_aeat_wallet",
                wallet_captured_at=_IVA_WALLET_DECIDED_AT,
                decided_at=_IVA_WALLET_DECIDED_AT,
            ),
        )


def _stage_status(payload: dict[str, object]) -> dict[str, str]:
    stages = payload["stages"]
    assert isinstance(stages, list)
    result: dict[str, str] = {}
    for stage in stages:
        assert isinstance(stage, dict)
        # ``isinstance(stage, dict)`` only proves *some* dict — this data is
        # always parsed JSON envelope output, so re-keying with ``str(k)``
        # gives an honestly-typed ``dict[str, object]`` to index into.
        typed_stage = {str(k): v for k, v in stage.items()}
        name, status = typed_stage["stage"], typed_stage["status"]
        assert isinstance(name, str)
        assert isinstance(status, str)
        result[name] = status
    return result


def test_quickfile_runs_full_chain_to_exported_fichero(
    tmp_path: Path,
) -> None:
    """One command carries a calculable M115 from create to a written fichero.

    Modelo 115 1T 2025 with one invoice-backed retención allocation is calculable, so
    the chain reaches granted verification and then EXPORTS: the revision's
    ``modelo-115-fichero-boe`` layout is a renderable fixed-width definition
    carrying its records, so local declaration bytes are produced. The quarter
    is 2025 because invoice-backed withholding recognition is grounded for the
    2025 applicable year only and refuses capture for any other year.

    This assertion was inverted for a period when no complete export layout was
    authored and the stage legitimately refused. The layout is authored again,
    so the refusal it asserted no longer describes the product -- and asserting
    a refusal that cannot happen is a test that passes by never running its
    subject.
    """

    _create_profile(activity_start_date="2025-01-01")
    _capture_m115_invoice_withholding()
    out = tmp_path / "modelo-115.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "115", "--year", "2025", "--period", "1T",
            "--casilla", "04=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is True, result.output
    assert payload["stopped_at_stage"] is None, json.dumps(payload, sort_keys=True)
    assert payload["granted_verificado_completo"] is True
    assert payload["work_unit_id"]
    assert payload["calculation_revision_id"]

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "ok"
    assert statuses["export"] == "ok"
    # readiness is advisory and may be ok or warning; it must never refuse.
    assert statuses["readiness"] in {"ok", "warning"}

    # The fichero is the point of the chain, so its BYTES are asserted rather
    # than the stage status alone: an export reported ok that wrote nothing
    # would satisfy every check above.
    assert payload["export"] is not None
    assert out.exists(), f"quickfile reported an ok export but wrote no file at {out}"
    assert out.stat().st_size > 0, "the exported fichero is empty"


def test_quickfile_m303_2026_refuses_an_attestation_pair_the_period_does_not_ask(tmp_path: Path) -> None:
    """1T does not ask the Modelo 390 exemption, so a supplied attestation pair stops quickfile at calculate."""

    _create_profile()
    out = tmp_path / "modelo-303-2026-1T.boe"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "303", "--year", "2026", "--period", "1T",
            "--joint-return-elected",
            "--m303-exonerado-390-attachment-id", "a" * 64,
            "--m303-exonerado-390-sha256", "a" * 64,
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is False, result.output
    assert payload["stopped_at_stage"] == "calculate", json.dumps(payload, sort_keys=True)
    assert payload["granted_verificado_completo"] is None

    statuses = _stage_status(payload)
    assert statuses["calculate"] == "refused"
    assert statuses["verify"] == "skipped"
    assert statuses["export"] == "skipped"
    assert payload["export"] is None
    assert not out.exists()
    assert "exonerado_390_attestation_outside_last_period" in result.output


def test_quickfile_help_exposes_explicit_result_elections() -> None:
    result = _invoke(["app", "quickfile", "--help"])
    assert result.exit_code == 0, result.output
    assert "--refund-election" in result.output
    assert "--payment-election" in result.output
    assert "--disposition" not in result.output


def test_quickfile_refuses_at_verify_when_a_previous_filing_source_is_absent(tmp_path: Path) -> None:
    """An absent previous-filing source is a verify-stage clean-state gap, not a calculate crash.

    Modelo 130 1T 2025 declares a ``previous_filing`` carry reading Modelo 100
    2024's prior-year income. With no Modelo 100 2024 observation in the local
    store, the registry resolver treats the binding as genuinely unsatisfied
    (there is nothing malformed about a taxpayer whose prior filing AEAT has
    simply never confirmed) rather than raising: calculate proceeds using the
    caller-supplied ``--binding`` override. The SAME gap is then caught where
    it belongs — the cross-period clean-state verification gate — which
    refuses to grant verificado-completo while the Modelo 100 2024 source is
    unclean, so quickfile still never writes an export file.
    """

    _create_profile(activity_start_date="2024-01-01")
    out = tmp_path / "modelo-130.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is False
    assert payload["stopped_at_stage"] == "verify", result.output
    assert payload["granted_verificado_completo"] is False
    assert payload["export"] is None

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "refused"
    assert statuses["export"] == "skipped"

    notice_text = json.dumps(_notices(result.output), sort_keys=True)
    assert "cross_period_dependency_unclean" in notice_text
    assert "Source modelo 100 2024 0A is not clean" in notice_text
    assert "irpf.previous_year_economic_activity_net_income" in notice_text
    assert not out.exists()


def test_quickfile_requires_output_flag() -> None:
    """Quickfile refuses without ``--output`` (the export destination is required)."""

    _create_profile()
    result = _invoke(
        ["app", "quickfile", "--modelo", "115", "--year", "2026", "--period", "1T"],
    )
    assert result.exit_code != 0
    assert "output" in result.output.lower()


def test_quickfile_stage_payload_refuses_unknown_stage_and_status() -> None:
    """The transport payload refuses a stage or status outside the canonical enums.

    ``QuickfileStageOutcomePayload`` mirrors the application-owned
    :class:`QuickfileStage` / :class:`QuickfileStageStatus` closed sets. Before
    these fields were typed from those enums the machine-facing payload accepted
    any string, so a drifted or malformed stage crossed the CLI boundary intact.
    """
    from pydantic import ValidationError

    from ....application.modelo.quickfile import QuickfileStage, QuickfileStageStatus
    from .._app_quickfile_payloads import QuickfileStageOutcomePayload

    with pytest.raises(ValidationError):
        QuickfileStageOutcomePayload(stage="bogus", status=QuickfileStageStatus.OK)

    with pytest.raises(ValidationError):
        QuickfileStageOutcomePayload(stage=QuickfileStage.VERIFY, status="bogus")


def test_quickfile_stage_payload_serialises_enums_as_strings() -> None:
    """A valid stage/status round-trips to the same JSON strings the CLI emitted before.

    Typing the fields must not change the wire contract: ``StrEnum`` members
    serialise to their value, so machine consumers keep reading plain strings.
    """
    from ....application.modelo.quickfile import QuickfileStage, QuickfileStageStatus
    from .._app_quickfile_payloads import QuickfileStageOutcomePayload

    row = QuickfileStageOutcomePayload(
        stage=QuickfileStage.VERIFY,
        status=QuickfileStageStatus.REFUSED,
    )
    dumped = row.model_dump(mode="json")
    assert dumped["stage"] == "verify"
    assert dumped["status"] == "refused"


def test_quickfile_result_payload_refuses_unknown_stopped_stage() -> None:
    """``stopped_at_stage`` names a canonical stage or nothing at all."""
    from pydantic import ValidationError

    from ....core.period import Period
    from .._app_quickfile_payloads import QuickfileResultPayload

    with pytest.raises(ValidationError):
        QuickfileResultPayload(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id="rev-1",
            completed=False,
            stopped_at_stage="bogus",
            stages=(),
        )


def _readiness(**overrides: object) -> ProjectionModeloReadiness:
    period = Period.from_year_and_code(2026, "1T")
    base: dict[str, object] = {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "modelo": "130",
        "revision_id": "rev-1",
        "filing_year": 2026,
        "period": period,
        "profile_ready": True,
        "per_operation_requirements_assessed": True,
        "ready": True,
    }
    base.update(overrides)
    return ProjectionModeloReadiness.model_validate(base)


def test_quickfile_result_payload_summarises_the_readiness_report_when_ready() -> None:
    """A ready readiness report reaches the operator as a compact axis verdict."""
    from .._app_quickfile_payloads import QuickfileReadinessSummaryPayload, QuickfileResultPayload

    payload = QuickfileResultPayload(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        registry_revision_id="rev-1",
        completed=False,
        stopped_at_stage=None,
        readiness=QuickfileReadinessSummaryPayload.from_result(_readiness()),
        stages=(),
    )

    assert payload.readiness is not None
    assert payload.readiness.ready is True
    assert payload.readiness.missing_profile_fact_count == 0
    assert payload.readiness.missing_binding_count == 0
    assert payload.readiness.ledger_issue_count == 0


def test_quickfile_result_payload_summarises_a_missing_profile_requirement() -> None:
    """A missing profile fact is retained as an axis verdict and blocker count."""
    from ....application.user_profile.commands import ProfilePreflightRequirement
    from .._app_quickfile_payloads import QuickfileReadinessSummaryPayload, QuickfileResultPayload

    not_ready = _readiness(
        profile_ready=False,
        ready=False,
        missing=(
            ProfilePreflightRequirement(
                selector="identity.tax_id",
                section_key="identity",
                field_key="tax_id",
                label="Tax ID",
            ),
        ),
    )
    payload = QuickfileResultPayload(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        registry_revision_id="rev-1",
        completed=False,
        stopped_at_stage=None,
        readiness=QuickfileReadinessSummaryPayload.from_result(not_ready),
        stages=(),
    )

    assert payload.readiness is not None
    assert payload.readiness.ready is False
    assert payload.readiness.profile_ready is False
    assert payload.readiness.missing_profile_fact_count == 1


def test_quickfile_result_payload_summarises_a_missing_binding_requirement() -> None:
    """A binding-blocked readiness report retains its axis verdict and blocker count."""
    from ....application.state_projection import ProjectionModeloBindingRequirement
    from .._app_quickfile_payloads import QuickfileReadinessSummaryPayload, QuickfileResultPayload

    blocked = _readiness(
        binding_ready=False,
        ready=False,
        missing_bindings=(
            ProjectionModeloBindingRequirement(
                binding_id="binding-1",
                source="ledger_renta_income_aggregation",
                input_channel="preflight",
            ),
        ),
    )
    payload = QuickfileResultPayload(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        registry_revision_id="rev-1",
        completed=False,
        stopped_at_stage=None,
        readiness=QuickfileReadinessSummaryPayload.from_result(blocked),
        stages=(),
    )

    assert payload.readiness is not None
    assert payload.readiness.binding_ready is False
    assert payload.readiness.missing_binding_count == 1


def _stage_notice_for(output: str, stage: str) -> dict[str, Any]:
    """Return the one notice the stage produced, re-validated through the production contract."""
    from ....core.json_contract import Notice

    matching = [notice for notice in _notices(output) if notice.get("code") == f"quickfile.stage.{stage}"]
    assert len(matching) == 1, json.dumps(_notices(output), sort_keys=True)
    notice = matching[0]
    Notice.model_validate_json(json.dumps(notice))
    message = notice["message"]
    assert isinstance(message, str) and message
    assert "aeat " not in message and "`aeat" not in message, message
    return notice


def _assert_stopped_at(output: str, stage: str) -> dict[str, Any]:
    payload = _payload(output)
    assert payload["completed"] is False, output
    assert payload["stopped_at_stage"] == stage, json.dumps(payload, sort_keys=True)
    assert payload["export"] is None
    statuses = _stage_status(payload)
    order = ("readiness", "create", "calculate", "verify", "export")
    assert statuses[stage] == "refused"
    assert all(statuses[later] == "skipped" for later in order[order.index(stage) + 1 :]), statuses
    return payload


def test_quickfile_setup_incomplete_refusal_reports_the_typed_completion_action(tmp_path: Path) -> None:
    """An undeclared-complete profile stops quickfile at create with a typed recovery, not a crash.

    The refusal's prose once named the completion command, which the notices
    contract refuses, so quickfile exited 2 instead of reporting the stage. The
    recovery now travels only on the notice's typed action.
    """
    _create_profile(complete=False)
    out = tmp_path / "modelo-130.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "130", "--year", "2026", "--period", "2T",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    _assert_stopped_at(result.output, "create")
    notice = _stage_notice_for(result.output, "create")
    action = notice["action"]
    assert isinstance(action, dict), notice
    assert action["failed_condition_id"] == "profile.setup.declared_complete"
    resolved = action["action"]
    assert isinstance(resolved, dict), action
    assert resolved["action_id"] == "operator.profile.complete_setup"
    assert resolved["target_command_key"] == "config.profile.complete_setup"
    assert resolved["cli_path"] == ["config", "profile", "complete-setup"]
    assert action["conditionality"] == "immediate"
    # The readiness warning is where the incomplete setup is first seen; it
    # carries the same typed recovery rather than a bare warning.
    readiness = _stage_notice_for(result.output, "readiness")
    readiness_action = readiness["action"]
    assert isinstance(readiness_action, dict), readiness
    assert readiness_action["action"]["action_id"] == "operator.profile.complete_setup"
    assert not out.exists()


def test_quickfile_create_stage_refusal_without_a_typed_action_reports_its_reason(tmp_path: Path) -> None:
    """A create-stage refusal that carries no verdict still reports its own reason, with no action."""
    _create_profile(activity_start_date="2026-01-01")
    out = tmp_path / "modelo-130.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    _assert_stopped_at(result.output, "create")
    notice = _stage_notice_for(result.output, "create")
    assert notice.get("action") is None, notice
    assert "pre-activity period" in str(notice["message"])
    assert "2026-01-01" in str(notice["message"])
    assert not out.exists()


def test_quickfile_calculate_refusal_reports_its_reason_and_typed_recovery(tmp_path: Path) -> None:
    """An unknown ``--binding`` stops quickfile at calculate with its own reason and a typed recovery.

    The refusal's reason names the rejected binding and the accepted ones, and
    no command: the bindings listing reaches the operator only as the typed
    action. (A reason that still named a command would fall back to the
    stage-and-code sentence; the detector below proves that path.)
    """
    _create_profile(activity_start_date="2025-01-01")
    out = tmp_path / "modelo-115.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "115", "--year", "2025", "--period", "1T",
            "--binding", "not-a-declared-binding=1",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    _assert_stopped_at(result.output, "calculate")
    notice = _stage_notice_for(result.output, "calculate")
    action = notice.get("action")
    assert isinstance(action, dict), notice
    assert action["failed_condition_id"] == "modelo.work.calculate.caller_overrides.binding_declared"
    assert action["action"]["action_id"] == "operator.modelo.bindings.list"
    context = notice["context"]
    assert isinstance(context, dict), notice
    assert context["stage"] == "calculate"
    assert context["status"] == "refused"
    assert "not-a-declared-binding" in str(notice["message"])
    assert not out.exists()


def test_notice_contract_refuses_the_command_prose_the_old_stage_projection_passed() -> None:
    """Detector: the reason the old projection copied into a notice is refused by the contract.

    Without this refusal, the fallback above would be dead code and the
    stage notices would carry an executable command outside the typed action.
    """
    from pydantic import ValidationError

    from ....application.modelo.action_errors import ModeloProfileReadinessError
    from ....application.modelo.quickfile import QuickfileStage, QuickfileStageOutcome, QuickfileStageStatus
    from ....core.json_contract import Notice, NoticeSeverity
    from .._app_quickfile import _stage_notice

    # Catalogued refusals no longer name commands, so the specimen is the shape
    # the old projection used to copy: a reason ending in an executable command.
    reason = "--binding not-a-declared-binding is unknown. Use `aeat app modelo bindings list 115` to list them."
    with pytest.raises(ValidationError, match="raw aeat command prose"):
        Notice(severity=NoticeSeverity.WARNING, code="quickfile.stage.calculate", message=reason)

    commanded = ModeloProfileReadinessError("run `aeat config profile complete-setup` first")
    notice = _stage_notice(
        QuickfileStageOutcome(
            stage=QuickfileStage.CREATE,
            status=QuickfileStageStatus.REFUSED,
            message=str(commanded),
            refusal=commanded,
        ),
    )
    assert "aeat" not in notice.message
    assert notice.context is not None
    assert notice.context["error_code"] == "REFUSED_MODELO_PROFILE_READINESS"
    assert notice.action is None
