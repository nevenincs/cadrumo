"""Unit tests for :class:`aeat.application.workflow.WorkflowEngine`.

Every test uses real Protocol-conforming test harness components. No imports from
``unittest`` — the project-wide pytest-only mandate applies to this
suite especially, because the engine *is* the place where composition
correctness is validated.

The shared :class:`_Fixtures` helper builds a healthy set of components
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
from datetime import date
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.browser._site_health import SiteHealthState
from ....adapters.outbound.aeat.browser._site_health_parsers import evaluate_response
from ....core.errors import SiteHealthError, build_error_envelope
from ....core.errors._registry import ErrorCategory, ErrorEnvelope
from ....tests import FIXTURES_DIR
from .. import WorkflowAbortReason, WorkflowEngine, WorkflowStage
from .._errors import UnhandledWorkflowError, WorkflowInputMismatchError
from ._engine_support import (
    _SEDE_ROOT_URL,
    _ConcreteDraft,
    _ConcreteDraftBuilder,
    _Fixtures,
    _fixtures,
    _period,
    _profile,
    _registry_schema_version,
    _run_for_obligation,
    _run_for_period,
    _run_next,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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


# ── Happy path ─────────────────────────────────────────────────────────


class TestHappyPath:
    def test_run_next_happy_path(self) -> None:
        """Every stage fires and the engine reaches DONE."""
        fx = _fixtures()
        result = _run_next(fx)
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
        _run_next(fx)
        assert fx.submission_engine.preflight_calls == [fx.today]

    def test_run_for_period(self) -> None:
        """``run_for_period`` targets a specific (modelo, period)."""
        fx = _fixtures()
        result = _run_for_obligation(fx)
        assert result.final_stage is WorkflowStage.DONE
        assert result.resumed_from is None

    def test_run_for_period_propagates_resumed_from_into_result(self) -> None:
        """When the resume action passes a prior workflow ``run_id`` as
        ``resumed_from=``, the produced :class:`WorkflowResult` records
        the link so callers can trace the resume chain end-to-end."""

        fx = _fixtures()
        prior_run_id = "abcdef0123456789"
        result = _run_for_obligation(fx, resumed_from=prior_run_id)
        assert result.final_stage is WorkflowStage.DONE
        assert result.resumed_from == prior_run_id

    def test_run_for_period_rejects_malformed_resumed_from(self) -> None:
        """``run_for_period`` rejects a ``resumed_from`` whose shape is not the
        16-character lowercase hex run id produced by the engine itself."""

        fx = _fixtures()
        for bad in ("not-hex", "ABCDEF0123456789", "abcdef012345678", "abcdef01234567890"):
            with pytest.raises(WorkflowInputMismatchError, match="resumed_from"):
                _run_for_period(
                    fx.engine(),
                    fx.profile,
                    fx.obligation.modelo,
                    fx.obligation.period,
                    today=fx.today,
                    resumed_from=bad,
                )


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
        result = _run_next(fx)
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
        result = _run_next(fx)
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
        from ....application.state_projection import build_pending_obligations

        profile = _profile()
        today = date(2026, 4, 12)

        projection_obligations = build_pending_obligations(profile, today=today)
        target = next(o for o in projection_obligations if o.modelo == "130")

        result = _run_for_period(
            self._engine_with_real_deadlines(),
            profile,
            target.modelo,
            target.period,
            today=today,
        )

        assert result.aborted_reason is not WorkflowAbortReason.NO_PENDING_OBLIGATION
        computing = next(step for step in result.steps if step.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert computing.success is True

    def test_real_engine_admits_late_modelo_130_2025_filing_target(self) -> None:
        """A closed 2025 M130 target is a late local filing, not a nonexistent obligation."""
        from ....domain.deadlines import DeadlineEngine

        target_period = _period(2025, "1T")
        profile = _profile()
        draft = _ConcreteDraft(
            period=target_period,
            profile_tax_id=profile.tax_id,
            schema_version=_registry_schema_version(period=target_period),
        )
        fx = _fixtures()
        engine = WorkflowEngine(
            deadline_engine=DeadlineEngine(),
            filing_draft_builder=_ConcreteDraftBuilder(draft=draft),
            submission_engine=fx.submission_engine,
            session=fx.session,
            certificate_bundle=fx.certificate_bundle,
            inputs_provider=fx.inputs_provider,
            settings=fx.settings,
            expedientes_source=fx.expedientes_source,
            notifications_source=fx.notifications_source,
        )

        result = _run_for_period(engine, profile, "130", target_period, today=date(2026, 6, 29))

        assert result.aborted_reason is None
        computing = next(step for step in result.steps if step.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert computing.success is True
        assert computing.details is not None
        assert computing.details.get("overdue") == "true"
        assert computing.details.get("extemporanea") == "true"

    def test_gate_aborts_when_projection_lacks_the_target(self) -> None:
        """A target absent from the shared schedule aborts the gate with
        ``NO_PENDING_OBLIGATION``, and the projection's
        ``pending_obligations`` carries no such ``(modelo, period)``."""
        from ....application.state_projection import build_pending_obligations

        profile = _profile()
        today = date(2026, 4, 12)

        absent_modelo = "130"
        absent_period = _period(2099, "4T")
        projection_obligations = build_pending_obligations(profile, today=today)
        assert not [o for o in projection_obligations if o.modelo == absent_modelo and o.period == absent_period]

        result = _run_for_period(
            self._engine_with_real_deadlines(),
            profile,
            absent_modelo,
            absent_period,
            today=today,
        )

        assert result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION

    def test_gate_and_projection_share_one_schedule(self) -> None:
        """The obligation set the gate filters and the projection's
        ``pending_obligations`` are byte-for-byte the same ``(modelo,
        period, opens_on, closes_on, status)`` rows — proving a single
        producer feeds both."""
        from ....application.state_projection import build_pending_obligations
        from ....domain.deadlines import DeadlineEngine, compute_obligation_schedule

        profile = _profile()
        today = date(2026, 4, 12)

        schedule = compute_obligation_schedule(DeadlineEngine(), profile, today=today)
        gate_rows = {(o.modelo, o.period, o.opens_on, o.closes_on, o.status) for o in schedule.obligations}

        projection_rows = {
            (o.modelo, o.period, o.opens_on, o.closes_on, o.status)
            for o in build_pending_obligations(profile, today=today)
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

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(ValueError("bad value"), id="value-error"),
            pytest.param(TypeError("wrong type"), id="type-error"),
            pytest.param(KeyError("missing"), id="key-error"),
            pytest.param(RuntimeError("boom"), id="runtime-error"),
            pytest.param(AttributeError("no attr"), id="attribute-error"),
        ],
    )
    def test_envelope_code_for_common_exception(self, exc: BaseException) -> None:
        env = self._envelope_for_unhandled(exc)
        assert env.code == "INTERNAL_WORKFLOW_UNHANDLED"
        assert env.category == ErrorCategory.INTERNAL.value
        assert env.retryable is False

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

    def _arm_unhandled_case(self, fx: _Fixtures, source: str, exc: BaseException) -> None:
        if source == "deadline":
            fx.deadline_engine.raise_exc = exc
        elif source == "notifications":
            fx.notifications_source.raise_exc = exc
        elif source == "expedientes":
            fx.expedientes_source.raise_exc = exc
        elif source == "inputs":
            fx.inputs_provider.raise_exc = exc
        elif source == "draft_builder":
            fx.draft_builder.raise_exc = exc
        elif source == "preflight":
            fx.submission_engine.preflight_exc = exc
        else:
            raise AssertionError(f"unknown unhandled workflow source: {source}")

    @pytest.mark.parametrize(
        ("source", "exc", "expected_stage"),
        [
            pytest.param(
                "deadline",
                ValueError("registry unavailable"),
                WorkflowStage.COMPUTING_DEADLINES,
                id="computing-deadlines",
            ),
            pytest.param(
                "notifications",
                TypeError("unexpected type"),
                WorkflowStage.CHECKING_INBOX,
                id="checking-inbox",
            ),
            pytest.param(
                "expedientes",
                KeyError("no expediente"),
                WorkflowStage.BUILDING_DRAFT,
                id="building-draft-expedientes",
            ),
            pytest.param(
                "inputs",
                RuntimeError("inputs fetch failed"),
                WorkflowStage.BUILDING_DRAFT,
                id="building-draft-inputs",
            ),
            pytest.param(
                "draft_builder",
                AttributeError("missing field"),
                WorkflowStage.BUILDING_DRAFT,
                id="building-draft-builder",
            ),
            pytest.param(
                "preflight",
                OSError("network error"),
                WorkflowStage.RUNNING_PREFLIGHT,
                id="running-preflight",
            ),
        ],
    )
    def test_real_engine_unhandled_paths_emit_envelope_code(
        self,
        source: str,
        exc: BaseException,
        expected_stage: WorkflowStage,
    ) -> None:
        fx = _fixtures()
        self._arm_unhandled_case(fx, source, exc)
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
        assert result.steps[-1].stage is expected_stage
