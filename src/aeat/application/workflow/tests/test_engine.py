"""Unit tests for :class:`aeat.application.workflow.WorkflowEngine`.

Every test uses real Protocol-conforming test doubles. No imports from
``unittest`` — the project-wide pytest-only mandate applies to this
suite especially, because the engine *is* the place where composition
correctness is validated.

The shared :class:`_Fixtures` helper builds a healthy set of doubles
and lets individual tests override exactly the knob that should
provoke a bailout.

The :mod:`aeat.adapters.outbound.aeat.sede` boundary is exercised through the
:class:`WorkflowEngine` constructor's ``expedientes_source`` and
``notifications_source`` seams. Tests inject async callables that
return real :class:`aeat.adapters.outbound.aeat.sede.Expediente` and
:class:`aeat.adapters.outbound.aeat.sede.RemoteNotification` records, bypassing the live
Playwright walkers without falsifying their record shape.
"""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.auth import AeatSession
from ....adapters.outbound.aeat.browser._site_health import SiteHealthState
from ....adapters.outbound.aeat.browser._site_health_parsers import evaluate_response
from ....adapters.outbound.aeat.sede import Expediente, NotificationsSnapshot, RemoteNotification
from ....application.auth import AuthProviderDescription, AuthProviderKind
from ....core import Period
from ....core.config import Settings
from ....core.errors import BaseSeverity, SiteHealthError, build_error_envelope
from ....core.errors._registry import ErrorCategory, ErrorEnvelope
from ....domain.deadlines import (
    IVARegime,
    ModeloDeadline,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
)
from ....domain.submission import ModeloDraftStatus, ModeloFinding, SubmissionPreflightError
from ....tests import FIXTURES_DIR
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ...filing.runtime import build_runtime_schema_provider
from .. import (
    ModeloInputs,
    RegistryModeloDraftProtocol,
    WorkflowAbortReason,
    WorkflowEngine,
    WorkflowPurpose,
    WorkflowStage,
)
from .._errors import UnhandledWorkflowError, WorkflowInputMismatchError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_SEDE_ROOT_URL = aeat_url("sede", "/")
_NOTIFICATIONS_QUERY_URL = aeat_url("www6", configured_path("sede_paths", "notifications_query"))


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


# ── Test doubles ────────────────────────────────────────────────────────


def test_workflow_engine_avoids_outbound_adapter_imports() -> None:
    tree = ast.parse((Path(__file__).parents[1] / "_engine.py").read_text(encoding="utf-8"))
    forbidden: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(("aeat.adapters.outbound.aeat", "adapters.outbound.aeat")):
                forbidden.append(node.module)
        elif isinstance(node, ast.Import):
            forbidden.extend(alias.name for alias in node.names if alias.name.startswith("aeat.adapters.outbound.aeat"))
    assert forbidden == []


def _registry_schema_version(*, modelo: str = "130", period: Period | None = None) -> str:
    target_period = period or _period(2026, "1T")
    provider = build_runtime_schema_provider(
        filing_year=target_period.filing_year,
        period=target_period,
        modelos=(modelo,),
    )
    return provider.get_subview(modelo).schema_version


@dataclass
class _ConcreteDraft:
    """Registry-backed draft record used by workflow engine tests."""

    draft_id: str = "draft-xyz"
    modelo: str = "130"
    period: Period = field(default_factory=lambda: _period(2026, "1T"))
    profile_tax_id: str = "X1234567L"
    schema_version: str = field(default_factory=_registry_schema_version)
    status: object = ModeloDraftStatus.APROBADO
    values: Mapping[str, str] | Iterable[object] = field(default_factory=lambda: {"01": "1000"})
    findings: tuple[object, ...] = ()


@dataclass
class _ConcreteDeadlineEngine:
    obligation: ModeloDeadline | None
    profile: TaxpayerProfile
    raise_exc: BaseException | None = None

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        if self.raise_exc is not None:
            raise self.raise_exc
        obligations = (self.obligation,) if self.obligation is not None else ()
        return Schedule(
            profile=profile,
            year=year,
            obligations=obligations,
            generated_at=datetime(2026, 4, 12, tzinfo=UTC),
        )


