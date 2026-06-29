"""Shared real-behavior harness for workflow engine tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from functools import cache

from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.auth import AeatSession, ClaveMovilSessionDetail
from ....adapters.outbound.aeat.sede import Expediente, NotificationsSnapshot, RemoteNotification
from ....application.auth import AuthProviderDescription, AuthProviderKind
from ....core import Period
from ....core.config import Settings
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.deadlines import (
    IVARegime,
    ModeloDeadline,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ...filing.runtime import build_runtime_schema_provider
from .. import (
    ModeloInputs,
    RegistryModeloDraftProtocol,
    WorkflowEngine,
    WorkflowPurpose,
    WorkflowResult,
)

_SEDE_ROOT_URL = aeat_url("sede", "/")
_NOTIFICATIONS_QUERY_URL = aeat_url("www6", configured_path("sede_paths", "notifications_query"))
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


@cache
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
    values: Mapping[str, str] | Iterable[object] = field(
        default_factory=lambda: {str(_M130_INGRESOS_CASILLA): "1000"},
    )
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
    """Protocol-shaped source over expediente rows for tests."""

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
    """Protocol-shaped source over remote notification rows for tests."""

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
    inputs: ModeloInputs = field(default_factory=lambda: {_M130_INGRESOS_CASILLA: "1000"})
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
    """A healthy path bundle that individual tests can tweak."""

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


_WORKFLOW_SESSION = AeatSession(
    provider_kind=AuthProviderKind.CLAVE_MOVIL,
    authenticated_at=datetime(2026, 4, 12, 8, 0, tzinfo=UTC),
    idle_deadline=datetime(2026, 4, 12, 8, 20, tzinfo=UTC),
    storage_state_path=None,
    identity_nif="X1234567L",
    provider_detail=ClaveMovilSessionDetail(
        dni_nie="X1234567L",
        used_non_qr_fallback=True,
        verification_code="ABC",
        landing_url=_SEDE_ROOT_URL,
    ),
)


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
        session=_WORKFLOW_SESSION,
    )


def _run_next(fx: _Fixtures) -> WorkflowResult:
    return asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))


def _run_for_period(
    engine: WorkflowEngine,
    profile: TaxpayerProfile,
    modelo: str,
    period: Period,
    *,
    today: date,
    purpose: WorkflowPurpose = WorkflowPurpose.FILE,
    resumed_from: str | None = None,
) -> WorkflowResult:
    return asyncio.run(
        engine.run_for_period(
            profile,
            modelo,
            period,
            today=today,
            purpose=purpose,
            resumed_from=resumed_from,
        ),
    )


def _run_for_obligation(
    fx: _Fixtures,
    *,
    purpose: WorkflowPurpose = WorkflowPurpose.FILE,
    resumed_from: str | None = None,
) -> WorkflowResult:
    return _run_for_period(
        fx.engine(),
        fx.profile,
        fx.obligation.modelo,
        fx.obligation.period,
        today=fx.today,
        purpose=purpose,
        resumed_from=resumed_from,
    )
