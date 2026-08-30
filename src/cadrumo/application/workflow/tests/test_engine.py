"""Workflow-engine tests over production authorities only.

The end-to-end engine path is exercised by the modelo verification and filing
suites through ``build_revision_workflow_engine``.  This module keeps the
workflow package's local witnesses focused on boundaries that can be exercised
without inventing collaborator behaviour: the dependency direction, the shared
registry-backed deadline schedule, and registered error-envelope metadata.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date

import pytest

from ....application.state_projection import build_pending_obligations
from ....core.errors.error_codes import ErrorCategory, build_error_envelope
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.deadlines.engine import DeadlineEngine, compute_obligation_schedule
from ....domain.deadlines.errors import ScheduleComputationError
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from .. import _deadline_stage as deadline_stage_module
from .. import engine as engine_module
from .. import engine_recording as engine_recording_module
from ..errors import UnhandledWorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORKFLOW_PRODUCER_MODULES = (
    engine_module,
    deadline_stage_module,
    engine_recording_module,
)


def _call_leaf_name(call: ast.Call) -> str | None:
    """Return the terminal name of one direct producer call."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_workflow_failure_producers_are_locale_keyed_and_verdict_complete() -> None:
    """Static producer guard closes refusal records against presentation drift."""
    violations: list[str] = []
    failure_producers: list[tuple[str, str, str]] = []
    conditional_actions: list[tuple[str, str, tuple[str, ...]]] = []
    for module in _WORKFLOW_PRODUCER_MODULES:
        tree = ast.parse(inspect.getsource(module), filename=module.__name__)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            leaf_name = _call_leaf_name(node)
            if leaf_name == "tr":
                violations.append(f"{module.__name__}:{node.lineno}: write-time translation marker")
            if leaf_name not in {"WorkflowStep", "WorkflowResult", "SiteHealthAlert"}:
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None}
            if "summary" in keywords:
                violations.append(f"{module.__name__}:{node.lineno}: persisted summary prose")
            locale_value = keywords.get("summary_locale_key")
            if isinstance(locale_value, ast.Call):
                violations.append(f"{module.__name__}:{node.lineno}: computed locale key")
            success = keywords.get("success")
            if leaf_name == "WorkflowStep" and isinstance(success, ast.Constant) and success.value is False:
                verdict = keywords.get("precondition_verdict")
                if not isinstance(verdict, ast.Call):
                    violations.append(f"{module.__name__}:{node.lineno}: failed step without verdict")
                if not isinstance(locale_value, ast.Constant) or not isinstance(locale_value.value, str):
                    violations.append(f"{module.__name__}:{node.lineno}: non-literal locale identity")
                elif isinstance(verdict, ast.Call):
                    verdict_leaf = _call_leaf_name(verdict)
                    if verdict_leaf is None:
                        violations.append(f"{module.__name__}:{node.lineno}: indirect verdict producer")
                    else:
                        failure_producers.append(
                            (module.__name__.rsplit(".", maxsplit=1)[-1], locale_value.value, verdict_leaf)
                        )
                        if verdict_leaf == "_conditional_action_verdict":
                            verdict_keywords = {
                                keyword.arg: keyword.value for keyword in verdict.keywords if keyword.arg is not None
                            }
                            action_id = verdict_keywords.get("action_id")
                            missing_names = verdict_keywords.get("missing_argument_names")
                            if not (
                                isinstance(action_id, ast.Constant)
                                and isinstance(action_id.value, str)
                                and isinstance(missing_names, ast.Tuple)
                                and all(
                                    isinstance(item, ast.Constant) and isinstance(item.value, str)
                                    for item in missing_names.elts
                                )
                            ):
                                violations.append(
                                    f"{module.__name__}:{node.lineno}: non-literal conditional action identity"
                                )
                            else:
                                conditional_actions.append(
                                    (
                                        locale_value.value,
                                        action_id.value,
                                        tuple(
                                            item.value
                                            for item in missing_names.elts
                                            if isinstance(item, ast.Constant) and isinstance(item.value, str)
                                        ),
                                    )
                                )
            if leaf_name == "SiteHealthAlert":
                status = keywords.get("status")
                if not (
                    isinstance(status, ast.Call)
                    and isinstance(status.func, ast.Attribute)
                    and status.func.attr == "from_status"
                ):
                    violations.append(f"{module.__name__}:{node.lineno}: raw site-health status")

    assert violations == []
    assert sorted(failure_producers) == sorted(
        (
            ("_deadline_stage", "application.workflow.steps.deadline_missing", "no_action_precondition_verdict"),
            ("engine", "application.workflow.steps.already_filed", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.auth_certificate_invalid", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.auth_certificate_load_failed", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.auth_provider_unavailable", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.deadline_closed", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.deadline_future", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.draft_build_failed", "_conditional_action_verdict"),
            ("engine", "application.workflow.steps.draft_identity_mismatch", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.draft_not_ready", "_conditional_action_verdict"),
            ("engine", "application.workflow.steps.inbox_blocked", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.preflight_failed", "_no_recovery_verdict"),
            ("engine", "application.workflow.steps.validation_failed", "_conditional_action_verdict"),
            ("engine_recording", "application.workflow.steps.site_unavailable", "_execution_failure_verdict"),
            ("engine_recording", "application.workflow.steps.workflow_failure", "_execution_failure_verdict"),
        )
    )
    assert sorted(conditional_actions) == sorted(
        (
            (
                "application.workflow.steps.draft_build_failed",
                "operator.modelo.work.calculate",
                ("work_unit_id",),
            ),
            (
                "application.workflow.steps.draft_not_ready",
                "operator.modelo.verification_report.list",
                ("calculation_revision_id",),
            ),
            (
                "application.workflow.steps.validation_failed",
                "operator.modelo.verification_report.list",
                ("calculation_revision_id",),
            ),
        )
    )


def test_workflow_engine_avoids_outbound_adapter_imports() -> None:
    """The application engine must not bind an outbound AEAT adapter module."""
    bound_outbound_modules = {
        name: value.__name__
        for name, value in vars(engine_module).items()
        if inspect.ismodule(value) and value.__name__.startswith("cadrumo.adapters.outbound.aeat")
    }

    assert bound_outbound_modules == {}


def test_workflow_deadline_gate_and_projection_share_the_production_schedule() -> None:
    """Both consumers expose every supported year's exact authority schedule."""
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    supported_years = bundled_authority().catalogues.supported_filing_years
    assert supported_years is not None

    for filing_year in supported_years.years:
        today = date(filing_year, 1, 1)
        schedule = compute_obligation_schedule(DeadlineEngine(), profile, today=today)
        authority_rows = tuple(
            (obligation.modelo, obligation.period, obligation.opens_on, obligation.closes_on, obligation.status)
            for obligation in schedule.obligations
        )
        projection_rows = tuple(
            (obligation.modelo, obligation.period, obligation.opens_on, obligation.closes_on, obligation.status)
            for obligation in build_pending_obligations(profile, today=today)
        )

        assert authority_rows, filing_year
        assert projection_rows == authority_rows, filing_year


def test_workflow_target_selection_refuses_duplicate_canonical_schedule_rows() -> None:
    """A consumer must not hide an upstream duplicate by choosing its first row."""
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    schedule = compute_obligation_schedule(DeadlineEngine(), profile, today=date(2026, 4, 12))
    obligation = schedule.obligations[0]
    duplicate_schedule = schedule.model_copy(update={"obligations": (*schedule.obligations, obligation)})

    with pytest.raises(ScheduleComputationError) as raised:
        deadline_stage_module._target_obligation_from_schedule(
            duplicate_schedule,
            target_modelo=obligation.modelo,
            target_period=obligation.period,
        )

    assert raised.value.context == {
        "modelo": obligation.modelo,
        "filing_year": str(obligation.period.filing_year),
        "period": obligation.period.registry_token,
        "match_count": "2",
    }


@pytest.mark.parametrize(
    "exc",
    (
        ValueError("bad value"),
        TypeError("wrong type"),
        KeyError("missing"),
        RuntimeError("boom"),
        AttributeError("no attr"),
    ),
)
def test_unhandled_workflow_error_uses_the_registered_envelope(exc: Exception) -> None:
    """A real workflow error resolves through the central envelope registry."""
    error = UnhandledWorkflowError(
        f"COMPUTING_DEADLINES raised {type(exc).__name__}: {exc}",
        context={
            "stage": "COMPUTING_DEADLINES",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )
    error.__cause__ = exc

    envelope = build_error_envelope(error)

    assert envelope.code == "INTERNAL_WORKFLOW_UNHANDLED"
    assert envelope.category == ErrorCategory.INTERNAL.value
    assert envelope.retryable is False
    assert envelope.context is not None
    assert envelope.context["stage"] == "COMPUTING_DEADLINES"
    assert envelope.context["error_type"] == type(exc).__name__