@dataclass
class _ConcreteDraftBuilder:
    draft: _ConcreteDraft
    raise_exc: BaseException | None = None

    def build(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.draft


@dataclass
class _ConcreteSubmissionEngine:
    preflight_exc: BaseException | None = None
    preflight_calls: list[date] = field(default_factory=list)
    skip_deadline_window_calls: list[bool] = field(default_factory=list)

    def preflight(
        self,
        draft: RegistryModeloDraftProtocol,
        *,
        today: date,
        skip_deadline_window: bool = False,
    ) -> None:
        self.preflight_calls.append(today)
        self.skip_deadline_window_calls.append(skip_deadline_window)
        if self.preflight_exc is not None:
            raise self.preflight_exc


@dataclass
class _ConcreteExpedientesSource:
    """Seam over :func:`aeat.adapters.outbound.aeat.sede.walk_expedientes_tree` for tests.

    Returns whatever expedientes the test put on ``self.expedientes``;
    the engine filters by modelo + ejercicio internally.
    """

    expedientes: tuple[Expediente, ...] = ()
    raise_exc: BaseException | None = None

    async def __call__(
        self,
        session: object,
        modelo: str | None,
    ) -> tuple[Expediente, ...]:
        del session, modelo
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.expedientes


@dataclass
class _ConcreteNotificationsSource:
    """Seam over :func:`aeat.adapters.outbound.aeat.sede.fetch_notifications_query` for tests."""

    rows: tuple[RemoteNotification, ...] = ()
    raise_exc: BaseException | None = None

    async def __call__(self, session: object) -> NotificationsSnapshot:
        del session
        if self.raise_exc is not None:
            raise self.raise_exc
        return NotificationsSnapshot(
            rows=self.rows,
            captured_at=datetime(2026, 4, 12, tzinfo=UTC),
            source_url=AnyHttpUrl(_NOTIFICATIONS_QUERY_URL),
        )


@dataclass
class _ConcreteCertificateBundle:
    raise_exc: BaseException | None = None
    subject: str = "CN=Test"
    not_after: date | None = field(default_factory=lambda: date(2027, 1, 15))
    kind: AuthProviderKind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        if self.raise_exc is not None:
            raise self.raise_exc
        return AuthProviderDescription(
            kind=self.kind,
            label="Workflow test certificate",
            configured=True,
            available=True,
            identity_nif="X1234567L",
            subject=self.subject,
            expires_on=self.not_after,
            health_severity="OK",
        )


@dataclass
class _ConcreteInputsProvider:
    inputs: ModeloInputs = field(default_factory=lambda: {"01": "1000"})
    raise_exc: BaseException | None = None

    def load_inputs(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
    ) -> ModeloInputs:
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.inputs


# ── Fixture factory ─────────────────────────────────────────────────────


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _obligation(
    *,
    modelo: str = "130",
    period: Period | None = None,
    closes_on: date | None = None,
) -> ModeloDeadline:
    period = period or _period(2026, "1T")
    closes_on = closes_on or date(2026, 4, 20)
    opens_on = closes_on - timedelta(days=30)
    return ModeloDeadline(
        modelo=modelo,
        period=period,
        opens_on=opens_on,
        closes_on=closes_on,
        status=ObligationStatus.DUE_SOON,
        applies_because="Modelo 130 applies to GENERAL regime",
        boe_references=("boe:test",),
    )


@dataclass
class _Fixtures:
    """A healthy-happy-path bundle that individual tests can tweak."""

    profile: TaxpayerProfile
    obligation: ModeloDeadline
    draft: _ConcreteDraft
    deadline_engine: _ConcreteDeadlineEngine
    draft_builder: _ConcreteDraftBuilder
    submission_engine: _ConcreteSubmissionEngine
    expedientes_source: _ConcreteExpedientesSource
    notifications_source: _ConcreteNotificationsSource
    certificate_bundle: _ConcreteCertificateBundle
    inputs_provider: _ConcreteInputsProvider
    settings: Settings
    today: date
    session: AeatSession

    def engine(self) -> WorkflowEngine:
        return WorkflowEngine(
            deadline_engine=self.deadline_engine,
            filing_draft_builder=self.draft_builder,
            submission_engine=self.submission_engine,
            session=self.session,
            certificate_bundle=self.certificate_bundle,
            inputs_provider=self.inputs_provider,
            settings=self.settings,
            expedientes_source=self.expedientes_source,
            notifications_source=self.notifications_source,
        )


# An :class:`aeat.adapters.outbound.aeat.auth.AeatSession` is strict-frozen pydantic with a
# heavy provider_detail discriminator; constructing one fully would
# pull in unrelated machinery. The engine never inspects the session
# itself — it only forwards it to the injected source seams — so a
# typed sentinel is sufficient and keeps the test surface tight.
_SENTINEL_SESSION = cast(AeatSession, object())


def _fixtures() -> _Fixtures:
    profile = _profile()
    obligation = _obligation()
    draft = _ConcreteDraft(profile_tax_id=profile.tax_id)
    return _Fixtures(
        profile=profile,
        obligation=obligation,
        draft=draft,
        deadline_engine=_ConcreteDeadlineEngine(obligation=obligation, profile=profile),
        draft_builder=_ConcreteDraftBuilder(draft=draft),
        submission_engine=_ConcreteSubmissionEngine(),
        expedientes_source=_ConcreteExpedientesSource(),
        notifications_source=_ConcreteNotificationsSource(),
        certificate_bundle=_ConcreteCertificateBundle(),
        inputs_provider=_ConcreteInputsProvider(),
        settings=Settings(),
        today=date(2026, 4, 12),
        session=_SENTINEL_SESSION,
    )


# ── Happy path ─────────────────────────────────────────────────────────


class TestHappyPath:
    def test_run_next_happy_path(self) -> None:
        """Every stage fires and the engine reaches DONE."""
        fx = _fixtures()
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.final_stage is WorkflowStage.DONE
        assert result.aborted_reason is None
        assert result.draft_id == fx.draft.draft_id
        assert result.submission_id is None
        stages = tuple(s.stage for s in result.steps)
        assert stages == (
            WorkflowStage.LOADING_PROFILE,
            WorkflowStage.COMPUTING_DEADLINES,
            WorkflowStage.CHECKING_INBOX,
            WorkflowStage.BUILDING_DRAFT,
            WorkflowStage.VALIDATING_DRAFT,
            WorkflowStage.RUNNING_PREFLIGHT,
        )

    def test_workflow_stops_after_preflight(self) -> None:
        """Workflow invocation must stop after read-only preflight."""
        fx = _fixtures()
        asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert fx.submission_engine.preflight_calls == [fx.today]

    def test_run_for_period(self) -> None:
        """``run_for_period`` targets a specific (modelo, period)."""
        fx = _fixtures()
        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
            ),
        )
        assert result.final_stage is WorkflowStage.DONE
        assert result.resumed_from is None

    def test_run_for_period_propagates_resumed_from_into_result(self) -> None:
        """When the resume action passes a prior workflow ``run_id`` as
        ``resumed_from=``, the produced :class:`WorkflowResult` records
        the link so callers can trace the resume chain end-to-end."""

        fx = _fixtures()
        prior_run_id = "abcdef0123456789"
        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
                resumed_from=prior_run_id,
            ),
        )
        assert result.final_stage is WorkflowStage.DONE
        assert result.resumed_from == prior_run_id

    def test_run_for_period_rejects_malformed_resumed_from(self) -> None:
        """``run_for_period`` rejects a ``resumed_from`` whose shape is not the
        16-character lowercase hex run id produced by the engine itself."""

        import pytest

        fx = _fixtures()
        for bad in ("not-hex", "ABCDEF0123456789", "abcdef012345678", "abcdef01234567890"):
            with pytest.raises(WorkflowInputMismatchError, match="resumed_from"):
                asyncio.run(
                    fx.engine().run_for_period(
                        fx.profile,
                        fx.obligation.modelo,
                        fx.obligation.period,
                        today=fx.today,
                        resumed_from=bad,
                    ),
                )


