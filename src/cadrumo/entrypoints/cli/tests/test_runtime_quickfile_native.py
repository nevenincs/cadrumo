"""Native human Quickfile calculation and honest cross-period verification refusal.

The fixture runs Windows named pipes, the real profile worker, and encrypted
profile repositories. Its native secret port and OS-login observation are
synthetic; this is not platform secret-store or live taxpayer filing acceptance.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from pydantic import JsonValue

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.modelo.quickfile import QUICKFILE_STAGE_ORDER, QuickfileStage, QuickfileStageStatus
from ....application.modelo.quickfile_operation import QUICKFILE_OPERATION_DEFINITION_ID
from ....application.modelo.quickfile_operation_contracts import QuickfileRequest
from ....application.modelo.quickfile_operation_projections import QuickfileProjection
from ....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ....application.runtime.operation_access import (
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.aggregation import RetencionScheme
from ....core.config import override_settings
from ....core.hashing import canonical_json_bytes, sha256_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.export import resolve_export_layout
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....tests.cli_envelope import require_error_document, unwrap_cli_result, unwrap_envelope_notices
from ..runtime_registered_operation import run_registered_operation
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, RuntimeFailureObservation, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _invoke_native_command(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    reply = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in reply.output
    return reply


def _invoke(profile: NativeCliProfileFixture, *arguments: str) -> Result:
    return _invoke_native_command(profile, "app", "quickfile", *arguments)


def test_native_quickfile_calculates_then_retains_cross_period_refusal_and_exact_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Persist the canonical M130 chain and refuse an unavailable previous filing."""
    selected = authority_operation.snapshot("130", filing_year=2025, period="1T")
    output = (tmp_path / "native-modelo-130.txt").resolve()
    original_operation = RuntimeFrontendClient.operation
    original_result = RuntimeFrontendClient.read_result_document
    requests: dict[str, QuickfileRequest] = {}
    terminal: dict[str, tuple[OperationTerminalCondition | None, OperationEffect]] = {}
    projections: list[QuickfileProjection] = []
    foreign_refused = False

    def observe_operation(
        client: RuntimeFrontendClient, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply:
        reply = original_operation(client, request, deadline=deadline)
        if isinstance(request, RuntimeOperationSubmit) and request.definition_id == QUICKFILE_OPERATION_DEFINITION_ID:
            assert isinstance(reply, RuntimeOperationSubmitted)
            payload = QuickfileRequest.model_validate_json(request.payload_json)
            assert payload.profile_id == client.profile_id
            assert request.subject_ref == profile_operation_subject(str(client.profile_id))
            assert payload.revision_id == str(selected.revision.id)
            requests[reply.receipt.operation_id] = payload
        if isinstance(reply, RuntimeOperationObserved) and isinstance(reply.observation, OperationObservationSuccessV1):
            state = reply.observation.projection
            terminal[state.operation_id] = (state.terminal_condition, state.effect)
        return reply

    def observe_result(
        client: RuntimeFrontendClient,
        result: OperationResultProjectionRequestV1,
        *,
        timeout: float = 60,
        deadline: float | None = None,
    ) -> dict[str, JsonValue]:
        nonlocal foreign_refused
        document = original_result(client, result, timeout=timeout, deadline=deadline)
        if result.operation_id not in requests:
            return document
        envelope = OperationResultProjectionSuccessV1[QuickfileProjection].model_validate_json(
            canonical_json_bytes(document)
        )
        projection = envelope.projection
        payload = requests[result.operation_id]
        assert projection.profile_id == payload.profile_id == client.profile_id
        assert projection.period == payload.period
        assert projection.registry_revision_id == payload.revision_id
        assert terminal[result.operation_id] == (OperationTerminalCondition.SUCCEEDED, projection.effect)
        projections.append(projection)
        # Exercise the actual resolver before dispatch even if the frontend also
        # rejects an asserted foreign bucket during its own input validation.
        foreign = QuickfileRequest.model_validate(
            {**payload.model_dump(mode="python"), "bucket_id": uuid4()}, strict=True
        )
        with pytest.raises(RuntimeFrontendRefusedError) as denied:
            run_registered_operation(
                client,
                foreign,
                definition_id=QUICKFILE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(client.profile_id)),
                result_type=QuickfileProjection,
                request_version=1,
                result_version=1,
                timeout=30,
            )
        assert denied.value.reason == AccessDenialCode.PROFILE_MISMATCH.value
        assert client.status().status.connected
        foreign_refused = True
        return document

    monkeypatch.setattr(RuntimeFrontendClient, "operation", observe_operation)
    monkeypatch.setattr(RuntimeFrontendClient, "read_result_document", observe_result)
    with native_cli_profile_scope(tmp_path) as profile:
        observations: list[RuntimeFailureObservation] = []
        profile.failure_observer = observations.append
        profile.register(
            label="native-quickfile",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Synthetic",
                "identity.surnames": "Quickfile",
                "activities.description": "design",
                "censo.activity_start_date": "2024-01-01",
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
        assert profile.label is not None
        profile_id = UUID(resolve_login_target(profile.label).bucket_id)
        arguments = (
            "--modelo",
            "130",
            "--year",
            "2025",
            "--period",
            "1T",
            "--revision",
            str(selected.revision.id),
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
            "--binding",
            "modelo-130-resultados-negativos-anteriores=0",
            "--output",
            str(output),
        )
        reply = _invoke(profile, *arguments)
        assert reply.exit_code == 1, reply.output + "\n" + "\n".join(str(row) for row in observations)
        payload = unwrap_cli_result(reply)
        assert payload["completed"] is False and payload["stopped_at_stage"] == QuickfileStage.VERIFY.value
        assert payload["granted_verificado_completo"] is False and payload["export"] is None
        assert len(projections) == 1 and foreign_refused
        projection = projections[0]
        assert projection.profile_id == profile_id
        assert projection.effect is OperationEffect.PARTIAL and projection.write_count > 0
        assert tuple(row.stage for row in projection.stages) == QUICKFILE_STAGE_ORDER
        assert projection.stages[1].status is QuickfileStageStatus.OK
        assert projection.stages[2].status is QuickfileStageStatus.OK
        assert projection.stages[3].status is QuickfileStageStatus.REFUSED
        assert projection.stages[4].status is QuickfileStageStatus.SKIPPED
        assert projection.work_unit_id is not None and projection.calculation_revision_id is not None
        assert (
            projection.verification_report is not None
            and not projection.verification_report.granted_verificado_completo
        )
        assert projection.export is None and not output.exists()
        notices = json.dumps(unwrap_envelope_notices(reply.output), sort_keys=True)
        assert "cross_period_dependency_unclean" in notices
        assert "irpf.previous_year_economic_activity_net_income" in notices

        def reopen() -> None:
            close_active_bucket_session()
            login_profile(
                name=profile.label,
                passphrase_callback=lambda: profile.passphrase,
                profile_decode_context=authority_operation.profile_decode_context(),
            )

        reopen()
        try:
            bucket_id = str(profile_id)
            work_before = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
            calculations_before = CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load(
                operation=authority_operation
            )
            reports_before = VerificationReportCatalogueRepository(bucket_id=bucket_id).load(
                operation=authority_operation
            )
            work = work_before.get(projection.work_unit_id)
            assert work is not None and work.bucket_id == bucket_id
            assert work.modelo == "130" and work.revision_id == selected.revision.id
            assert work.period == projection.period.to_period()
            calculation = calculations_before.get(projection.calculation_revision_id)
            assert calculation is not None and calculation.work_unit_id == work.work_unit_id
            assert calculation.registry_snapshot_ref.revision_id == selected.revision.id
            assert calculation.registry_snapshot_ref.modelo == "130"
            assert calculation.registry_snapshot_ref.period == "1T"
            report = reports_before.get(projection.verification_report.verification_report_id)
            assert report is not None and report.calculation_revision_id == calculation.calculation_revision_id
            assert not report.granted_verificado_completo
            assert any(row.message_locale_key.endswith("cross_period_dependency_unclean") for row in report.findings)
        finally:
            close_active_bucket_session()
        denied = _invoke(profile, *arguments, "--bucket-id", str(uuid4()))
        assert denied.exit_code == 2, (denied.output, observations)
        require_error_document(denied.output)
        assert len(projections) == 1 and not output.exists()
        reopen()
        try:
            assert WorkUnitCatalogueRepository(bucket_id=bucket_id).load() == work_before
            assert (
                CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load(operation=authority_operation)
                == calculations_before
            )
            assert (
                VerificationReportCatalogueRepository(bucket_id=bucket_id).load(operation=authority_operation)
                == reports_before
            )
        finally:
            close_active_bucket_session()


def test_native_quickfile_m115_completes_all_stages_and_exports_valid_local_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Capture real invoice evidence and export the verified synthetic M115 revision."""
    original_operation = RuntimeFrontendClient.operation
    original_result = RuntimeFrontendClient.read_result_document
    quickfile_ids: set[str] = set()
    receipts: dict[str, tuple[OperationTerminalCondition | None, OperationEffect]] = {}
    projections: list[QuickfileProjection] = []

    def observe_operation(
        client: RuntimeFrontendClient, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply:
        reply = original_operation(client, request, deadline=deadline)
        if isinstance(request, RuntimeOperationSubmit) and request.definition_id == QUICKFILE_OPERATION_DEFINITION_ID:
            assert isinstance(reply, RuntimeOperationSubmitted)
            payload = QuickfileRequest.model_validate_json(request.payload_json)
            assert payload.profile_id == client.profile_id and payload.modelo == "115"
            assert request.subject_ref == profile_operation_subject(str(client.profile_id))
            quickfile_ids.add(reply.receipt.operation_id)
        if isinstance(reply, RuntimeOperationObserved) and isinstance(reply.observation, OperationObservationSuccessV1):
            state = reply.observation.projection
            receipts[state.operation_id] = (state.terminal_condition, state.effect)
        return reply

    def observe_result(
        client: RuntimeFrontendClient,
        result: OperationResultProjectionRequestV1,
        *,
        timeout: float = 60,
        deadline: float | None = None,
    ) -> dict[str, JsonValue]:
        document = original_result(client, result, timeout=timeout, deadline=deadline)
        if result.operation_id in quickfile_ids:
            envelope = OperationResultProjectionSuccessV1[QuickfileProjection].model_validate_json(
                canonical_json_bytes(document)
            )
            assert envelope.projection.profile_id == client.profile_id
            assert receipts[result.operation_id] == (OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED)
            projections.append(envelope.projection)
        return document

    monkeypatch.setattr(RuntimeFrontendClient, "operation", observe_operation)
    monkeypatch.setattr(RuntimeFrontendClient, "read_result_document", observe_result)
    with override_settings(cadrumo_cli_reveal_identifiers=True), native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-quickfile-m115",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Synthetic",
                "identity.surnames": "Quickfile",
                "activities.description": "design",
                "censo.activity_start_date": "2025-01-01",
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
        assert profile.label is not None
        profile_id = UUID(resolve_login_target(profile.label).bucket_id)

        def invoke(*command: str) -> Result:
            reply = _invoke_native_command(profile, *command)
            assert reply.exit_code == 0, reply.output
            return reply

        created = invoke(
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "received",
            "--counterparty-name",
            "Arrendador Ejemplo SL",
            "--counterparty-nif",
            "B12345674",
            "--invoice-number",
            "M115-RENT-2025-001",
            "--invoice-date",
            "2025-03-15",
            "--country-code",
            "ES",
            "--taxable-base",
            "2700.00",
            "--iva-rate",
            "21",
            "--retention-rate",
            "0.19",
            "--retention-amount",
            "513.00",
            "--iva-category",
            "domestic_general",
        )
        invoice_id = unwrap_cli_result(created)["invoice_id"]
        assert isinstance(invoice_id, str)
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice_id,
            income_kind=WithholdingIncomeKind.URBAN_RENT,
            scheme=RetencionScheme("arrendamiento_urbano"),
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            payment_event_id="m115-rent-payment-2025-03-15",
            payment_occurred_on=date(2025, 3, 15),
            allocation_id="m115-rent-allocation-1",
            idempotency_key="m115-rent-allocation-1",
            allocated_base=Decimal("2700.00"),
            allocated_withholding=Decimal("513.00"),
            allocated_settlement=Decimal("2754.00"),
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
        captured = invoke(
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            "115",
            "--year",
            "2025",
            "--period",
            "1T",
            "--received-invoice-retencion",
            evidence.model_dump_json(),
        )
        assert unwrap_cli_result(captured)["observation_count"] == 1
        output = (tmp_path / "native-modelo-115.txt").resolve()
        completed = invoke(
            "app",
            "quickfile",
            "--modelo",
            "115",
            "--year",
            "2025",
            "--period",
            "1T",
            "--casilla",
            "04=0",
            "--output",
            str(output),
        )
        payload = unwrap_cli_result(completed)
        assert payload["completed"] is True and payload["stopped_at_stage"] is None
        assert payload["granted_verificado_completo"] is True
        assert len(projections) == 1
        projection = projections[0]
        assert projection.profile_id == profile_id and projection.completed
        assert projection.effect is OperationEffect.UPDATED and projection.write_count > 0
        assert tuple(row.stage for row in projection.stages) == QUICKFILE_STAGE_ORDER
        assert projection.stages[0].status in {QuickfileStageStatus.OK, QuickfileStageStatus.WARNING}
        assert all(row.status is QuickfileStageStatus.OK for row in projection.stages[1:])
        assert projection.stopped_at_stage is None
        assert projection.work_unit_id is not None and projection.calculation_revision_id is not None
        assert projection.verification_report is not None and projection.verification_report.granted_verificado_completo
        receipt = projection.export
        assert receipt is not None and receipt.bucket_id == str(profile_id)
        assert receipt.output_path == str(output)
        exported = output.read_bytes()
        assert exported and receipt.byte_size == len(exported)
        assert receipt.file_sha256 == sha256_hex(exported)
        close_active_bucket_session()
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            bucket_id = str(profile_id)
            work = WorkUnitCatalogueRepository(bucket_id=bucket_id).load().get(projection.work_unit_id)
            calculation = (
                CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
                .load(operation=authority_operation)
                .get(projection.calculation_revision_id)
            )
            report = (
                VerificationReportCatalogueRepository(bucket_id=bucket_id)
                .load(operation=authority_operation)
                .get(projection.verification_report.verification_report_id)
            )
            assert work is not None and work.bucket_id == bucket_id and work.modelo == "115"
            assert calculation is not None and calculation.work_unit_id == work.work_unit_id
            assert report is not None and report.granted_verificado_completo
            assert report.calculation_revision_id == calculation.calculation_revision_id
            snapshot = authority_operation.snapshot("115", filing_year=2025, period="1T", revision_id=work.revision_id)
            assert projection.registry_revision_id == snapshot.revision.id
            layout = resolve_export_layout(snapshot, str(snapshot.revision.export_layouts[0].id)).layout
            parsed = parse_export_payload(layout, exported)
            compared = 0
            for field in parsed.casillas:
                if (
                    field.value is not None
                    and field.casilla_id is not None
                    and field.casilla_id in calculation.casilla_values
                ):
                    assert field.value == calculation.casilla_values[field.casilla_id]
                    compared += 1
            assert compared > 0
            assert Decimal("513.00") in calculation.casilla_values.values()
        finally:
            close_active_bucket_session()
