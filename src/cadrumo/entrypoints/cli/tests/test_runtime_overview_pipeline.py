"""Overview pipeline CLI uses one correlated worker snapshot and receipt."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.operations.public_period import PublicPeriod
from ....application.overview.pipeline_operation import OverviewPipelineProjection, OverviewPipelineRequest
from ....application.overview.pipeline_projection import PipelineHealthSnapshot, PipelineLedgerSnapshot
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.period import Period
from .. import _overview as handler
from .. import runtime_overview_pipeline as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2025, "1T")
_PUBLIC_PERIOD = PublicPeriod.from_period(_PERIOD)
_OPERATION_ID = "a" * 64


def _snapshot(*, profile_id: UUID = _PROFILE, period: PublicPeriod = _PUBLIC_PERIOD) -> PipelineHealthSnapshot:
    return PipelineHealthSnapshot(
        profile_id=profile_id,
        period=period,
        ledger=PipelineLedgerSnapshot(
            business_income_total="0.00",
            business_expense_total="0.00",
            business_net_total="0.00",
            total_count=0,
            active_count=0,
            archived_count=0,
            stashed_count=0,
            split_count=0,
            pending_review_count=0,
            reviewed_count=0,
            skipped_count=0,
            checked_transaction_count=0,
            readiness_issue_count=0,
            unconverted_currency_count=0,
            ready=True,
        ),
        modelos=(),
        total_blocking_findings=0,
        total_warning_findings=0,
        ready=True,
    )


def _projection(
    *,
    profile_id: UUID = _PROFILE,
    period: PublicPeriod = _PUBLIC_PERIOD,
    language: OutputLanguage = OutputLanguage.ES,
    report: PipelineHealthSnapshot | None = None,
) -> OverviewPipelineProjection:
    return OverviewPipelineProjection(
        profile_id=profile_id,
        period=period,
        output_language=language,
        report=report or _snapshot(),
    )


def _client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )


def test_bridge_submits_exact_profile_period_and_language(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    submitted: list[OverviewPipelineRequest] = []

    def submit(_client: object, request: OverviewPipelineRequest, **_kwargs: object):
        submitted.append(request)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    read = bridge.read_overview_pipeline(
        cast(typer.Context, cast(object, None)), period=_PERIOD, output_language=OutputLanguage.ES
    )
    assert read.completion.operation_id == _OPERATION_ID
    assert read.report == _snapshot()
    assert submitted == [
        OverviewPipelineRequest(profile_id=_PROFILE, period=_PUBLIC_PERIOD, output_language=OutputLanguage.ES)
    ]


@pytest.mark.parametrize(
    ("projection", "condition", "effect"),
    [
        (_projection(profile_id=_OTHER), OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (
            _projection(period=PublicPeriod.from_period(Period.from_year_and_code(2025, "2T"))),
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
        (_projection(language=OutputLanguage.CA), OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (
            _projection(report=_snapshot(profile_id=_OTHER)),
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
        (_projection(), OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        (_projection(), OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
    ],
)
def test_bad_projection_retains_submitted_receipt(
    monkeypatch: pytest.MonkeyPatch,
    projection: OverviewPipelineProjection,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
) -> None:
    _client(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            terminal_condition=condition,
            effect=effect,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_overview_pipeline(
            cast(typer.Context, cast(object, None)), period=_PERIOD, output_language=OutputLanguage.ES
        )
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value
    assert refused.value.context["terminal_condition"] == condition.value


def test_handler_presentation_error_retains_completed_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID, projection=_projection(), effect=OperationEffect.NONE
    )
    monkeypatch.setattr(handler, "current_output_language", lambda: "es")
    monkeypatch.setattr(
        handler,
        "read_overview_pipeline",
        lambda *_args, **_kwargs: bridge.OverviewPipelineRead(
            completion=completion, report=completion.projection.report
        ),
    )
    monkeypatch.setattr(
        handler, "emit_envelope", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("private"))
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        handler.overview_pipeline(cast(typer.Context, cast(object, None)), year=2025, period="1T")
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == OperationEffect.NONE.value
    assert refused.value.__cause__ is None