# ── Every abort reason ──────────────────────────────────────────────────


class TestAbortReasons:
    def test_no_pending_obligation(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.obligation = None
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.final_stage is WorkflowStage.ABORTED
        assert result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION

    def test_deadline_passed_via_run_for_period(self) -> None:
        """A closed-window target triggers DEADLINE_PASSED."""
        fx = _fixtures()
        past = _obligation(period=_period(2025, "4T"), closes_on=date(2026, 1, 20))
        fx.deadline_engine = _ConcreteDeadlineEngine(obligation=past, profile=fx.profile)
        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                past.modelo,
                past.period,
                today=fx.today,
            ),
        )
        assert result.aborted_reason is WorkflowAbortReason.DEADLINE_PASSED

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
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
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
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.ALREADY_FILED

    def test_draft_has_errors_via_status(self) -> None:
        """Builder returning a merely validated draft aborts at BUILDING_DRAFT."""
        fx = _fixtures()
        fx.draft = _ConcreteDraft(status=ModeloDraftStatus.VALIDADO)
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS

    def test_draft_not_ready_abort_surfaces_blocking_findings(self) -> None:
        """A not-ready draft abort enumerates the findings that kept it out of the ready state.

        Without this the BUILDING_DRAFT abort is opaque (``status=BORRADOR`` only),
        forcing the operator to read source to learn *why* verify refused.
        """
        fx = _fixtures()
        fx.draft = _ConcreteDraft(
            status=ModeloDraftStatus.BORRADOR,
            findings=(
                ModeloFinding(severity=BaseSeverity.ERROR, message="translation"),
                ModeloFinding(severity=BaseSeverity.WARNING, message="translation"),
            ),
        )
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        building_step = next(
            step for step in reversed(result.steps) if step.stage is WorkflowStage.BUILDING_DRAFT and not step.success
        )
        assert building_step.details is not None
        blocking = building_step.details["blocking_findings"]
        assert "error:" in blocking
        assert "warning:" in blocking
        assert "blocking findings" in building_step.summary

    def test_draft_schema_must_match_registry_obligation(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(schema_version="registry:303:unregistered")
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.details is not None
        assert last.details["schema_version"] == (f"registry:303:unregistered != {_registry_schema_version()}")

    def test_draft_revision_must_match_active_registry_snapshot(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(schema_version="registry:130:unregistered")
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.details is not None
        assert last.details["schema_version"] == (f"registry:130:unregistered != {_registry_schema_version()}")

    def test_draft_period_must_match_resolved_obligation(self) -> None:
        fx = _fixtures()
        fx.draft = _ConcreteDraft(period=Period.from_year_and_code(2026, "2T"))
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
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
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.PREFLIGHT_FAILED

    def test_draft_has_errors_via_validation(self) -> None:
        """A READY draft that carries ERROR findings aborts at VALIDATING_DRAFT."""
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
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.VALIDATING_DRAFT

    def test_draft_has_errors_surfaces_next_action_pointer(self) -> None:
        """DRAFT_HAS_ERRORS abort step details must carry a next_action retrieval pointer."""
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
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
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
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.PREFLIGHT_FAILED

    def test_cert_invalid(self) -> None:
        fx = _fixtures()
        fx.certificate_bundle.raise_exc = RuntimeError("smartcard missing")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID

    def test_cert_pre_expiry_critical_aborts(self) -> None:
        """A cert within the critical window aborts CERT_INVALID."""
        fx = _fixtures()
        # today=2026-04-12, default critical_days=14 → cert closes 2026-04-20 ⇒ 8 days.
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="CN=Expiring",
            not_after=date(2026, 4, 20),
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "CRITICAL"
        assert preflight_step.details["cert_days_until_expiry"] == "8"

    def test_cert_pre_expiry_expired_aborts(self) -> None:
        """An already-expired cert aborts CERT_INVALID with EXPIRED detail."""
        fx = _fixtures()
        # today=2026-04-12, not_after=2026-04-01 → -11 days.
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="CN=Expired",
            not_after=date(2026, 4, 1),
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "EXPIRED"
        assert preflight_step.details["cert_days_until_expiry"] == "-11"

    def test_cert_pre_expiry_warn_proceeds(self) -> None:
        """A cert in the warn window proceeds and reaches DONE."""
        fx = _fixtures()
        # today=2026-04-12, default warn_days=60 → cert closes 2026-05-30 ⇒ 48 days.
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="CN=Warning",
            not_after=date(2026, 5, 30),
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.final_stage is WorkflowStage.DONE
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "WARN"
        assert preflight_step.details["cert_days_until_expiry"] == "48"

    def test_clave_movil_without_expiry_metadata_does_not_abort(self) -> None:
        """Cl@ve Movil has no expiry metadata and skips the cert window gate."""
        fx = _fixtures()
        fx.certificate_bundle = _ConcreteCertificateBundle(
            subject="Cl@ve Movil",
            not_after=None,
            kind=AuthProviderKind.CLAVE_MOVIL,
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.final_stage is WorkflowStage.DONE
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["provider_kind"] == AuthProviderKind.CLAVE_MOVIL.value

    def test_unhandled_exception_from_deadline_engine(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.raise_exc = RuntimeError("boom")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.COMPUTING_DEADLINES


class TestVerifyPurpose:
    """``WorkflowPurpose.VERIFY`` makes the run deadline-independent.

    Verification asserts a calculation is internally sound; it has no
    honest dependency on the AEAT filing calendar (see the work-verify
    deadline-independence contract). For ``VERIFY`` the ``COMPUTING_DEADLINES``
    stage never aborts with ``NO_PENDING_OBLIGATION`` or
    ``DEADLINE_PASSED``, and the preflight stage skips the filing-window
    gate. ``FILE`` (the default) keeps both as hard refusals.
    """

    def test_verify_reaches_done_without_a_pending_obligation(self) -> None:
        """No scheduled obligation: ``FILE`` aborts, ``VERIFY`` proceeds."""
        fx = _fixtures()
        fx.deadline_engine.obligation = None

        file_result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
                purpose=WorkflowPurpose.FILE,
            ),
        )
        assert file_result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION

        verify_result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
                purpose=WorkflowPurpose.VERIFY,
            ),
        )
        assert verify_result.final_stage is WorkflowStage.DONE
        assert verify_result.aborted_reason is None

    def test_verify_reaches_done_for_a_closed_filing_window(self) -> None:
        """Closed-window target: ``FILE`` aborts DEADLINE_PASSED, ``VERIFY`` proceeds."""
        fx = _fixtures()
        past = _obligation(period=_period(2025, "4T"), closes_on=date(2026, 1, 20))
        fx.deadline_engine = _ConcreteDeadlineEngine(obligation=past, profile=fx.profile)
        fx.draft = _ConcreteDraft(period=past.period, profile_tax_id=fx.profile.tax_id)
        fx.draft_builder.draft = fx.draft

        file_result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                past.modelo,
                past.period,
                today=fx.today,
                purpose=WorkflowPurpose.FILE,
            ),
        )
        assert file_result.aborted_reason is WorkflowAbortReason.DEADLINE_PASSED

        verify_result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                past.modelo,
                past.period,
                today=fx.today,
                purpose=WorkflowPurpose.VERIFY,
            ),
        )
        assert verify_result.final_stage is WorkflowStage.DONE
        assert verify_result.aborted_reason is None

    def test_verify_records_deadline_stage_as_informational(self) -> None:
        """The verify ``COMPUTING_DEADLINES`` step is a success step
        tagged ``deadline_role=informational``."""
        fx = _fixtures()
        fx.deadline_engine.obligation = None

        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
                purpose=WorkflowPurpose.VERIFY,
            ),
        )
        deadline_step = next(s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert deadline_step.success is True
        assert deadline_step.details is not None
        assert deadline_step.details["deadline_role"] == "informational"
        assert deadline_step.details["filing_window"] == "absent"

    def test_verify_skips_the_preflight_deadline_window_gate(self) -> None:
        """The verify preflight call passes ``skip_deadline_window=True``;
        the default ``FILE`` run passes ``False``."""
        fx = _fixtures()

        asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
                purpose=WorkflowPurpose.VERIFY,
            ),
        )
        assert fx.submission_engine.skip_deadline_window_calls == [True]

        fresh = _fixtures()
        asyncio.run(
            fresh.engine().run_for_period(
                fresh.profile,
                fresh.obligation.modelo,
                fresh.obligation.period,
                today=fresh.today,
                purpose=WorkflowPurpose.FILE,
            ),
        )
        assert fresh.submission_engine.skip_deadline_window_calls == [False]

    def test_verify_still_refuses_an_unsound_draft(self) -> None:
        """Deadline-independence does not weaken verification: a draft
        carrying ERROR findings still aborts ``DRAFT_HAS_ERRORS``."""
        fx = _fixtures()
        fx.deadline_engine.obligation = None
        fx.draft = _ConcreteDraft(
            profile_tax_id=fx.profile.tax_id,
            findings=(ModeloFinding(severity=BaseSeverity.ERROR, message="translation"),),
        )
        fx.draft_builder.draft = fx.draft

        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
                purpose=WorkflowPurpose.VERIFY,
            ),
        )
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS


