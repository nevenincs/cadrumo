"""Unit tests for :class:`aeat.workflow.WorkflowEngine`.

Every test uses real Protocol-conforming test doubles. No mocks,
patches, or ``unittest.mock`` imports — the project-wide no-mocks
mandate applies to this suite especially, because the engine *is*
the place where composition correctness is validated.

The shared :class:`_Fixtures` helper builds a healthy set of doubles
and lets individual tests override exactly the knob that should
provoke a bailout.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest

from aeat.config import Settings
from aeat.deadlines import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)
from aeat.submission import (
    DraftStatus,
    FilingFinding,
    FilingFindingSeverity,
    LoadedCertificate,
    SubmissionPreflightError,
)
from aeat.workflow import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    ExpedienteLike,
    FilingDraftBuilderProtocol,
    FilingInputsProviderProtocol,
    InboxProtocol,
    RequerimientoLike,
    StatusReaderProtocol,
    SubmissionEngineProtocol,
    SubmittedFilingLike,
    SyncRunnerProtocol,
    SyncRunSummary,
    WorkflowAbortReason,
    WorkflowEngine,
    WorkflowResult,
    WorkflowStage,
)

# ── Test doubles ────────────────────────────────────────────────────────


@dataclass
class _FakeDraft:
    """Structural :class:`aeat.submission.FilingDraftLike` test double."""

    draft_id: str = "draft-xyz"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.READY_TO_SUBMIT
    values: Mapping[str, str] = field(default_factory=lambda: {"01": "1000"})
    findings: tuple[FilingFinding, ...] = ()


@dataclass
class _FakeDeadlineEngine:
    obligation: FilingObligation | None
    profile: AutonomoProfile
    raise_exc: BaseException | None = None

    def compute(
        self,
        profile: AutonomoProfile,
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
class _FakeDraftBuilder:
    draft: _FakeDraft
    raise_exc: BaseException | None = None

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> _FakeDraft:
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.draft


@dataclass
class _FakeSubmissionEngine:
    preflight_exc: BaseException | None = None
    submit_exc: BaseException | None = None
    submission_id: str = "sub-abc"
    submit_calls: list[tuple[bool, bool]] = field(default_factory=list)

    def preflight(self, draft: _FakeDraft, *, today: date) -> None:
        if self.preflight_exc is not None:
            raise self.preflight_exc

    async def submit_draft(
        self,
        draft: _FakeDraft,
        *,
        dry_run: bool = True,
        override_confirmation: bool = False,
        today: date | None = None,
    ) -> SubmittedFilingLike:
        self.submit_calls.append((dry_run, override_confirmation))
        if self.submit_exc is not None:
            raise self.submit_exc
        return SubmittedFilingLike(
            submission_id=self.submission_id,
            draft_id=draft.draft_id,
            modelo=draft.modelo,
            period=draft.period,
            status="PENDING",
            submitted_at=datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC),
        )


@dataclass
class _FakeSyncRunner:
    raise_exc: BaseException | None = None
    summary: SyncRunSummary = field(
        default_factory=lambda: SyncRunSummary(divergence_count=0, auto_healed_count=0, escalated_count=0)
    )

    async def run(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
        auto_heal: bool = False,
    ) -> SyncRunSummary:
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.summary


@dataclass
class _FakeStatusReader:
    expedientes: tuple[ExpedienteLike, ...] = ()

    async def fetch_expedientes(self, *, tax_id: str) -> tuple[ExpedienteLike, ...]:
        return self.expedientes


@dataclass
class _FakeInbox:
    requerimientos: tuple[RequerimientoLike, ...] = ()

    async def fetch_blocking_requerimientos(
        self,
        *,
        tax_id: str,
        modelo: str,
    ) -> tuple[RequerimientoLike, ...]:
        return self.requerimientos


@dataclass
class _FakeCertificateBundle:
    raise_exc: BaseException | None = None
    subject: str = "CN=Test"
    not_after: date = field(default_factory=lambda: date(2027, 1, 15))
    fingerprint_sha256: str = "a" * 64

    def load(self) -> LoadedCertificate:
        if self.raise_exc is not None:
            raise self.raise_exc
        return LoadedCertificate(
            subject=self.subject,
            not_after=self.not_after,
            fingerprint_sha256=self.fingerprint_sha256,
        )


@dataclass
class _FakeInputsProvider:
    inputs: Mapping[str, object] = field(default_factory=lambda: {"01": "1000"})
    raise_exc: BaseException | None = None

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.inputs


# ── Fixture factory ─────────────────────────────────────────────────────


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
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
    period: str = "2026Q1",
    closes_on: date | None = None,
) -> FilingObligation:
    closes_on = closes_on or date(2026, 4, 20)
    opens_on = closes_on - timedelta(days=30)
    return FilingObligation(
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

    profile: AutonomoProfile
    obligation: FilingObligation
    draft: _FakeDraft
    deadline_engine: _FakeDeadlineEngine
    draft_builder: _FakeDraftBuilder
    submission_engine: _FakeSubmissionEngine
    sync_runner: _FakeSyncRunner
    status_reader: _FakeStatusReader
    inbox: _FakeInbox
    certificate_bundle: _FakeCertificateBundle
    inputs_provider: _FakeInputsProvider
    settings: Settings
    today: date

    def engine(self) -> WorkflowEngine:
        return WorkflowEngine(
            deadline_engine=cast(DeadlineEngineProtocol, self.deadline_engine),
            filing_draft_builder=cast(FilingDraftBuilderProtocol, self.draft_builder),
            submission_engine=cast(SubmissionEngineProtocol, self.submission_engine),
            sync_runner=cast(SyncRunnerProtocol, self.sync_runner),
            status_reader=cast(StatusReaderProtocol, self.status_reader),
            inbox=cast(InboxProtocol, self.inbox),
            certificate_bundle=cast(CertificateBundleProtocol, self.certificate_bundle),
            inputs_provider=cast(FilingInputsProviderProtocol, self.inputs_provider),
            settings=self.settings,
        )


def _fixtures() -> _Fixtures:
    profile = _profile()
    obligation = _obligation()
    draft = _FakeDraft(profile_tax_id=profile.tax_id)
    return _Fixtures(
        profile=profile,
        obligation=obligation,
        draft=draft,
        deadline_engine=_FakeDeadlineEngine(obligation=obligation, profile=profile),
        draft_builder=_FakeDraftBuilder(draft=draft),
        submission_engine=_FakeSubmissionEngine(),
        sync_runner=_FakeSyncRunner(),
        status_reader=_FakeStatusReader(),
        inbox=_FakeInbox(),
        certificate_bundle=_FakeCertificateBundle(),
        inputs_provider=_FakeInputsProvider(),
        settings=Settings(),
        today=date(2026, 4, 12),
    )


# ── Happy path + dry-run default ────────────────────────────────────────


@pytest.mark.unit
class TestHappyPath:
    def test_run_next_happy_path(self) -> None:
        """Every stage fires and the engine reaches DONE."""
        fx = _fixtures()
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.final_stage is WorkflowStage.DONE
        assert result.aborted_reason is None
        assert result.draft_id == fx.draft.draft_id
        assert result.submission_id == "sub-abc"
        stages = tuple(s.stage for s in result.steps)
        assert stages == (
            WorkflowStage.LOADING_PROFILE,
            WorkflowStage.SYNCING_CATALOGUES,
            WorkflowStage.COMPUTING_DEADLINES,
            WorkflowStage.CHECKING_INBOX,
            WorkflowStage.BUILDING_DRAFT,
            WorkflowStage.VALIDATING_DRAFT,
            WorkflowStage.RUNNING_PREFLIGHT,
            WorkflowStage.DRY_RUN_SUBMIT,
        )

    def test_dry_run_is_default(self) -> None:
        """Default invocation must call submit_draft with dry_run=True."""
        fx = _fixtures()
        asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert fx.submission_engine.submit_calls == [(True, False)]

    def test_run_for_period(self) -> None:
        """``run_for_period`` targets a specific (modelo, period)."""
        fx = _fixtures()
        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                fx.obligation.modelo,
                fx.obligation.period,
                today=fx.today,
            )
        )
        assert result.final_stage is WorkflowStage.DONE

    def test_sync_first_false_skips_sync_stage(self) -> None:
        """When ``sync_first=False`` the sync stage skips cleanly."""
        fx = _fixtures()
        asyncio.run(fx.engine().run_next(fx.profile, today=fx.today, sync_first=False))
        # The sync step is still recorded but as "skipped".
        step = next(s for s in _result(fx).steps if s.stage is WorkflowStage.SYNCING_CATALOGUES)
        assert step.details == {"skipped": "sync_first_false"}


def _result(fx: _Fixtures) -> WorkflowResult:
    """Helper used in the tests above to re-run with sync skipped."""
    return asyncio.run(fx.engine().run_next(fx.profile, today=fx.today, sync_first=False))


# ── Every abort reason ──────────────────────────────────────────────────


@pytest.mark.unit
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
        past = _obligation(period="2025Q4", closes_on=date(2026, 1, 20))
        fx.deadline_engine = _FakeDeadlineEngine(obligation=past, profile=fx.profile)
        result = asyncio.run(
            fx.engine().run_for_period(
                fx.profile,
                past.modelo,
                past.period,
                today=fx.today,
            )
        )
        assert result.aborted_reason is WorkflowAbortReason.DEADLINE_PASSED

    def test_inbox_blocking_requerimiento(self) -> None:
        fx = _fixtures()
        fx.inbox.requerimientos = (
            RequerimientoLike(
                modelo="130",
                notificacion_id="nf-1",
                received_at=datetime(2026, 4, 10, tzinfo=UTC),
                blocks_submission=True,
                subject="requerimiento pendiente",
            ),
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO

    def test_already_filed(self) -> None:
        fx = _fixtures()
        fx.status_reader.expedientes = (
            ExpedienteLike(
                modelo="130",
                period="2026Q1",
                tax_id=fx.profile.tax_id,
                filed_at=datetime(2026, 4, 11, tzinfo=UTC),
            ),
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.ALREADY_FILED

    def test_draft_has_errors_via_status(self) -> None:
        """Builder returning an un-promoted draft aborts at BUILDING_DRAFT."""
        fx = _fixtures()
        fx.draft = _FakeDraft(status=DraftStatus.INCOMPLETE)
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS

    def test_draft_has_errors_via_validation(self) -> None:
        """A READY draft that carries ERROR findings aborts at VALIDATING_DRAFT."""
        fx = _fixtures()
        fx.draft = _FakeDraft(
            findings=(
                FilingFinding(
                    severity=FilingFindingSeverity.ERROR,
                    message={"en": "missing casilla 03"},
                ),
            ),
        )
        fx.draft_builder.draft = fx.draft
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
        last = result.steps[-1]
        assert last.stage is WorkflowStage.VALIDATING_DRAFT

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
        """A cert within the critical window aborts CERT_INVALID (#94)."""
        fx = _fixtures()
        # today=2026-04-12, default critical_days=14 → cert closes 2026-04-20 ⇒ 8 days.
        fx.certificate_bundle = _FakeCertificateBundle(
            subject="CN=Expiring",
            not_after=date(2026, 4, 20),
            fingerprint_sha256="b" * 64,
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.CERT_INVALID
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "CRITICAL"
        assert preflight_step.details["cert_days_until_expiry"] == "8"

    def test_cert_pre_expiry_warn_proceeds(self) -> None:
        """A cert in the warn window proceeds and reaches DONE (#94)."""
        fx = _fixtures()
        # today=2026-04-12, default warn_days=60 → cert closes 2026-05-30 ⇒ 48 days.
        fx.certificate_bundle = _FakeCertificateBundle(
            subject="CN=Warning",
            not_after=date(2026, 5, 30),
            fingerprint_sha256="c" * 64,
        )
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.final_stage is WorkflowStage.DONE
        preflight_step = next(s for s in result.steps if s.stage is WorkflowStage.RUNNING_PREFLIGHT)
        assert preflight_step.details is not None
        assert preflight_step.details["cert_severity"] == "WARN"
        assert preflight_step.details["cert_days_until_expiry"] == "48"

    def test_user_cancelled_without_override(self) -> None:
        """Live mode without override_confirmation aborts without submitting."""
        fx = _fixtures()
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today, dry_run=False))
        assert result.aborted_reason is WorkflowAbortReason.USER_CANCELLED
        assert fx.submission_engine.submit_calls == []  # never called

    def test_live_submit_requires_override_confirmation(self) -> None:
        """Live mode *with* override_confirmation proceeds."""
        fx = _fixtures()
        result = asyncio.run(
            fx.engine().run_next(
                fx.profile,
                today=fx.today,
                dry_run=False,
                override_confirmation=True,
            )
        )
        assert result.final_stage is WorkflowStage.DONE
        assert fx.submission_engine.submit_calls == [(False, True)]

    def test_unhandled_exception_from_deadline_engine(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.raise_exc = RuntimeError("boom")
        result = asyncio.run(fx.engine().run_next(fx.profile, today=fx.today))
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is WorkflowStage.COMPUTING_DEADLINES
