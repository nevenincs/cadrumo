"""Real-behavior CLI tests for ``aeat app quickfile``.

Drives the one-command filing chain through the real ``cadrumo`` CLI against an
isolated real-session backend (real KEK/DEK, real encrypted SQLite) — no mocks,
no seeded revisions. Each test runs the actual
readiness -> create -> calculate -> verify -> export services in sequence.

Coverage:
- a calculable modelo (115, fed one real retención observation) reaches granted
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

import pytest
from click.testing import Result

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.state_projection import ProjectionModeloReadiness
from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind, Period
from ....core.resources import resources
from ....domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    IvaDeductionClassificationProvenance,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.modelos import (
    FilingInstanceEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
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
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

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


def _create_profile(*, activity_start_date: str = "2026-01-01") -> None:
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
    )


def _seed_m115_retencion_observation() -> None:
    """Persist one real URBAN_RENTAL retención observation for M115 2026 1T.

    Modelo 115 aggregates its cuota from persisted retención evidence; with one
    observation seeded the calculate stage resolves and the chain runs to
    completion. This is the source-preflight the ``calculate`` stage reads.
    """
    observation = json.dumps(
        {
            "source_kind": "ledger_transaction",
            "source_object_id": "rent-ledger-row-001",
            "perceptor_nif": "B12345678",
            "perceptor_name": "Arrendador Ejemplo SL",
            "scheme": "arrendamiento_urbano",
            "taxable_base": "2700.00",
            "retencion_amount": "513.00",
            "accrued_on": "2026-03-15",
        },
    )
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "115", "--year", "2026", "--period", "1T",
            "--retencion-observation", observation,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _active_bucket_id() -> str:
    from ....core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "profile create must install an active-profile pointer"
    return bucket_id


def _write_m303_filing_evidence(path: Path) -> None:
    period = Period.from_year_and_code(2026, "1T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=resources().modelos.authority.snapshot(
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
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(
                    reference="test:quickfile:exonerado-390:not-applicable",
                ),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=snapshot,
                dana_2024_eligibility=None,
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
        "category_id": "test_iva_operation",
        "taxable_base": taxable_base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": iva_amount,
        "classified_at": _IVA_WALLET_DECIDED_AT,
        "classified_by": "manual",
    }
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
        payload["deduction_fact_kind"] = IvaDeductionFactKind.DOMESTIC_CURRENT
        payload["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator=f"invoice:{purchase_invoice_evidence_id}",
            evidence_digest=purchase_invoice_evidence_id,
        )
    if invoice_id is not None:
        payload["invoice_id"] = invoice_id
    return Transaction.model_validate(payload)


def _seed_m303_ledger_and_wallet(bucket_id: str) -> None:
    from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ....application.calculations import IvaWalletDecisionRepository
    from ....application.invoices import build_catalogue_invoice
    from ....domain.invoices import InvoiceCatalogue, link_transaction
    from ....domain.iva import InvoiceKind

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
        InvoiceCatalogue.from_invoices((purchase_invoice,)),
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
                selected_authority="aeat_wallet",
                selected_amount=Decimal("0.00"),
                wallet_amount=Decimal("0.00"),
                local_recurrence_amount=Decimal("0.00"),
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


def test_quickfile_m115_reaches_granted_verify_before_withdrawn_export(
    tmp_path: Path,
) -> None:
    """A calculable M115 reaches verify, then refuses its unavailable layout.

    Modelo 115 1T 2026 with one seeded retención observation is calculable, so
    the chain reaches granted verification. Because no complete export layout is
    currently authored, export must refuse without writing a local artefact.
    """

    _create_profile()
    _seed_m115_retencion_observation()
    out = tmp_path / "modelo-115.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "115", "--year", "2026", "--period", "1T",
            "--casilla", "04=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is False, result.output
    assert payload["stopped_at_stage"] == "export", json.dumps(payload, sort_keys=True)
    assert payload["granted_verificado_completo"] is True
    assert payload["work_unit_id"]
    assert payload["calculation_revision_id"]

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "ok"
    assert statuses["export"] == "refused"
    # readiness is advisory and may be ok or warning; it must never refuse.
    assert statuses["readiness"] in {"ok", "warning"}

    notice_text = json.dumps(_notices(result.output), sort_keys=True)
    assert "no complete export_layouts definition" in notice_text
    assert payload["export"] is None
    assert not out.exists()


def test_quickfile_m303_fully_taxable_ledger_reaches_granted_verify_before_withdrawn_export(
    tmp_path: Path,
) -> None:
    """A fully taxable M303 reaches verify, then honestly refuses the withdrawn layout."""

    _create_profile()
    bucket_id = _active_bucket_id()
    _seed_m303_ledger_and_wallet(bucket_id)
    evidence_path = tmp_path / "m303-filing-evidence.json"
    _write_m303_filing_evidence(evidence_path)
    out = tmp_path / "modelo-303-2026-1T.boe"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "303", "--year", "2026", "--period", "1T",
            "--m303-filing-evidence", str(evidence_path),
            "--payment-election", "ingreso",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is False, result.output
    assert payload["stopped_at_stage"] == "export", json.dumps(payload, sort_keys=True)
    assert payload["granted_verificado_completo"] is True

    statuses = _stage_status(payload)
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "ok"
    assert statuses["export"] == "refused"

    notice_text = json.dumps(_notices(result.output), sort_keys=True)
    assert "prorrata" not in notice_text.lower()
    assert "no complete export_layouts definition" in notice_text
    assert payload["export"] is None
    assert not out.exists()


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

    from ....application.modelo import QuickfileStage, QuickfileStageStatus
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
    from ....application.modelo import QuickfileStage, QuickfileStageStatus
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

    from ....core import Period
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
