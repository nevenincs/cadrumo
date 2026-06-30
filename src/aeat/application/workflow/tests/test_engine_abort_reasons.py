"""Abort-reason coverage for :class:`aeat.application.workflow.WorkflowEngine`."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import Expediente, RemoteNotification
from ....application.auth import AuthProviderKind
from ....core import Period
from ....core.errors import BaseSeverity
from ....domain.submission import ModeloDraftStatus, ModeloFinding, SubmissionPreflightError
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from .. import WorkflowAbortReason, WorkflowStage
from .._models import WorkflowStepDetails
from ._engine_support import (
    _NOTIFICATIONS_QUERY_URL,
    _ConcreteCertificateBundle,
    _ConcreteDeadlineEngine,
    _ConcreteDraft,
    _fixtures,
    _obligation,
    _period,
    _registry_schema_version,
    _run_for_period,
    _run_next,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestAbortReasons:
    def test_no_pending_obligation(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.obligation = None
        result = _run_next(fx)
        assert result.final_stage is WorkflowStage.ABORTED
        assert result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION

    def test_targeted_overdue_obligation_admitted_as_late_filing(self) -> None:
        """A closed-window target is admitted as a late local filing."""
        fx = _fixtures()
        past = _obligation(period=_period(2025, "4T"), closes_on=date(2026, 1, 20))
        fx.deadline_engine = _ConcreteDeadlineEngine(obligation=past, profile=fx.profile)
        result = _run_for_period(fx.engine(), fx.profile, past.modelo, past.period, today=fx.today)
        assert result.aborted_reason is not WorkflowAbortReason.DEADLINE_PASSED
        deadline_step = next(s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert deadline_step.success
        assert isinstance(deadline_step.details, WorkflowStepDetails)
        assert deadline_step.details.get("extemporanea") == "true"

    def test_targeted_future_obligation_refuses_until_window_opens(self) -> None:
        fx = _fixtures()
        future = _obligation(
            period=_period(2026, "3T"),
            closes_on=date(2026, 10, 20),
        )
        fx.deadline_engine = _ConcreteDeadlineEngine(obligation=future, profile=fx.profile)

        result = _run_for_period(
            fx.engine(),
            fx.profile,
            future.modelo,
            future.period,
            today=date(2026, 6, 29),
        )

        assert result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION
        deadline_step = next(s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert deadline_step.success is False
        assert deadline_step.details is not None
        assert deadline_step.details["filing_window"] == "future"
        assert deadline_step.details["opens_on"] == "2026-09-20"
        assert "aeat app modelo export" in deadline_step.summary
        stages = [step.stage for step in result.steps]
        assert WorkflowStage.BUILDING_DRAFT not in stages
        assert WorkflowStage.RUNNING_PREFLIGHT not in stages
        assert fx.submission_engine.preflight_calls == []

    def test_inbox_blocking_requerimiento(self) -> None:
        fx = _fixtures()
        fx.notifications_source.rows = (
            RemoteNotification(
                certificado_id="2699101808461",
                tipo="notificacion",
                concepto="requerimiento pendiente",
                titular_nif="X1234567L",
                titular_nombre="PERSONA PRUEBA UNO",
                destinatario_nif="X1234567L",
                destinatario_nombre="PERSONA PRUEBA UNO",
                fecha_emision=date(2026, 4, 10),
                fecha_notificacion=None,
                modo_notificacion=None,
                leida=False,
                source_url=AnyHttpUrl(_NOTIFICATIONS_QUERY_URL),
            ),
        )
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO

    def test_already_filed(self) -> None:
        fx = _fixtures()
        fx.expedientes_source.expedientes = (
            Expediente(
                expediente_id="202610013522456T",
                modelo="130",
                ejercicio=2026,
                category_path=("Agencia Tributaria", "IRPF", "Modelo 130"),
                detail_url=AnyHttpUrl(
                    aeat_url(
                        "www6",
                        f"{configured_path('sede_paths', 'irpf_expediente_detail_year_prefix')}"
                        f"2026{configured_path('sede_paths', 'irpf_expediente_detail_year_suffix')}"
                        "?exp=202610013522456T",
                    ),
                ),
            ),
        )
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.ALREADY_FILED

    def test_draft_has_errors_via_status(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(status=ModeloDraftStatus.VALIDADO)
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS

    def test_draft_not_ready_abort_surfaces_blocking_findings(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(
            status=ModeloDraftStatus.BORRADOR,
            findings=(
                ModeloFinding(severity=BaseSeverity.ERROR, message="translation"),
                ModeloFinding(severity=BaseSeverity.WARNING, message="translation"),
            ),
        )
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        building_step = next(
            step for step in reversed(result.steps) if step.stage is WorkflowStage.BUILDING_DRAFT and not step.success
        )
        assert isinstance(building_step.details, WorkflowStepDetails)
        blocking = building_step.details["blocking_findings"]
        assert isinstance(blocking, str)
        assert "error:" in blocking
        assert "warning:" in blocking
        assert "blocking findings" in building_step.summary

    def test_draft_schema_must_match_registry_obligation(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(schema_version="registry:303:unregistered")
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.details is not None
        assert last.details["schema_version"] == (f"registry:303:unregistered != {_registry_schema_version()}")

    def test_draft_revision_must_match_active_registry_snapshot(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(schema_version="registry:130:unregistered")
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.details is not None
        assert last.details["schema_version"] == (f"registry:130:unregistered != {_registry_schema_version()}")

    def test_draft_period_must_match_resolved_obligation(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(period=Period.from_year_and_code(2026, "2T"))
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.details is not None
        assert last.details["period"] == "2026 2T != 2026 1T"

    def test_unapproved_ready_draft_fails_preflight(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(status=ModeloDraftStatus.LISTO_PARA_PRESENTAR)
        fx.draft_builder.draft = fx.draft
        fx.submission_engine.preflight_exc = SubmissionPreflightError(
            "draft not approved for submission (status=READY_TO_SUBMIT)",
        )
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.PREFLIGHT_FAILED

    def test_draft_has_errors_via_validation(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(
            findings=(
                ModeloFinding(
                    severity=BaseSeverity.ERROR,
                    message="translation",
                ),
            ),
        )
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.VALIDATING_DRAFT
        assert "ERROR finding(s):" in result.summary
        assert "error:" in result.summary

    def test_draft_has_errors_surfaces_next_action_pointer(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(
            findings=(
                ModeloFinding(
                    severity=BaseSeverity.ERROR,
                    message="blocking rule violated",
                ),
            ),
        )
        fx.draft_builder.draft = fx.draft
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.VALIDATING_DRAFT
        assert last.details is not None
        details = dict(last.details)
        assert details["error_count"] == "1"
        assert "next_action" in details
        assert "verification-report list" in str(details["next_action"])

    def test_preflight_failed(self) -> None:
        fx = _fixtures()
        fx.submission_engine.preflight_exc = SubmissionPreflightError("gate-3")
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.PREFLIGHT_FAILED

    def test_cert_invalid(self) -> None:
        fx = _fixtures()
        fx.certificate_bundle.raise_exc = RuntimeError("smartcard missing")
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID

    def test_cert_pre_expiry_critical_aborts(self) -> None:
        fx = _fixtures()
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="CN=Expiring",
            not_after=date(2026, 4, 20),
        )
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "CRITICAL"
        assert preflight_step.details["cert_days_until_expiry"] == "8"

    def test_cert_pre_expiry_expired_aborts(self) -> None:
        fx = _fixtures()
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="CN=Expired",
            not_after=date(2026, 4, 1),
        )
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "EXPIRED"
        assert preflight_step.details["cert_days_until_expiry"] == "-11"

    def test_cert_pre_expiry_warn_proceeds(self) -> None:
        fx = _fixtures()
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="CN=Warning",
            not_after=date(2026, 5, 30),
        )
        result = _run_next(fx)
        assert result.final_stage is WorkflowStage.DONE
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "WARN"
        assert preflight_step.details["cert_days_until_expiry"] == "48"

    def test_clave_movil_without_expiry_metadata_does_not_abort(self) -> None:
        fx = _fixtures()
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="Cl@ve Movil",
            not_after=None,
            kind=AuthProviderKind.CLAVE_MOVIL,
        )
        result = _run_next(fx)
        assert result.final_stage is WorkflowStage.DONE
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["provider_kind"] == AuthProviderKind.CLAVE_MOVIL.value
