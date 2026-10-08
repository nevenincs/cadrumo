"""The review bridge accepts only the selected profile and unit snapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.work_review_contracts import (
    ModeloWorkReviewProgressSnapshot,
    ModeloWorkReviewProjection,
    ModeloWorkReviewRequest,
    ModeloWorkReviewSnapshot,
)
from ....application.operations.public_period import PublicPeriod
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.operations import OperationEffect
from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .. import _modelo_work_review_cli as handler
from .. import runtime_modelo_work_review as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2026, "1T")
_OPERATION_ID = "a" * 64


def _unit() -> WorkUnit:
    instant = datetime(2026, 3, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=_PERIOD, revision_id="2026-y-siguientes"
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        revision_id="2026-y-siguientes",
        name="First quarter",
        created_at=instant,
        updated_at=instant,
    )


def _projection(unit: WorkUnit, *, profile_id: UUID = _PROFILE, revision_id: str | None = None):
    return ModeloWorkReviewProjection(
        profile_id=profile_id,
        review=ModeloWorkReviewSnapshot(
            bucket_id=str(profile_id),
            modelo=str(unit.modelo),
            filing_year=unit.filing_year,
            period=PublicPeriod.from_period(unit.period),
            registry_revision_id=revision_id or unit.revision_id,
            work_unit_id=unit.work_unit_id,
            calculation_revision_id=None,
            lifecycle_state=None,
            verification_outcome=None,
            progress=ModeloWorkReviewProgressSnapshot(state=ModeloWorkProgressState.UNDEFINED),
            casilla_count=0,
            findings=(),
            blockers=(),
            row_source_fingerprint_count=0,
        ),
    )


def test_review_bridge_correlates_selected_unit_and_result(monkeypatch: pytest.MonkeyPatch) -> None:
    unit = _unit()
    submitted: list[ModeloWorkReviewRequest] = []
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )

    def submit(_client: object, request: ModeloWorkReviewRequest, **_kwargs: object):
        submitted.append(request)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID, projection=_projection(unit), effect=OperationEffect.NONE
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    observed = bridge.read_modelo_work_review(cast(typer.Context, cast(object, None)), unit=unit)
    assert observed.review.work_unit_id == unit.work_unit_id
    assert observed.completion.operation_id == _OPERATION_ID
    assert submitted == [ModeloWorkReviewRequest(profile_id=_PROFILE, work_unit_id=unit.work_unit_id)]


@pytest.mark.parametrize(
    ("profile_id", "revision_id", "effect"),
    [
        (_OTHER, None, OperationEffect.NONE),
        (_PROFILE, "different-revision", OperationEffect.NONE),
        (_PROFILE, None, OperationEffect.UPDATED),
    ],
)
def test_bad_review_retains_operation_receipt(
    monkeypatch: pytest.MonkeyPatch, profile_id: UUID, revision_id: str | None, effect: OperationEffect
) -> None:
    unit = _unit()
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(unit, profile_id=profile_id, revision_id=revision_id),
            effect=effect,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_work_review(cast(typer.Context, cast(object, None)), unit=unit)
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value


@pytest.mark.parametrize("failure_point", ["lines", "emit"])
def test_post_submission_render_failure_retains_receipt(monkeypatch: pytest.MonkeyPatch, failure_point: str) -> None:
    unit = _unit()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID, projection=_projection(unit), effect=OperationEffect.NONE
    )
    monkeypatch.setattr(handler, "activate_subcommand_output_language", lambda *_args: None)
    monkeypatch.setattr(handler, "read_modelo_work_unit", lambda *_args, **_kwargs: unit)
    monkeypatch.setattr(
        handler,
        "read_modelo_work_review",
        lambda *_args, **_kwargs: bridge.ModeloWorkReviewed(completion=completion, review=completion.projection.review),
    )
    if failure_point == "lines":
        monkeypatch.setattr(handler, "_review_lines", lambda _result: (_ for _ in ()).throw(ValueError("private")))
    else:
        monkeypatch.setattr(
            handler, "emit_envelope", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("private"))
        )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        handler.work_review(cast(typer.Context, cast(object, None)), work_unit_id=unit.work_unit_id)
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == OperationEffect.NONE.value
    assert refused.value.context["reason"] == "runtime_unavailable"
    assert refused.value.__cause__ is None