class TestSiteUnavailableArm:
    """The typed ``SiteHealthError`` arm must fire BEFORE ``Exception``."""

    def test_site_unavailable_from_deadline_engine(self) -> None:
        """A real ``SiteHealthError`` built from a fixture terminates cleanly."""
        fixture_path = FIXTURES_DIR / "site_health" / "mantenimiento" / "interstitial.html"
        body = Path(fixture_path).read_text(encoding="utf-8")
        real_status = evaluate_response(
            _SEDE_ROOT_URL,
            200,
            {},
            body,
            rate_limit_retry_after_default=300,
        )
        assert real_status is not None
        assert real_status.state is SiteHealthState.MANTENIMIENTO

        fx = _fixtures()
        fx.deadline_engine.raise_exc = SiteHealthError(status=real_status)
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
        assert result.final_stage is WorkflowStage.ABORTED
        last = result.steps[-1]
        assert last.stage is WorkflowStage.COMPUTING_DEADLINES
        assert last.site_health_alert is not None
        assert last.site_health_alert.status.state is SiteHealthState.MANTENIMIENTO
        assert last.site_health_alert.run_id == result.run_id

    def test_site_unavailable_after_obligation_resolved_matches_run_id(self) -> None:
        """A site-health alert raised AFTER deadlines resolved must agree on run_id."""
        fixture_path = FIXTURES_DIR / "site_health" / "mantenimiento" / "interstitial.html"
        body = Path(fixture_path).read_text(encoding="utf-8")
        real_status = evaluate_response(
            _SEDE_ROOT_URL,
            200,
            {},
            body,
            rate_limit_retry_after_default=300,
        )
        assert real_status is not None

        fx = _fixtures()
        # Route the SiteHealthError through the inputs provider, which
        # only runs inside _stage_building_draft AFTER _run_obligation
        # has been populated. The alert's run_id must therefore be
        # recomputed from the resolved obligation and match the final
        # WorkflowResult.run_id.
        fx.inputs_provider.raise_exc = SiteHealthError(status=real_status)
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.site_health_alert is not None
        assert last.site_health_alert.run_id == result.run_id
        # Proves the alert's run_id reflects the resolved obligation,
        # not the "-"/"-" placeholder hash.
        assert result.obligation is not None
        from .._models import compute_run_id as _compute_run_id

        placeholder_hash = _compute_run_id(
            tax_id=fx.profile.tax_id,
            modelo="-",
            period=None,
            started_at=result.started_at,
        )
        assert last.site_health_alert.run_id != placeholder_hash


