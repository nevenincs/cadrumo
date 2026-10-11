"""A workflow run read releases exactly the detail fields listed for each variant.

Run reads reach an MCP client, and the terminal detail of a run is copied into
a result that has no schema of its own for each variant. The projection copies
only the fields listed for the variant, so a field a variant gains is held back
until someone reads what it can carry and lists it. These tests put the real
variants and the real projection to that rule.
"""

from __future__ import annotations

from datetime import date
from typing import cast, get_args

import pytest
from pydantic import BaseModel

from ....core.auth_provider import AuthProviderKind
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.submission.models import ModeloDraftStatus
from ..engine_helpers import DeadlineRole, FilingWindowState
from ..run_models import (
    WorkflowAlreadyFiledDetails,
    WorkflowAuthCheckDetails,
    WorkflowDeadlineContextDetails,
    WorkflowDiagnosticSkipReason,
    WorkflowDraftBuiltDetails,
    WorkflowDraftMismatchDetails,
    WorkflowDraftNotReadyDetails,
    WorkflowFailureDetails,
    WorkflowInboxBlockedDetails,
    WorkflowInboxSkippedDetails,
    WorkflowPreflightFailedDetails,
    WorkflowStepDetails,
    WorkflowValidationFailedDetails,
)
from ..run_projection import RELEASED_DETAIL_FIELDS, WorkflowDetailSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = Modelo("303")
_PERIOD = Period.from_year_and_code(2025, "1T")
_OPENS = date(2025, 4, 1)
_CLOSES = date(2025, 4, 20)
_SKIPPED = WorkflowAuthCheckDetails(
    kind="auth_check",
    provider_check_skipped=True,
    skip_reason=WorkflowDiagnosticSkipReason.NOT_WIRED,
)
_CONFIGURED = WorkflowAuthCheckDetails(
    kind="auth_check",
    provider_kind=AuthProviderKind.CERTIFICATE,
    cert_not_after=date(2026, 12, 31),
    cert_severity="OK",
    cert_days_until_expiry=400,
)

_SAMPLES: tuple[WorkflowStepDetails, ...] = (
    WorkflowDeadlineContextDetails(
        kind="deadline_context",
        modelo=_MODELO,
        period=_PERIOD,
        opens_on=_OPENS,
        closes_on=_CLOSES,
        filing_window=FilingWindowState.FUTURE,
        deadline_role=DeadlineRole.BINDING,
    ),
    WorkflowDeadlineContextDetails(
        kind="deadline_context",
        modelo=_MODELO,
        period=_PERIOD,
        closes_on=_CLOSES,
        overdue=True,
        extemporanea=True,
    ),
    WorkflowInboxSkippedDetails(kind="inbox_skipped", skip_reason=WorkflowDiagnosticSkipReason.NOT_WIRED),
    WorkflowInboxBlockedDetails(kind="inbox_blocked", blocker_count=2, first_notificacion_id="notificacion-01"),
    WorkflowDraftBuiltDetails(kind="draft_built", draft_id="draft-01"),
    WorkflowAlreadyFiledDetails(kind="already_filed", modelo=_MODELO, period=_PERIOD, expediente_count=1),
    WorkflowDraftNotReadyDetails(
        kind="draft_not_ready",
        draft_id="draft-01",
        draft_status=ModeloDraftStatus.BORRADOR,
        blocking_finding_codes=("finding.one", "finding.two"),
    ),
    WorkflowDraftMismatchDetails(kind="draft_mismatch", draft_id="draft-01"),
    WorkflowValidationFailedDetails(kind="validation_failed", error_count=3),
    _SKIPPED,
    _CONFIGURED,
    WorkflowPreflightFailedDetails(kind="preflight_failed", error_code="workflow.preflight.refused"),
    WorkflowPreflightFailedDetails(
        kind="preflight_failed", error_code="workflow.preflight.refused", auth_check=_CONFIGURED
    ),
    WorkflowFailureDetails(kind="workflow_failure", error_code="workflow.run.failed"),
)


def _variants() -> tuple[type[BaseModel], ...]:
    """The closed variants of the detail union, read from the declared type."""
    union = get_args(WorkflowStepDetails.__value__)[0]
    return cast("tuple[type[BaseModel], ...]", get_args(union))


def _kind(variant: type[BaseModel]) -> str:
    (kind,) = get_args(variant.model_fields["kind"].annotation)
    return str(kind)


def _declared_fields(variant: type[BaseModel]) -> frozenset[str]:
    return frozenset[str](variant.model_fields) - {"kind"}


def _released_names(snapshot: WorkflowDetailSnapshot) -> set[str]:
    names = {item.key for item in (*snapshot.scalars, *snapshot.dates, *snapshot.strings)}
    if snapshot.period is not None:
        names.add("period")
    if snapshot.auth_check is not None:
        names.add("auth_check")
    return names


def _populated_fields(detail: WorkflowStepDetails) -> set[str]:
    return {name for name in _declared_fields(type(detail)) if getattr(detail, name) is not None}


def test_every_detail_variant_lists_exactly_the_fields_it_declares() -> None:
    """A variant that gains a field fails here until the field is read and listed."""
    variants = {_kind(variant): variant for variant in _variants()}
    assert variants
    assert set(RELEASED_DETAIL_FIELDS) == set(variants)
    for kind, variant in variants.items():
        assert RELEASED_DETAIL_FIELDS[kind] == _declared_fields(variant), kind


def test_the_samples_exercise_every_listed_field_of_every_variant() -> None:
    """The projection assertions below rest on samples that set each listed field at least once."""
    exercised: dict[str, set[str]] = {}
    for sample in _SAMPLES:
        exercised.setdefault(sample.kind, set()).update(_populated_fields(sample))
    assert {kind: frozenset(fields) for kind, fields in exercised.items()} == dict(RELEASED_DETAIL_FIELDS)


@pytest.mark.parametrize("sample", _SAMPLES, ids=lambda sample: f"{sample.kind}-{sorted(_populated_fields(sample))}")
def test_the_projection_releases_each_populated_listed_field_and_restores_the_variant(
    sample: WorkflowStepDetails,
) -> None:
    snapshot = WorkflowDetailSnapshot.from_detail(sample)

    assert snapshot.kind == sample.kind
    assert _released_names(snapshot) == _populated_fields(sample)
    assert snapshot.to_detail() == sample


def test_a_field_a_variant_gains_is_not_released_until_it_is_listed() -> None:
    class LeakyDraftBuilt(WorkflowDraftBuiltDetails):
        host_path: str
        message: str

    leaky = LeakyDraftBuilt(
        kind="draft_built", draft_id="draft-01", host_path="C:/synthetic/drafts/draft-01.pdf", message="synthetic text"
    )

    snapshot = WorkflowDetailSnapshot.from_detail(leaky)

    assert _released_names(snapshot) == {"draft_id"}
    released_text = snapshot.model_dump_json()
    assert "host_path" not in released_text and "synthetic" not in released_text


def test_a_variant_with_no_listing_is_not_released_at_all() -> None:
    unlisted = WorkflowDraftBuiltDetails.model_construct(kind="unlisted_kind", draft_id="draft-01")

    with pytest.raises(KeyError):
        WorkflowDetailSnapshot.from_detail(unlisted)