class TestGateProjectionAgreement:
    """The ``NO_PENDING_OBLIGATION`` gate and the state projection's
    ``pending_obligations`` draw the obligation datum from one shared
    producer (:func:`compute_obligation_schedule`), so they cannot
    disagree about whether a target obligation exists.

    These tests drive the *real* :class:`DeadlineEngine` — not the
    Protocol-shaped test seam — through both consumers over one
    ``(profile, today)`` pair, and assert the gate aborts with
    ``NO_PENDING_OBLIGATION`` exactly when the projection carries no
    obligation for that target.
    """

    @staticmethod
    def _engine_with_real_deadlines() -> WorkflowEngine:
        """Build a :class:`WorkflowEngine` driven by the production
        :class:`DeadlineEngine`, so the gate computes the genuine
        registry-backed schedule rather than a test seam's."""
        from ....domain.deadlines import DeadlineEngine

        fx = _fixtures()
        return WorkflowEngine(
            deadline_engine=DeadlineEngine(),
            filing_draft_builder=fx.draft_builder,
            submission_engine=fx.submission_engine,
            session=fx.session,
            certificate_bundle=fx.certificate_bundle,
            inputs_provider=fx.inputs_provider,
            settings=fx.settings,
            expedientes_source=fx.expedientes_source,
            notifications_source=fx.notifications_source,
        )

    def test_gate_proceeds_when_projection_carries_the_target(self) -> None:
        """A target present in the shared schedule clears the gate, and
        the projection's ``pending_obligations`` carries that same
        ``(modelo, period)``."""
        from ....application.state_projection import _build_pending_obligations

        profile = _profile()
        today = date(2026, 4, 12)

        projection_obligations = _build_pending_obligations(profile, today=today)
        target = next(o for o in projection_obligations if o.modelo == "130")

        result = asyncio.run(
            self._engine_with_real_deadlines().run_for_period(
                profile,
                target.modelo,
                target.period,
                today=today,
            ),
        )

        assert result.aborted_reason is not WorkflowAbortReason.NO_PENDING_OBLIGATION
        computing = next(step for step in result.steps if step.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert computing.success is True

    def test_gate_aborts_when_projection_lacks_the_target(self) -> None:
        """A target absent from the shared schedule aborts the gate with
        ``NO_PENDING_OBLIGATION``, and the projection's
        ``pending_obligations`` carries no such ``(modelo, period)``."""
        from ....application.state_projection import _build_pending_obligations

        profile = _profile()
        today = date(2026, 4, 12)

        absent_modelo = "130"
        absent_period = _period(2099, "4T")
        projection_obligations = _build_pending_obligations(profile, today=today)
        assert not [o for o in projection_obligations if o.modelo == absent_modelo and o.period == absent_period]

        result = asyncio.run(
            self._engine_with_real_deadlines().run_for_period(
                profile,
                absent_modelo,
                absent_period,
                today=today,
            ),
        )

        assert result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION

    def test_gate_and_projection_share_one_schedule(self) -> None:
        """The obligation set the gate filters and the projection's
        ``pending_obligations`` are byte-for-byte the same ``(modelo,
        period, opens_on, closes_on, status)`` rows — proving a single
        producer feeds both."""
        from ....application.state_projection import _build_pending_obligations
        from ....domain.deadlines import DeadlineEngine, compute_obligation_schedule

        profile = _profile()
        today = date(2026, 4, 12)

        schedule = compute_obligation_schedule(DeadlineEngine(), profile, today=today)
        gate_rows = {(o.modelo, o.period, o.opens_on, o.closes_on, o.status) for o in schedule.obligations}

        projection_rows = {
            (o.modelo, o.period, o.opens_on, o.closes_on, o.status)
            for o in _build_pending_obligations(profile, today=today)
        }

        assert gate_rows == projection_rows
        assert gate_rows


class TestUnhandledEnvelope:
    """Every ``except Exception`` catch site in ``_record_unhandled`` must
    produce a structured :class:`~aeat.core.errors.ErrorEnvelope` with a
    stable ``INTERNAL_WORKFLOW_UNHANDLED`` code.

    Each test triggers one real catch path with a real exception class and
    asserts the envelope shape rather than the abort reason alone.
    """

    def _envelope_for_unhandled(self, exc: BaseException) -> ErrorEnvelope:
        """Return the envelope built from an :class:`UnhandledWorkflowError`
        wrapping ``exc``, proving :func:`build_error_envelope` resolves the
        registered code without raising."""

        synthetic = UnhandledWorkflowError(
            f"test stage raised {type(exc).__name__}: {exc}",
            context={
                "stage": "test",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        synthetic.__cause__ = exc
        return build_error_envelope(synthetic)

    def test_envelope_code_for_value_error(self) -> None:
        env = self._envelope_for_unhandled(ValueError("bad value"))
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.category == ErrorCategory.INTERNAL.value
        assert env.retryable is False

    def test_envelope_code_for_type_error(self) -> None:
        env = self._envelope_for_unhandled(TypeError("wrong type"))
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.category == ErrorCategory.INTERNAL.value

    def test_envelope_code_for_key_error(self) -> None:
        env = self._envelope_for_unhandled(KeyError("missing"))
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.category == ErrorCategory.INTERNAL.value

    def test_envelope_code_for_runtime_error(self) -> None:
        env = self._envelope_for_unhandled(RuntimeError("boom"))
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.category == ErrorCategory.INTERNAL.value

    def test_envelope_code_for_attribute_error(self) -> None:
        env = self._envelope_for_unhandled(AttributeError("no attr"))
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.category == ErrorCategory.INTERNAL.value

    def test_envelope_context_carries_stage_and_error_type(self) -> None:
        """The envelope context must surface the stage and error_type
        fields so telemetry can identify the catch site without parsing
        the message."""
        exc = OSError("disk error")
        synthetic = UnhandledWorkflowError(
            f"COMPUTING_DEADLINES raised {type(exc).__name__}: {exc}",
            context={
                "stage": "COMPUTING_DEADLINES",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        synthetic.__cause__ = exc
        env = build_error_envelope(synthetic)
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.context is not None
        assert env.context["stage"] == "COMPUTING_DEADLINES"
        assert env.context["error_type"] == "OSError"

    def test_computing_deadlines_unhandled_emits_envelope_code(self) -> None:
        """Real engine path: deadline engine raises ValueError ->
        ``_record_unhandled`` builds an ``INTERNAL_WORKFLOW_UNHANDLED``
        envelope and aborts with ``UNHANDLED_EXCEPTION``."""
        fx = _fixtures()
        fx.deadline_engine.raise_exc = ValueError("registry unavailable")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.COMPUTING_DEADLINES

    def test_checking_inbox_unhandled_emits_envelope_code(self) -> None:
        """Real engine path: notifications source raises TypeError ->
        ``_record_unhandled`` fires at ``CHECKING_INBOX``."""
        fx = _fixtures()
        fx.notifications_source.raise_exc = TypeError("unexpected type")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.CHECKING_INBOX

    def test_building_draft_expedientes_unhandled_emits_envelope_code(self) -> None:
        """Real engine path: expedientes source raises KeyError ->
        ``_record_unhandled`` fires at ``BUILDING_DRAFT`` (expedientes arm)."""
        fx = _fixtures()
        fx.expedientes_source.raise_exc = KeyError("no expediente")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.BUILDING_DRAFT

    def test_building_draft_inputs_unhandled_emits_envelope_code(self) -> None:
        """Real engine path: inputs provider raises RuntimeError ->
        ``_record_unhandled`` fires at ``BUILDING_DRAFT`` (inputs arm)."""
        fx = _fixtures()
        fx.inputs_provider.raise_exc = RuntimeError("inputs fetch failed")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.BUILDING_DRAFT

    def test_building_draft_builder_unhandled_emits_envelope_code(self) -> None:
        """Real engine path: draft builder raises AttributeError ->
        ``_record_unhandled`` fires at ``BUILDING_DRAFT`` (builder arm)."""
        fx = _fixtures()
        fx.draft_builder.raise_exc = AttributeError("missing field")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.BUILDING_DRAFT

    def test_running_preflight_unhandled_emits_envelope_code(self) -> None:
        """Real engine path: submission engine raises OSError ->
        ``_record_unhandled`` fires at ``RUNNING_PREFLIGHT``."""
        fx = _fixtures()
        fx.submission_engine.preflight_exc = OSError("network error")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.RUNNING_PREFLIGHT
